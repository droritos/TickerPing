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
import subprocess
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
        max_runtime_seconds: int = 18000,
        loop_interval_seconds: int = 60
    ):
        self.token = token
        self.chat_id = chat_id
        self.max_runtime_seconds = max_runtime_seconds
        self.loop_interval_seconds = loop_interval_seconds
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.storage_path = storage_path
        self.state_path = state_path
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

    def poll_telegram_updates(self) -> bool:
        """Poll Telegram for new commands or button clicks. Returns True if any updates were handled."""
        if not self.token:
            return False
        last_offset = self.state_manager.get_last_offset()
        offset = last_offset + 1 if last_offset > 0 else 0
        try:
            params = {"timeout": 3}
            if offset > 0:
                params["offset"] = offset
            res = requests.get(f"{self.base_url}/getUpdates", params=params, timeout=8)
            data = res.json()
            if not data.get("ok"):
                return False

            updates = data.get("result", [])
            for u in updates:
                if "callback_query" in u:
                    self.cmd_handler.handle_callback_query(u["callback_query"])
                elif "message" in u:
                    self.cmd_handler.handle_update(u)
                self.state_manager.set_last_offset(u["update_id"])
            return len(updates) > 0
        except Exception as e:
            logger.error(f"Error polling Telegram updates: {e}")
            return False

    def git_sync_changes(self):
        """Sync alarms.json and bot_state.json to GitHub if running inside GitHub Actions."""
        if os.getenv("GITHUB_ACTIONS") != "true":
            return
        try:
            subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=False)
            subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], check=False)
            subprocess.run(["git", "add", self.storage_path, self.state_path], check=False)
            diff = subprocess.run(["git", "diff", "--staged", "--quiet"], check=False)
            if diff.returncode != 0:
                subprocess.run(["git", "commit", "-m", "chore: sync alarms and bot state [skip ci]"], check=False)
                subprocess.run(["git", "push"], check=False)
                logger.info("Auto-synced state changes to git.")
        except Exception as e:
            logger.warning(f"Git auto-sync warning: {e}")

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
                self.git_sync_changes()

    def ensure_bot_avatar(self):
        """Automatically set the bot profile photo in Telegram if not already configured."""
        if not self.token or not os.path.exists("bot_avatar.jpg"):
            return
        if self.state_manager.get("avatar_set"):
            return
        try:
            with open("bot_avatar.jpg", "rb") as f:
                res = requests.post(
                    f"{self.base_url}/setMyProfilePhoto",
                    data={"photo": '{"type": "static", "photo": "attach://avatar"}'},
                    files={"avatar": ("bot_avatar.jpg", f, "image/jpeg")},
                    timeout=15
                )
                if res.status_code == 200 and res.json().get("ok"):
                    logger.info("Bot profile photo successfully configured in Telegram!")
                    self.state_manager.set("avatar_set", True)
                else:
                    logger.info(f"setMyProfilePhoto response: {res.text}")
        except Exception as e:
            logger.warning(f"Could not auto-set bot profile photo: {e}")

    def run(self) -> int:
        start_time = time.time()
        logger.info(f"Starting CloudRunner (Max runtime: {self.max_runtime_seconds}s, Interval: {self.loop_interval_seconds}s)")
        self.ensure_bot_avatar()
        cycles = 0
        last_stock_check = 0.0
        last_git_sync = time.time()

        while True:
            now = time.time()
            elapsed = now - start_time
            if elapsed >= self.max_runtime_seconds:
                logger.info(f"Max runtime budget reached ({elapsed:.1f}s >= {self.max_runtime_seconds}s). Exiting cycle.")
                break

            # 1. Telegram Updates (fast long-poll: returns immediately on message)
            had_updates = self.poll_telegram_updates()

            # 2. Stock Alarm Check every `loop_interval_seconds`
            if (now - last_stock_check) >= self.loop_interval_seconds:
                logger.info(f"--- Running stock evaluation cycle #{cycles + 1} (Elapsed: {elapsed:.1f}s) ---")
                self.evaluate_active_alarms()
                last_stock_check = time.time()
                cycles += 1

            # 3. Auto-sync changes to Git if updates occurred or periodically
            if had_updates or (now - last_git_sync >= 300):
                self.git_sync_changes()
                last_git_sync = time.time()

            # Brief pause if idle to prevent tight CPU looping
            if not had_updates:
                remaining_time = self.max_runtime_seconds - (time.time() - start_time)
                if remaining_time <= 0:
                    break
                time.sleep(min(1.0, max(0.05, remaining_time)))

        # Final git sync before exiting
        self.git_sync_changes()
        return cycles

if __name__ == "__main__":
    cfg = load_config()
    storage = os.getenv("DATA_FILE_PATH", cfg.data_file)
    state = os.getenv("STATE_FILE_PATH", "bot_state.json")
    max_runtime = int(os.getenv("MAX_RUNTIME_SECONDS", "18000"))
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
