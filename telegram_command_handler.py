"""
telegram_command_handler.py — Core Telegram Command Handler for TickerPing.
Encapsulates all command parsing, routing, and response formatting for both
local bots and cloud runners.
"""

import logging
from typing import Callable, List, Dict, Any, Optional

from engine import StockEngine
from alarms_manager import AlarmManager

logger = logging.getLogger(__name__)


class TelegramCommandHandler:
    """Handles Telegram incoming updates, parses commands, and executes operations."""

    def __init__(
        self,
        alarm_manager: AlarmManager,
        engine: StockEngine,
        send_msg_fn: Callable[[str, str], None],
    ) -> None:
        """
        Initialize the command handler.

        :param alarm_manager: AlarmManager instance for managing stored alarms.
        :param engine: StockEngine instance for querying stock market data.
        :param send_msg_fn: Callable accepting (chat_id, text) to transmit Telegram replies.
        """
        self.alarm_manager = alarm_manager
        self.engine = engine
        self.send_msg = send_msg_fn

    def handle_update(self, update: Dict[str, Any]) -> bool:
        """
        Process a Telegram update dictionary.

        :param update: Dict representing a Telegram Update object.
        :return: True if a message was recognized and processed, False otherwise.
        """
        if not isinstance(update, dict):
            return False

        msg = update.get("message")
        if not msg or not isinstance(msg, dict):
            return False

        chat = msg.get("chat")
        if not chat or not isinstance(chat, dict) or "id" not in chat:
            return False

        chat_id = str(chat["id"])
        text = msg.get("text")
        if not isinstance(text, str):
            return False

        text = text.strip()
        tokens = text.split()
        if not tokens:
            return False

        cmd = tokens[0].lower()

        if cmd in ("/start", "/help", "help"):
            self.handle_start(chat_id)
        elif cmd in ("/set", "/add", "add", "set"):
            self.handle_set(chat_id, tokens[1:])
        elif cmd in ("/list", "/alarms", "list", "alarms"):
            self.handle_list(chat_id)
        elif cmd in ("/del", "/delete", "/rm", "del", "delete"):
            if len(tokens) > 1:
                self.handle_delete(chat_id, tokens[1])
            else:
                self.send_msg(chat_id, "⚠️ Specify what to delete, e.g.: <code>/del AAPL</code>")
        elif cmd in ("/price", "/quote", "price", "quote"):
            if len(tokens) > 1:
                self.handle_price(chat_id, tokens[1])
            else:
                self.send_msg(chat_id, "⚠️ Specify a ticker, e.g.: <code>/price AAPL</code>")
        elif cmd in ("/check", "check"):
            self.send_msg(chat_id, "⏰ Alarms are monitored and checked automatically 24/7!")
        else:
            # Check for shorthand syntax like "AAPL 340" or "NVDA 130 ABOVE"
            is_shorthand = False
            if len(tokens) >= 2:
                clean_target = tokens[1].replace("$", "")
                try:
                    float(clean_target)
                    is_shorthand = True
                except ValueError:
                    is_shorthand = False

            if is_shorthand:
                self.handle_set(chat_id, tokens)
            else:
                self.send_msg(
                    chat_id,
                    "❓ Unknown command. Send <code>/help</code> or <code>AAPL 340</code> to set an alarm.",
                )

        return True

    def handle_start(self, chat_id: str) -> None:
        """Send welcome message and command documentation."""
        msg = (
            "📈 <b>Welcome to TickerPing!</b>\n\n"
            "You can manage your stock alarms directly inside this chat:\n\n"
            "<b>➕ Add Alarm:</b>\n"
            "<code>/set AAPL 340 ABOVE</code>\n"
            "<code>/set TSLA 210 BELOW</code>\n"
            "<i>(Or simply send: <code>AAPL 340</code>)</i>\n\n"
            "<b>📋 Other Commands:</b>\n"
            "• <code>/list</code> — View your active alarms\n"
            "• <code>/del AAPL</code> — Delete an alarm\n"
            "• <code>/price AAPL</code> — Check live quote\n"
            "• <code>/help</code> — Show this guide\n\n"
            "⏰ <i>Alarms are monitored 24/7 in the cloud!</i>"
        )
        self.send_msg(chat_id, msg)

    def handle_price(self, chat_id: str, ticker: str) -> None:
        """Fetch and send the current live stock quote for a ticker."""
        clean = ticker.strip().upper()
        quote = self.engine.get_quote(clean)
        if not quote:
            self.send_msg(chat_id, f"❌ Could not find quote for <b>{clean}</b>. Please check the ticker symbol.")
            return

        sign = "+" if quote.change_percent >= 0 else ""
        msg = (
            f"📊 <b>{quote.symbol} Live Quote</b>\n\n"
            f"💰 <b>Price:</b> ${quote.price:,.2f} {quote.currency}\n"
            f"📈 <b>Session Change:</b> {sign}{quote.change_percent:.2f}%\n"
            f"🏁 <b>Previous Close:</b> ${quote.previous_close:,.2f}"
        )
        self.send_msg(chat_id, msg)

    def handle_set(self, chat_id: str, args: List[str]) -> None:
        """Create a new stock price alarm."""
        if len(args) < 2:
            self.send_msg(
                chat_id,
                "⚠️ Usage: <code>/set TICKER TARGET_PRICE [ABOVE/BELOW] [NOTE]</code>\n"
                "Example: <code>/set AAPL 340 ABOVE Breakout</code>",
            )
            return

        ticker = args[0].strip().upper()
        try:
            target_price = float(args[1].replace("$", ""))
        except ValueError:
            self.send_msg(chat_id, f"❌ Invalid target price: '{args[1]}'. Must be a number like 250.50")
            return

        direction = "ABOVE"
        note = ""
        has_explicit_direction = False

        if len(args) >= 3 and args[2].upper() in ("ABOVE", "BELOW"):
            direction = args[2].upper()
            has_explicit_direction = True
            if len(args) >= 4:
                note = " ".join(args[3:])
        elif len(args) >= 3:
            note = " ".join(args[2:])

        self.send_msg(chat_id, f"🔍 Checking <b>{ticker}</b>...")
        quote = self.engine.get_quote(ticker)
        if not quote:
            self.send_msg(chat_id, f"❌ Ticker <b>{ticker}</b> not found on Yahoo Finance. Please verify the symbol.")
            return

        if not has_explicit_direction:
            if target_price < quote.price:
                direction = "BELOW"
            else:
                direction = "ABOVE"

        alarm = self.alarm_manager.add_alarm(
            ticker=ticker,
            target_price=target_price,
            direction=direction,
            note=note,
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
        self.send_msg(chat_id, msg)

    def handle_list(self, chat_id: str) -> None:
        """List all configured stock alarms and their current states."""
        alarms = self.alarm_manager.get_alarms()
        if not alarms:
            self.send_msg(chat_id, "📭 You have no stock alarms set.\nSend <code>AAPL 340</code> to create one!")
            return

        lines = [f"📋 <b>Your Stock Alarms ({len(alarms)}):</b>\n"]
        for i, a in enumerate(alarms, 1):
            ticker = a["ticker"]
            target = a["target_price"]
            direction = a["direction"]
            status = "🚨 Triggered" if a.get("triggered") else ("Active 🟢" if a.get("active") else "Paused ⏸️")
            quote = self.engine.get_quote(ticker)
            price_str = f"${quote.price:.2f}" if quote else "N/A"
            lines.append(
                f"<b>{i}. {ticker}</b> — {direction} ${target:,.2f}\n"
                f"   Current: <b>{price_str}</b> | Status: {status}\n"
                f"   Delete: <code>/del {ticker}</code>\n"
            )

        self.send_msg(chat_id, "\n".join(lines))

    def handle_delete(self, chat_id: str, identifier: str) -> None:
        """Delete an alarm matching identifier by ID or ticker."""
        target = identifier.strip().upper()
        alarms = self.alarm_manager.get_alarms()
        deleted = False
        for a in alarms:
            if a.get("id", "").upper() == target or a.get("ticker", "").upper() == target:
                self.alarm_manager.delete_alarm(a["id"])
                self.send_msg(chat_id, f"🗑️ Deleted alarm for <b>{a['ticker']}</b> (${a['target_price']:.2f})")
                deleted = True
                break

        if not deleted:
            self.send_msg(
                chat_id,
                f"❌ No alarm found matching '<b>{identifier}</b>'. Use <code>/list</code> to view active alarms.",
            )
