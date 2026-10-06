import os
import asyncio
import threading
import time
import logging
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import requests

from config import load_config
from engine import StockEngine, evaluate_alarm
from notifier import TelegramNotifier, CallMeBotWhatsAppNotifier, create_notifier_from_config
from alarms_manager import AlarmManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TickerPing")

config = load_config()
alarm_manager = AlarmManager(storage_path=config.data_file)
engine = StockEngine()

# --- Price Poller ---
async def poll_alarms_cycle():
    cfg = load_config()
    alarms = alarm_manager.get_alarms()
    notifier = create_notifier_from_config(cfg)

    for alarm in alarms:
        if not alarm.get("active", True) or alarm.get("triggered", False):
            continue

        ticker = alarm.get("ticker", "")
        target = alarm.get("target_price", 0.0)
        direction = alarm.get("direction", "ABOVE")
        note = alarm.get("note", "")

        quote = engine.get_quote(ticker)
        if not quote:
            continue

        if evaluate_alarm(current_price=quote.price, target_price=target, direction=direction):
            logger.info(f"🚨 ALARM TRIGGERED: {ticker} hit {quote.price} (Target: {direction} {target})")
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

async def poller_worker():
    while True:
        try:
            await poll_alarms_cycle()
        except Exception as e:
            logger.error(f"Error in poller cycle: {e}")
        
        cfg = load_config()
        await asyncio.sleep(cfg.poll_interval)

# --- Telegram 2-Way Bot Thread ---
def telegram_listener_thread():
    from telegram_bot import run_bot
    try:
        run_bot()
    except Exception as e:
        logger.error(f"Telegram listener error: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Poller worker for local web dashboard
    poller_task = asyncio.create_task(poller_worker())
    yield
    poller_task.cancel()

app = FastAPI(title="TickerPing", lifespan=lifespan)

# Request Models
class CreateAlarmRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10)
    target_price: float = Field(..., gt=0)
    direction: str = Field(default="ABOVE")
    note: Optional[str] = ""

class TestTelegramRequest(BaseModel):
    bot_token: str
    chat_id: str

class DetectTelegramChatRequest(BaseModel):
    bot_token: str

class SaveSettingsRequest(BaseModel):
    telegram_bot_token: Optional[str] = ""
    telegram_chat_id: Optional[str] = ""
    phone: Optional[str] = ""
    apikey: Optional[str] = ""
    poll_interval: Optional[int] = 60

@app.get("/api/status")
@app.get("/health")
def get_status():
    cfg = load_config()
    channel = "None"
    if cfg.telegram_bot_token and cfg.telegram_chat_id:
        channel = "Telegram"
    elif cfg.phone and cfg.apikey:
        channel = "WhatsApp"
    return {
        "status": "ok",
        "configured": cfg.is_configured,
        "channel": channel,
        "poll_interval": cfg.poll_interval,
        "storage": cfg.data_file
    }

@app.get("/api/settings")
def get_settings():
    cfg = load_config()
    masked_tg = (cfg.telegram_bot_token[:6] + "..." + cfg.telegram_bot_token[-4:]) if len(cfg.telegram_bot_token) > 10 else ""
    return {
        "telegram_bot_token_masked": masked_tg,
        "telegram_chat_id": cfg.telegram_chat_id,
        "phone": cfg.phone,
        "is_configured": cfg.is_configured,
        "poll_interval": cfg.poll_interval
    }

@app.post("/api/settings")
def save_settings(req: SaveSettingsRequest):
    env_lines = [
        f"TELEGRAM_BOT_TOKEN={req.telegram_bot_token.strip() if req.telegram_bot_token else os.getenv('TELEGRAM_BOT_TOKEN', '')}",
        f"TELEGRAM_CHAT_ID={req.telegram_chat_id.strip() if req.telegram_chat_id else os.getenv('TELEGRAM_CHAT_ID', '')}",
        f"CALLMEBOT_PHONE={req.phone.strip() if req.phone else os.getenv('CALLMEBOT_PHONE', '')}",
        f"CALLMEBOT_APIKEY={req.apikey.strip() if req.apikey else os.getenv('CALLMEBOT_APIKEY', '')}",
        f"POLL_INTERVAL_SECONDS={req.poll_interval or 60}",
        "DATA_FILE_PATH=alarms.json"
    ]
    try:
        with open(".env", "w", encoding="utf-8") as f:
            f.write("\n".join(env_lines) + "\n")
        
        for line in env_lines:
            k, v = line.split("=", 1)
            os.environ[k] = v
        return {"success": True, "message": "Settings saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/telegram/detect-chat-id")
