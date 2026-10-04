import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class AppConfig:
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    phone: str = ""
    apikey: str = ""
    poll_interval: int = 60
    data_file: str = "alarms.json"

    @property
    def is_configured(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id) or bool(self.phone and self.apikey)

def load_config() -> AppConfig:
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    tg_chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    phone = os.getenv("CALLMEBOT_PHONE", "").strip()
    apikey = os.getenv("CALLMEBOT_APIKEY", "").strip()
    poll_interval_str = os.getenv("POLL_INTERVAL_SECONDS", "60").strip()
    data_file = os.getenv("DATA_FILE_PATH", "alarms.json").strip()
    
    try:
        poll_interval = int(poll_interval_str)
    except ValueError:
        poll_interval = 60
        
    return AppConfig(
        telegram_bot_token=tg_token,
        telegram_chat_id=tg_chat,
        phone=phone,
        apikey=apikey,
        poll_interval=poll_interval,
        data_file=data_file or "alarms.json"
    )
