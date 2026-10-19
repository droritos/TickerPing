"""
reminders_manager.py — Smart Tasks & Reminders Manager for TickerPing.
Supports relative timers (25m, 2h), time of day (18:30, 8:30pm), calendar dates (18/11 19:30),
and open to-dos with thread-safe atomic JSON persistence.
"""
from datetime import datetime, timedelta
import json
import logging
import os
import re
import shutil
import threading
from typing import Any, Dict, List, Optional, Tuple
import uuid

from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


def get_bot_timezone() -> ZoneInfo:
    """Returns the configured timezone for the bot, defaulting to Asia/Jerusalem."""
    tz_name = os.getenv("BOT_TIMEZONE", os.getenv("TZ", "Asia/Jerusalem"))
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("Asia/Jerusalem")


def _parse_time_component(
    hour_str: str,
    min_str: Optional[str],
    ampm_str: Optional[str],
    now: datetime
) -> Optional[datetime]:
    try:
        hour = int(hour_str)
        minute = int(min_str) if min_str is not None else 0
        if ampm_str:
            ampm = ampm_str.lower()
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
        if hour >= 24 or minute >= 60:
            return None
        tz = now.tzinfo
        if tz:
            due_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0, tzinfo=tz)
        else:
            due_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if due_at <= now:
            due_at += timedelta(days=1)
        return due_at
    except (ValueError, OverflowError):
        return None


def _parse_rel_component(val_str: str, unit_str: str, now: datetime) -> Optional[datetime]:
    try:
        val = float(val_str)
        unit = unit_str.lower()
        if unit.startswith("m"):
            return now + timedelta(minutes=val)
        else:
            return now + timedelta(hours=val)
    except (ValueError, OverflowError):
        return None


