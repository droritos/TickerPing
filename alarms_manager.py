import json
import os
import uuid
import threading
from datetime import datetime
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class AlarmManager:
    def __init__(self, storage_path: str = "alarms.json"):
        self.storage_path = storage_path
        self._lock = threading.Lock()
        self._ensure_file_exists()

    def _ensure_file_exists(self):
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
                logger.error(f"Error reading alarms storage: {e}")
                return []

    def _write_file(self, data: List[Dict[str, Any]]) -> bool:
        with self._lock:
            try:
                # Write to temp file then rename for atomic safety
                temp_path = f"{self.storage_path}.tmp"
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                if os.path.exists(self.storage_path):
                    os.replace(temp_path, self.storage_path)
                else:
                    os.rename(temp_path, self.storage_path)
                return True
            except Exception as e:
                logger.error(f"Error writing alarms storage: {e}")
                return False

    def get_alarms(self) -> List[Dict[str, Any]]:
        return self._read_file()

    def get_alarm(self, alarm_id: str) -> Optional[Dict[str, Any]]:
        alarms = self._read_file()
        for a in alarms:
            if a.get("id") == alarm_id:
                return a
        return None

    def add_alarm(
        self,
        ticker: str,
        target_price: float,
        direction: str,
        note: str = ""
    ) -> Dict[str, Any]:
        clean_ticker = ticker.strip().upper()
        clean_direction = direction.strip().upper()
        if clean_direction not in ("ABOVE", "BELOW"):
            clean_direction = "ABOVE"

        alarm = {
            "id": str(uuid.uuid4())[:8],
            "ticker": clean_ticker,
            "target_price": round(float(target_price), 2),
            "direction": clean_direction,
            "note": note.strip(),
            "active": True,
            "triggered": False,
            "trigger_price": None,
            "created_at": datetime.now().isoformat(),
            "last_triggered_at": None
        }

        alarms = self._read_file()
        alarms.append(alarm)
        self._write_file(alarms)
        return alarm

    def delete_alarm(self, alarm_id: str) -> bool:
        alarms = self._read_file()
        initial_len = len(alarms)
        alarms = [a for a in alarms if a.get("id") != alarm_id]
        if len(alarms) < initial_len:
            self._write_file(alarms)
            return True
        return False

    def toggle_active(self, alarm_id: str) -> bool:
        alarms = self._read_file()
        for a in alarms:
            if a.get("id") == alarm_id:
                a["active"] = not a.get("active", True)
                self._write_file(alarms)
                return True
        return False

    def mark_triggered(self, alarm_id: str, trigger_price: float) -> bool:
        alarms = self._read_file()
        for a in alarms:
            if a.get("id") == alarm_id:
                a["triggered"] = True
                a["trigger_price"] = round(float(trigger_price), 2)
                a["last_triggered_at"] = datetime.now().isoformat()
                self._write_file(alarms)
                return True
        return False

    def reset_alarm(self, alarm_id: str) -> bool:
        alarms = self._read_file()
        for a in alarms:
            if a.get("id") == alarm_id:
                a["triggered"] = False
                a["trigger_price"] = None
                self._write_file(alarms)
                return True
        return False
