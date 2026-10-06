"""
telegram_command_handler.py — Core Telegram Command Handler for TickerPing.
Encapsulates all command parsing, routing, button keyboards, and response formatting for both
local bots and cloud runners.
"""

import logging
from typing import Callable, List, Dict, Any, Optional

from engine import StockEngine
from alarms_manager import AlarmManager

logger = logging.getLogger(__name__)

MAIN_MENU_KEYBOARD: Dict[str, Any] = {
    "keyboard": [
        [{"text": "📋 My Alarms"}, {"text": "📈 Quick Quotes"}],
        [{"text": "➕ How to Set"}, {"text": "❓ Help"}]
    ],
    "resize_keyboard": True,
    "is_persistent": True
}


class TelegramCommandHandler:
    """Handles Telegram incoming updates, parses commands, and executes operations with button support."""

    def __init__(
        self,
        alarm_manager: AlarmManager,
        engine: StockEngine,
        send_msg_fn: Callable[..., None],
        answer_cb_fn: Optional[Callable[[str, Optional[str]], None]] = None,
    ) -> None:
        """
        Initialize the command handler.

        :param alarm_manager: AlarmManager instance for managing stored alarms.
        :param engine: StockEngine instance for querying stock market data.
        :param send_msg_fn: Callable accepting (chat_id, text, reply_markup=None) to transmit Telegram replies.
        :param answer_cb_fn: Optional callable accepting (callback_query_id, text=None) to acknowledge callback queries.
        """
        self.alarm_manager = alarm_manager
        self.engine = engine
        self.send_msg = send_msg_fn
        self.answer_cb = answer_cb_fn

    def _send(self, chat_id: str, text: str, reply_markup: Optional[Dict[str, Any]] = None) -> None:
        """Helper to invoke send_msg with or without reply_markup gracefully."""
        try:
            self.send_msg(chat_id, text, reply_markup=reply_markup)
        except TypeError:
            self.send_msg(chat_id, text)

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

        # Handle persistent menu buttons or commands
        if text in ("📋 My Alarms", "📋 my alarms") or cmd in ("/list", "/alarms", "list", "alarms"):
            self.handle_list(chat_id)
        elif text in ("📈 Quick Quotes", "📈 quick quotes", "quotes", "quick quotes"):
            self.handle_quick_quotes(chat_id)
        elif text in ("➕ How to Set", "➕ how to set") or cmd in ("/how", "how"):
            self.handle_how_to_set(chat_id)
        elif text in ("❓ Help", "❓ help") or cmd in ("/start", "/help", "help"):
            self.handle_start(chat_id)
        elif cmd in ("/set", "/add", "add", "set"):
            self.handle_set(chat_id, tokens[1:])
        elif cmd in ("/del", "/delete", "/rm", "del", "delete"):
            if len(tokens) > 1:
                self.handle_delete(chat_id, tokens[1])
            else:
                self._send(chat_id, "⚠️ Specify what to delete, e.g.: <code>/del AAPL</code>", reply_markup=MAIN_MENU_KEYBOARD)
        elif cmd in ("/price", "/quote", "price", "quote"):
            if len(tokens) > 1:
                self.handle_price(chat_id, tokens[1])
            else:
                self._send(chat_id, "⚠️ Specify a ticker, e.g.: <code>/price AAPL</code>", reply_markup=MAIN_MENU_KEYBOARD)
        elif cmd in ("/check", "check"):
            self._send(chat_id, "⏰ Alarms are monitored and checked automatically 24/7 in the cloud!", reply_markup=MAIN_MENU_KEYBOARD)
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
                self._send(
                    chat_id,
                    "❓ Unknown command. Tap <b>📋 My Alarms</b> below or send <code>AAPL 340</code> to set an alert.",
                    reply_markup=MAIN_MENU_KEYBOARD,
                )

        return True

    def handle_callback_query(self, query: Dict[str, Any]) -> bool:
        """
        Process an inline button callback query from Telegram.

        :param query: Dict representing a CallbackQuery object.
        :return: True if handled successfully, False otherwise.
        """
        if not isinstance(query, dict):
            return False

        query_id = query.get("id")
        data = query.get("data", "")
        message = query.get("message", {})
        chat = message.get("chat", {})
        chat_id = str(chat.get("id", ""))

        if not query_id or not data:
            return False

        if data.startswith("del:"):
            alarm_id = data.split(":", 1)[1].strip()
            alarms = self.alarm_manager.get_alarms()
            deleted = False
            deleted_ticker = "Alarm"

            for a in alarms:
                if a.get("id") == alarm_id or a.get("ticker", "").upper() == alarm_id.upper():
                    deleted_ticker = a.get("ticker", "Alarm")
                    self.alarm_manager.delete_alarm(a["id"])
                    deleted = True
                    break

            if deleted:
                if self.answer_cb:
                    self.answer_cb(query_id, f"🗑️ Deleted {deleted_ticker}!")
                if chat_id:
                    self._send(chat_id, f"🗑️ Deleted alarm for <b>{deleted_ticker}</b>.", reply_markup=MAIN_MENU_KEYBOARD)
            else:
                if self.answer_cb:
                    self.answer_cb(query_id, "Alarm already deleted.")
            return True

        if self.answer_cb:
            self.answer_cb(query_id, None)
        return True

    def handle_start(self, chat_id: str) -> None:
        """Send welcome message and command documentation with persistent bottom menu keyboard."""
        msg = (
            "📈 <b>Welcome to TickerPing!</b>\n\n"
            "Use the quick menu buttons below or send stock commands directly:\n\n"
            "<b>➕ Add Alarm:</b>\n"
            "• <code>AAPL 340</code> <i>(smart target)</i>\n"
            "• <code>/set TSLA 210 BELOW</code>\n"
            "• <code>/set NVDA 140 ABOVE Breakout</code>\n\n"
            "<b>⚡ Quick Actions:</b>\n"
            "Tap <b>📋 My Alarms</b> below to manage your active triggers."
        )
        self._send(chat_id, msg, reply_markup=MAIN_MENU_KEYBOARD)

    def handle_how_to_set(self, chat_id: str) -> None:
        """Send interactive instructions on setting stock alarms."""
        msg = (
            "➕ <b>How to Set a Stock Alarm</b>\n\n"
            "Simply send the ticker and target price in the chat:\n\n"
            "• <code>AAPL 350</code> — Alerts if Apple rises to $350\n"
            "• <code>TSLA 200 BELOW</code> — Alerts if Tesla drops below $200\n"
            "• <code>NVDA 135 ABOVE Dip buy</code> — Add an optional note\n\n"
            "<i>💡 Tip: If you don't specify ABOVE or BELOW, TickerPing picks the right direction automatically based on current price!</i>"
        )
        self._send(chat_id, msg, reply_markup=MAIN_MENU_KEYBOARD)

    def handle_quick_quotes(self, chat_id: str) -> None:
        """Fetch and send quick quotes for popular market tickers."""
        tickers = ["AAPL", "NVDA", "TSLA", "SPY"]
        lines = ["📈 <b>Market Quick Quotes:</b>\n"]

        for t in tickers:
            quote = self.engine.get_quote(t)
            if quote:
                sign = "+" if quote.change_percent >= 0 else ""
                lines.append(f"• <b>{t}:</b> ${quote.price:,.2f} ({sign}{quote.change_percent:.2f}%)")
            else:
                lines.append(f"• <b>{t}:</b> Quote unavailable")

        lines.append("\n<i>Send <code>/price TICKER</code> for any stock quote.</i>")
        self._send(chat_id, "\n".join(lines), reply_markup=MAIN_MENU_KEYBOARD)

    def handle_price(self, chat_id: str, ticker: str) -> None:
        """Fetch and send the current live stock quote for a ticker."""
        clean = ticker.strip().upper()
        quote = self.engine.get_quote(clean)
        if not quote:
            self._send(chat_id, f"❌ Could not find quote for <b>{clean}</b>. Please check the ticker symbol.", reply_markup=MAIN_MENU_KEYBOARD)
            return

        sign = "+" if quote.change_percent >= 0 else ""
        msg = (
            f"📊 <b>{quote.symbol} Live Quote</b>\n\n"
            f"💰 <b>Price:</b> ${quote.price:,.2f} {quote.currency}\n"
            f"📈 <b>Session Change:</b> {sign}{quote.change_percent:.2f}%\n"
            f"🏁 <b>Previous Close:</b> ${quote.previous_close:,.2f}"
        )
        self._send(chat_id, msg, reply_markup=MAIN_MENU_KEYBOARD)

    def handle_set(self, chat_id: str, args: List[str]) -> None:
        """Parse arguments, validate ticker with Yahoo Finance, and register a new alarm."""
        if len(args) < 2:
            self._send(
                chat_id,
                "⚠️ Usage: <code>/set TICKER TARGET_PRICE [ABOVE/BELOW] [NOTE]</code>\nExample: <code>AAPL 340</code>",
                reply_markup=MAIN_MENU_KEYBOARD
            )
            return

        ticker = args[0].strip().upper()
        try:
            target_price = float(args[1].replace("$", ""))
        except ValueError:
            self._send(chat_id, f"❌ Invalid target price: '<b>{args[1]}</b>'. Must be a number like 250.50", reply_markup=MAIN_MENU_KEYBOARD)
            return

        direction = "ABOVE"
        note = ""

        if len(args) >= 3 and args[2].upper() in ("ABOVE", "BELOW"):
            direction = args[2].upper()
            if len(args) >= 4:
                note = " ".join(args[3:])
        elif len(args) >= 3:
            note = " ".join(args[2:])

        self._send(chat_id, f"🔍 Checking <b>{ticker}</b>...")
        quote = self.engine.get_quote(ticker)
        if not quote:
            self._send(chat_id, f"❌ Ticker <b>{ticker}</b> not found on Yahoo Finance. Please verify the symbol.", reply_markup=MAIN_MENU_KEYBOARD)
            return

        if len(args) < 3 or args[2].upper() not in ("ABOVE", "BELOW"):
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
        self._send(chat_id, msg, reply_markup=MAIN_MENU_KEYBOARD)

    def handle_list(self, chat_id: str) -> None:
        """List all configured stock alarms with inline 1-tap delete buttons."""
        alarms = self.alarm_manager.get_alarms()
        if not alarms:
            self._send(
                chat_id,
                "📭 You have no stock alarms set.\nSend <code>AAPL 340</code> to create your first alert!",
                reply_markup=MAIN_MENU_KEYBOARD,
            )
            return

        lines = [f"📋 <b>Your Stock Alarms ({len(alarms)}):</b>\n"]
        inline_keyboard = []

        for i, a in enumerate(alarms, 1):
            ticker = a["ticker"]
            target = a["target_price"]
            direction = a["direction"]
            status = "🚨 Triggered" if a.get("triggered") else ("Active 🟢" if a.get("active") else "Paused ⏸️")

            quote = self.engine.get_quote(ticker)
            price_str = f"${quote.price:.2f}" if quote else "N/A"

            lines.append(
                f"<b>{i}. {ticker}</b> — {direction} ${target:,.2f}\n"
                f"   Current: <b>{price_str}</b> | Status: {status}"
            )
            inline_keyboard.append([
                {"text": f"🗑️ Delete {ticker}", "callback_data": f"del:{a['id']}"},
                {"text": f"🌐 {ticker} Chart", "url": f"https://finance.yahoo.com/quote/{ticker}"}
            ])

        reply_markup = {"inline_keyboard": inline_keyboard} if inline_keyboard else MAIN_MENU_KEYBOARD
        self._send(chat_id, "\n".join(lines), reply_markup=reply_markup)

    def handle_delete(self, chat_id: str, identifier: str) -> None:
        """Delete an existing alarm by UUID ID or ticker symbol."""
        target = identifier.strip().upper()
        alarms = self.alarm_manager.get_alarms()
        deleted = False

        for a in alarms:
            if a["id"].upper() == target or a["ticker"].upper() == target:
                self.alarm_manager.delete_alarm(a["id"])
                self._send(chat_id, f"🗑️ Deleted alarm for <b>{a['ticker']}</b> (${a['target_price']:.2f}).", reply_markup=MAIN_MENU_KEYBOARD)
                deleted = True
                break

        if not deleted:
            self._send(chat_id, f"❌ No alarm found matching '<b>{identifier}</b>'. Tap <b>📋 My Alarms</b> to check active IDs.", reply_markup=MAIN_MENU_KEYBOARD)
