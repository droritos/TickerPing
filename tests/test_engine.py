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

def test_engine_get_news_success():
    engine = StockEngine()
    mock_ticker = MagicMock()
    mock_ticker.news = [
        {
            "title": "Nvidia Announces Blackwell Ultra",
            "publisher": "Reuters",
            "link": "https://finance.yahoo.com/news/nvidia-blackwell",
            "providerPublishTime": 1728300000
        },
        {
            "title": "Chip Stocks Surge",
            "publisher": "Bloomberg",
            "link": "https://finance.yahoo.com/news/chip-stocks",
            "providerPublishTime": 1728290000
        }
    ]
    with patch("yfinance.Ticker", return_value=mock_ticker):
        news = engine.get_news("NVDA", limit=2)
        assert len(news) == 2
        assert news[0]["title"] == "Nvidia Announces Blackwell Ultra"
        assert news[0]["publisher"] == "Reuters"
        assert "link" in news[0]

def test_engine_get_news_empty():
    engine = StockEngine()
    mock_ticker = MagicMock()
    mock_ticker.news = []
    with patch("yfinance.Ticker", return_value=mock_ticker):
        news = engine.get_news("UNKNOWN")
        assert news == []

def test_engine_get_earnings_info_success():
    engine = StockEngine()
    mock_ticker = MagicMock()
    from datetime import datetime, timedelta
    future_date = datetime.now() + timedelta(days=20)
    mock_ticker.calendar = {
        "Earnings Date": [future_date.date()],
        "Earnings Average": 0.85
    }
    with patch("yfinance.Ticker", return_value=mock_ticker):
        info = engine.get_earnings_info("AAPL")
        assert info is not None
        assert info["days_until"] >= 19
        assert info["date_str"] == future_date.strftime("%b %d, %Y")
        assert info["eps_estimate"] == 0.85

def test_engine_get_earnings_info_none():
    engine = StockEngine()
    mock_ticker = MagicMock()
    mock_ticker.calendar = None
    with patch("yfinance.Ticker", return_value=mock_ticker):
        info = engine.get_earnings_info("NOEARN")
        assert info is None

def test_engine_get_earnings_info_dataframe():
    engine = StockEngine()
    mock_ticker = MagicMock()
    from datetime import datetime, timedelta
    future_date = datetime.now() + timedelta(days=10)
    mock_df = MagicMock()
    mock_df.empty = False
    mock_df.to_dict.return_value = {
        0: {
            "Earnings Date": future_date.date(),
            "Earnings Average": 1.25
        }
    }
    mock_ticker.calendar = mock_df
    with patch("yfinance.Ticker", return_value=mock_ticker):
        info = engine.get_earnings_info("MSFT")
        assert info is not None
        assert info["days_until"] >= 9
        assert info["eps_estimate"] == 1.25

def test_engine_get_news_exception():
    engine = StockEngine()
    with patch("yfinance.Ticker", side_effect=RuntimeError("API error")):
        news = engine.get_news("FAIL")
        assert news == []

def test_engine_get_earnings_info_exception():
    engine = StockEngine()
    with patch("yfinance.Ticker", side_effect=RuntimeError("API error")):
        info = engine.get_earnings_info("FAIL")
        assert info is None

def test_engine_empty_tickers():
    engine = StockEngine()
    assert engine.get_news("") == []
    assert engine.get_earnings_info("   ") is None


