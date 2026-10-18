# Smart Tasks & Reminders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform `TickerPing` into a multi-purpose personal assistant bot by adding a modular, 24/7 autonomous Tasks & Reminders engine with natural time/date parsing and Telegram 1-tap buttons.

**Architecture:** A standalone `ReminderManager` handles CRUD, snooze, and JSON persistence for both timed reminders and untimed to-dos. The 24/7 `CloudRunner` checks due reminders every minute alongside stock alarms and auto-syncs `reminders.json` to GitHub. `TelegramCommandHandler` routes commands (`/remind`, `/todo`, `/tasks`) and handles callback queries (`task_done:`, `task_del:`, `task_snooze:`).

**Architecture Diagram:**
```mermaid
graph TD
    User["📱 User (Telegram)"] --> Handler["TelegramCommandHandler (telegram_command_handler.py)"]
    
    subgraph Commands & Buttons
        Handler -->|"/remind", "/todo", "/task"| ParseHelper["parse_reminder_input()"]
        ParseHelper --> Mgr["ReminderManager (reminders_manager.py)"]
        Handler -->|"/tasks", "/reminders"| Mgr
        Handler -->|"task_done:", "task_del:", "task_snooze:"| Mgr
    end
    
    subgraph Storage
        Mgr --> RemindersJSON["reminders.json"]
    end
    
    subgraph "24/7 Autonomous Runner"
        Runner["CloudRunner (cloud_runner.py)"] -->|Every 60s| DueCheck["ReminderManager.get_due_reminders()"]
        DueCheck -->|Due items| TelegramAlert["Send Alert with [✅ Done] [⏰ Snooze]"]
        DueCheck -->|State changed| GitSync["git_sync_changes() -> GitHub"]
    end
```

**Tech Stack:** Python 3.12, standard library (`datetime`, `re`, `json`, `uuid`, `threading`), `pytest`.

## Global Constraints

- EXCLUSIVELY use `droritos` (`droritos@users.noreply.github.com`) for all git commits, authors, pushes, and GitHub operations.
- STRICT PROHIBITION: NEVER under any circumstance use `Dror-Vizel`, `Dror Vizel`, or `dror.v@superplay.co`.
- 100% zero third-party dependencies for date/time parsing (use standard library `datetime` and `re`).
- Complete isolation: Stock alarms, charts, and news remain 100% functional and untouched.

---

### Task 1: `reminders_manager.py` (Core Engine & Date Parser)

**Files:**
- Create: `reminders_manager.py`
- Test: `tests/test_reminders_manager.py`

**Interfaces:**
- Produces:
  - `parse_reminder_input(raw_text: str, now: Optional[datetime] = None) -> Tuple[Optional[datetime], str]`
  - `ReminderManager(storage_path: str = "reminders.json")`
    - `add_reminder(title: str, due_at: Optional[datetime] = None, note: str = "") -> Dict[str, Any]`
    - `get_reminders(include_completed: bool = False) -> List[Dict[str, Any]]`
    - `get_due_reminders(now: Optional[datetime] = None) -> List[Dict[str, Any]]`
    - `mark_completed(reminder_id: str) -> bool`
    - `mark_triggered(reminder_id: str) -> bool`
    - `delete_reminder(reminder_id: str) -> bool`
    - `snooze_reminder(reminder_id: str, minutes: int = 10, now: Optional[datetime] = None) -> Optional[Dict[str, Any]]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_reminders_manager.py`:
