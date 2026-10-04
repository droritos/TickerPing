import urllib.parse
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
import logging
import requests

from chart import generate_stock_chart

logger = logging.getLogger(__name__)

class BaseNotifier(ABC):
    @abstractmethod
    def send_alert(
        self,
        ticker: str,
        current_price: float,
        target_price: float,
        direction: str,
        change_percent: float = 0.0,
        currency: str = "USD",
        note: str = ""
    ) -> bool:
        pass

    @abstractmethod
    def send_raw_message(self, message: str) -> bool:
        pass


class TelegramNotifier(BaseNotifier):
    """Official Telegram Bot API Notifier (100% Free & Unlimited)"""
    BASE_URL = "https://api.telegram.org/bot"

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token.strip()
        self.chat_id = chat_id.strip()

    @staticmethod
    def detect_chat_id(bot_token: str) -> Optional[dict]:
        """Queries getUpdates to automatically discover the user's chat_id after they message /start to the bot."""
        if not bot_token:
            return None
        url = f"https://api.telegram.org/bot{bot_token.strip()}/getUpdates"
        try:
            res = requests.get(url, timeout=10)
            data = res.json()
            if data.get("ok") and data.get("result"):
                for update in reversed(data["result"]):
                    msg = update.get("message") or update.get("my_chat_member")
                    if msg and "chat" in msg:
                        chat = msg["chat"]
                        return {
                            "chat_id": str(chat.get("id")),
                            "username": chat.get("username", ""),
                            "first_name": chat.get("first_name", "")
                        }
            return None
        except Exception as e:
            logger.error(f"Failed to detect Telegram chat ID: {e}")
            return None

    def send_raw_message(self, message: str) -> bool:
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram bot credentials missing.")
            return False

        url = f"{self.BASE_URL}{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        try:
            res = requests.post(url, json=payload, timeout=15)
            return res.status_code == 200 and res.json().get("ok", False)
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    def send_photo(self, photo_bytes: bytes, caption: str) -> bool:
        if not self.bot_token or not self.chat_id:
            return False
        url = f"{self.BASE_URL}{self.bot_token}/sendPhoto"
        try:
            res = requests.post(
                url,
                data={"chat_id": self.chat_id, "caption": caption, "parse_mode": "HTML"},
                files={"photo": ("chart.png", photo_bytes, "image/png")},
                timeout=20
            )
            return res.status_code == 200 and res.json().get("ok", False)
        except Exception as e:
            logger.error(f"Failed to send Telegram photo: {e}")
            return False

    def send_alert(
        self,
        ticker: str,
        current_price: float,
        target_price: float,
        direction: str,
        change_percent: float = 0.0,
        currency: str = "USD",
        note: str = ""
    ) -> bool:
        sign = "+" if change_percent > 0 else ""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        msg = (
            f"🚨 <b>TickerPing Stock Alert!</b>\n\n"
            f"📈 <b>Symbol:</b> <code>{ticker.upper()}</code>\n"
            f"💰 <b>Current Price:</b> <b>${current_price:,.2f} {currency}</b>\n"
            f"🎯 <b>Condition:</b> {direction.upper()} ${target_price:,.2f}\n"
            f"📊 <b>Session Change:</b> {sign}{change_percent:.2f}%\n"
        )
        if note:
            msg += f"📝 <b>Note:</b> {note}\n"
        msg += f"⏰ <b>Time:</b> {now_str}"

        # Try sending with visual chart first
        try:
            chart_bytes = generate_stock_chart(ticker=ticker, target_price=target_price)
            if chart_bytes:
                sent = self.send_photo(photo_bytes=chart_bytes, caption=msg)
                if sent:
                    return True
        except Exception as e:
            logger.warning(f"Could not generate/send chart for {ticker}: {e}")

        # Fallback to text message
        return self.send_raw_message(msg)


class CallMeBotWhatsAppNotifier(BaseNotifier):
    BASE_URL = "https://api.callmebot.com/whatsapp.php"

    def __init__(self, phone: str, apikey: str):
        self.phone = phone.strip()
        self.apikey = apikey.strip()

    def send_raw_message(self, message: str) -> bool:
        if not self.phone or not self.apikey:
            return False

        try:
            params = {
                "phone": self.phone,
                "text": message,
                "apikey": self.apikey
            }
            url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"
            response = requests.get(url, timeout=15)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send CallMeBot message: {e}")
            return False

    def send_alert(
        self,
        ticker: str,
        current_price: float,
        target_price: float,
        direction: str,
        change_percent: float = 0.0,
        currency: str = "USD",
        note: str = ""
    ) -> bool:
        sign = "+" if change_percent > 0 else ""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        msg_lines = [
            "🚨 *TickerPing Stock Alert!*",
            f"📈 *Symbol:* {ticker.upper()}",
            f"💰 *Current Price:* ${current_price:,.2f} {currency}",
            f"🎯 *Trigger:* {direction.upper()} ${target_price:,.2f}",
            f"📊 *Session Change:* {sign}{change_percent:.2f}%"
        ]
        if note:
            msg_lines.append(f"📝 *Note:* {note}")
        msg_lines.append(f"⏰ *Time:* {now_str}")

        return self.send_raw_message("\n".join(msg_lines))


class ConsoleNotifier(BaseNotifier):
    def send_raw_message(self, message: str) -> bool:
        print(f"\n[ALERT NOTIFICATION]\n{message}\n")
        return True

    def send_alert(
        self,
        ticker: str,
        current_price: float,
        target_price: float,
        direction: str,
        change_percent: float = 0.0,
        currency: str = "USD",
        note: str = ""
    ) -> bool:
        msg = f"[ALERT] {ticker}: ${current_price:.2f} reached {direction} ${target_price:.2f} ({change_percent:+.2f}%) | {note}"
        return self.send_raw_message(msg)


def create_notifier_from_config(cfg) -> BaseNotifier:
    if cfg.telegram_bot_token and cfg.telegram_chat_id:
        return TelegramNotifier(bot_token=cfg.telegram_bot_token, chat_id=cfg.telegram_chat_id)
    elif cfg.phone and cfg.apikey:
        return CallMeBotWhatsAppNotifier(phone=cfg.phone, apikey=cfg.apikey)
    return ConsoleNotifier()
