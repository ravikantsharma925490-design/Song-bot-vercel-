"""/status (owner only) + group tracking so the group count is correct."""
 
import asyncio
import logging
import time
 
from telegram import Update
from telegram.ext import ContextTypes
 
import database as db
from config import ADMINS, STORAGE_LIMIT_MB
from utils import status_text, process_ram, cpu_load_percent
 
logger = logging.getLogger(__name__)
 
# Time this server instance started. On Vercel the instance restarts often,
# so uptime means "time since the current instance started".
_STARTED = time.time()
 
 
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user is None or user.id not in ADMINS:
        return
    users = await asyncio.to_thread(db.count_users)
    groups = await asyncio.to_thread(db.count_groups)
    files = await asyncio.to_thread(db.count_songs)
    used = await asyncio.to_thread(db.storage_used)
    rss, total = process_ram()
    text = status_text(
        users, groups, files, used, STORAGE_LIMIT_MB * 1024 * 1024,
        time.time() - _STARTED, rss, total, cpu_load_percent(),
    )
    await update.effective_message.reply_text(text)
 
 
async def track_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Runs on every group message (does not block other handlers): remembers the group."""
    chat = update.effective_chat
    if chat is None or chat.type not in ("group", "supergroup"):
        return
    try:
        await asyncio.to_thread(db.track_chat, chat.id, chat.title)
    except Exception as e:
        logger.warning("track_group failed: %s", e)
 
 
async def bot_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """When the bot is added to or removed from a group."""
    cmu = update.my_chat_member
    if cmu is None or cmu.chat.type not in ("group", "supergroup"):
        return
    try:
        if cmu.new_chat_member.status in ("member", "administrator"):
            await asyncio.to_thread(db.track_chat, cmu.chat.id, cmu.chat.title)
        else:
            await asyncio.to_thread(db.remove_chat, cmu.chat.id)
    except Exception as e:
        logger.warning("bot_membership failed: %s", e)
 
