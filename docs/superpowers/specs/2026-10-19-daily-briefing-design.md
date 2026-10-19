# Design Spec: Daily Morning Briefing for TickerPing (Lainey)

**Date:** 2026-10-19  
**Status:** Approved  
**Author:** droritos & Antigravity  

---

## 1. Overview & Goals
Provide a personalized daily morning briefing delivered by Lainey to Telegram every morning at 08:30 Israel time (`Asia/Jerusalem`), as well as on-demand anytime the user sends `/briefing` (or `/morning`).

The briefing aggregates:
1. **Greeting & Date:** Friendly greeting from Lainey with the current date.
2. **Today's Reminders:** All pending reminders scheduled for today from `ReminderManager`. If none, shows a celebratory "No reminders today 🎉".
3. **Market Pulse:** Benchmark indices (`SPY` and `QQQ`) showing current/closing prices and percentage change. If markets are closed (e.g. weekends), display a clear `[Market Closed]` badge.
4. **Tracked Stock Alarms:** Status of all active alarms from `AlarmManager`, showing ticker, current price, day's change %, and distance to target price.
5. **Daily Motivation:** A short positive closing thought.

---

## 2. Architecture & Components

```
                          +-------------------------+
                          |   Telegram Chat User    |
                          +------------+------------+
                                       |
                   /briefing command   |
                                       v
+------------------+       +-----------+-------------+
|   cloud_runner   | ----> | telegram_command_handler|
|  (08:30 daily    |       +-----------+-------------+
|   auto-eval)     |                   |
+--------+---------+                   |
         |                             |
         +-------------+---------------+
                       |
                       v
        +--------------+---------------+
        |      briefing_manager.py     |
        |  (build_daily_briefing(...)) |
        +--------------+---------------+
                       |
        +--------------+--------------+---------------+
        |                             |               |
        v                             v               v
+-------+----------+        +---------+-----+   +-----+------+
| reminders_manager|        | alarms_manager|   |   engine   |
| (today's due)    |        | (active alerts|   |  (quotes)  |
+------------------+        +---------------+   +------------+
```

### 2.1 `briefing_manager.py` (New Module)
Pure aggregation and formatting engine.
- Function:
  ```python
  def build_daily_briefing(
      reminder_manager: ReminderManager,
      alarm_manager: AlarmManager,
      engine: StockEngine,
      tz: Optional[ZoneInfo] = None,
      now: Optional[datetime] = None
  ) -> str
  ```
- **Reminders Section:**
  - Calls `reminder_manager.get_reminders(include_completed=False)`.
  - Normalizes `due_at` into `tz`.
  - Identifies items where `due_dt.date() == now.date()`.
  - Formats as: `• [HH:MM] Title` (or `• Title` if untimed).
  - If no items today: `🎉 No reminders scheduled for today! Enjoy your day.`
- **Market Pulse Section:**
  - Queries `engine.get_quote("SPY")` and `engine.get_quote("QQQ")`.
  - Determines if regular market hours or closed.
  - Displays formatted price, change $, change %, and direction emoji (`🟢` / `🔴`).
  - If a quote fails or times out, displays `SPY: Price unavailable`.
- **Tracked Alarms Section:**
  - Calls `alarm_manager.get_alarms()`.
  - Extracts active (untriggered) alarms.
  - Queries current price for each unique ticker.
  - Calculates distance to target:
    - If `target > current`: `+X.X% away`
    - If `target < current`: `-X.X% away`
  - If no alarms exist: `No active price alarms set.`
- **HTML Escaping:**
  - All dynamic titles, notes, and tickers are escaped with `html.escape`.

### 2.2 `cloud_runner.py`
- On each loop cycle (default 60s):
  - Calls `self.evaluate_daily_briefing()`.
  - In `evaluate_daily_briefing()`:
    - Get current time in `get_bot_timezone()`.
    - Check if `now.hour >= 8 and (now.hour > 8 or now.minute >= 30)`.
    - Check `last_briefing_date = self.state_manager.get("last_briefing_date")`.
    - If `last_briefing_date != now.strftime("%Y-%m-%d")`:
      - Generate briefing via `build_daily_briefing(...)`.
      - Send message via `self.send_telegram_msg(...)`.
      - Record `self.state_manager.set("last_briefing_date", now.strftime("%Y-%m-%d"))`.
      - Trigger `self.git_sync_changes()`.

### 2.3 `telegram_command_handler.py`
- Route `/briefing`, `/morning`, `briefing`, `morning`:
  - Call `self.handle_briefing(chat_id)`.
  - In `handle_briefing()`:
    - Generate briefing via `build_daily_briefing(...)`.
    - Send with `reply_markup=MAIN_MENU_KEYBOARD`.
- Documentation in `/help` and `/start` updated to explain `/briefing`.

---

## 3. Data Integrity & Persistence
- `last_briefing_date` is persisted to `bot_state.json`.
- Thread-safe and atomic updates via `BotStateManager`.
- Automated git sync ensures the state survives runner restarts or GitHub Actions runner transitions.

---

## 4. Test Strategy
1. `tests/test_briefing_manager.py`:
   - `test_briefing_formatting_full`: with reminders, active alarms, and mocked quotes.
   - `test_briefing_no_reminders_no_alarms`: clean empty state formatting.
   - `test_briefing_handles_engine_failures`: resilient when quotes throw exceptions.
   - `test_briefing_html_escaping`: user input containing `<>&"` properly sanitized.
   - `test_briefing_timezone_accuracy`: correct today filtering based on `Asia/Jerusalem`.
2. `tests/test_cloud_runner.py`:
   - `test_evaluate_daily_briefing_triggers_at_0830`: verify trigger condition.
   - `test_evaluate_daily_briefing_idempotent_same_day`: verify only sends once per day.
3. `tests/test_telegram_command_handler.py`:
   - `test_briefing_command`: verify `/briefing` command execution and reply.