```python
from datetime import datetime, timedelta
import pytest
from reminders_manager import parse_reminder_input, ReminderManager


def test_parse_reminder_input_relative_minutes():
    base_time = datetime(2026, 10, 18, 14, 0, 0)
    due_at, text = parse_reminder_input("25m Check oven", now=base_time)
    assert due_at == datetime(2026, 10, 18, 14, 25, 0)
    assert text == "Check oven"

    due_at2, text2 = parse_reminder_input("in 10 min take out trash", now=base_time)
    assert due_at2 == datetime(2026, 10, 18, 14, 10, 0)
    assert text2 == "take out trash"


def test_parse_reminder_input_relative_hours():
    base_time = datetime(2026, 10, 18, 14, 0, 0)
    due_at, text = parse_reminder_input("2h Laundry", now=base_time)
    assert due_at == datetime(2026, 10, 18, 16, 0, 0)
    assert text == "Laundry"

    due_at2, text2 = parse_reminder_input("1.5h Call mom", now=base_time)
    assert due_at2 == datetime(2026, 10, 18, 15, 30, 0)
    assert text2 == "Call mom"


def test_parse_reminder_input_time_today_and_tomorrow():
    # If time is later today
    base_time = datetime(2026, 10, 18, 14, 0, 0)
    due_at, text = parse_reminder_input("18:30 Call doctor", now=base_time)
    assert due_at == datetime(2026, 10, 18, 18, 30, 0)
    assert text == "Call doctor"

    # If time has already passed today -> schedule for tomorrow
    due_at_past, text_past = parse_reminder_input("09:00 Morning standup", now=base_time)
    assert due_at_past == datetime(2026, 10, 19, 9, 0, 0)
    assert text_past == "Morning standup"


def test_parse_reminder_input_tomorrow():
    base_time = datetime(2026, 10, 18, 14, 0, 0)
    due_at, text = parse_reminder_input("tomorrow 09:00 Buy groceries", now=base_time)
    assert due_at == datetime(2026, 10, 19, 9, 0, 0)
    assert text == "Buy groceries"

    due_at2, text2 = parse_reminder_input("tomorrow Clean desk", now=base_time)
    assert due_at2 == datetime(2026, 10, 19, 9, 0, 0)
    assert text2 == "Clean desk"


def test_parse_reminder_input_calendar_date():
    base_time = datetime(2026, 10, 18, 14, 0, 0)
    # Day/Month with time
    due_at, text = parse_reminder_input("18/11 19:30 Wedding anniversary", now=base_time)
    assert due_at == datetime(2026, 11, 18, 19, 30, 0)
    assert text == "Wedding anniversary"

    # Day/Month without time -> default to 09:00
    due_at2, text2 = parse_reminder_input("18/11 Wedding", now=base_time)
    assert due_at2 == datetime(2026, 11, 18, 9, 0, 0)
    assert text2 == "Wedding"


def test_parse_reminder_input_untimed_todo():
    base_time = datetime(2026, 10, 18, 14, 0, 0)
    due_at, text = parse_reminder_input("Buy almond milk and coffee", now=base_time)
    assert due_at is None
    assert text == "Buy almond milk and coffee"


def test_reminder_manager_crud(tmp_path):
    storage = str(tmp_path / "reminders.json")
    mgr = ReminderManager(storage_path=storage)

    # 1. Add timed reminder
    due = datetime(2026, 10, 18, 18, 0, 0)
    r1 = mgr.add_reminder("Call accountant", due_at=due, note="Tax docs")
    assert r1["title"] == "Call accountant"
    assert r1["due_at"] == due.isoformat()
    assert r1["completed"] is False
    assert r1["triggered"] is False

    # 2. Add untimed task
    r2 = mgr.add_reminder("Buy notebook")
    assert r2["title"] == "Buy notebook"
    assert r2["due_at"] is None

    # 3. Retrieve active
    active = mgr.get_reminders()
    assert len(active) == 2

    # 4. Mark completed
    assert mgr.mark_completed(r2["id"]) is True
    assert len(mgr.get_reminders(include_completed=False)) == 1
    assert len(mgr.get_reminders(include_completed=True)) == 2

    # 5. Delete reminder
    assert mgr.delete_reminder(r1["id"]) is True
    assert len(mgr.get_reminders(include_completed=True)) == 1


def test_reminder_manager_get_due_reminders(tmp_path):
    storage = str(tmp_path / "reminders.json")
    mgr = ReminderManager(storage_path=storage)

    base = datetime(2026, 10, 18, 15, 0, 0)
    past = base - timedelta(minutes=5)
    future = base + timedelta(minutes=10)

    r_due = mgr.add_reminder("Past task", due_at=past)
    r_future = mgr.add_reminder("Future task", due_at=future)
    mgr.add_reminder("Untimed task")

    due_list = mgr.get_due_reminders(now=base)
    assert len(due_list) == 1
    assert due_list[0]["id"] == r_due["id"]

    # Mark triggered
    mgr.mark_triggered(r_due["id"])
    assert len(mgr.get_due_reminders(now=base)) == 0


def test_reminder_manager_snooze(tmp_path):
    storage = str(tmp_path / "reminders.json")
    mgr = ReminderManager(storage_path=storage)

    base = datetime(2026, 10, 18, 15, 0, 0)
    past = base - timedelta(minutes=5)
    r = mgr.add_reminder("Oven alert", due_at=past)
    mgr.mark_triggered(r["id"])

    # Snooze for 10 minutes from base
    snoozed = mgr.snooze_reminder(r["id"], minutes=10, now=base)
    assert snoozed is not None
    assert snoozed["triggered"] is False
    assert snoozed["due_at"] == (base + timedelta(minutes=10)).isoformat()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_reminders_manager.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'reminders_manager'`

- [ ] **Step 3: Write minimal implementation in `reminders_manager.py`**

