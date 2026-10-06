import pytest
from unittest.mock import MagicMock
from alarms_manager import AlarmManager
from engine import Quote
from telegram_command_handler import TelegramCommandHandler


@pytest.fixture
def mock_engine():
    engine = MagicMock()
    # Default quote for AAPL at $230.00
    engine.get_quote.return_value = Quote(
        symbol="AAPL",
        price=230.0,
        previous_close=226.6,
        change_percent=1.5,
        currency="USD"
    )
    return engine


@pytest.fixture
def alarm_mgr(tmp_path):
    storage = str(tmp_path / "test_alarms.json")
    return AlarmManager(storage_path=storage)


@pytest.fixture
def sent_messages():
    messages = []
    return messages


@pytest.fixture
def handler(mock_engine, alarm_mgr, sent_messages):
    def send_fn(chat_id: str, text: str):
        sent_messages.append((chat_id, text))

    return TelegramCommandHandler(
        alarm_manager=alarm_mgr,
        engine=mock_engine,
        send_msg_fn=send_fn
    )


# 1. Shorthand set: AAPL 250 -> smart ABOVE; AAPL 200 -> smart BELOW
def test_shorthand_set_above(handler, alarm_mgr, sent_messages):
    update = {
        "update_id": 100,
        "message": {
            "chat": {"id": 1438330510},
            "text": "AAPL 250"
        }
    }
    handled = handler.handle_update(update)
    assert handled is True
    assert len(sent_messages) == 2
    assert "Checking <b>AAPL</b>" in sent_messages[0][1]
    assert "Alarm Set Successfully" in sent_messages[1][1]
    assert "ABOVE $250.00" in sent_messages[1][1]

    alarms = alarm_mgr.get_alarms()
    assert len(alarms) == 1
    assert alarms[0]["ticker"] == "AAPL"
    assert alarms[0]["target_price"] == 250.0
    assert alarms[0]["direction"] == "ABOVE"


def test_shorthand_set_below(handler, alarm_mgr, sent_messages):
    update = {
        "update_id": 101,
        "message": {
            "chat": {"id": 1438330510},
            "text": "AAPL 200"
        }
    }
    handled = handler.handle_update(update)
    assert handled is True
    assert len(sent_messages) == 2
    assert "Alarm Set Successfully" in sent_messages[1][1]
    assert "BELOW $200.00" in sent_messages[1][1]

    alarms = alarm_mgr.get_alarms()
    assert len(alarms) == 1
    assert alarms[0]["ticker"] == "AAPL"
    assert alarms[0]["target_price"] == 200.0
    assert alarms[0]["direction"] == "BELOW"


# 2. Explicit set: /set TSLA 200 BELOW Buy dip
def test_explicit_set_with_direction_and_note(handler, mock_engine, alarm_mgr, sent_messages):
    mock_engine.get_quote.return_value = Quote(
        symbol="TSLA",
        price=215.0,
        previous_close=210.0,
        change_percent=2.38,
        currency="USD"
    )
    update = {
        "update_id": 102,
        "message": {
            "chat": {"id": 1438330510},
            "text": "/set TSLA 200 BELOW Buy dip"
        }
    }
    handled = handler.handle_update(update)
    assert handled is True
    assert len(sent_messages) == 2
    assert "Alarm Set Successfully" in sent_messages[1][1]
    assert "BELOW $200.00" in sent_messages[1][1]
    assert "Buy dip" in sent_messages[1][1]

    alarms = alarm_mgr.get_alarms()
    assert len(alarms) == 1
    assert alarms[0]["ticker"] == "TSLA"
    assert alarms[0]["target_price"] == 200.0
    assert alarms[0]["direction"] == "BELOW"
    assert alarms[0]["note"] == "Buy dip"


def test_set_invalid_price(handler, sent_messages):
    update = {
        "update_id": 103,
        "message": {
            "chat": {"id": 1438330510},
            "text": "/set AAPL invalid_price"
        }
    }
    handled = handler.handle_update(update)
    assert handled is True
    assert len(sent_messages) == 1
    assert "Invalid target price" in sent_messages[0][1]


