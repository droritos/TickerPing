import pytest
from unittest.mock import patch, MagicMock
from notifier import TelegramNotifier, CallMeBotWhatsAppNotifier, ConsoleNotifier

@patch("notifier.requests.post")
def test_telegram_send_alert_success(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True}
    mock_post.return_value = mock_resp

    notifier = TelegramNotifier(bot_token="test_token_123", chat_id="987654321")
    success = notifier.send_alert(
        ticker="AAPL",
        current_price=251.20,
        target_price=250.00,
        direction="ABOVE",
        change_percent=1.45,
        note="Resistance broken"
    )

    assert success is True
    assert mock_post.called
    args, kwargs = mock_post.call_args
    assert "https://api.telegram.org/bottest_token_123/" in args[0]
    assert ("sendPhoto" in args[0]) or ("sendMessage" in args[0])

@patch("notifier.requests.get")
def test_telegram_detect_chat_id(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "ok": True,
        "result": [
            {
                "message": {
                    "chat": {"id": 12345678, "first_name": "Dror", "username": "droritos"}
                }
            }
        ]
    }
    mock_get.return_value = mock_resp

    info = TelegramNotifier.detect_chat_id("test_token")
    assert info is not None
    assert info["chat_id"] == "12345678"
    assert info["first_name"] == "Dror"

def test_console_notifier():
    notifier = ConsoleNotifier()
    success = notifier.send_alert(
        ticker="TSLA",
        current_price=220.0,
        target_price=215.0,
        direction="BELOW"
    )
    assert success is True
