#!/usr/bin/env python3
"""
check_alarms.py — Autonomous headless stock checker for GitHub Actions or cron.
Reads alarms.json, evaluates active alarms, sends instant alerts via Telegram (or CallMeBot),
and updates alarm trigger states.
"""
import os
import sys
import logging
from config import load_config
from engine import StockEngine, evaluate_alarm
from notifier import create_notifier_from_config
from alarms_manager import AlarmManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("HeadlessChecker")

def run_check():
    cfg = load_config()
    storage_file = os.getenv("DATA_FILE_PATH", "alarms.json")
    
    logger.info(f"Starting stock price check (storage: {storage_file})")
    manager = AlarmManager(storage_path=storage_file)

    alarms = manager.get_alarms()
    active_alarms = [a for a in alarms if a.get("active", True) and not a.get("triggered", False)]
    
    logger.info(f"Found {len(alarms)} total alarms ({len(active_alarms)} active and awaiting trigger).")
    
    if not active_alarms:
        logger.info("No active alarms need checking at this time.")
        return

    engine = StockEngine()
    notifier = create_notifier_from_config(cfg)
    
    triggered_count = 0

    for alarm in active_alarms:
        ticker = alarm.get("ticker", "")
        target = alarm.get("target_price", 0.0)
        direction = alarm.get("direction", "ABOVE")
        note = alarm.get("note", "")

        logger.info(f"Checking {ticker} (Target: {direction} ${target})...")
        quote = engine.get_quote(ticker)
        
        if not quote:
            logger.warning(f"Skipping {ticker}: Quote could not be retrieved.")
            continue

        logger.info(f"{ticker} Current Price: ${quote.price:.2f} {quote.currency} ({quote.change_percent:+.2f}%)")

        if evaluate_alarm(current_price=quote.price, target_price=target, direction=direction):
            logger.info(f"🚨 TRIGGER MET! {ticker} is ${quote.price:.2f} ({direction} ${target:.2f})")
            
            # Send notification
            sent = notifier.send_alert(
                ticker=ticker,
                current_price=quote.price,
                target_price=target,
                direction=direction,
                change_percent=quote.change_percent,
                currency=quote.currency,
                note=note
            )
            logger.info(f"Notification status: {'Sent' if sent else 'Failed'}")

            # Mark as triggered in state storage so repeat alerts don't fire
            manager.mark_triggered(alarm["id"], trigger_price=quote.price)
            triggered_count += 1

    logger.info(f"Check cycle finished. {triggered_count} alarms triggered.")

if __name__ == "__main__":
    run_check()
