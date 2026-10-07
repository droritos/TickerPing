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
            self.handle_help(chat_id)
        elif cmd in ("/menu", "menu", "/buttons", "buttons"):
            self._send(chat_id, "🔘 <b>Menu buttons refreshed!</b> Tap any button below to proceed:", reply_markup=MAIN_MENU_KEYBOARD)
        elif cmd in ("/set", "/add", "add", "set"):
            self.handle_set(chat_id, tokens[1:])
        elif cmd in ("/del", "/delete", "/rm", "del", "delete"):
            if len(tokens) > 1:
                self.handle_delete(chat_id, tokens[1])
            else:
                self._send(chat_id, "⚠️ Specify what to delete, e.g.: <code>/del AAPL</code>", reply_markup=MAIN_MENU_KEYBOARD)
        elif cmd in ("/clear", "clear", "/cleanup", "cleanup"):
            self.handle_clear_triggered(chat_id)
        elif cmd in ("/price", "/quote", "price", "quote"):
            if len(tokens) > 1:
                self.handle_price(chat_id, tokens[1])
            else:
                self._send(chat_id, "⚠️ Specify a ticker, e.g.: <code>/price AAPL</code>", reply_markup=MAIN_MENU_KEYBOARD)
        elif cmd in ("/news", "news"):
            if len(tokens) > 1:
                self.handle_news(chat_id, tokens[1])
            else:
                self._send(chat_id, "⚠️ Usage: Specify a ticker, e.g.: <code>/news AAPL</code>", reply_markup=MAIN_MENU_KEYBOARD)
        elif cmd in ("/earnings", "earnings"):
            if len(tokens) > 1:
                self.handle_earnings(chat_id, tokens[1])
            else:
                self._send(chat_id, "⚠️ Usage: Specify a ticker, e.g.: <code>/earnings AAPL</code>", reply_markup=MAIN_MENU_KEYBOARD)
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

        elif data.startswith("rearm:"):
            # Format: rearm:<ticker>:<price>:<direction>
            parts = data.split(":")
            if len(parts) >= 4:
                ticker = parts[1].strip().upper()
                try:
                    target_price = float(parts[2].replace("$", "").strip())
                except ValueError:
                    if self.answer_cb:
                        self.answer_cb(query_id, "Invalid price.")
                    return True

                direction = parts[3].strip().upper()
                if direction not in ("ABOVE", "BELOW"):
                    direction = "ABOVE"

                # Clean up any previously triggered alarms for this ticker
                for old in self.alarm_manager.get_alarms():
                    if old.get("ticker", "").upper() == ticker and old.get("triggered", False):
                        self.alarm_manager.delete_alarm(old["id"])

                alarm = self.alarm_manager.add_alarm(
                    ticker=ticker,
                    target_price=target_price,
                    direction=direction,
                    note="Re-armed alert",
                )

                if self.answer_cb:
                    self.answer_cb(query_id, f"🎯 Re-armed {ticker} at ${target_price:,.2f}!")
                if chat_id:
                    self._send(
                        chat_id,
                        f"🎯 <b>Alarm Re-armed!</b>\n\n"
                        f"Alert set for <b>{ticker}</b> when price is <b>{direction} ${target_price:,.2f}</b>.\n"
                        f"🆔 <b>ID:</b> <code>{alarm['id']}</code>",
                        reply_markup=MAIN_MENU_KEYBOARD,
                    )
            return True

        elif data.startswith("news:"):
            # Format: news:<ticker>
            parts = data.split(":", 1)
            ticker = parts[1].strip().upper() if len(parts) > 1 else ""
            if self.answer_cb:
                self.answer_cb(query_id, f"📰 Loading news for {ticker}...")
            if chat_id and ticker:
                self.handle_news(chat_id, ticker)
            return True

        if self.answer_cb:
            self.answer_cb(query_id, None)
        return True

    def handle_start(self, chat_id: str) -> None:
        """Send welcome message and command documentation with persistent bottom menu keyboard."""
        self.handle_help(chat_id)

    def handle_help(self, chat_id: str) -> None:
        """Send welcome message and command documentation with persistent bottom menu keyboard."""
        msg = (
            "📈 <b>Welcome to TickerPing!</b>\n\n"
            "Use the quick menu buttons below or send stock commands directly:\n\n"
            "<b>➕ Add Alarm:</b>\n"
            "• <code>AAPL 340</code> <i>(smart target)</i>\n"
            "• <code>/set TSLA 210 BELOW</code>\n"
            "• <code>/set NVDA 140 ABOVE Breakout</code>\n\n"
            "<b>📊 Quotes & Market Data:</b>\n"
            "• <code>/price AAPL</code> — Live stock quote\n"
            "• <code>/news NVDA</code> — Latest top headlines\n"
            "• <code>/earnings MSFT</code> — Next earnings date & EPS estimate\n\n"
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

    def handle_news(self, chat_id: str, ticker: str) -> None:
        """Fetch and send the latest top news headlines with clickable links for a ticker."""
        clean = ticker.strip().replace("$", "").upper()
        if not clean:
            self._send(chat_id, "⚠️ Usage: Specify a ticker, e.g.: <code>/news AAPL</code>", reply_markup=MAIN_MENU_KEYBOARD)
            return

        articles = self.engine.get_news(clean, limit=3)
        if not articles:
            self._send(chat_id, f"📰 No recent headlines found for <b>{clean}</b>.", reply_markup=MAIN_MENU_KEYBOARD)
            return

        lines = [f"📰 <b>Latest News for {clean}:</b>\n"]
        for i, item in enumerate(articles, 1):
            title = item.get("title", "").strip()
            link = item.get("link", "").strip()
            publisher = item.get("publisher", "Yahoo Finance").strip() or "Yahoo Finance"
            if link:
                lines.append(f"{i}. <a href=\"{link}\">{title}</a> <i>({publisher})</i>")
            else:
                lines.append(f"{i}. <b>{title}</b> <i>({publisher})</i>")

        self._send(chat_id, "\n\n".join(lines), reply_markup=MAIN_MENU_KEYBOARD)

    def handle_earnings(self, chat_id: str, ticker: str) -> None:
        """Fetch and send upcoming earnings report date and EPS estimate for a ticker."""
        clean = ticker.strip().replace("$", "").upper()
        if not clean:
            self._send(chat_id, "⚠️ Usage: Specify a ticker, e.g.: <code>/earnings AAPL</code>", reply_markup=MAIN_MENU_KEYBOARD)
            return

        info = self.engine.get_earnings_info(clean)
        if not info:
            self._send(chat_id, f"📅 No upcoming earnings date announced yet for <b>{clean}</b>.", reply_markup=MAIN_MENU_KEYBOARD)
            return

        date_str = info.get("date_str", "N/A")
        days = info.get("days_until", 0)
        eps = info.get("eps_estimate")
        eps_str = f"${eps:.2f}" if eps is not None else "N/A"

        days_text = f"in {days} days" if days > 0 else "today"

        msg = (
            f"📅 <b>{clean} Upcoming Earnings</b>\n\n"
            f"🗓️ <b>Report Date:</b> {date_str} ({days_text})\n"
            f"⏳ <b>Countdown:</b> {days} days\n"
            f"💵 <b>Est. EPS:</b> {eps_str}"
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

        # Clean up any previously triggered alarms for this ticker
        for old in self.alarm_manager.get_alarms():
            if old.get("ticker", "").upper() == ticker and old.get("triggered", False):
                self.alarm_manager.delete_alarm(old["id"])

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

    def handle_clear_triggered(self, chat_id: str) -> None:
        """Clear all triggered/expired alarms."""
        cleared = self.alarm_manager.clear_triggered()
        if cleared > 0:
            plural = f"{cleared} triggered alarms" if cleared > 1 else "1 triggered alarm"
            self._send(chat_id, f"🧹 Cleared {plural}!", reply_markup=MAIN_MENU_KEYBOARD)
        else:
            self._send(chat_id, "✨ No triggered alarms to clear.", reply_markup=MAIN_MENU_KEYBOARD)

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
        """Delete an existing alarm by UUID ID or all alarms matching a ticker symbol."""
        target = identifier.strip().upper()

        # 1. Check if identifier is an exact alarm ID
        alarm = self.alarm_manager.get_alarm(target)
        if alarm:
            ticker = alarm.get("ticker", target)
            self.alarm_manager.delete_alarm(target)
            self._send(chat_id, f"🗑️ Deleted alarm for <b>{ticker}</b> (${alarm['target_price']:.2f}).", reply_markup=MAIN_MENU_KEYBOARD)
            return

        # 2. Otherwise delete all alarms matching ticker
        deleted_count = self.alarm_manager.delete_by_ticker(target)
        if deleted_count > 0:
            plural = f"{deleted_count} alarms" if deleted_count > 1 else "alarm"
            self._send(chat_id, f"🗑️ Deleted {plural} for <b>{target}</b>.", reply_markup=MAIN_MENU_KEYBOARD)
        else:
            self._send(chat_id, f"❌ No alarm found matching '<b>{identifier}</b>'. Tap <b>📋 My Alarms</b> to check active IDs.", reply_markup=MAIN_MENU_KEYBOARD)
