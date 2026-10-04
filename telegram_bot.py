#!/usr/bin/env python3
"""
telegram_bot.py — Interactive 2-Way Telegram Bot for TickerPing.
Allows users to add, list, delete, and check stock alarms directly inside Telegram chat.
Polls stock prices every 60 seconds and sends alerts with charts.
"""
import os
import time
import threading
import logging
import requests
from typing import Optional, List, Dict, Any

from config import load_config
from engine import StockEngine, evaluate_alarm
from notifier import TelegramNotifier
from alarms_manager import AlarmManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TelegramBot")

config = load_config()
alarm_manager = AlarmManager(storage_path=config.data_file)
engine = StockEngine()

TOKEN = config.telegram_bot_token
ADMIN_CHAT_ID = config.telegram_chat_id
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))

def send_msg(chat_id: str, text: str):
    try:
        requests.post(
            f"{BASE_URL}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=15
        )
    except Exception as e:
        logger.error(f"Failed to send message: {e}")

def handle_start(chat_id: str):
    msg = (
        "📈 <b>Welcome to TickerPing!</b>\n\n"
        "You can manage your stock alarms directly inside this chat:\n\n"
        "<b>➕ Add Alarm:</b>\n"
        "<code>/set AAPL 340 ABOVE</code>\n"
        "<code>/set TSLA 210 BELOW</code>\n"
        "<i>(Or simply send: <code>AAPL 340</code>)</i>\n\n"
        "<b>📋 Other Commands:</b>\n"
        "• <code>/list</code> — View all your active alarms\n"
        "• <code>/del AAPL</code> — Delete an alarm\n"
        "• <code>/price AAPL</code> — Check live stock price right now\n"
        "• <code>/check</code> — Trigger an immediate price check\n\n"
        "⏰ <i>Prices are checked automatically every 60 seconds!</i>"
    )
    send_msg(chat_id, msg)

def handle_price(chat_id: str, ticker: str):
    clean = ticker.strip().upper()
    quote = engine.get_quote(clean)
    if not quote:
        send_msg(chat_id, f"❌ Could not find quote for <b>{clean}</b>. Please check the ticker symbol.")
        return
    sign = "+" if quote.change_percent >= 0 else ""
    msg = (
        f"📊 <b>{quote.symbol} Live Quote</b>\n\n"
        f"💰 <b>Price:</b> ${quote.price:,.2f} {quote.currency}\n"
        f"📈 <b>Session Change:</b> {sign}{quote.change_percent:.2f}%\n"
        f"🏁 <b>Previous Close:</b> ${quote.previous_close:,.2f}"
    )
    send_msg(chat_id, msg)

def handle_set(chat_id: str, args: List[str]):
    # /set AAPL 340 ABOVE [Optional note]
    if len(args) < 2:
        send_msg(chat_id, "⚠️ Usage: <code>/set TICKER TARGET_PRICE [ABOVE/BELOW] [NOTE]</code>\nExample: <code>/set AAPL 340 ABOVE Breakout</code>")
        return

    ticker = args[0].strip().upper()
    try:
        target_price = float(args[1].replace("$", ""))
    except ValueError:
        send_msg(chat_id, f"❌ Invalid target price: '{args[1]}'. Must be a number like 250.50")
        return

    direction = "ABOVE"
    note = ""

    if len(args) >= 3 and args[2].upper() in ("ABOVE", "BELOW"):
        direction = args[2].upper()
        if len(args) >= 4:
            note = " ".join(args[3:])
    elif len(args) >= 3:
        note = " ".join(args[2:])

    # Validate ticker
    send_msg(chat_id, f"🔍 Checking <b>{ticker}</b>...")
    quote = engine.get_quote(ticker)
    if not quote:
        send_msg(chat_id, f"❌ Ticker <b>{ticker}</b> not found on Yahoo Finance. Please verify the symbol.")
        return

    # If direction was default ABOVE, but target is below current price, smart default to BELOW
    if len(args) < 3:
        if target_price < quote.price:
            direction = "BELOW"
        else:
            direction = "ABOVE"

    alarm = alarm_manager.add_alarm(
        ticker=ticker,
        target_price=target_price,
        direction=direction,
        note=note
    )

    diff = round(((target_price - quote.price) / quote.price) * 100, 2)
    diff_sign = "+" if diff > 0 else ""

    msg = (
        f"✅ <b>Alarm Set Successfully!</b>\n\n"
        f"🎯 <b>{ticker}</b>: Alert when price is <b>{direction} ${target_price:,.2f}</b>\n"
        f"💰 <b>Current Price:</b> ${quote.price:,.2f} ({diff_sign}{diff}% away)\n"
    )
    if note:
        msg += f"📝 <b>Note:</b> {note}\n"
    msg += f"🆔 <b>ID:</b> <code>{alarm['id']}</code>"
    send_msg(chat_id, msg)

