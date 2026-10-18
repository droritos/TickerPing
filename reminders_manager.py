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

    # 1. Relative duration: "in 25m", "25m", "10 min", "2h", "1.5h", "in 1 hour", "1 minute"
    rel_match = re.match(
        r"^(?:in\s+)?(\d+(?:\.\d+)?)\s*(m|min|mins|minutes?|h|hr|hrs|hours?)\b\s*(.*)$",
        text,
        re.IGNORECASE
    )
    if rel_match:
        try:
            val = float(rel_match.group(1))
            unit = rel_match.group(2).lower()
            remainder = rel_match.group(3).strip()
            if unit.startswith("m"):
                due_at = now + timedelta(minutes=val)
            else:
                due_at = now + timedelta(hours=val)
            return due_at, remainder
        except (ValueError, OverflowError):
            pass

    # 2. "tomorrow" with optional time: "tomorrow 09:00 Buy milk", "tomorrow Buy milk", "tomorrow 8:30pm dinner"
    tom_match = re.match(
        r"^tomorrow(?:\s+at)?(?:\s+(\d{1,2}):(\d{2})\s*(am|pm)?)?\b\s*(.*)$",
        text,
        re.IGNORECASE
    )
    if tom_match:
        hour_str = tom_match.group(1)
        min_str = tom_match.group(2)
        ampm_str = tom_match.group(3)
        remainder = tom_match.group(4).strip()
        hour = int(hour_str) if hour_str is not None else 9
        minute = int(min_str) if min_str is not None else 0
        if ampm_str:
            ampm = ampm_str.lower()
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
        try:
            tomorrow = now + timedelta(days=1)
            due_at = datetime(tomorrow.year, tomorrow.month, tomorrow.day, hour, minute, 0)
            return due_at, remainder
        except (ValueError, OverflowError):
            pass

    # 3. Calendar date: "18/11 19:30 Wedding", "18/11 Wedding", "2026-11-18 19:30", etc.
    date_match = re.match(
        r"^(\d{1,4})([/\-\.])(\d{1,2})(?:[/\-\.](\d{2,4}))?(?:\s+(?:at\s+)?(\d{1,2}):(\d{2})\s*(am|pm)?)?\b\s*(.*)$",
        text,
        re.IGNORECASE
    )
    if date_match:
        part1 = date_match.group(1)
        sep = date_match.group(2)
        part2 = date_match.group(3)
        part3 = date_match.group(4)
        hour_str = date_match.group(5)
        min_str = date_match.group(6)
        ampm_str = date_match.group(7)
        remainder = date_match.group(8).strip()

        is_valid_date = True
        # Prevent false positives: decimals (e.g. 3.5 star review) and ranges (e.g. 5-6 apples)
        if sep in (".", "-"):
            if not part3 and not hour_str:
                # Require explicit year or explicit time for dot and dash separators
                is_valid_date = False
        elif sep == "/":
            if not part3 and not hour_str:
                # Common fractions without year or time (e.g. 1/2 cup sugar)
                common_fractions = {
                    (1, 2), (1, 3), (2, 3), (1, 4), (3, 4),
                    (1, 5), (2, 5), (3, 5), (4, 5),
                    (1, 6), (5, 6),
                    (1, 8), (3, 8), (5, 8), (7, 8),
                    (1, 10), (3, 10), (7, 10), (9, 10)
                }
                try:
                    if (int(part1), int(part2)) in common_fractions:
                        is_valid_date = False
                except ValueError:
                    pass

                first_word = remainder.split()[0].lower() if remainder.split() else ""
                measurement_units = {
                    "cup", "cups", "tsp", "tbsp", "teaspoon", "teaspoons",
                    "tablespoon", "tablespoons", "oz", "ounce", "ounces",
                    "lb", "lbs", "pound", "pounds", "g", "gram", "grams",
                    "kg", "kilo", "kilos", "slice", "slices", "can", "cans",
                    "bottle", "bottles", "pinch", "pinches", "quart", "quarts",
                    "pint", "pints", "gallon", "gallons"
                }
                if first_word in measurement_units:
                    is_valid_date = False

        if is_valid_date:
            if len(part1) == 4:
                year = int(part1)
                month = int(part2)
                day = int(part3) if part3 else 1
                has_explicit_year = True
            else:
                day = int(part1)
                month = int(part2)
                has_explicit_year = bool(part3)
                year = int(part3) if part3 else now.year
                if year < 100:
                    year += 2000

            hour = int(hour_str) if hour_str is not None else 9
            minute = int(min_str) if min_str is not None else 0
            if ampm_str:
                ampm = ampm_str.lower()
                if ampm == "pm" and hour < 12:
                    hour += 12
                elif ampm == "am" and hour == 12:
                    hour = 0

            try:
                due_at = datetime(year, month, day, hour, minute, 0)
                if not has_explicit_year and due_at < now:
                    due_at = datetime(year + 1, month, day, hour, minute, 0)
                return due_at, remainder
            except (ValueError, OverflowError):
                pass

    # 4. Time of day: "18:30 Call doctor", "at 18:30 Call doctor", "8:30pm dinner"
    time_match = re.match(
        r"^(?:at\s+)?(\d{1,2}):(\d{2})\s*(am|pm)?\b\s*(.*)$",
        text,
        re.IGNORECASE
    )
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
        ampm_str = time_match.group(3)
        remainder = time_match.group(4).strip()
        if ampm_str:
            ampm = ampm_str.lower()
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
        try:
            due_at = datetime(now.year, now.month, now.day, hour, minute, 0)
            if due_at <= now:
                due_at += timedelta(days=1)
            return due_at, remainder
        except (ValueError, OverflowError):
            pass

    # Untimed to-do item
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
        if now is None:
            now = datetime.now()
        with self._lock:
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
        if now is None:
            now = datetime.now()
        clean_id = str(reminder_id).strip().lower()
        with self._lock:
            items = self._read_file()
            target = None
            for i in items:
                if str(i.get("id", "")).strip().lower() == clean_id:
                    new_due = now + timedelta(minutes=minutes)
                    i["due_at"] = new_due.isoformat()
                    i["triggered"] = False
                    i["completed"] = False
                    i["completed_at"] = None
                    target = i
                    break
            if target:
                self._write_file(items)
            return target
