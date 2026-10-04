# Stock Price Alarmer Design Document

**Date:** 2026-10-04  
**Status:** Approved  
**Author:** Pair Programming (User & Antigravity)

---

## 1. Overview & Goals

The **Stock Price Alarmer** is a 100% free, 24/7 autonomous stock price tracking and alerting system. It allows users to set price threshold alarms (`ABOVE` or `BELOW`) for any stock ticker and receive instant direct notifications to their **WhatsApp DM**.

### Key Constraints & Requirements:
- **100% Free**: No paid APIs, no paid cloud infrastructure, no subscriptions.
- **24/7 Operation without PC Running**: Uses free GitHub Actions cloud runners on schedule so the user does not need to leave their computer on or run local servers.
- **Privacy & Security**: Zero private personal data (phone numbers, API keys) stored in code or git commits. Compatible with public or private repositories via encrypted GitHub Secrets and `.gitignore`.
- **Easy UI Management**: Modern, responsive dashboard to view live prices, create, mute, and delete alarms, and test WhatsApp delivery.
- **Extensible Notification Pipeline**: Designed with a modular notifier interface, allowing Telegram bot (2-way chat) integration in the future without altering the price monitoring core.

---

## 2. Architecture & Data Flow

```
┌────────────────────────────────────────────────────────────────────────┐
│                        USER CONFIGURATION                              │
│   • Local Web Dashboard (http://localhost:8000) OR                     │
│   • GitHub-hosted Dashboard / alarms.json                              │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        STORAGE & SECRETS                               │
│   • alarms.json: Stores ticker, target price, direction, active state  │
│   • GitHub Secrets: CALLMEBOT_PHONE, CALLMEBOT_APIKEY (Encrypted)      │
│   • Local .env: Environment variables (never committed to git)         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                  ┌─────────────────┴─────────────────┐
                  ▼                                   ▼
┌───────────────────────────────────┐ ┌───────────────────────────────────┐
│     LOCAL RUNNER (On Demand)      │ │   GITHUB ACTIONS 24/7 (Cloud)     │
│  • FastAPI local server           │ │  • Scheduled cron (every 5-15 min)│
│  • Instant browser testing        │ │  • Runs headless in cloud         │
│  • One-click Windows run.bat      │ │  • Zero electricity / 0 PC cost   │
└─────────────────┬─────────────────┘ └─────────────────┬─────────────────┘
                  │                                   │
                  └─────────────────┬─────────────────┘
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         PRICE CHECK ENGINE                             │
│   1. Fetches real-time / delayed quotes via Yahoo Finance (yfinance)   │
│   2. Evaluates threshold:                                              │
│      - ABOVE: current_price >= target_price                            │
│      - BELOW: current_price <= target_price                            │
│   3. Checks anti-spam state: Triggered only once per alarm breach      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (If triggered)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     CALLMEBOT WHATSAPP GATEWAY                         │
│   • Sends encrypted HTTP GET request to CallMeBot API                  │
│   • Delivers formatted alert directly to user's WhatsApp DM            │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Privacy & Security Architecture

To ensure **absolute privacy**, especially if hosted on a public GitHub repository:

1. **Zero Hardcoded Secrets**:
   - Phone numbers and API keys are NEVER committed to git.
   - A `.gitignore` file strictly excludes:
     ```
     .env
     .env.local
     __pycache__/
     *.pyc
     alarms_local.json
     ```
2. **GitHub Secrets Integration**:
   - For 24/7 GitHub Actions execution, users configure two repository secrets in GitHub (`Settings -> Secrets and variables -> Actions`):
     - `CALLMEBOT_PHONE`: Target phone number in international format (e.g., `+1234567890`).
     - `CALLMEBOT_APIKEY`: The free key received from CallMeBot.
   - GitHub automatically masks these values in runner execution logs (displayed as `***`).
3. **Local PC Security**:
   - When running locally, settings are read from a local `.env` file or SQLite/local store excluded from git.

---

## 4. Components & Implementation Details

### 4.1. Price Engine (`engine.py`)
- **Library**: `yfinance` / direct Yahoo Finance query.
- **Logic**:
  - For each active alarm in `alarms.json`:
    - Fetch latest market price and current session change %.
    - If `direction == 'ABOVE'` and `price >= target_price`: Flag triggered.
    - If `direction == 'BELOW'` and `price <= target_price`: Flag triggered.
  - If triggered and `triggered == False`:
    - Dispatch WhatsApp alert via `NotificationService`.
    - Mark `triggered = True` and record `last_triggered_at = ISO8601`.
  - Persist updated status so repeat notifications are prevented until user resets.

### 4.2. Notification Service (`notifier.py`)
- Abstract base class `BaseNotifier`:
  - `send_alert(ticker: str, current_price: float, target_price: float, direction: str, note: str) -> bool`
- Implementations:
  - `CallMeBotWhatsAppNotifier`: Formats alert message with emojis, URL-encodes, and sends HTTP request to CallMeBot.
  - `ConsoleNotifier`: Local fallback logging when API keys are not yet configured.
  - *(Future)* `TelegramNotifier`: Pre-structured stub to plug in Telegram Bot API without touching engine logic.

### 4.3. Web Dashboard (`web/`)
- **Technology**: Lightweight modern single-page dashboard (HTML5, Tailwind CSS via CDN, Vanilla JavaScript).
- **Backend API (`app.py`)**:
  - `GET /api/alarms` — Retrieve all configured alarms with live market prices.
  - `POST /api/alarms` — Create a new alarm (`ticker`, `target_price`, `direction`, `note`).
  - `DELETE /api/alarms/{id}` — Delete an alarm.
  - `POST /api/alarms/{id}/reset` — Re-arm a triggered alarm.
  - `POST /api/test-whatsapp` — Send a test ping to verify WhatsApp credentials.
  - `GET /api/status` — Health check, market status (open/closed), and last poll time.

### 4.4. 24/7 Cloud Automation (`.github/workflows/stock_check.yml`)
- Runs on GitHub-hosted Ubuntu runner (`ubuntu-latest`).
- **Trigger**:
  - `schedule`: Cron expression running during trading days/hours (e.g., `*/10 * * * 1-5` or custom interval).
  - `workflow_dispatch`: Manual trigger button in GitHub Actions tab.
- **Workflow Steps**:
  1. Checkout repository.
  2. Set up Python 3.12.
  3. Install dependencies (`yfinance`, `requests`).
  4. Run `python check_alarms.py`.
  5. Commit and push updated `alarms.json` back to repo (using GitHub Actions bot token) so triggered states are saved.

---

## 5. Error Handling & Edge Cases

| Scenario | Handling Strategy |
| :--- | :--- |
| **Market Closed / Weekend** | Yahoo Finance returns latest close price. System continues checking without crashing. |
| **Invalid Ticker Symbol** | Engine validates symbol before saving alarm; returns clear user-friendly error in UI. |
| **CallMeBot Rate Limiting** | Max 1 notification per minute per phone number. Script includes try/except with exponential backoff. |
| **Network / Yahoo Timeout** | Retry up to 3 times with 2s delay; skip ticker and log warning if Yahoo is unreachable. |
| **Merge Conflicts on alarms.json** | State updates use atomic write and automated rebase in GitHub Actions commit step. |

---

## 6. Testing & Verification Plan

1. **Unit / Logic Tests**:
   - Verify price comparison logic (ABOVE/BELOW trigger boundaries).
   - Verify anti-spam state updates (ensure alarm does not fire twice consecutively).
2. **WhatsApp Gateway Test**:
   - Provide a dedicated test script (`python test_whatsapp.py`) and UI test button to verify phone number and API key delivery.
3. **Local End-to-End Test**:
   - Start local dashboard (`run.bat` or `python app.py`).
   - Add a test alarm with a price target that triggers immediately (e.g. AAPL above $1).
   - Verify WhatsApp message delivery and status update in UI.
4. **GitHub Actions Workflow Dry-Run**:
   - Validate `.github/workflows/stock_check.yml` syntax and test via `workflow_dispatch`.