def test_set_missing_args(handler, sent_messages):
    update = {
        "update_id": 104,
        "message": {
            "chat": {"id": 1438330510},
            "text": "/set AAPL"
        }
    }
    handled = handler.handle_update(update)
    assert handled is True
    assert len(sent_messages) == 1
    assert "Usage:" in sent_messages[0][1]


def test_set_ticker_not_found(handler, mock_engine, sent_messages):
    mock_engine.get_quote.return_value = None
    update = {
        "update_id": 105,
        "message": {
            "chat": {"id": 1438330510},
            "text": "/set NONEXISTENT 100 ABOVE"
        }
    }
    handled = handler.handle_update(update)
    assert handled is True
    assert len(sent_messages) == 2
    assert "Ticker <b>NONEXISTENT</b> not found" in sent_messages[1][1]


# 3. Price quote: /price AAPL
def test_price_quote_positive_change(handler, mock_engine, sent_messages):
    mock_engine.get_quote.return_value = Quote(
        symbol="AAPL",
        price=230.50,
        previous_close=225.00,
        change_percent=2.44,
        currency="USD"
    )
    update = {
        "update_id": 106,
        "message": {
            "chat": {"id": 1438330510},
            "text": "/price AAPL"
        }
    }
    handled = handler.handle_update(update)
    assert handled is True
    assert len(sent_messages) == 1
    msg_text = sent_messages[0][1]
    assert "AAPL Live Quote" in msg_text
    assert "$230.50 USD" in msg_text
    assert "+2.44%" in msg_text


def test_price_quote_negative_change(handler, mock_engine, sent_messages):
    mock_engine.get_quote.return_value = Quote(
        symbol="MSFT",
        price=400.00,
        previous_close=410.00,
        change_percent=-2.44,
        currency="USD"
    )
    update = {
        "update_id": 107,
        "message": {
            "chat": {"id": 1438330510},
            "text": "/quote MSFT"
        }
    }
    handled = handler.handle_update(update)
    assert handled is True
    assert len(sent_messages) == 1
    msg_text = sent_messages[0][1]
    assert "MSFT Live Quote" in msg_text
    assert "-2.44%" in msg_text


def test_price_quote_ticker_not_found(handler, mock_engine, sent_messages):
    mock_engine.get_quote.return_value = None
    update = {
        "update_id": 108,
        "message": {
            "chat": {"id": 1438330510},
            "text": "/price FAKETICKER"
        }
    }
    handled = handler.handle_update(update)
    assert handled is True
    assert len(sent_messages) == 1
    assert "Could not find quote" in sent_messages[0][1]


def test_price_missing_ticker(handler, sent_messages):
    update = {
        "update_id": 109,
        "message": {
            "chat": {"id": 1438330510},
            "text": "/price"
        }
    }
    handled = handler.handle_update(update)
    assert handled is True
    assert len(sent_messages) == 1
    assert "Specify a ticker" in sent_messages[0][1]


# 4. List alarms: /list (empty and active states)
def test_list_empty_alarms(handler, sent_messages):
    update = {
        "update_id": 110,
        "message": {
            "chat": {"id": 1438330510},
            "text": "/list"
        }
    }
    handled = handler.handle_update(update)
    assert handled is True
    assert len(sent_messages) == 1
    assert "You have no stock alarms set" in sent_messages[0][1]


def test_list_active_and_triggered_alarms(handler, alarm_mgr, mock_engine, sent_messages):
    a1 = alarm_mgr.add_alarm(ticker="AAPL", target_price=250.0, direction="ABOVE")
    a2 = alarm_mgr.add_alarm(ticker="TSLA", target_price=180.0, direction="BELOW")
    alarm_mgr.mark_triggered(a2["id"], trigger_price=175.0)

    update = {
        "update_id": 111,
        "message": {
            "chat": {"id": 1438330510},
            "text": "/alarms"
        }
    }
    handled = handler.handle_update(update)
    assert handled is True
    assert len(sent_messages) == 1
    msg_text = sent_messages[0][1]
    assert "Your Stock Alarms (2)" in msg_text
    assert "AAPL" in msg_text
    assert "Active 🟢" in msg_text
    assert "TSLA" in msg_text
    assert "🚨 Triggered" in msg_text