Create `reminders_manager.py`:
```python
"""
reminders_manager.py — Smart Tasks & Reminders Manager for TickerPing.
Supports relative timers (25m, 2h), time of day (18:30), calendar dates (18/11 19:30),
and open to-dos with thread-safe atomic JSON persistence.
"""
from datetime import datetime, timedelta
import json
import logging
import os
import re
import threading
from typing import Any, Dict, List, Optional, Tuple
import uuid

logger = logging.getLogger(__name__)


def parse_reminder_input(raw_text: str, now: Optional[datetime] = None) -> Tuple[Optional[datetime], str]:
    """
    Parses natural reminder input into (due_at, task_title).
    If no time is detected, returns (None, raw_text) indicating an untimed to-do item.
    """
    if now is None:
        now = datetime.now()

    text = raw_text.strip()
    if not text:
        return None, ""

    # 1. Relative duration: "in 25m", "25m", "10 min", "2h", "1.5h"
    rel_match = re.match(r"^(?:in\s+)?(\d+(?:\.\d+)?)\s*(m|min|mins|minutes|h|hr|hrs|hours)\b\s*(.*)$", text, re.IGNORECASE)
    if rel_match:
        val = float(rel_match.group(1))
        unit = rel_match.group(2).lower()
        remainder = rel_match.group(3).strip()
        if unit.startswith("m"):
            due_at = now + timedelta(minutes=val)
        else:
            due_at = now + timedelta(hours=val)
        return due_at, remainder

    # 2. "tomorrow" with optional time: "tomorrow 09:00 Buy milk", "tomorrow Buy milk"
    tom_match = re.match(r"^tomorrow(?:\s+at)?(?:\s+(\d{1,2}):(\d{2}))?\b\s*(.*)$", text, re.IGNORECASE)
    if tom_match:
        hour_str = tom_match.group(1)
        min_str = tom_match.group(2)
        remainder = tom_match.group(3).strip()
        hour = int(hour_str) if hour_str is not None else 9
        minute = int(min_str) if min_str is not None else 0
        tomorrow = now + timedelta(days=1)
        due_at = datetime(tomorrow.year, tomorrow.month, tomorrow.day, hour, minute, 0)
        return due_at, remainder

    # 3. Calendar date: "18/11 19:30 Wedding" or "18/11 Wedding"
    date_match = re.match(r"^(\d{1,2})[/\-\.](\d{1,2})(?:[/\-\.](\d{2,4}))?(?:\s+(?:at\s+)?(\d{1,2}):(\d{2}))?\b\s*(.*)$", text, re.IGNORECASE)
    if date_match:
        day = int(date_match.group(1))
        month = int(date_match.group(2))
        year_str = date_match.group(3)
        hour_str = date_match.group(4)
        min_str = date_match.group(5)
        remainder = date_match.group(6).strip()

        year = int(year_str) if year_str else now.year
        if year < 100:
            year += 2000
        hour = int(hour_str) if hour_str is not None else 9
        minute = int(min_str) if min_str is not None else 0

        try:
            due_at = datetime(year, month, day, hour, minute, 0)
            if not year_str and due_at < now:
                due_at = datetime(year + 1, month, day, hour, minute, 0)
            return due_at, remainder
        except ValueError:
            # Invalid date format, fall through
            pass

    # 4. Time of day: "18:30 Call doctor" or "at 18:30 Call doctor"
    time_match = re.match(r"^(?:at\s+)?(\d{1,2}):(\d{2})\b\s*(.*)$", text, re.IGNORECASE)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
        remainder = time_match.group(3).strip()
        due_at = datetime(now.year, now.month, now.day, hour, minute, 0)
        if due_at <= now:
            due_at += timedelta(days=1)
        return due_at, remainder

    # Untimed to-do item
    return None, text


class ReminderManager:
    """Thread-safe CRUD manager for tasks and reminders persisted to JSON."""

    def __init__(self, storage_path: str = "reminders.json") -> None:
        self.storage_path = storage_path
        self._lock = threading.Lock()
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        if not os.path.exists(self.storage_path):
            directory = os.path.dirname(self.storage_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            self._write_file([])

    def _read_file(self) -> List[Dict[str, Any]]:
        with self._lock:
            try:
                if not os.path.exists(self.storage_path):
                    return []
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if not content:
                        return []
                    return json.loads(content)
            except Exception as e:
                logger.error(f"Error reading reminders file: {e}")
                return []

    def _write_file(self, data: List[Dict[str, Any]]) -> bool:
        with self._lock:
            try:
                temp_path = f"{self.storage_path}.tmp"
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                if os.path.exists(self.storage_path):
                    os.replace(temp_path, self.storage_path)
                else:
                    os.rename(temp_path, self.storage_path)
                return True
            except Exception as e:
                logger.error(f"Error writing reminders file: {e}")
                return False

    def add_reminder(
        self,
        title: str,
        due_at: Optional[datetime] = None,
        note: str = ""
    ) -> Dict[str, Any]:
        item = {
            "id": str(uuid.uuid4())[:8],
            "title": title.strip(),
            "due_at": due_at.isoformat() if due_at else None,
            "completed": False,
            "triggered": False,
            "created_at": datetime.now().isoformat(),
            "completed_at": None,
            "note": note.strip()
        }
        items = self._read_file()
        items.append(item)
        self._write_file(items)
        return item

    def get_reminders(self, include_completed: bool = False) -> List[Dict[str, Any]]:
        items = self._read_file()
        if include_completed:
            return items
        return [i for i in items if not i.get("completed", False)]

    def get_due_reminders(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        if now is None:
            now = datetime.now()
        items = self.get_reminders(include_completed=False)
        due = []
        for i in items:
            due_at_str = i.get("due_at")
            if not due_at_str or i.get("triggered", False):
                continue
            try:
                due_dt = datetime.fromisoformat(due_at_str)
                if due_dt <= now:
                    due.append(i)
            except Exception:
                continue
        return due

    def mark_completed(self, reminder_id: str) -> bool:
        clean_id = str(reminder_id).strip().lower()
        items = self._read_file()
        found = False
        for i in items:
            if str(i.get("id", "")).strip().lower() == clean_id:
                i["completed"] = True
                i["completed_at"] = datetime.now().isoformat()
                found = True
                break
        if found:
            self._write_file(items)
        return found

    def mark_triggered(self, reminder_id: str) -> bool:
        clean_id = str(reminder_id).strip().lower()
        items = self._read_file()
        found = False
        for i in items:
            if str(i.get("id", "")).strip().lower() == clean_id:
                i["triggered"] = True
                found = True
                break
        if found:
            self._write_file(items)
        return found

    def delete_reminder(self, reminder_id: str) -> bool:
        clean_id = str(reminder_id).strip().lower()
        items = self._read_file()
        initial_len = len(items)
        items = [i for i in items if str(i.get("id", "")).strip().lower() != clean_id]
        if len(items) < initial_len:
            self._write_file(items)
            return True
        return False

    def snooze_reminder(
        self,
        reminder_id: str,
        minutes: int = 10,
        now: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        if now is None:
            now = datetime.now()
        clean_id = str(reminder_id).strip().lower()
        items = self._read_file()
        target = None
        for i in items:
            if str(i.get("id", "")).strip().lower() == clean_id:
                new_due = now + timedelta(minutes=minutes)
                i["due_at"] = new_due.isoformat()
                i["triggered"] = False
                target = i
                break
        if target:
            self._write_file(items)
        return target
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_reminders_manager.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: Commit**

```bash
git add reminders_manager.py tests/test_reminders_manager.py
git commit --author="droritos <droritos@users.noreply.github.com>" -m "feat(reminders): implement ReminderManager and natural date/time parser"
```

---

### Task 2: Cloud Runner Integration (`cloud_runner.py`)

**Files:**
- Modify: `cloud_runner.py`
- Modify: `tests/test_cloud_runner.py`

**Interfaces:**
- Consumes: `ReminderManager.get_due_reminders()`, `ReminderManager.mark_triggered()`
- Produces:
  - `CloudRunner.__init__(..., reminders_path: str = "reminders.json")`
  - `CloudRunner.evaluate_due_reminders()`: sends alert message with `[ ✅ Done ]` and `[ ⏰ Snooze ]` inline buttons, marks triggered, and triggers `git_sync_changes()`.
  - Updated `CloudRunner.git_sync_changes()`: includes `self.reminders_path` in `git add`.
  - Updated `CloudRunner.run()`: evaluates due reminders in the main execution loop.

- [ ] **Step 1: Write the failing tests**

Add tests to `tests/test_cloud_runner.py`:
```python
def test_cloud_runner_evaluates_due_reminders(tmp_path):
    alarms_file = str(tmp_path / "alarms.json")
    state_file = str(tmp_path / "bot_state.json")
    reminders_file = str(tmp_path / "reminders.json")

    runner = CloudRunner(
        token="test_token",
        chat_id="12345",
        storage_path=alarms_file,
        state_path=state_file,
        reminders_path=reminders_file
    )

    runner.send_telegram_msg = MagicMock()
    runner.git_sync_changes = MagicMock()
    runner.reminder_manager = MagicMock()
    runner.reminder_manager.get_due_reminders.return_value = [
        {"id": "rem_1", "title": "Check the oven", "due_at": "2026-10-18T14:30:00"}
    ]

    runner.evaluate_due_reminders()

    runner.send_telegram_msg.assert_called_once()
    call_args = runner.send_telegram_msg.call_args
    assert "Check the oven" in call_args[0][1]
    assert "reply_markup" in call_args[1]
    markup = call_args[1]["reply_markup"]
    assert "inline_keyboard" in markup
    # Check buttons
    buttons = [b["callback_data"] for row in markup["inline_keyboard"] for b in row]
    assert "task_done:rem_1" in buttons
    assert "task_snooze:rem_1:10" in buttons
    assert "task_snooze:rem_1:60" in buttons

    runner.reminder_manager.mark_triggered.assert_called_with("rem_1")
    runner.git_sync_changes.assert_called_once()


