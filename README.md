# 📈 TickerPing — 24/7 Free Stock Price Alarmer

**TickerPing** is a 100% free, autonomous stock price tracking and alerting system. Set price targets (`ABOVE` or `BELOW`) for any stock ticker and receive instant direct messages to your phone via **Telegram** when breached.

Designed to run **24/7 in the cloud for free via GitHub Actions** without keeping your computer on, plus an optional local web dashboard on your PC.

---

## 🚀 Key Features

* **100% Free Forever:** No paid APIs, no cloud bills, no subscriptions.
* **Instant Phone Push Alerts:** Delivered directly to your phone via official Telegram Bot API (never blocked or capped).
* **Zero PC Up-time Needed (24/7 Cloud):** Scheduled GitHub Actions runs automatically in the background even when your PC is turned off.
* **Anti-Spam Safeguard:** Fires once when a price target is breached; easily re-arm or reset with 1 click.
* **Clean Modern Web UI:** Manage your stocks, target prices, and notification settings easily from your browser.
* **Complete Privacy & Multi-Account Safe:** Your personal credentials are stored strictly in GitHub Secrets and local `.env` — never exposed in commits.

---

## 🛠️ Step 1: Create Your Free Telegram Bot (45 Seconds)

1. Open Telegram on your phone or PC and search for: **`@BotFather`**
2. Send:
   ```text
   /newbot
   ```
3. Choose a name (e.g. `My TickerPing`) and a username ending in `bot` (e.g. `dror_tickerping_bot`).
4. `@BotFather` will reply with your **HTTP API Token** (e.g. `7123456789:AAH...`).
5. Open your newly created bot in Telegram and tap **Start** (or send `/start`).

---

## ☁️ Step 2: Enable 24/7 Cloud Alerts on GitHub

To let GitHub monitor prices 24/7 without needing your PC on:

1. Open your repository on GitHub: [`droritos/TickerPing`](https://github.com/droritos/TickerPing)
2. Go to **Settings** → **Secrets and variables** → **Actions**.
3. Click **New repository secret** and add two secrets:
   * `TELEGRAM_BOT_TOKEN` → The Bot Token you got from `@BotFather`
   * `TELEGRAM_CHAT_ID` → Your Telegram Chat ID
4. Go to the **Actions** tab on your GitHub repository and enable workflows.
   * That's it! GitHub Actions will now automatically check your stock alarms every 15 minutes during market hours and alert your Telegram DM.

---

## 💻 Step 3: Running Locally on Your PC (Optional)

You can also run the local dashboard on your computer anytime:

### 1. Install dependencies
```powershell
pip install -r requirements.txt
```

### 2. Start the application
Double-click **`run.bat`** or run:
```powershell
python -m uvicorn app:app --reload
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

---

## ⚙️ How It Works

```
[ Stock Targets in alarms.json ]
              │
              ▼
[ GitHub Actions / Local Poller ]
              │
              ├── 1. Fetches real-time price from Yahoo Finance
              ├── 2. Checks condition (Price >= Target OR Price <= Target)
              └── 3. If crossed:
                      │
                      ▼
              [ Official Telegram Bot API ]
                      │
                      ▼
              [ Your Phone Notification 📲 ]
              "🚨 AAPL reached $333.69 (Target: Above $250.00)"
```

---

## 🔒 Privacy & Security

* **`.gitignore`** strictly ignores all `.env`, `.env.local`, and secrets.
* GitHub Secrets are encrypted and masked (`***`) in all execution logs.
* No data is shared with any third party other than Yahoo Finance for public quotes and Telegram for your private alert messages.