# 5. Delete alarm: /del AAPL (by ticker or ID)
def test_delete_alarm_by_ticker(handler, alarm_mgr, sent_messages):
    alarm_mgr.add_alarm(ticker="AAPL", target_price=250.0, direction="ABOVE")
    assert len(alarm_mgr.get_alarms()) == 1

    update = {
        "update_id": 112,
        "message": {
            "chat": {"id": 1438330510},
            "text": "/del AAPL"
        }
    }
    handled = handler.handle_update(update)
    assert handled is True
    assert len(sent_messages) == 1
    assert "Deleted alarm for <b>AAPL</b>" in sent_messages[0][1]
    assert len(alarm_mgr.get_alarms()) == 0


def test_delete_alarm_by_id(handler, alarm_mgr, sent_messages):
    alarm = alarm_mgr.add_alarm(ticker="AAPL", target_price=250.0, direction="ABOVE")
    alarm_id = alarm["id"]

    update = {
        "update_id": 113,
        "message": {
            "chat": {"id": 1438330510},
            "text": f"/del {alarm_id}"
        }
    }
    handled = handler.handle_update(update)
    assert handled is True
    assert len(sent_messages) == 1
    assert "Deleted alarm for <b>AAPL</b>" in sent_messages[0][1]
    assert len(alarm_mgr.get_alarms()) == 0


def test_delete_alarm_not_found(handler, sent_messages):
    update = {
        "update_id": 114,
        "message": {
            "chat": {"id": 1438330510},
            "text": "/del NONEXISTENT"
        }
    }
    handled = handler.handle_update(update)
    assert handled is True
    assert len(sent_messages) == 1
    assert "No alarm found matching" in sent_messages[0][1]


def test_delete_missing_arg(handler, sent_messages):
    update = {
        "update_id": 115,
        "message": {
            "chat": {"id": 1438330510},
            "text": "/del"
        }
    }
    handled = handler.handle_update(update)
    assert handled is True
    assert len(sent_messages) == 1
    assert "Specify what to delete" in sent_messages[0][1]


# 6. Help/Start: /start and /help
def test_start_and_help_commands(handler, sent_messages):
    for cmd in ("/start", "/help", "help"):
        sent_messages.clear()
        update = {
            "update_id": 116,
            "message": {
                "chat": {"id": 1438330510},
                "text": cmd
            }
        }
        handled = handler.handle_update(update)
        assert handled is True
        assert len(sent_messages) == 1
        assert "Welcome to TickerPing" in sent_messages[0][1]


# 7. Unknown command handling
def test_unknown_command(handler, sent_messages):
    update = {
        "update_id": 117,
        "message": {
            "chat": {"id": 1438330510},
            "text": "/foobar"
        }
    }
    handled = handler.handle_update(update)
    assert handled is True
    assert len(sent_messages) == 1
    assert "Unknown command" in sent_messages[0][1]


# 8. Malformed updates (empty text, missing fields)
def test_malformed_updates(handler, sent_messages):
    # Empty update dict
    assert handler.handle_update({}) is False

    # Missing message
    assert handler.handle_update({"update_id": 118}) is False

    # Message is not a dict
    assert handler.handle_update({"update_id": 119, "message": "hello"}) is False

    # Missing text
    assert handler.handle_update({"update_id": 120, "message": {"chat": {"id": 123}}}) is False

    # Text is not a string
    assert handler.handle_update({"update_id": 121, "message": {"chat": {"id": 123}, "text": 12345}}) is False

    # Empty text
    assert handler.handle_update({"update_id": 122, "message": {"chat": {"id": 123}, "text": ""}}) is False

    # Whitespace only text
    assert handler.handle_update({"update_id": 123, "message": {"chat": {"id": 123}, "text": "   "}}) is False

    # Missing chat
    assert handler.handle_update({"update_id": 124, "message": {"text": "/start"}}) is False

    # Missing chat id
    assert handler.handle_update({"update_id": 125, "message": {"chat": {}, "text": "/start"}}) is False

    # Nothing should have been sent
    assert len(sent_messages) == 0