def test_git_sync_changes_includes_reminders(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    alarms_file = str(tmp_path / "alarms.json")
    state_file = str(tmp_path / "bot_state.json")
    reminders_file = str(tmp_path / "reminders.json")
    runner = CloudRunner("tok", "123", alarms_file, state_file, reminders_path=reminders_file)

    mock_diff = MagicMock()
    mock_diff.returncode = 1

    with patch("subprocess.run", return_value=mock_diff) as mock_run:
        runner.git_sync_changes()
        # Verify git add call includes reminders_file
        add_call = [call for call in mock_run.call_args_list if call[0][0][:2] == ["git", "add"]][0]
        assert reminders_file in add_call[0][0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cloud_runner.py -k "test_cloud_runner_evaluates_due_reminders" -v`
Expected: FAIL with `TypeError: CloudRunner.__init__() got an unexpected keyword argument 'reminders_path'` or `AttributeError`

- [ ] **Step 3: Update `cloud_runner.py`**

In `cloud_runner.py`:
1. Import `ReminderManager`:
```python
from reminders_manager import ReminderManager
```
2. Update `CloudRunner.__init__`:
```python
    def __init__(
        self,
        token: str,
        chat_id: str,
        storage_path: str = "alarms.json",
        state_path: str = "bot_state.json",
        reminders_path: str = "reminders.json",
        max_runtime_seconds: int = 18000,
        loop_interval_seconds: int = 60
    ):
        self.token = token
        self.chat_id = chat_id
        self.max_runtime_seconds = max_runtime_seconds
        self.loop_interval_seconds = loop_interval_seconds
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.storage_path = storage_path
        self.state_path = state_path
        self.reminders_path = reminders_path
        self.alarm_manager = AlarmManager(storage_path=storage_path)
        self.state_manager = BotStateManager(storage_path=state_path)
        self.reminder_manager = ReminderManager(storage_path=reminders_path)
        self.engine = StockEngine()
        self.notifier = TelegramNotifier(bot_token=token, chat_id=chat_id)
        self.cmd_handler = TelegramCommandHandler(
            alarm_manager=self.alarm_manager,
            engine=self.engine,
            send_msg_fn=self.send_telegram_msg,
            answer_cb_fn=self.answer_callback_query,
            reminder_manager=self.reminder_manager
        )
```
3. Update `git_sync_changes`:
```python
    def git_sync_changes(self):
        """Sync alarms.json, reminders.json, and bot_state.json to GitHub if running inside GitHub Actions."""
        if os.getenv("GITHUB_ACTIONS") != "true":
            return
        try:
            subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=False)
            subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], check=False)
            subprocess.run(["git", "add", self.storage_path, self.state_path, self.reminders_path], check=False)
            diff = subprocess.run(["git", "diff", "--staged", "--quiet"], check=False)
            if diff.returncode != 0:
                subprocess.run(["git", "commit", "-m", "chore: sync alarms, reminders, and bot state [skip ci]"], check=False)
                subprocess.run(["git", "push"], check=False)
                logger.info("Auto-synced state changes to git.")
        except Exception as e:
            logger.warning(f"Git auto-sync warning: {e}")
