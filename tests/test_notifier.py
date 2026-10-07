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

@patch("notifier.requests.post")
@patch("notifier.generate_stock_chart", return_value=None)
def test_send_alert_includes_rearm_and_news_buttons(mock_chart, mock_post):
    import json
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True}
    mock_post.return_value = mock_resp

    notifier = TelegramNotifier(bot_token="test_tok", chat_id="12345")
    success = notifier.send_alert(
        ticker="GOOGL",
        current_price=350.0,
        target_price=340.0,
        direction="ABOVE",
        change_percent=2.5,
        currency="USD",
        note=""
    )

    assert success is True
    assert mock_post.called
    call_kwargs = mock_post.call_args[1]
    if "json" in call_kwargs and "reply_markup" in call_kwargs["json"]:
        markup = call_kwargs["json"]["reply_markup"]
    elif "data" in call_kwargs and "reply_markup" in call_kwargs["data"]:
        rm = call_kwargs["data"]["reply_markup"]
        markup = json.loads(rm) if isinstance(rm, str) else rm
    else:
        pytest.fail("reply_markup not found in post call")

    keyboard = markup.get("inline_keyboard", [])
    assert len(keyboard) == 2
    # Row 0: +5% and -5%
    assert keyboard[0][0]["text"] == "📈 +5% ($367.50)"
    assert keyboard[0][0]["callback_data"] == "rearm:GOOGL:367.50:ABOVE"
    assert keyboard[0][1]["text"] == "📉 -5% ($332.50)"
    assert keyboard[0][1]["callback_data"] == "rearm:GOOGL:332.50:BELOW"
    # Row 1: News and Yahoo chart
    assert keyboard[1][0]["text"] == "📰 Top News"
    assert keyboard[1][0]["callback_data"] == "news:GOOGL"
    assert keyboard[1][1]["text"] == "🌐 GOOGL on Yahoo"
    assert keyboard[1][1]["url"] == "https://finance.yahoo.com/quote/GOOGL"

@patch("notifier.requests.post")
@patch("notifier.generate_stock_chart", return_value=b"fake_chart_bytes")
def test_send_alert_photo_includes_rearm_and_news_buttons(mock_chart, mock_post):
    import json
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True}
    mock_post.return_value = mock_resp

    notifier = TelegramNotifier(bot_token="test_tok", chat_id="12345")
    success = notifier.send_alert(
        ticker="msft",
        current_price=400.0,
        target_price=390.0,
        direction="ABOVE",
        change_percent=1.0,
        currency="USD",
        note="chart test"
    )

    assert success is True
    assert mock_post.called
    call_args, call_kwargs = mock_post.call_args
    assert "sendPhoto" in call_args[0]
    data = call_kwargs.get("data", {})
    assert "reply_markup" in data
    markup = json.loads(data["reply_markup"])
    keyboard = markup.get("inline_keyboard", [])
    assert len(keyboard) == 2
    assert keyboard[0][0]["callback_data"] == "rearm:MSFT:420.00:ABOVE"
    assert keyboard[0][1]["callback_data"] == "rearm:MSFT:380.00:BELOW"
    assert keyboard[1][0]["callback_data"] == "news:MSFT"
    assert keyboard[1][1]["url"] == "https://finance.yahoo.com/quote/MSFT"