def parse_reminder_input(raw_text: str, now: Optional[datetime] = None) -> Tuple[Optional[datetime], str]:
    """
    Parses natural reminder input into (due_at, task_title).
    Supports time/duration at the start or end of the text:
      - Relative: "25m Check oven", "Check oven in 25m", "Check oven 25m", "2h Laundry", "Laundry 2h"
      - Time of day: "17:45 cake", "take cake 17:45", "take cake at 17:45", "17 take cake", "take cake 17", "take cake at 17", "8:30pm dinner"
      - Tomorrow: "tomorrow 09:00 Meeting", "Meeting tomorrow 09:00", "Meeting tomorrow at 9:00", "Buy milk tomorrow"
      - Calendar date: "18/11 19:30 Wedding", "Wedding 18/11 19:30", "Wedding on 18/11 at 19:30", "Wedding 18/11"
    If no time is detected, returns (None, raw_text).
    """
    tz = get_bot_timezone()
    return_naive = (now is not None and now.tzinfo is None)
    if now is None:
        now = datetime.now(tz)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=tz)

    text = raw_text.strip()
    if not text:
        return None, ""

    def _finish(due: Optional[datetime], rem: str) -> Tuple[Optional[datetime], str]:
        if due is not None and return_naive:
            due = due.replace(tzinfo=None)
        return due, rem

    # 1. Relative duration at start: "in 25m Check oven", "25m Check oven", "2h Laundry"
    rel_pre = re.match(
        r"^(?:in\s+)?(\d+(?:\.\d+)?)\s*(m|min|mins|minutes?|h|hr|hrs|hours?)\b\s*(.*)$",
        text,
        re.IGNORECASE
    )
    if rel_pre and rel_pre.group(3).strip():
        due = _parse_rel_component(rel_pre.group(1), rel_pre.group(2), now)
        if due:
            return _finish(due, rel_pre.group(3).strip())

    # 2. Relative duration at end: "Check oven in 25m", "Check oven 25m", "Laundry 2h", "Laundry in 2h"
    rel_post = re.match(
        r"^(.*?)\s+(?:in\s+)?(\d+(?:\.\d+)?)\s*(m|min|mins|minutes?|h|hr|hrs|hours?)$",
        text,
        re.IGNORECASE
    )
    if rel_post and rel_post.group(1).strip():
        due = _parse_rel_component(rel_post.group(2), rel_post.group(3), now)
        if due:
            return _finish(due, rel_post.group(1).strip())

    # 3. "tomorrow" at start: "tomorrow 09:00 Meeting", "tomorrow Buy milk"
    tom_pre = re.match(
        r"^tomorrow(?:\s+at)?(?:\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?\b\s*(.*)$",
        text,
        re.IGNORECASE
    )
    if tom_pre:
        h_str, mn_str, ampm, rem = tom_pre.group(1), tom_pre.group(2), tom_pre.group(3), tom_pre.group(4).strip()
        try:
            hour = int(h_str) if h_str else 9
            minute = int(mn_str) if mn_str else 0
            if hour >= 24 or minute >= 60:
                return None, text
            if ampm:
                if ampm.lower() == "pm" and hour < 12:
                    hour += 12
                elif ampm.lower() == "am" and hour == 12:
                    hour = 0
            tom = now + timedelta(days=1)
            due = tom.replace(hour=hour, minute=minute, second=0, microsecond=0, tzinfo=now.tzinfo)
            return _finish(due, rem)
        except (ValueError, OverflowError):
            return None, text

    # 4. "tomorrow" at end: "Meeting tomorrow 09:00", "Meeting tomorrow at 9:00", "Buy milk tomorrow"
    tom_post = re.match(
        r"^(.*?)\s+tomorrow(?:\s+at)?(?:\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?$",
        text,
        re.IGNORECASE
    )
    if tom_post and tom_post.group(1).strip():
        rem, h_str, mn_str, ampm = tom_post.group(1).strip(), tom_post.group(2), tom_post.group(3), tom_post.group(4)
        try:
            hour = int(h_str) if h_str else 9
            minute = int(mn_str) if mn_str else 0
            if hour >= 24 or minute >= 60:
                return None, text
            if ampm:
                if ampm.lower() == "pm" and hour < 12:
                    hour += 12
                elif ampm.lower() == "am" and hour == 12:
                    hour = 0
            tom = now + timedelta(days=1)
            due = tom.replace(hour=hour, minute=minute, second=0, microsecond=0, tzinfo=now.tzinfo)
            return _finish(due, rem)
        except (ValueError, OverflowError):
            return None, text

    # 5. Calendar date at start: "18/11 19:30 Wedding", "18/11 Wedding"
    date_pre = re.match(
        r"^(\d{1,4})([/\-\.])(\d{1,2})(?:[/\-\.](\d{2,4}))?(?:\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?\b\s*(.*)$",
        text,
        re.IGNORECASE
    )
    if date_pre:
        part1, sep, part2, part3 = date_pre.group(1), date_pre.group(2), date_pre.group(3), date_pre.group(4)
        h_str, mn_str, ampm, rem = date_pre.group(5), date_pre.group(6), date_pre.group(7), date_pre.group(8).strip()
        is_valid_date = True
        if sep in (".", "-") and not part3 and not h_str:
            is_valid_date = False
        elif sep == "/" and not part3 and not h_str:
            common_fractions = {(1, 2), (1, 3), (2, 3), (1, 4), (3, 4)}
            try:
                if (int(part1), int(part2)) in common_fractions:
                    is_valid_date = False
            except ValueError:
                pass
        if is_valid_date:
            try:
                if len(part1) == 4:
                    year, month, day = int(part1), int(part2), int(part3) if part3 else 1
                    has_explicit_year = True
                else:
                    day, month = int(part1), int(part2)
                    has_explicit_year = bool(part3)
                    year = int(part3) if part3 else now.year
                    if year < 100:
                        year += 2000
                hour = int(h_str) if h_str is not None else 9
                minute = int(mn_str) if mn_str is not None else 0
                if hour >= 24 or minute >= 60:
                    return None, text
                if ampm:
                    if ampm.lower() == "pm" and hour < 12:
                        hour += 12
                    elif ampm.lower() == "am" and hour == 12:
                        hour = 0
                due_at = datetime(year, month, day, hour, minute, 0, tzinfo=now.tzinfo)
                if not has_explicit_year and due_at < now:
                    due_at = datetime(year + 1, month, day, hour, minute, 0, tzinfo=now.tzinfo)
                return _finish(due_at, rem)
            except (ValueError, OverflowError):
                pass

    # 6. Calendar date at end: "Wedding 18/11 19:30", "Wedding on 18/11 at 19:30", "Wedding 18/11"
    date_post = re.match(
        r"^(.*?)\s+(?:on\s+)?(\d{1,4})([/\-\.])(\d{1,2})(?:[/\-\.](\d{2,4}))?(?:\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?$",
        text,
        re.IGNORECASE
    )
    if date_post and date_post.group(1).strip():
        rem = date_post.group(1).strip()
        part1, sep, part2, part3 = date_post.group(2), date_post.group(3), date_post.group(4), date_post.group(5)
        h_str, mn_str, ampm = date_post.group(6), date_post.group(7), date_post.group(8)
        try:
            if len(part1) == 4:
                year, month, day = int(part1), int(part2), int(part3) if part3 else 1
                has_explicit_year = True
            else:
                day, month = int(part1), int(part2)
                has_explicit_year = bool(part3)
                year = int(part3) if part3 else now.year
                if year < 100:
                    year += 2000
            hour = int(h_str) if h_str is not None else 9
            minute = int(mn_str) if mn_str is not None else 0
            if hour >= 24 or minute >= 60:
                return None, text
            if ampm:
                if ampm.lower() == "pm" and hour < 12:
                    hour += 12
                elif ampm.lower() == "am" and hour == 12:
                    hour = 0
            due_at = datetime(year, month, day, hour, minute, 0, tzinfo=now.tzinfo)
            if not has_explicit_year and due_at < now:
                due_at = datetime(year + 1, month, day, hour, minute, 0, tzinfo=now.tzinfo)
            return _finish(due_at, rem)
        except (ValueError, OverflowError):
            pass

    # 7. Time of day at start: "17:45 cake", "at 17:45 cake", "17 cake", "at 17 cake", "8:30pm dinner"
    time_pre = re.match(
        r"^(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b\s*(.*)$",
        text,
        re.IGNORECASE
    )
    if time_pre:
        h_str, mn_str, ampm, rem = time_pre.group(1), time_pre.group(2), time_pre.group(3), time_pre.group(4).strip()
        if not rem.startswith((".", ",", "-", "/")):
            is_valid_time = False
            if mn_str is not None or ampm is not None:
                is_valid_time = True
            elif text.lower().startswith("at "):
                is_valid_time = True
            elif rem and int(h_str) in range(12, 24):
                is_valid_time = True
            if is_valid_time:
                due = _parse_time_component(h_str, mn_str, ampm, now)
                if due and rem:
                    return _finish(due, rem)

    # 8. Time of day at end: "take cake 17:45", "take cake at 17:45", "take cake 17", "take cake at 17", "dinner 8:30pm"
    time_post = re.match(
        r"^(.*?)\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$",
        text,
        re.IGNORECASE
    )
    if time_post:
        rem, h_str, mn_str, ampm = time_post.group(1).strip(), time_post.group(2), time_post.group(3), time_post.group(4)
        is_valid_time = False
        if mn_str is not None or ampm is not None:
            is_valid_time = True
        elif " at " in text.lower():
            is_valid_time = True
        elif rem and int(h_str) in range(0, 24):
            is_valid_time = True
        if is_valid_time:
            due = _parse_time_component(h_str, mn_str, ampm, now)
            if due and rem:
                return _finish(due, rem)

    # Untimed reminder item
    return None, text


