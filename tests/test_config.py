import os
from config import load_config

def test_load_config_defaults(monkeypatch):
    monkeypatch.setenv("CALLMEBOT_PHONE", "+1234567890")
    monkeypatch.setenv("CALLMEBOT_APIKEY", "test_key_123")
    monkeypatch.setenv("POLL_INTERVAL_SECONDS", "45")
    
    cfg = load_config()
    assert cfg.phone == "+1234567890"
    assert cfg.apikey == "test_key_123"
    assert cfg.poll_interval == 45
    assert cfg.data_file == "alarms.json"

def test_load_config_missing_keys(monkeypatch):
    monkeypatch.delenv("CALLMEBOT_PHONE", raising=False)
    monkeypatch.delenv("CALLMEBOT_APIKEY", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    
    cfg = load_config()
    assert cfg.phone == ""
    assert cfg.apikey == ""
    assert cfg.telegram_bot_token == ""
    assert cfg.telegram_chat_id == ""
    assert cfg.is_configured is False
