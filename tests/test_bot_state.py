import os
import json
import pytest
from bot_state import BotStateManager

def test_bot_state_default(tmp_path):
    state_file = str(tmp_path / "bot_state.json")
    manager = BotStateManager(storage_path=state_file)
    assert manager.get_last_offset() == 0

def test_bot_state_save_and_load(tmp_path):
    state_file = str(tmp_path / "bot_state.json")
    manager = BotStateManager(storage_path=state_file)
    manager.set_last_offset(12345)
    assert manager.get_last_offset() == 12345

    # Reload from disk
    manager2 = BotStateManager(storage_path=state_file)
    assert manager2.get_last_offset() == 12345

def test_bot_state_nested_directory(tmp_path):
    nested_file = str(tmp_path / "sub" / "dir" / "bot_state.json")
    manager = BotStateManager(storage_path=nested_file)
    assert manager.get_last_offset() == 0
    manager.set_last_offset(999)
    assert manager.get_last_offset() == 999

def test_bot_state_corrupted_file(tmp_path):
    state_file = str(tmp_path / "bot_state.json")
    with open(state_file, "w", encoding="utf-8") as f:
        f.write("{invalid_json")
    manager = BotStateManager(storage_path=state_file)
    assert manager.get_last_offset() == 0
