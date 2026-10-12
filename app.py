import os

from fastapi import FastAPI, Request, Header, HTTPException
from telegram import Update

import database as db
from main import build_application, _post_init
from handlers.common import send_log
from config import BOT_NAME, BOT_VERSION
from utils import restart_text

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

db.init_db()
tg = build_application()
app = FastAPI()
_ready = False


async def _ensure_ready():
    global _ready
    if not _ready:
        await tg.initialize()
        _ready = True


@app.get("/")
def home():
    return {"status": "ok"}


@app.post("/api/webhook")
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None),
):
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=403)
    await _ensure_ready()
    update = Update.de_json(await request.json(), tg.bot)
    await tg.process_update(update)
    return {"ok": True}


@app.get("/api/setup")
async def setup(request: Request, key: str = ""):
    """Open once in a browser: sets the webhook and commands."""
    if not WEBHOOK_SECRET or key != WEBHOOK_SECRET:
        raise HTTPException(status_code=403)
    await _ensure_ready()
    host = request.headers.get("x-forwarded-host") or request.url.hostname
    url = f"https://{host}/api/webhook"
    await tg.bot.set_webhook(
        url=url,
        secret_token=WEBHOOK_SECRET,
        allowed_updates=Update.ALL_TYPES,
    )
    await _post_init(tg)
    await send_log(tg.bot, restart_text(BOT_NAME, BOT_VERSION))  # "Bot Restarted" message in LOG_CHANNEL
    return {"webhook": url, "commands": "set"}
