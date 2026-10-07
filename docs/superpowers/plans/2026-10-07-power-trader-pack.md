# Power Trader Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Power Trader Pack for TickerPing: 1-Tap Re-Arm buttons on triggered alerts (+5% / -5%), live stock news via `/news <ticker>` and alert button, and quarterly earnings countdown via `/earnings <ticker>`.

**Architecture:** Extend `StockEngine` with `get_news` and `get_earnings_info` using Yahoo Finance; enhance `TelegramNotifier.send_alert` to attach interactive Re-Arm and News inline buttons; and route new commands and callback queries through `TelegramCommandHandler` with automated tests and git persistence.

**Architecture Diagram:**

```mermaid
flowchart TD
    User["📱 Telegram User"] --> Handler["TelegramCommandHandler"]
    
    subgraph Routing
        Handler -->|"/news AAPL" or "news:AAPL"| NewsCmd["handle_news()"]
        Handler -->|"/earnings AAPL"| EarnCmd["handle_earnings()"]
        Handler -->|"rearm:AAPL:260:ABOVE"| ReArmCmd["handle_rearm()"]
    end
    
    subgraph Engine & Storage
        NewsCmd --> Engine["StockEngine.get_news()"]
        EarnCmd --> EngineCal["StockEngine.get_earnings_info()"]
        ReArmCmd --> AlarmMgr["AlarmManager.add_alarm()"]
    end

    subgraph Notifier
        AlarmRunner["cloud_runner.py"] --> Notifier["TelegramNotifier.send_alert()"]
        Notifier --> AlertButtons["Alert with Re-Arm (+5%/-5%) & News Buttons"]
    end
```

**Tech Stack:** Python 3.12, yfinance, requests, pytest.

## Global Constraints

- Exclusively use `droritos` (`droritos@users.noreply.github.com`) for all git commits, authors, and GitHub pushes.
- Never use `Dror-Vizel`, `Dror Vizel`, or `dror.v@superplay.co`.
- 100% free with zero additional external API keys or paid services.
- Maintain existing 63 passing unit tests across all modifications.

---

### Task 1: StockEngine Data Methods (`engine.py`)

**Files:**
- Modify: `engine.py:1-120`
- Test: `tests/test_engine.py`

**Interfaces:**
- Produces:
  - `StockEngine.get_news(ticker: str, limit: int = 3) -> List[Dict[str, str]]`
  - `StockEngine.get_earnings_info(ticker: str) -> Optional[Dict[str, Any]]`

- [ ] **Step 1: Write the failing tests in `tests/test_engine.py`**

```python
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
    # Mock calendar with future earnings date
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_engine.py -k "test_engine_get_news or test_engine_get_earnings" -v`  
Expected: FAIL with `AttributeError: 'StockEngine' object has no attribute 'get_news'`

- [ ] **Step 3: Implement `get_news` and `get_earnings_info` in `engine.py`**

```python
    def get_news(self, ticker: str, limit: int = 3) -> List[Dict[str, str]]:
        clean_ticker = ticker.strip().upper()
        try:
            t = yf.Ticker(clean_ticker)
            raw_news = getattr(t, "news", []) or []
            results = []
            for item in raw_news[:limit]:
                title = item.get("title", "").strip()
                link = item.get("link", "").strip()
                publisher = item.get("publisher", "Yahoo Finance").strip()
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
        try:
            t = yf.Ticker(clean_ticker)
            cal = getattr(t, "calendar", None)
            if not cal:
                return None
            
            # yfinance returns calendar as dict or DataFrame
            earnings_date = None
            eps_estimate = None
            
            if isinstance(cal, dict):
                dates = cal.get("Earnings Date") or cal.get("earningsDate")
                if dates:
                    earnings_date = dates[0] if isinstance(dates, list) else dates
                eps_estimate = cal.get("Earnings Average") or cal.get("earningsAverage")
            elif hasattr(cal, "to_dict"):
                cal_dict = cal.to_dict()
                # DataFrame format inspection
                for key in cal_dict:
                    k_str = str(key).lower()
                    if "earnings" in k_str and "date" in k_str:
                        vals = list(cal_dict[key].values())
                        if vals:
                            earnings_date = vals[0]
                    if "earnings" in k_str and "average" in k_str:
                        vals = list(cal_dict[key].values())
                        if vals:
                            eps_estimate = vals[0]

            if not earnings_date:
                return None

            from datetime import date, datetime
            if isinstance(earnings_date, str):
                try:
                    dt = datetime.fromisoformat(earnings_date).date()
                except ValueError:
                    dt = datetime.strptime(earnings_date, "%Y-%m-%d").date()
            elif isinstance(earnings_date, datetime):
                dt = earnings_date.date()
            elif isinstance(earnings_date, date):
                dt = earnings_date
            else:
                return None

            today = date.today()
            days_until = (dt - today).days

            return {
                "date_str": dt.strftime("%b %d, %Y"),
                "days_until": days_until,
                "eps_estimate": round(float(eps_estimate), 2) if eps_estimate is not None else None
            }
        except Exception as e:
            logger.warning(f"Error fetching earnings info for {clean_ticker}: {e}")
            return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_engine.py -v`  