```
4. Add `evaluate_due_reminders`:
```python
    def evaluate_due_reminders(self):
        due_items = self.reminder_manager.get_due_reminders()
        if not due_items:
            return

        for item in due_items:
            rem_id = item["id"]
            title = item.get("title", "Reminder")
            due_at_str = item.get("due_at", "")
            time_display = ""
            if due_at_str:
                try:
                    time_display = due_at_str[11:16]
                except Exception:
                    pass

            text = (
                f"⏰ <b>REMINDER ALERT!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<b>{title}</b>\n"
            )
            if time_display:
                text += f"🕒 <i>Scheduled for {time_display}</i>\n"

            reply_markup = {
                "inline_keyboard": [
                    [
                        {"text": "✅ Done", "callback_data": f"task_done:{rem_id}"},
                        {"text": "⏰ Snooze 10m", "callback_data": f"task_snooze:{rem_id}:10"},
                        {"text": "⏰ Snooze 1h", "callback_data": f"task_snooze:{rem_id}:60"}
                    ]
                ]
            }

            self.send_telegram_msg(self.chat_id, text, reply_markup=reply_markup)
            self.reminder_manager.mark_triggered(rem_id)
            self.git_sync_changes()
```
5. In `run()` loop, invoke `evaluate_due_reminders()` alongside `evaluate_active_alarms()` or on the loop interval:
```python
            # 2. Check stock alarms and due reminders
            if (now - last_stock_check) >= self.loop_interval_seconds:
                logger.info(f"--- Running stock & reminder cycle #{cycles + 1} (Elapsed: {elapsed:.1f}s) ---")
                self.evaluate_due_reminders()
                self.evaluate_active_alarms()
                last_stock_check = time.time()
                cycles += 1
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cloud_runner.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add cloud_runner.py tests/test_cloud_runner.py
git commit --author="droritos <droritos@users.noreply.github.com>" -m "feat(runner): integrate reminders evaluation and git auto-sync in CloudRunner"
```

---

### Task 3: Telegram Command Handler Routing & UI (`telegram_command_handler.py`)

**Files:**
- Modify: `telegram_command_handler.py`
- Modify: `tests/test_telegram_command_handler.py`

**Interfaces:**
- Consumes: `ReminderManager`, `parse_reminder_input`
- Produces:
  - Commands: `/remind <time/date> <task>`, `/todo <task>`, `/task <task>`, `/tasks`, `/reminders`, `/todos`
  - Callback queries: `task_done:<id>`, `task_del:<id>`, `task_snooze:<id>:<minutes>`
  - Updated persistent keyboard: `[📋 My Alarms] [📝 Tasks & Reminders]` / `[📈 Quick Quotes] [❓ Help]`
  - Updated `/start` and `/help` descriptions

- [ ] **Step 1: Write the failing tests**

Add tests to `tests/test_telegram_command_handler.py`:
```python
def test_remind_command_timed(tmp_path):
    storage = str(tmp_path / "reminders.json")
    rem_mgr = ReminderManager(storage_path=storage)
    mock_send = MagicMock()
    handler = TelegramCommandHandler(
        alarm_manager=MagicMock(),
        engine=MagicMock(),
        send_msg_fn=mock_send,
        reminder_manager=rem_mgr
    )

    update = {
        "message": {
            "chat": {"id": 12345},
            "text": "/remind 25m Check oven"
        }
    }
    handled = handler.handle_update(update)
    assert handled is True
    mock_send.assert_called_once()
    assert "Reminder set" in mock_send.call_args[0][1]
    assert "Check oven" in mock_send.call_args[0][1]

    items = rem_mgr.get_reminders()
    assert len(items) == 1
    assert items[0]["title"] == "Check oven"
    assert items[0]["due_at"] is not None