# 9. Additional aliases and check command
def test_command_aliases(handler, alarm_mgr, sent_messages):
    # Add alias
    update = {
        "update_id": 126,
        "message": {
            "chat": {"id": 1438330510},
            "text": "add AAPL 250 ABOVE"
        }
    }
    handled = handler.handle_update(update)
    assert handled is True
    assert "Alarm Set Successfully" in sent_messages[1][1]

    # Check command
    sent_messages.clear()
    update = {
        "update_id": 127,
        "message": {
            "chat": {"id": 1438330510},
            "text": "/check"
        }
    }
    handled = handler.handle_update(update)
    assert handled is True
    assert len(sent_messages) == 1
    assert "monitored" in sent_messages[0][1].lower() or "checked" in sent_messages[0][1].lower()


def test_persistent_menu_button_triggers(handler, sent_messages):
    # Test "📈 Quick Quotes"
    update = {
        "update_id": 130,
        "message": {"chat": {"id": 1438330510}, "text": "📈 Quick Quotes"}
    }
    assert handler.handle_update(update) is True
    assert "Market Quick Quotes" in sent_messages[-1][1]

    # Test "➕ How to Set"
    update = {
        "update_id": 131,
        "message": {"chat": {"id": 1438330510}, "text": "➕ How to Set"}
    }
    assert handler.handle_update(update) is True
    assert "How to Set a Stock Alarm" in sent_messages[-1][1]


def test_callback_query_delete(handler, alarm_mgr, sent_messages):
    a = alarm_mgr.add_alarm(ticker="NVDA", target_price=135.0, direction="ABOVE")
    alarm_id = a["id"]
    assert len(alarm_mgr.get_alarms()) == 1

    callback_answers = []
    handler.answer_cb = lambda query_id, text: callback_answers.append((query_id, text))

    query = {
        "id": "cb_999",
        "data": f"del:{alarm_id}",
        "message": {
            "chat": {"id": 1438330510}
        }
    }
    assert handler.handle_callback_query(query) is True
    assert len(alarm_mgr.get_alarms()) == 0
    assert len(callback_answers) == 1
    assert "Deleted NVDA" in callback_answers[0][1]
    assert "Deleted alarm for <b>NVDA</b>" in sent_messages[-1][1]


def test_delete_all_by_ticker(handler, alarm_mgr, sent_messages):
    alarm_mgr.add_alarm(ticker="URA", target_price=50.0, direction="BELOW")
    alarm_mgr.add_alarm(ticker="URA", target_price=56.0, direction="BELOW")
    assert len(alarm_mgr.get_alarms()) == 2

    update = {
        "update_id": 132,
        "message": {"chat": {"id": 1438330510}, "text": "/del URA"}
    }
    assert handler.handle_update(update) is True
    assert len(alarm_mgr.get_alarms()) == 0
    assert "Deleted 2 alarms for <b>URA</b>" in sent_messages[-1][1]


def test_clear_command(handler, alarm_mgr, sent_messages):
    a1 = alarm_mgr.add_alarm(ticker="URA", target_price=50.0, direction="BELOW")
    alarm_mgr.add_alarm(ticker="AAPL", target_price=250.0, direction="ABOVE")
    alarm_mgr.mark_triggered(a1["id"], 49.0)

    update = {
        "update_id": 133,
        "message": {"chat": {"id": 1438330510}, "text": "/clear"}
    }
    assert handler.handle_update(update) is True
    assert len(alarm_mgr.get_alarms()) == 1
    assert "Cleared 1 triggered alarm" in sent_messages[-1][1]

    # Run again when none are triggered
    update2 = {
        "update_id": 134,
        "message": {"chat": {"id": 1438330510}, "text": "/clear"}
    }
    assert handler.handle_update(update2) is True
    assert "No triggered alarms to clear" in sent_messages[-1][1]


def test_set_cleans_triggered_alarms_for_same_ticker(handler, alarm_mgr, sent_messages):
    a1 = alarm_mgr.add_alarm(ticker="URA", target_price=50.0, direction="BELOW")
    alarm_mgr.mark_triggered(a1["id"], 48.0)
    assert len(alarm_mgr.get_alarms()) == 1

    # Now user sets a new alarm for URA
    update = {
        "update_id": 135,
        "message": {"chat": {"id": 1438330510}, "text": "URA 60 BELOW"}
    }
    assert handler.handle_update(update) is True
    alarms = alarm_mgr.get_alarms()
    assert len(alarms) == 1
    assert alarms[0]["target_price"] == 60.0
    assert alarms[0]["triggered"] is False


