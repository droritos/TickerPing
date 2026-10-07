from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import date, datetime
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

    def get_news(self, ticker: str, limit: int = 3) -> List[Dict[str, str]]:
        clean_ticker = ticker.strip().upper()
        if not clean_ticker:
            return []

        try:
            t = yf.Ticker(clean_ticker)
            raw_news = getattr(t, "news", []) or []
            results = []
            for item in raw_news[:limit]:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title", "") or "").strip()
                link = str(item.get("link", "") or "").strip()
                publisher = str(item.get("publisher", "Yahoo Finance") or "").strip()
                if not publisher:
                    publisher = "Yahoo Finance"
                if title:
                    results.append({
                        "title": title,
                        "link": link,
                        "publisher": publisher
                    })
            return results
        except Exception as e:
            logger.warning(f"Error fetching news for {clean_ticker}: {e}")
            return []

    def get_earnings_info(self, ticker: str) -> Optional[Dict[str, Any]]:
        clean_ticker = ticker.strip().upper()
        if not clean_ticker:
            return None

        try:
            t = yf.Ticker(clean_ticker)
            cal = getattr(t, "calendar", None)
            if cal is None:
                return None
            if hasattr(cal, "empty") and cal.empty:
                return None
            if isinstance(cal, dict) and not cal:
                return None

            # yfinance returns calendar as dict or DataFrame
            earnings_date = None
            eps_estimate = None

            if isinstance(cal, dict):
                dates = cal.get("Earnings Date") or cal.get("earningsDate")
                if dates:
                    earnings_date = dates[0] if isinstance(dates, (list, tuple)) else dates
                eps_estimate = cal.get("Earnings Average") or cal.get("earningsAverage")
            elif hasattr(cal, "to_dict"):
                cal_dict = cal.to_dict()
                for key, val_map in cal_dict.items():
                    k_str = str(key).lower()
                    if "earnings" in k_str and "date" in k_str:
                        if isinstance(val_map, dict):
                            vals = list(val_map.values())
                            if vals:
                                earnings_date = vals[0]
                        else:
                            earnings_date = val_map
                    if "earnings" in k_str and "average" in k_str:
                        if isinstance(val_map, dict):
                            vals = list(val_map.values())
                            if vals:
                                eps_estimate = vals[0]
                        else:
                            eps_estimate = val_map
                    if isinstance(val_map, dict):
                        for inner_key, inner_val in val_map.items():
                            ik_str = str(inner_key).lower()
                            if "earnings" in ik_str and "date" in ik_str and earnings_date is None:
                                earnings_date = inner_val
                            if "earnings" in ik_str and "average" in ik_str and eps_estimate is None:
                                eps_estimate = inner_val

            if isinstance(earnings_date, (list, tuple)) and len(earnings_date) > 0:
                earnings_date = earnings_date[0]

            if not earnings_date or (hasattr(earnings_date, "__str__") and str(earnings_date) == "NaT"):
                return None

            if isinstance(earnings_date, str):
                try:
                    dt = datetime.fromisoformat(earnings_date).date()
                except ValueError:
                    dt = datetime.strptime(earnings_date[:10], "%Y-%m-%d").date()
            elif isinstance(earnings_date, datetime):
                dt = earnings_date.date()
            elif isinstance(earnings_date, date):
                dt = earnings_date
            elif hasattr(earnings_date, "date") and callable(earnings_date.date):
                dt = earnings_date.date()
            else:
                return None

            today = date.today()
            days_until = (dt - today).days

            parsed_eps = None
            if eps_estimate is not None:
                try:
                    import math
                    val = float(eps_estimate)
                    if not math.isnan(val):
                        parsed_eps = round(val, 2)
                except (ValueError, TypeError):
                    parsed_eps = None

            return {
                "date_str": dt.strftime("%b %d, %Y"),
                "days_until": days_until,
                "eps_estimate": parsed_eps
            }
        except Exception as e:
            logger.warning(f"Error fetching earnings info for {clean_ticker}: {e}")
            return None

