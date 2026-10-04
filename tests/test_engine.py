import pytest
from unittest.mock import patch, MagicMock
from engine import evaluate_alarm, StockEngine, Quote

def test_evaluate_alarm_above():
    assert evaluate_alarm(current_price=250.50, target_price=250.00, direction="ABOVE") is True
    assert evaluate_alarm(current_price=250.00, target_price=250.00, direction="ABOVE") is True
    assert evaluate_alarm(current_price=249.99, target_price=250.00, direction="ABOVE") is False

def test_evaluate_alarm_below():
    assert evaluate_alarm(current_price=120.00, target_price=125.00, direction="BELOW") is True
    assert evaluate_alarm(current_price=125.00, target_price=125.00, direction="BELOW") is True
    assert evaluate_alarm(current_price=125.01, target_price=125.00, direction="BELOW") is False

def test_evaluate_alarm_case_insensitive():
    assert evaluate_alarm(current_price=100.0, target_price=90.0, direction="above") is True
    assert evaluate_alarm(current_price=80.0, target_price=90.0, direction="below") is True

@patch("engine.yf.Ticker")
def test_get_quote_success(mock_ticker_class):
    mock_ticker_instance = MagicMock()
    mock_ticker_instance.fast_info = {
        "last_price": 182.50,
        "previous_close": 180.00,
        "currency": "USD"
    }
    mock_ticker_class.return_value = mock_ticker_instance

    engine = StockEngine()
    quote = engine.get_quote("AAPL")

    assert quote.symbol == "AAPL"
    assert quote.price == 182.50
    assert quote.previous_close == 180.00
    assert quote.currency == "USD"
    assert quote.change_percent == round(((182.50 - 180.00) / 180.00) * 100, 2)
