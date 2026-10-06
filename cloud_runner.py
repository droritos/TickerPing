#!/usr/bin/env python3
"""
cloud_runner.py — Autonomous 24/7 cloud runner for GitHub Actions.
Executes an internal loop for a designated time budget (e.g. 260s),
polling Telegram commands, replying to user messages, and checking active alarms.
"""
import os
import sys
import time
import logging
import requests
from typing import Optional

from config import load_config
from engine import StockEngine, evaluate_alarm
from notifier import TelegramNotifier
from alarms_manager import AlarmManager
from bot_state import BotStateManager
from telegram_command_handler import TelegramCommandHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CloudRunner")

class CloudRunner:
    def __init__(
        self,
        token: str,
        chat_id: str,
        storage_path: str = "alarms.json",
        state_path: str = "bot_state.json",
        max_runtime_seconds: int = 260,
        loop_interval_seconds: int = 60
    ):
        self.token = token
        self.chat_id = chat_id
        self.max_runtime_seconds = max_runtime_seconds
        self.loop_interval_seconds = loop_interval_seconds
        self.base_url = f"https://api.telegram.org/bot{token}"

        self.alarm_manager = AlarmManager(storage_path=storage_path)
        self.state_manager = BotStateManager(storage_path=state_path)
        self.engine = StockEngine()
        self.notifier = TelegramNotifier(bot_token=token, chat_id=chat_id)
        self.cmd_handler = TelegramCommandHandler(
            alarm_manager=self.alarm_manager,
            engine=self.engine,
            send_msg_fn=self.send_telegram_msg,
            answer_cb_fn=self.answer_callback_query
        )

    def send_telegram_msg(self, chat_id: str, text: str, reply_markup: Optional[dict] = None):
        if not self.token:
            logger.warning("No Telegram token configured; skipping send_telegram_msg.")
            return
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            requests.post(
                f"{self.base_url}/sendMessage",
                json=payload,
                timeout=15
            )
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")

    def answer_callback_query(self, callback_query_id: str, text: Optional[str] = None):
        if not self.token:
            return
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        try:
            requests.post(
                f"{self.base_url}/answerCallbackQuery",
                json=payload,
                timeout=10
            )
        except Exception as e:
            logger.error(f"Failed to answer Telegram callback query: {e}")

    def poll_telegram_updates(self):
        if not self.token:
            return
        last_offset = self.state_manager.get_last_offset()
        offset = last_offset + 1 if last_offset > 0 else 0
        try:
            params = {"timeout": 5}
            if offset > 0:
                params["offset"] = offset
            res = requests.get(f"{self.base_url}/getUpdates", params=params, timeout=10)
            data = res.json()
            if not data.get("ok"):
                return

            updates = data.get("result", [])
            for u in updates:
                if "callback_query" in u:
                    self.cmd_handler.handle_callback_query(u["callback_query"])
                elif "message" in u:
                    self.cmd_handler.handle_update(u)
                self.state_manager.set_last_offset(u["update_id"])
        except Exception as e:
            logger.error(f"Error polling Telegram updates: {e}")

    def evaluate_active_alarms(self):
        alarms = self.alarm_manager.get_alarms()
        active_alarms = [a for a in alarms if a.get("active", True) and not a.get("triggered", False)]
        if not active_alarms:
            return

        for alarm in active_alarms:
            ticker = alarm.get("ticker", "")
            target = alarm.get("target_price", 0.0)
            direction = alarm.get("direction", "ABOVE")
            note = alarm.get("note", "")

            quote = self.engine.get_quote(ticker)
            if not quote:
                continue

            logger.info(f"{ticker} Current: ${quote.price:.2f} (Target: {direction} ${target:.2f})")

            if evaluate_alarm(current_price=quote.price, target_price=target, direction=direction):
                logger.info(f"🚨 Target met for {ticker} at ${quote.price:.2f}!")
                self.notifier.send_alert(
                    ticker=ticker,
                    current_price=quote.price,
                    target_price=target,
                    direction=direction,
                    change_percent=quote.change_percent,
                    currency=quote.currency,
                    note=note
                )
                self.alarm_manager.mark_triggered(alarm["id"], trigger_price=quote.price)

    def run(self) -> int:
        start_time = time.time()
        logger.info(f"Starting CloudRunner (Max runtime: {self.max_runtime_seconds}s, Interval: {self.loop_interval_seconds}s)")
        cycles = 0

        while True:
            elapsed = time.time() - start_time
            if elapsed >= self.max_runtime_seconds:
                logger.info(f"Max runtime budget reached ({elapsed:.1f}s >= {self.max_runtime_seconds}s). Exiting cycle.")
                break

            cycle_start = time.time()
            logger.info(f"--- Running cloud cycle #{cycles + 1} (Elapsed: {elapsed:.1f}s) ---")
            
            # 1. Telegram Updates
            self.poll_telegram_updates()

            # 2. Stock Alarm Check
            self.evaluate_active_alarms()

            cycles += 1
            cycle_duration = time.time() - cycle_start
            remaining = self.loop_interval_seconds - cycle_duration

            if remaining > 0 and (time.time() - start_time + remaining) < self.max_runtime_seconds:
                time.sleep(remaining)
            elif (time.time() - start_time) < self.max_runtime_seconds:
                sleep_time = min(5, self.max_runtime_seconds - (time.time() - start_time))
                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    break
            else:
                break

        return cycles

if __name__ == "__main__":
    cfg = load_config()
    storage = os.getenv("DATA_FILE_PATH", cfg.data_file)
    state = os.getenv("STATE_FILE_PATH", "bot_state.json")
    max_runtime = int(os.getenv("MAX_RUNTIME_SECONDS", "260"))
    interval = int(os.getenv("LOOP_INTERVAL_SECONDS", "60"))

    runner = CloudRunner(
        token=cfg.telegram_bot_token,
        chat_id=cfg.telegram_chat_id,
        storage_path=storage,
        state_path=state,
        max_runtime_seconds=max_runtime,
        loop_interval_seconds=interval
    )
    runner.run()