Expected: PASS (all tests passing)

- [ ] **Step 5: Commit**

```bash
git add engine.py tests/test_engine.py
git commit --author="droritos <droritos@users.noreply.github.com>" -m "feat(engine): add get_news and get_earnings_info data methods"
```

---

### Task 2: 1-Tap Re-Arm & News Buttons in Notifier (`notifier.py`)

**Files:**
- Modify: `notifier.py:35-120`
- Test: `tests/test_notifier.py`

**Interfaces:**
- Consumes: `ticker`, `current_price`
- Produces: `TelegramNotifier.send_alert()` with inline keyboard containing:
  - `📈 +5% ($...)` -> `rearm:<ticker>:<up_price>:ABOVE`
  - `📉 -5% ($...)` -> `rearm:<ticker>:<down_price>:BELOW`
  - `📰 Top News` -> `news:<ticker>`
  - `🌐 View on Yahoo` -> URL

- [ ] **Step 1: Write the failing test in `tests/test_notifier.py`**

```python
def test_send_alert_includes_rearm_and_news_buttons():
    notifier = TelegramNotifier(bot_token="test_tok", chat_id="12345")
    with patch("requests.post") as mock_post, patch("chart.generate_stock_chart", return_value=None):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"ok": True}

        notifier.send_alert(
            ticker="GOOGL",
            current_price=350.0,
            target_price=340.0,
            direction="ABOVE",
            change_percent=2.5,
            currency="USD",
            note=""
        )

        assert mock_post.called
        call_kwargs = mock_post.call_args[1]
        data = call_kwargs.get("data", {})
        assert "reply_markup" in data
        import json
        markup = json.loads(data["reply_markup"])
        keyboard = markup.get("inline_keyboard", [])
        assert len(keyboard) == 2
        # Row 1: +5% and -5%
        assert "📈 +5%" in keyboard[0][0]["text"]
        assert keyboard[0][0]["callback_data"] == "rearm:GOOGL:367.50:ABOVE"
        assert "📉 -5%" in keyboard[0][1]["text"]
        assert keyboard[0][1]["callback_data"] == "rearm:GOOGL:332.50:BELOW"
        # Row 2: News and Yahoo chart
        assert keyboard[1][0]["text"] == "📰 Top News"
        assert keyboard[1][0]["callback_data"] == "news:GOOGL"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_notifier.py -k "test_send_alert_includes_rearm_and_news_buttons" -v`  
Expected: FAIL (callback_data is currently just Yahoo link)

- [ ] **Step 3: Update `notifier.py` to build the new 1-tap inline keyboard**

In `TelegramNotifier.send_alert()`:
```python
        # Calculate re-arm price levels
        up_price = round(current_price * 1.05, 2)
        down_price = round(current_price * 0.95, 2)

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

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_notifier.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add notifier.py tests/test_notifier.py
git commit --author="droritos <droritos@users.noreply.github.com>" -m "feat(notifier): add 1-tap re-arm and news buttons to alert notifications"
```

---

### Task 3: Telegram Command & Callback Routing (`telegram_command_handler.py`)

**Files:**
- Modify: `telegram_command_handler.py`
- Test: `tests/test_telegram_command_handler.py`

**Interfaces:**
- Consumes: `StockEngine.get_news`, `StockEngine.get_earnings_info`, `AlarmManager.add_alarm`
- Produces:
  - Command `/news <ticker>` and `news <ticker>`
  - Command `/earnings <ticker>` and `earnings <ticker>`
  - Callback queries: `rearm:<ticker>:<price>:<direction>` and `news:<ticker>`

- [ ] **Step 1: Write the failing tests in `tests/test_telegram_command_handler.py`**