def test_todo_command_untimed(tmp_path):
    storage = str(tmp_path / "reminders.json")
    rem_mgr = ReminderManager(storage_path=storage)
    mock_send = MagicMock()
    handler = TelegramCommandHandler(
        alarm_manager=MagicMock(),
        engine=MagicMock(),
        send_msg_fn=mock_send,
        reminder_manager=rem_mgr
    )

    update = {
        "message": {
            "chat": {"id": 12345},
            "text": "/todo Buy almond milk"
        }
    }
    handled = handler.handle_update(update)
    assert handled is True
    mock_send.assert_called_once()
    assert "To-Do added" in mock_send.call_args[0][1]

    items = rem_mgr.get_reminders()
    assert len(items) == 1
    assert items[0]["title"] == "Buy almond milk"
    assert items[0]["due_at"] is None


def test_tasks_list_command(tmp_path):
    storage = str(tmp_path / "reminders.json")
    rem_mgr = ReminderManager(storage_path=storage)
    rem_mgr.add_reminder("Buy milk")
    rem_mgr.add_reminder("Doctor appointment", due_at=datetime(2026, 10, 18, 18, 30))

    mock_send = MagicMock()
    handler = TelegramCommandHandler(
        alarm_manager=MagicMock(),
        engine=MagicMock(),
        send_msg_fn=mock_send,
        reminder_manager=rem_mgr
    )

    update = {
        "message": {
            "chat": {"id": 12345},
            "text": "/tasks"
        }
    }
    handler.handle_update(update)
    mock_send.assert_called_once()
    text = mock_send.call_args[0][1]
    assert "Your Tasks & Reminders" in text
    assert "Buy milk" in text
    assert "Doctor appointment" in text
    assert "reply_markup" in mock_send.call_args[1]
    markup = mock_send.call_args[1]["reply_markup"]
    assert "inline_keyboard" in markup


def test_callback_task_done(tmp_path):
    storage = str(tmp_path / "reminders.json")
    rem_mgr = ReminderManager(storage_path=storage)
    item = rem_mgr.add_reminder("Clean room")

    mock_send = MagicMock()
    mock_answer = MagicMock()
    handler = TelegramCommandHandler(
        alarm_manager=MagicMock(),
        engine=MagicMock(),
        send_msg_fn=mock_send,
        answer_cb_fn=mock_answer,
        reminder_manager=rem_mgr
    )

    query = {
        "id": "cb_done_1",
        "data": f"task_done:{item['id']}",
        "message": {"chat": {"id": 12345}}
    }
    assert handler.handle_callback_query(query) is True
    mock_answer.assert_called_with("cb_done_1", "✅ Completed Clean room!")
    assert rem_mgr.get_reminders()[0]["completed"] if rem_mgr.get_reminders(include_completed=True) else True


def test_callback_task_del(tmp_path):
    storage = str(tmp_path / "reminders.json")
    rem_mgr = ReminderManager(storage_path=storage)
    item = rem_mgr.add_reminder("Discard me")

    mock_send = MagicMock()
    mock_answer = MagicMock()
    handler = TelegramCommandHandler(
        alarm_manager=MagicMock(),
        engine=MagicMock(),
        send_msg_fn=mock_send,
        answer_cb_fn=mock_answer,
        reminder_manager=rem_mgr
    )

    query = {
        "id": "cb_del_1",
        "data": f"task_del:{item['id']}",
        "message": {"chat": {"id": 12345}}
    }
    assert handler.handle_callback_query(query) is True
    mock_answer.assert_called_with("cb_del_1", "🗑️ Task deleted!")
    assert len(rem_mgr.get_reminders(include_completed=True)) == 0


