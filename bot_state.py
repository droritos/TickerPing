import json
import logging
import os
import threading
from typing import Any, Dict

logger = logging.getLogger(__name__)


class BotStateManager:
    """Manages persistent state for the Telegram bot, specifically update offsets."""

    def __init__(self, storage_path: str = "bot_state.json"):
        """Initialize the state manager with a persistent storage path."""
        self.storage_path = storage_path
        self._lock = threading.Lock()
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Ensure that the state file and parent directories exist."""
        if not os.path.exists(self.storage_path):
            directory = os.path.dirname(self.storage_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            self._write_state({"last_update_id": 0})

    def _read_state(self) -> Dict[str, Any]:
        """Read the state dictionary from disk safely under a lock."""
        with self._lock:
            try:
                if not os.path.exists(self.storage_path):
                    return {"last_update_id": 0}
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if not content:
                        return {"last_update_id": 0}
                    data = json.loads(content)
                    if not isinstance(data, dict):
                        logger.warning(
                            f"Bot state data is not a dictionary in {self.storage_path}, returning default."
                        )
                        return {"last_update_id": 0}
                    return data
            except Exception as e:
                logger.error(f"Error reading bot state: {e}")
                return {"last_update_id": 0}

    def _write_state(self, state: Dict[str, Any]):
        """Write the state dictionary to disk atomically under a lock."""
        temp_path = f"{self.storage_path}.tmp"
        with self._lock:
            try:
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=2)
                os.replace(temp_path, self.storage_path)
            except Exception as e:
                logger.error(f"Error writing bot state: {e}")
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass

    def get_last_offset(self) -> int:
        """Get the last processed Telegram update ID."""
        val = self._read_state().get("last_update_id", 0)
        try:
            return int(val)
        except (ValueError, TypeError):
            return 0

    def set_last_offset(self, offset: int):
        """Set and persist the last processed Telegram update ID."""
        state = self._read_state()
        state["last_update_id"] = offset
        self._write_state(state)

    def get(self, key: str, default: Any = None) -> Any:
        """Get an arbitrary key from persistent state."""
        return self._read_state().get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set and persist an arbitrary key in state."""
        state = self._read_state()
        state[key] = value
        self._write_state(state)