```python
def test_news_command_with_ticker(handler, sent_messages):
    handler.engine.get_news = MagicMock(return_value=[
        {"title": "Tech Rally Leads S&P Higher", "publisher": "Reuters", "link": "https://reuters.com/1"},
        {"title": "Apple Previews AI Features", "publisher": "CNBC", "link": "https://cnbc.com/2"}
    ])

    update = {
        "update_id": 201,
        "message": {"chat": {"id": 1438330510}, "text": "/news AAPL"}
    }
    assert handler.handle_update(update) is True
    assert len(sent_messages) == 1
    assert "Top Headlines for AAPL" in sent_messages[0][1]
    assert "Tech Rally Leads S&P Higher" in sent_messages[0][1]
    assert "https://reuters.com/1" in sent_messages[0][1]

def test_news_command_empty_news(handler, sent_messages):
    handler.engine.get_news = MagicMock(return_value=[])
    update = {
        "update_id": 202,
        "message": {"chat": {"id": 1438330510}, "text": "/news UNK"}
    }
    assert handler.handle_update(update) is True
    assert "No recent headlines found for <b>UNK</b>" in sent_messages[0][1]

def test_earnings_command_with_ticker(handler, sent_messages):
    handler.engine.get_earnings_info = MagicMock(return_value={
        "date_str": "Oct 24, 2026",
        "days_until": 17,
        "eps_estimate": 0.85
    })
    update = {
        "update_id": 203,
        "message": {"chat": {"id": 1438330510}, "text": "/earnings TSLA"}
    }
    assert handler.handle_update(update) is True
    assert "Earnings Report: TSLA" in sent_messages[0][1]
    assert "Oct 24, 2026" in sent_messages[0][1]
    assert "17 days" in sent_messages[0][1]
    assert "0.85" in sent_messages[0][1]

def test_earnings_command_no_calendar(handler, sent_messages):
    handler.engine.get_earnings_info = MagicMock(return_value=None)
    update = {
        "update_id": 204,
        "message": {"chat": {"id": 1438330510}, "text": "/earnings NOEARN"}
    }
    assert handler.handle_update(update) is True
    assert "No upcoming earnings date announced yet for <b>NOEARN</b>" in sent_messages[0][1]

def test_callback_query_rearm(handler, alarm_mgr, sent_messages):
    callback_answers = []
    handler.answer_cb = lambda query_id, text: callback_answers.append((query_id, text))

    query = {
        "id": "cb_rearm_1",
        "data": "rearm:GOOGL:368.50:ABOVE",
        "message": {"chat": {"id": 1438330510}}
    }
    assert handler.handle_callback_query(query) is True
    alarms = alarm_mgr.get_alarms()
    assert len(alarms) == 1
    assert alarms[0]["ticker"] == "GOOGL"
    assert alarms[0]["target_price"] == 368.50
    assert alarms[0]["direction"] == "ABOVE"
    assert len(callback_answers) == 1
    assert "Re-armed GOOGL for $368.50" in callback_answers[0][1]
    assert "New alarm set for <b>GOOGL</b>" in sent_messages[-1][1]

def test_callback_query_news(handler, sent_messages):
    handler.engine.get_news = MagicMock(return_value=[
        {"title": "Breaking Tech Update", "publisher": "Bloomberg", "link": "https://bloomberg.com/1"}
    ])
    callback_answers = []
    handler.answer_cb = lambda query_id, text: callback_answers.append((query_id, text))

    query = {
        "id": "cb_news_1",
        "data": "news:NVDA",
        "message": {"chat": {"id": 1438330510}}
    }
    assert handler.handle_callback_query(query) is True
    assert len(sent_messages) == 1
    assert "Top Headlines for NVDA" in sent_messages[0][1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_telegram_command_handler.py -k "test_news or test_earnings or test_callback_query_rearm" -v`  
Expected: FAIL

- [ ] **Step 3: Implement routing and handlers in `telegram_command_handler.py`**

1. In `handle_update`:
```python
        elif cmd in ("/news", "news"):
            if len(tokens) > 1:
                self.handle_news(chat_id, tokens[1])
            else:
                self._send(chat_id, "⚠️ Specify a stock ticker, e.g.: <code>/news NVDA</code>", reply_markup=MAIN_MENU_KEYBOARD)
        elif cmd in ("/earnings", "earnings"):
            if len(tokens) > 1:
                self.handle_earnings(chat_id, tokens[1])
            else:
                self._send(chat_id, "⚠️ Specify a stock ticker, e.g.: <code>/earnings TSLA</code>", reply_markup=MAIN_MENU_KEYBOARD)
```

