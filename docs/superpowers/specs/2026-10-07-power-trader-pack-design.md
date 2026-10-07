# Specification: Power Trader Pack (1-Tap Re-Arm, Live News & Earnings Countdown)

**Date:** 2026-10-07  
**Status:** Approved  
**Author:** droritos & Antigravity  
**Repository:** [droritos/TickerPing](https://github.com/droritos/TickerPing)

---

## 1. Overview & Goals

The **Power Trader Pack** upgrades `TickerPing` with three high-impact, frictionless trading tools:
1. **Interactive 1-Tap Re-Arm Buttons on Price Alerts:** When an alarm triggers, inline buttons provide instantaneous `+5%` (ABOVE) and `-5%` (BELOW) targets with single-tap creation.
2. **Live Financial News (`/news <ticker>` or 1-tap):** Displays the top 3 live headlines from top financial media (Reuters, Bloomberg, CNBC) with direct links.
3. **Earnings Countdown (`/earnings <ticker>`):** Reports the next quarterly earnings release date, estimated EPS, and a human-readable countdown in days.

All features are 100% free, require **zero new API keys**, and run directly within the existing GitHub Actions runner.

---

## 2. User Experience & Telegram Interface

### 2.1 Triggered Price Alert with 1-Tap Action Buttons
When a price alarm triggers, the notification chart is sent with interactive inline buttons:

```
🚨 STOCK ALERT: GOOGL Target Met!
━━━━━━━━━━━━━━━━━━━━
💰 Current Price: $351.20
🎯 Triggered Target: ABOVE $350.00 (+2.40%)
🕒 Time: 2026-10-07 15:42:00
📝 Note: Dip buy hit
```
**Inline Keyboard:**
| Button 1 | Button 2 |
| :--- | :--- |
| `📈 Next +5% ($368.76)` | `📉 Dip -5% ($333.64)` |
| `📰 Top News` | `🌐 View on Yahoo` |

* **Tap Action `[📈 Next +5%]`:** Instantly registers `GOOGL 368.76 ABOVE`, shows Telegram toast *"✅ New alarm set for GOOGL at $368.76"*, sends confirmation message, and syncs to git.
* **Tap Action `[📉 Dip -5%]`:** Instantly registers `GOOGL 333.64 BELOW`, shows toast, and syncs to git.
* **Tap Action `[📰 Top News]`:** Triggers the news handler for that ticker.

### 2.2 Live Stock News (`/news <ticker>`)
Accessible via text command `/news <ticker>` (e.g. `/news TSLA`) or shorthand `news TSLA`:

```
📰 Top News for TSLA:
━━━━━━━━━━━━━━━━━━━━
1. Tesla Robotaxi Event Preview: What Wall Street Expects
   Reuters • 2h ago
   🔗 https://finance.yahoo.com/...

2. EV Delivery Numbers Surpass Quarterly Forecasts
   Bloomberg • 4h ago
   🔗 https://finance.yahoo.com/...

3. Analysts Upgrade Price Target Ahead of Earnings
   CNBC • 7h ago
   🔗 https://finance.yahoo.com/...
```

### 2.3 Earnings Date Countdown (`/earnings <ticker>`)
Accessible via text command `/earnings <ticker>` (e.g. `/earnings NVDA`) or shorthand `earnings NVDA`:

```
📅 Earnings Calendar: NVDA
━━━━━━━━━━━━━━━━━━━━
• Next Report Date: Nov 20, 2026
• Countdown: In 44 days ⏳
• Estimated EPS: $0.75
• Session: After Market Close
```

---

## 3. Architecture & Component Changes

```mermaid
flowchart TD
    User["📱 User (Telegram)"] --> Handler["TelegramCommandHandler"]
    
    subgraph Commands & Callbacks
        Handler -->|"/news AAPL" or "news:AAPL"| NewsCmd["handle_news()"]
        Handler -->|"/earnings AAPL"| EarnCmd["handle_earnings()"]
        Handler -->|"set:AAPL:262.50:ABOVE"| ReArmCmd["handle_rearm()"]
    end
    
    subgraph Data Layer
        NewsCmd --> EngineNews["StockEngine.get_news()"]
        EarnCmd --> EngineEarn["StockEngine.get_earnings_info()"]
        ReArmCmd --> AlarmMgr["AlarmManager.add_alarm()"]
    end
    
    EngineNews --> YF["yfinance.Ticker.news"]
    EngineEarn --> YFCal["yfinance.Ticker.calendar"]
    AlarmMgr --> Storage["alarms.json & Git Sync"]
```

### 3.1 `engine.py` (Stock Engine Upgrades)
Add two methods to `StockEngine`:
1. `get_news(ticker: str, limit: int = 3) -> List[Dict[str, str]]`:
   - Calls `yfinance.Ticker(ticker).news`.
   - Extracts `title`, `publisher`, `link`, `providerPublishTime` (converted to human "Xh ago" or ISO date).
   - Returns empty list if no news found or on error.
2. `get_earnings_info(ticker: str) -> Optional[Dict[str, Any]]`:
   - Inspects `yfinance.Ticker(ticker).calendar` or `earnings_dates`.
   - Parses the next upcoming report date, calculates days difference (`days_until = (earnings_date - today).days`), and extracts estimated EPS if present.
   - Returns `None` if no upcoming earnings date is published.

### 3.2 `notifier.py` (Alert Keyboard Upgrades)
In `TelegramNotifier.send_alert()`:
- Given `current_price` and `ticker`:
  - Calculate `up_price = round(current_price * 1.05, 2)`
  - Calculate `down_price = round(current_price * 0.95, 2)`
- Construct inline keyboard:
  ```python
  reply_markup = {
      "inline_keyboard": [
          [
              {"text": f"📈 +5% (${up_price:.2f})", "callback_data": f"rearm:{ticker}:{up_price:.2f}:ABOVE"},
              {"text": f"📉 -5% (${down_price:.2f})", "callback_data": f"rearm:{ticker}:{down_price:.2f}:BELOW"}
          ],
          [
              {"text": "📰 Top News", "callback_data": f"news:{ticker}"},
              {"text": f"🌐 {ticker} on Yahoo", "url": f"https://finance.yahoo.com/quote/{ticker}"}
          ]
      ]
  }
  ```

### 3.3 `telegram_command_handler.py` (Command & Callback Routing)
1. In `handle_update`:
   - Support `/news <ticker>` and `news <ticker>`.
   - Support `/earnings <ticker>` and `earnings <ticker>`.
2. In `handle_callback_query`:
   - Support `rearm:<ticker>:<price>:<direction>`:
     - Parses ticker, price, direction.
     - Calls `self.alarm_manager.add_alarm(ticker, float(price), direction)`.
     - Calls `self.answer_cb(callback_id, f"✅ Re-armed {ticker} for ${price} ({direction})")`.
     - Sends confirmation message with `MAIN_MENU_KEYBOARD`.
   - Support `news:<ticker>`:
     - Calls `self.answer_cb(callback_id, f"Fetching news for {ticker}...")`.
     - Calls `self.handle_news(chat_id, ticker)`.
3. In `handle_news(chat_id, ticker)`:
   - Fetches news from `engine.get_news(ticker)`.
   - Formats nicely with HTML links `<a href="...">...</a>`.
   - Sends to `chat_id`.
4. In `handle_earnings(chat_id, ticker)`:
   - Fetches earnings info from `engine.get_earnings_info(ticker)`.
   - Formats report date, countdown days, and EPS.
   - Sends to `chat_id`.

---

## 4. Error Handling & Edge Cases

| Scenario | Behavior |
| :--- | :--- |
| **Ticker not found or invalid symbol** | Responds: `⚠️ Could not find ticker symbol 'XYZ'. Please verify spelling.` |
| **No news returned by Yahoo Finance** | Responds: `📰 No recent headlines found for <b>XYZ</b>.` |
| **Earnings date unannounced / penny stock** | Responds: `📅 No upcoming earnings date announced yet for <b>XYZ</b>.` |
| **Re-arm button tapped multiple times** | Re-arms target and auto-cleans any old triggered alerts for that ticker. |
| **Network timeout / Yahoo rate limit** | Graceful log warning; sends friendly user message without crashing runner. |

---

## 5. Verification & Testing Plan

1. **Unit Tests for `engine.py`:**
   - Test `get_news` parsing valid yfinance output, mock data, and empty responses.
   - Test `get_earnings_info` parsing calendar dict/dataframe and missing calendar handling.
2. **Unit Tests for `notifier.py`:**
   - Verify `send_alert` generates `+5%` and `-5%` re-arm callback buttons and news button.
3. **Unit Tests for `telegram_command_handler.py`:**
   - Test `/news AAPL` sends formatted news items.
   - Test `/earnings TSLA` sends formatted earnings countdown.
   - Test callback query `rearm:AAPL:260.00:ABOVE` creates alarm in `alarm_manager`.
   - Test callback query `news:NVDA` invokes news handler.
   - Test missing ticker arguments (`/news`, `/earnings`).
4. **Integration Test Suite:**
   - Run full `pytest` suite ensuring 100% pass rate (63+ tests).
