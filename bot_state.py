import json
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class BotStateManager:
    def __init__(self, storage_path: str = "bot_state.json"):
        self.storage_path = storage_path
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.storage_path):
            directory = os.path.dirname(self.storage_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            self._write_state({"last_update_id": 0})

    def _read_state(self) -> Dict[str, Any]:
        try:
            if not os.path.exists(self.storage_path):
                return {"last_update_id": 0}
            with open(self.storage_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {"last_update_id": 0}
                return json.loads(content)
        except Exception as e:
            logger.error(f"Error reading bot state: {e}")
            return {"last_update_id": 0}

    def _write_state(self, state: Dict[str, Any]):
        try:
            temp_path = f"{self.storage_path}.tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            if os.path.exists(self.storage_path):
                os.replace(temp_path, self.storage_path)
            else:
                os.rename(temp_path, self.storage_path)
        except Exception as e:
            logger.error(f"Error writing bot state: {e}")

    def get_last_offset(self) -> int:
        return self._read_state().get("last_update_id", 0)

    def set_last_offset(self, offset: int):
        state = self._read_state()
        state["last_update_id"] = offset
        self._write_state(state)