class ReminderManager:
    """Thread-safe CRUD manager for tasks and reminders persisted to JSON."""

    def __init__(self, storage_path: str = "reminders.json") -> None:
        self.storage_path = storage_path
        self._lock = threading.RLock()
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        with self._lock:
            if not os.path.exists(self.storage_path):
                directory = os.path.dirname(self.storage_path)
                if directory and not os.path.exists(directory):
                    os.makedirs(directory, exist_ok=True)
                self._write_file([])

    def _read_file(self) -> List[Dict[str, Any]]:
        with self._lock:
            if not os.path.exists(self.storage_path):
                return []
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if not content:
                        return []
                    return json.loads(content)
            except Exception as e:
                logger.error(f"Error reading reminders file: {e}")
                try:
                    bak_path = f"{self.storage_path}.bak"
                    if os.path.exists(self.storage_path):
                        shutil.copy2(self.storage_path, bak_path)
                except Exception:
                    pass
                raise IOError(f"Failed to read or parse reminders file {self.storage_path}: {e}") from e

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
        clean_title = title.strip() if title else ""
        if not clean_title:
            clean_title = "Reminder"

        item = {
            "id": str(uuid.uuid4())[:8],
            "title": clean_title,
            "due_at": due_at.isoformat() if due_at else None,
            "completed": False,
            "triggered": False,
            "created_at": datetime.now().isoformat(),
            "completed_at": None,
            "last_triggered_at": None,
            "note": note.strip()
        }
        with self._lock:
            items = self._read_file()
            items.append(item)
            self._write_file(items)
        return item

    def get_reminder(self, reminder_id: str) -> Optional[Dict[str, Any]]:
        clean_id = str(reminder_id).strip().lower()
        with self._lock:
            items = self._read_file()
            for i in items:
                if str(i.get("id", "")).strip().lower() == clean_id:
                    return dict(i)
            return None

    def get_reminders(self, include_completed: bool = False) -> List[Dict[str, Any]]:
        with self._lock:
            items = self._read_file()
            if include_completed:
                return items
            return [i for i in items if not i.get("completed", False)]

    def get_due_reminders(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        tz = get_bot_timezone()
        if now is None:
            now = datetime.now(tz)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=tz)

        with self._lock:
            items = self.get_reminders(include_completed=False)
            due = []
            for i in items:
                due_at_str = i.get("due_at")
                if not due_at_str or i.get("triggered", False):
                    continue
                try:
                    due_dt = datetime.fromisoformat(due_at_str)
                    if due_dt.tzinfo is None:
                        due_dt = due_dt.replace(tzinfo=tz)
                    else:
                        due_dt = due_dt.astimezone(tz)
                    if due_dt <= now:
                        due.append(i)
                except Exception:
                    continue
            return due

    def mark_completed(self, reminder_id: str) -> bool:
        clean_id = str(reminder_id).strip().lower()
        with self._lock:
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
        with self._lock:
            items = self._read_file()
            found = False
            for i in items:
                if str(i.get("id", "")).strip().lower() == clean_id:
                    i["triggered"] = True
                    i["last_triggered_at"] = datetime.now().isoformat()
                    found = True
                    break
            if found:
                self._write_file(items)
            return found

    def delete_reminder(self, reminder_id: str) -> bool:
        clean_id = str(reminder_id).strip().lower()
        with self._lock:
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
        tz = get_bot_timezone()
        is_naive = (now is not None and now.tzinfo is None)
        if now is None:
            now = datetime.now(tz)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=tz)
        clean_id = str(reminder_id).strip().lower()
        with self._lock:
            items = self._read_file()
            target = None
            for i in items:
                if str(i.get("id", "")).strip().lower() == clean_id:
                    new_due = now + timedelta(minutes=minutes)
                    if is_naive:
                        new_due = new_due.replace(tzinfo=None)
                    i["due_at"] = new_due.isoformat()
                    i["triggered"] = False
                    i["completed"] = False
                    i["completed_at"] = None
                    target = i
                    break
            if target:
                self._write_file(items)
            return target

