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
