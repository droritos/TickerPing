from dataclasses import dataclass
from typing import Optional
import yfinance as yf
import logging

logger = logging.getLogger(__name__)

@dataclass
class Quote:
    symbol: str
    price: float
    previous_close: float
    change_percent: float
    currency: str = "USD"

def evaluate_alarm(current_price: float, target_price: float, direction: str) -> bool:
    """
    Evaluates whether the current price meets the alarm condition.
    - 'ABOVE': current_price >= target_price
    - 'BELOW': current_price <= target_price
    """
    dir_clean = direction.strip().upper()
    if dir_clean == "ABOVE":
        return current_price >= target_price
    elif dir_clean == "BELOW":
        return current_price <= target_price
    return False

class StockEngine:
    def __init__(self):
        pass

    def get_quote(self, ticker: str) -> Optional[Quote]:
        clean_ticker = ticker.strip().upper()
        if not clean_ticker:
            return None

        try:
            t = yf.Ticker(clean_ticker)
            fast_info = getattr(t, "fast_info", None)

            price = None
            prev_close = None
            currency = "USD"

            if fast_info:
                price = fast_info.get("last_price") or fast_info.get("lastPrice")
                prev_close = fast_info.get("previous_close") or fast_info.get("previousClose")
                currency = fast_info.get("currency") or "USD"

            # Fallback 1: history
            if price is None:
                hist = t.history(period="2d")
                if not hist.empty:
                    price = float(hist["Close"].iloc[-1])
                    if len(hist) > 1:
                        prev_close = float(hist["Close"].iloc[-2])
                    else:
                        prev_close = price

            # Fallback 2: regular info
            if price is None:
                info = t.info or {}
                price = info.get("currentPrice") or info.get("regularMarketPrice")
                prev_close = info.get("regularMarketPreviousClose") or prev_close

            if price is None:
                logger.warning(f"Could not retrieve price for ticker: {clean_ticker}")
                return None

            price = round(float(price), 2)
            prev_close = round(float(prev_close), 2) if prev_close else price
            
            if prev_close and prev_close > 0:
                change_pct = round(((price - prev_close) / prev_close) * 100, 2)
            else:
                change_pct = 0.0

            return Quote(
                symbol=clean_ticker,
                price=price,
                previous_close=prev_close,
                change_percent=change_pct,
                currency=currency
            )
        except Exception as e:
            logger.error(f"Error fetching quote for {clean_ticker}: {e}")
            return None