def test_callback_task_snooze(tmp_path):
    storage = str(tmp_path / "reminders.json")
    rem_mgr = ReminderManager(storage_path=storage)
    item = rem_mgr.add_reminder("Oven reminder", due_at=datetime(2026, 10, 18, 14, 0))

    mock_send = MagicMock()
    mock_answer = MagicMock()
    handler = TelegramCommandHandler(
        alarm_manager=MagicMock(),
        engine=MagicMock(),
        send_msg_fn=mock_send,
        answer_cb_fn=mock_answer,
        reminder_manager=rem_mgr
    )

    query = {
        "id": "cb_snooze_1",
        "data": f"task_snooze:{item['id']}:15",
        "message": {"chat": {"id": 12345}}
    }
    assert handler.handle_callback_query(query) is True
    mock_answer.assert_called_with("cb_snooze_1", "⏰ Snoozed for 15m!")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_telegram_command_handler.py -k "test_remind or test_todo or test_tasks" -v`
Expected: FAIL with missing reminder handling

- [ ] **Step 3: Implement task commands and callbacks in `telegram_command_handler.py`**

1. Import `ReminderManager` and `parse_reminder_input`:
```python
from reminders_manager import ReminderManager, parse_reminder_input
```
2. Update `MAIN_MENU_KEYBOARD`:
```python
MAIN_MENU_KEYBOARD: Dict[str, Any] = {
    "keyboard": [
        [{"text": "📋 My Alarms"}, {"text": "📝 Tasks & Reminders"}],
        [{"text": "📈 Quick Quotes"}, {"text": "❓ Help"}]
    ],
    "resize_keyboard": True,
    "is_persistent": True
}
```
3. Update `TelegramCommandHandler.__init__`:
```python
    def __init__(
        self,
        alarm_manager: AlarmManager,
        engine: StockEngine,
        send_msg_fn: Callable[..., None],
        answer_cb_fn: Optional[Callable[[str, Optional[str]], None]] = None,
        reminder_manager: Optional[ReminderManager] = None,
    ) -> None:
        self.alarm_manager = alarm_manager
        self.engine = engine
        self.send_msg = send_msg_fn
        self.answer_cb = answer_cb_fn
        self.reminder_manager = reminder_manager or ReminderManager()
```
4. In `handle_update`:
```python
        # Handle persistent menu buttons or commands
        if text in ("📋 My Alarms", "📋 my alarms") or cmd in ("/list", "/alarms", "list", "alarms"):
            self.handle_list(chat_id)
        elif text in ("📝 Tasks & Reminders", "📝 tasks & reminders") or cmd in ("/tasks", "/reminders", "/todos", "tasks", "reminders", "todos"):
            self.handle_tasks(chat_id)
        elif text in ("📈 Quick Quotes", "📈 quick quotes", "quotes", "quick quotes"):
            self.handle_quick_quotes(chat_id)
        elif text in ("➕ How to Set", "➕ how to set") or cmd in ("/how", "how"):
            self.handle_how_to_set(chat_id)
        elif text in ("❓ Help", "❓ help") or cmd in ("/start", "/help", "help"):
            self.handle_help(chat_id)
        elif cmd in ("/remind", "remind"):
            self.handle_remind(chat_id, " ".join(tokens[1:]))
        elif cmd in ("/todo", "/task", "todo", "task"):
            self.handle_todo(chat_id, " ".join(tokens[1:]))