def detect_telegram_chat(req: DetectTelegramChatRequest):
    info = TelegramNotifier.detect_chat_id(req.bot_token)
    if not info:
        raise HTTPException(status_code=404, detail="No messages found yet. Please send /start or any message to your bot in Telegram first, then try again.")
    return info

@app.post("/api/test-telegram")
def test_telegram(req: TestTelegramRequest):
    notifier = TelegramNotifier(bot_token=req.bot_token, chat_id=req.chat_id)
    msg = "🚀 <b>TickerPing Test Alert!</b>\nYour Telegram notifications are active and ready!"
    success = notifier.send_raw_message(msg)
    if not success:
        raise HTTPException(status_code=502, detail="Failed to send message to Telegram. Check Bot Token and Chat ID.")
    return {"success": True, "message": "Telegram test alert sent successfully! Check your Telegram app."}

class TestWhatsAppRequest(BaseModel):
    phone: Optional[str] = None
    apikey: Optional[str] = None

@app.post("/api/test-whatsapp")
def test_whatsapp(req: TestWhatsAppRequest):
    cfg = load_config()
    phone = req.phone or cfg.phone
    apikey = req.apikey or cfg.apikey
    if not phone or not apikey:
        raise HTTPException(status_code=400, detail="Phone number and CallMeBot API key are required.")

    notifier = CallMeBotWhatsAppNotifier(phone=phone, apikey=apikey)
    msg = "🚀 *TickerPing Test Alert!*\nYour WhatsApp notifications are working!"
    success = notifier.send_raw_message(msg)
    if not success:
        raise HTTPException(status_code=502, detail="Failed to send test message via CallMeBot.")
    return {"success": True, "message": "WhatsApp test message sent successfully!"}

@app.get("/api/alarms")
def list_alarms():
    alarms = alarm_manager.get_alarms()
    result = []
    for a in alarms:
        item = dict(a)
        quote = engine.get_quote(a.get("ticker", ""))
        if quote:
            item["current_price"] = quote.price
            item["change_percent"] = quote.change_percent
            item["currency"] = quote.currency
            target = a.get("target_price", 0.0)
            if target > 0:
                item["diff_percent"] = round(((quote.price - target) / target) * 100, 2)
            else:
                item["diff_percent"] = 0.0
        else:
            item["current_price"] = None
            item["change_percent"] = None
            item["currency"] = "USD"
            item["diff_percent"] = None
        result.append(item)
    return result

@app.post("/api/alarms")
def create_alarm(req: CreateAlarmRequest):
    quote = engine.get_quote(req.ticker)
    if not quote:
        raise HTTPException(status_code=400, detail=f"Invalid ticker '{req.ticker}'. Quote could not be found.")

    alarm = alarm_manager.add_alarm(
        ticker=req.ticker,
        target_price=req.target_price,
        direction=req.direction,
        note=req.note or ""
    )
    return alarm

@app.delete("/api/alarms/{alarm_id}")
def delete_alarm(alarm_id: str):
    success = alarm_manager.delete_alarm(alarm_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alarm not found")
    return {"success": True}

@app.post("/api/alarms/{alarm_id}/toggle")
def toggle_alarm(alarm_id: str):
    success = alarm_manager.toggle_active(alarm_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alarm not found")
    return {"success": True}

@app.post("/api/alarms/{alarm_id}/reset")
def reset_alarm(alarm_id: str):
    success = alarm_manager.reset_alarm(alarm_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alarm not found")
    return {"success": True}

# Static files for UI
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def serve_index():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "TickerPing API running"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