2. In `handle_callback_query`:
```python
        if data.startswith("rearm:"):
            # format: rearm:TICKER:PRICE:DIRECTION
            parts = data.split(":")
            if len(parts) == 4:
                ticker = parts[1].upper()
                target_price = float(parts[2])
                direction = parts[3].upper()

                # Clean up any previously triggered alarms for this ticker
                for old in self.alarm_manager.get_alarms():
                    if old.get("ticker", "").upper() == ticker and old.get("triggered", False):
                        self.alarm_manager.delete_alarm(old["id"])

                alarm = self.alarm_manager.add_alarm(
                    ticker=ticker,
                    target_price=target_price,
                    direction=direction,
                    note="1-tap re-arm"
                )
                self.answer_cb(callback_id, f"✅ Re-armed {ticker} for ${target_price:.2f} ({direction})")
                self._send(
                    chat_id,
                    f"✅ <b>New alarm set for {ticker}!</b>\n"
                    f"🎯 <b>Target:</b> {direction} ${target_price:.2f}\n"
                    f"🆔 <b>ID:</b> <code>{alarm['id']}</code>",
                    reply_markup=MAIN_MENU_KEYBOARD
                )
                return True

        if data.startswith("news:"):
            parts = data.split(":")
            if len(parts) == 2:
                ticker = parts[1].upper()
                self.answer_cb(callback_id, f"Loading headlines for {ticker}...")
                self.handle_news(chat_id, ticker)
                return True
```

3. Implement `handle_news(self, chat_id: str, ticker: str)`:
```python
    def handle_news(self, chat_id: str, ticker: str) -> None:
        """Fetch and format top news articles for ticker."""
        clean = ticker.strip().upper()
        news = self.engine.get_news(clean, limit=3)
        if not news:
            self._send(chat_id, f"📰 No recent headlines found for <b>{clean}</b>.", reply_markup=MAIN_MENU_KEYBOARD)
            return

        lines = [f"📰 <b>Top Headlines for {clean}:</b>", "━━━━━━━━━━━━━━━━━━━━"]
        for idx, item in enumerate(news, 1):
            title = item.get("title", "")
            publisher = item.get("publisher", "Yahoo Finance")
            link = item.get("link", "")
            if link:
                lines.append(f"{idx}. <a href=\"{link}\">{title}</a>\n   <i>{publisher}</i>\n")
            else:
                lines.append(f"{idx}. {title}\n   <i>{publisher}</i>\n")

        self._send(chat_id, "\n".join(lines), reply_markup=MAIN_MENU_KEYBOARD)
```

4. Implement `handle_earnings(self, chat_id: str, ticker: str)`:
```python
    def handle_earnings(self, chat_id: str, ticker: str) -> None:
        """Fetch and format next earnings report countdown for ticker."""
        clean = ticker.strip().upper()
        info = self.engine.get_earnings_info(clean)
        if not info:
            self._send(chat_id, f"📅 No upcoming earnings date announced yet for <b>{clean}</b>.", reply_markup=MAIN_MENU_KEYBOARD)
            return

        days = info.get("days_until", 0)
        date_str = info.get("date_str", "TBD")
        eps = info.get("eps_estimate")

        countdown_text = f"In <b>{days} days</b> ⏳" if days > 0 else "<b>Today!</b> 🚨" if days == 0 else f"{abs(days)} days ago"

        lines = [
            f"📅 <b>Earnings Report: {clean}</b>",
            "━━━━━━━━━━━━━━━━━━━━",
            f"• <b>Report Date:</b> {date_str}",
            f"• <b>Countdown:</b> {countdown_text}"
        ]
        if eps is not None:
            lines.append(f"• <b>Estimated EPS:</b> ${eps:.2f}")

        self._send(chat_id, "\n".join(lines), reply_markup=MAIN_MENU_KEYBOARD)
```

5. Update `handle_help` to list `/news` and `/earnings`:
Add lines to help text:
- `• <code>/news &lt;ticker&gt;</code> - Top financial headlines`
- `• <code>/earnings &lt;ticker&gt;</code> - Upcoming quarterly report countdown`

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_telegram_command_handler.py -v`  
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest`  
Expected: PASS with 69+ tests passing

- [ ] **Step 6: Commit & Push**

```bash
git add telegram_command_handler.py tests/test_telegram_command_handler.py
git commit --author="droritos <droritos@users.noreply.github.com>" -m "feat(telegram): add /news, /earnings commands and 1-tap re-arm callback handlers"
git push origin main
```