```
5. Implement `handle_remind`, `handle_todo`, `handle_tasks`:
```python
    def handle_remind(self, chat_id: str, raw_text: str) -> None:
        if not raw_text.strip():
            self._send(
                chat_id,
                "⚠️ <b>Usage:</b> <code>/remind &lt;time&gt; &lt;task&gt;</code>\n\n"
                "<b>Examples:</b>\n"
                "• <code>/remind 25m Check oven</code>\n"
                "• <code>/remind 18:30 Call doctor</code>\n"
                "• <code>/remind tomorrow 09:00 Buy groceries</code>\n"
                "• <code>/remind 18/11 19:30 Wedding</code>",
                reply_markup=MAIN_MENU_KEYBOARD
            )
            return

        due_at, task_title = parse_reminder_input(raw_text)
        if not task_title:
            task_title = "Reminder"

        item = self.reminder_manager.add_reminder(title=task_title, due_at=due_at)
        time_str = due_at.strftime("%a %b %d, %H:%M") if due_at else "No deadline"

        self._send(
            chat_id,
            f"⏰ <b>Reminder set!</b>\n\n"
            f"📝 <b>Task:</b> {html.escape(task_title)}\n"
            f"🕒 <b>When:</b> {time_str}\n"
            f"🆔 <b>ID:</b> <code>{item['id']}</code>",
            reply_markup=MAIN_MENU_KEYBOARD
        )

    def handle_todo(self, chat_id: str, raw_text: str) -> None:
        if not raw_text.strip():
            self._send(
                chat_id,
                "⚠️ <b>Usage:</b> <code>/todo &lt;task&gt;</code>\n\n"
                "<b>Example:</b> <code>/todo Buy milk</code>",
                reply_markup=MAIN_MENU_KEYBOARD
            )
            return

        due_at, task_title = parse_reminder_input(raw_text)
        if not task_title:
            task_title = raw_text.strip()

        item = self.reminder_manager.add_reminder(title=task_title, due_at=due_at)
        if due_at:
            time_str = due_at.strftime("%a %b %d, %H:%M")
            self._send(
                chat_id,
                f"⏰ <b>Reminder set!</b>\n\n"
                f"📝 <b>Task:</b> {html.escape(task_title)}\n"
                f"🕒 <b>When:</b> {time_str}\n"
                f"🆔 <b>ID:</b> <code>{item['id']}</code>",
                reply_markup=MAIN_MENU_KEYBOARD
            )
        else:
            self._send(
                chat_id,
                f"📝 <b>To-Do added!</b>\n\n"
                f"• {html.escape(task_title)}\n"
                f"🆔 <b>ID:</b> <code>{item['id']}</code>",
                reply_markup=MAIN_MENU_KEYBOARD
            )

    def handle_tasks(self, chat_id: str) -> None:
        items = self.reminder_manager.get_reminders(include_completed=False)
        if not items:
            self._send(
                chat_id,
                "✨ <b>No active tasks or reminders!</b>\n\n"
                "Send <code>/remind 25m Check oven</code> or <code>/todo Buy milk</code> to add one.",
                reply_markup=MAIN_MENU_KEYBOARD
            )
            return

        lines = ["📋 <b>Your Tasks & Reminders:</b>\n━━━━━━━━━━━━━━━━━━━━"]
        keyboard_rows = []

        for idx, item in enumerate(items, start=1):
            rem_id = item["id"]
            title = html.escape(item.get("title", ""))
            due_at_str = item.get("due_at")

            if due_at_str:
                try:
                    dt = datetime.fromisoformat(due_at_str)
                    time_label = dt.strftime("%d/%m %H:%M")
                    lines.append(f"{idx}. ⏰ [<b>{time_label}</b>] {title}")
                except Exception:
                    lines.append(f"{idx}. ⏰ {title}")
            else:
                lines.append(f"{idx}. 📝 {title}")

            keyboard_rows.append([
                {"text": f"✅ Done #{idx}", "callback_data": f"task_done:{rem_id}"},
                {"text": f"🗑️ Del #{idx}", "callback_data": f"task_del:{rem_id}"}
            ])

        markup = {"inline_keyboard": keyboard_rows}
        self._send(chat_id, "\n".join(lines), reply_markup=markup)
```
6. In `handle_callback_query`:
```python
        elif data.startswith("task_done:"):
            rem_id = data.split(":", 1)[1].strip()
            item = next((i for i in self.reminder_manager.get_reminders(include_completed=True) if i["id"] == rem_id), None)
            title = item.get("title", "Task") if item else "Task"
            success = self.reminder_manager.mark_completed(rem_id)
            if self.answer_cb:
                self.answer_cb(query_id, f"✅ Completed {title}!" if success else "Task not found.")
            if chat_id and success:
                self._send(chat_id, f"✅ Marked <b>{html.escape(title)}</b> as completed!", reply_markup=MAIN_MENU_KEYBOARD)
            return True

        elif data.startswith("task_del:"):
            rem_id = data.split(":", 1)[1].strip()
            success = self.reminder_manager.delete_reminder(rem_id)
            if self.answer_cb:
                self.answer_cb(query_id, "🗑️ Task deleted!" if success else "Task not found.")
            if chat_id and success:
                self._send(chat_id, "🗑️ Task deleted.", reply_markup=MAIN_MENU_KEYBOARD)
            return True

        elif data.startswith("task_snooze:"):
            parts = data.split(":")
            rem_id = parts[1].strip()
            minutes = int(parts[2].strip()) if len(parts) > 2 and parts[2].isdigit() else 10
            snoozed = self.reminder_manager.snooze_reminder(rem_id, minutes=minutes)
            if self.answer_cb:
                self.answer_cb(query_id, f"⏰ Snoozed for {minutes}m!" if snoozed else "Task not found.")
            if chat_id and snoozed:
                self._send(chat_id, f"⏰ Snoozed <b>{html.escape(snoozed.get('title', 'Task'))}</b> for {minutes} minutes.", reply_markup=MAIN_MENU_KEYBOARD)
            return True
```
7. Update `handle_help` to list `/remind`, `/todo`, `/tasks`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_telegram_command_handler.py -v`
Expected: PASS (44+ passed)

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest -v`
Expected: PASS (105+ passed, 0 failures)

- [ ] **Step 6: Commit**

```bash
git add telegram_command_handler.py tests/test_telegram_command_handler.py
git commit --author="droritos <droritos@users.noreply.github.com>" -m "feat(telegram): add /remind, /todo, /tasks commands and interactive callback buttons"
```