def handle_list(chat_id: str):
    alarms = alarm_manager.get_alarms()
    if not alarms:
        send_msg(chat_id, "📭 You have no stock alarms set.\nSend <code>/set AAPL 340 ABOVE</code> to create one!")
        return

    lines = [f"📋 <b>Your Stock Alarms ({len(alarms)}):</b>\n"]
    for i, a in enumerate(alarms, 1):
        ticker = a["ticker"]
        target = a["target_price"]
        direction = a["direction"]
        status = "🚨 Triggered" if a.get("triggered") else ("Active 🟢" if a.get("active") else "Paused ⏸️")
        
        quote = engine.get_quote(ticker)
        price_str = f"${quote.price:.2f}" if quote else "N/A"
        
        lines.append(
            f"<b>{i}. {ticker}</b> — {direction} ${target:,.2f}\n"
            f"   Current: <b>{price_str}</b> | Status: {status}\n"
            f"   Delete: <code>/del {ticker}</code>\n"
        )

    send_msg(chat_id, "\n".join(lines))

def handle_delete(chat_id: str, identifier: str):
    target = identifier.strip().upper()
    alarms = alarm_manager.get_alarms()
    
    # Try by ID first, then by Ticker
    deleted = False
    for a in alarms:
        if a["id"].upper() == target or a["ticker"].upper() == target:
            alarm_manager.delete_alarm(a["id"])
            send_msg(chat_id, f"🗑️ Deleted alarm for <b>{a['ticker']}</b> (${a['target_price']:.2f})")
            deleted = True
            break

    if not deleted:
        send_msg(chat_id, f"❌ No alarm found matching '<b>{identifier}</b>'. Use <code>/list</code> to view active alarms.")

def check_all_alarms_now(notifier: TelegramNotifier, specific_chat: Optional[str] = None):
    alarms = alarm_manager.get_alarms()
    active_alarms = [a for a in alarms if a.get("active", True) and not a.get("triggered", False)]
    
    logger.info(f"Checking {len(active_alarms)} active alarms...")

    triggered_count = 0
    for alarm in active_alarms:
        ticker = alarm["ticker"]
        target = alarm["target_price"]
        direction = alarm["direction"]
        note = alarm.get("note", "")

        quote = engine.get_quote(ticker)
        if not quote:
            continue

        if evaluate_alarm(current_price=quote.price, target_price=target, direction=direction):
            logger.info(f"🚨 TRIGGERED: {ticker} at ${quote.price}")
            alarm_manager.mark_triggered(alarm["id"], trigger_price=quote.price)
            notifier.send_alert(
                ticker=ticker,
                current_price=quote.price,
                target_price=target,
                direction=direction,
                change_percent=quote.change_percent,
                currency=quote.currency,
                note=note
            )
            triggered_count += 1

    if specific_chat:
        send_msg(specific_chat, f"✅ Check complete. Evaluated {len(active_alarms)} alarms. ({triggered_count} triggered)")

def background_price_checker(notifier: TelegramNotifier):
    logger.info(f"Background price checker started (Interval: {POLL_INTERVAL}s)")
    while True:
        try:
            check_all_alarms_now(notifier)
        except Exception as e:
            logger.error(f"Error in background price check: {e}")
        time.sleep(POLL_INTERVAL)

def run_bot():
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in .env! Cannot start bot.")
        return

    notifier = TelegramNotifier(bot_token=TOKEN, chat_id=ADMIN_CHAT_ID)

    # Start 60-second background price checker thread
    bg_thread = threading.Thread(target=background_price_checker, args=(notifier,), daemon=True)
    bg_thread.start()

    logger.info("TickerPing Telegram Bot is listening for user messages...")
    offset = 0

    while True:
        try:
            res = requests.get(f"{BASE_URL}/getUpdates", params={"offset": offset, "timeout": 20}, timeout=25)
            data = res.json()
            if not data.get("ok"):
                time.sleep(2)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message")
                if not msg or "text" not in msg:
                    continue

                chat_id = str(msg["chat"]["id"])
                text = msg["text"].strip()
                tokens = text.split()

                if not tokens:
                    continue

                cmd = tokens[0].lower()

                if cmd in ("/start", "/help", "help"):
                    handle_start(chat_id)
                elif cmd in ("/set", "/add", "add", "set"):
                    handle_set(chat_id, tokens[1:])
                elif cmd in ("/list", "/alarms", "list", "alarms"):
                    handle_list(chat_id)
                elif cmd in ("/del", "/delete", "/rm", "del", "delete"):
                    if len(tokens) > 1:
                        handle_delete(chat_id, tokens[1])
                    else:
                        send_msg(chat_id, "⚠️ Specify what to delete, e.g.: <code>/del AAPL</code>")
                elif cmd in ("/price", "/quote", "price", "quote"):
                    if len(tokens) > 1:
                        handle_price(chat_id, tokens[1])
                    else:
                        send_msg(chat_id, "⚠️ Specify a ticker, e.g.: <code>/price AAPL</code>")
                elif cmd in ("/check", "check"):
                    check_all_alarms_now(notifier, specific_chat=chat_id)
                else:
                    # Smart parse: "AAPL 340" or "NVDA 130 ABOVE"
                    if len(tokens) >= 2 and tokens[1].replace(".", "", 1).replace("$", "").isdigit():
                        handle_set(chat_id, tokens)
                    else:
                        send_msg(chat_id, "❓ Unknown command. Send <code>/help</code> to see available commands, or <code>AAPL 340</code> to set an alarm.")

        except requests.exceptions.RequestException as e:
            time.sleep(3)
        except Exception as e:
            logger.error(f"Error in Telegram bot loop: {e}")
            time.sleep(2)

if __name__ == "__main__":
    run_bot()
