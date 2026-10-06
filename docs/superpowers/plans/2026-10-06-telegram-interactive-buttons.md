# Telegram Interactive Clickable Buttons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Equip `@dror_tickerbot_bot` with a persistent mobile bottom menu (1-tap access to alarms, quick quotes, help) and inline clickable buttons attached to alarm cards and alert charts (1-tap delete and direct Yahoo Finance charts).

**Architecture:** Extend `TelegramCommandHandler` to include `ReplyKeyboardMarkup` in responses and generate `InlineKeyboardMarkup` on each alarm in `/list`. In `cloud_runner.py`, intercept `callback_query` events from Telegram `getUpdates`, acknowledge them via `answerCallbackQuery`, and execute 1-tap alarm deletions. In `notifier.py`, attach inline web links to alert photo notifications.

**Tech Stack:** Python 3.12, Telegram Bot API (`ReplyKeyboardMarkup`, `InlineKeyboardMarkup`, `answerCallbackQuery`), `requests`, `pytest`.

## Global Constraints
- Target repository: `droritos/TickerPing` on branch `main`.
- All automated commits must preserve `droritos` author identity.
- Full test suite must pass without regressions.
- Cloud runner must remain within its execution budget.

---

### Task 1: Persistent Bottom Menu Keyboard & Quick Quotes

**Files:**
- Modify: `telegram_command_handler.py`
- Modify: `tests/test_telegram_command_handler.py`

**Interfaces:**
- Produces: `MAIN_MENU_KEYBOARD`, `handle_quick_quotes(chat_id: str)`, `handle_how_to_set(chat_id: str)`
- Enhances: `send_msg_fn` accepting optional `reply_markup: Optional[Dict[str, Any]] = None`

- [ ] **Step 1: Write failing tests in `tests/test_telegram_command_handler.py`**
- [ ] **Step 2: Run pytest to verify tests fail**
- [ ] **Step 3: Implement keyboard markup and handlers in `telegram_command_handler.py`**
- [ ] **Step 4: Run pytest to verify all tests pass**
- [ ] **Step 5: Git commit**

---

### Task 2: Inline Delete Buttons & Callback Query Processing

**Files:**
- Modify: `telegram_command_handler.py`
- Modify: `tests/test_telegram_command_handler.py`

**Interfaces:**
- Consumes: `answer_callback_query_fn: Optional[Callable[[str, Optional[str]], None]]`
- Produces: `handle_callback_query(query: Dict[str, Any]) -> bool`, inline delete button markup for each alarm in `/list`

- [ ] **Step 1: Write failing tests for inline buttons and callback queries**
- [ ] **Step 2: Run pytest to verify tests fail**
- [ ] **Step 3: Implement inline buttons and `handle_callback_query`**
- [ ] **Step 4: Run pytest to verify all tests pass**
- [ ] **Step 5: Git commit**

---

### Task 3: Cloud Runner & Notifier Integration

**Files:**
- Modify: `cloud_runner.py`
- Modify: `notifier.py`
- Modify: `telegram_bot.py`
- Test: `tests/test_cloud_runner.py`

**Interfaces:**
- Updates `CloudRunner.poll_telegram_updates` to parse `callback_query`
- Adds `CloudRunner.answer_callback_query`
- Adds inline button `[🌐 View on Yahoo Finance]` to `TelegramNotifier.send_alert`

- [ ] **Step 1: Write unit tests in `tests/test_cloud_runner.py` for callback query polling**
- [ ] **Step 2: Implement callback query handling in `cloud_runner.py` and inline button in `notifier.py`**
- [ ] **Step 3: Run full pytest suite (all 50+ tests passing)**
- [ ] **Step 4: Git commit**

---

### Task 4: Push to GitHub & Verify Cloud Execution

- [ ] **Step 1: Push changes to `origin main`**
- [ ] **Step 2: Verify GitHub Actions run triggers and succeeds**
