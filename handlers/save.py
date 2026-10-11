"""
Saving songs to the database:
 1) Automatically when a new audio/file arrives in a channel (bot must be a channel admin)
 2) When an admin sends audio to the bot in PM or FORWARDS songs from a channel (for old songs)
"""
 
import asyncio
import logging
 
from telegram import Update
from telegram.ext import ContextTypes
 
import database as db
from config import ADMINS, CHANNELS
from utils import AUDIO_EXT, normalize, clean_title
 
logger = logging.getLogger(__name__)
 
 
def _extract(msg):
    """Extracts song info from a message. Returns None if it isn't a song."""
    caption = (msg.caption or "").strip()
    if msg.audio:
        a = msg.audio
        name = " - ".join(x for x in (a.performer, a.title) if x) or a.file_name or ""
        file_name, unique, file_id, size, kind = a.file_name or "", a.file_unique_id, a.file_id, a.file_size or 0, "audio"
    elif msg.document:
        d = msg.document
        fname = (d.file_name or "").lower()
        if not ((d.mime_type or "").startswith("audio/") or fname.endswith(AUDIO_EXT)):
            return None
        name, file_name, unique, file_id, size, kind = d.file_name or "", d.file_name or "", d.file_unique_id, d.file_id, d.file_size or 0, "document"
    else:
        return None
 
    if not name:
        name = caption.split("\n")[0][:80] or "Unknown song"
    title = clean_title(name)
    search = normalize(f"{title} {file_name} {caption[:100]}")
    return {
        "name": title,
        "search": search,
        "size": size,
        "kind": kind,
        "file_id": file_id,
        "unique": unique,
    }
 
 
def _source(msg):
    """Which channel and message the song lives in (for copy_message)."""
    if msg.chat.type == "channel":
        return msg.chat.id, msg.message_id
    origin = getattr(msg, "forward_origin", None)
    if origin is not None and getattr(origin, "type", "") == "channel":
        return origin.chat.id, origin.message_id
    return None, None
 
 
def _build_doc(msg):
    info = _extract(msg)
    if not info:
        return None
    src_chat, src_msg = _source(msg)
    doc_id = f"{abs(src_chat)}_{src_msg}" if src_chat else info["unique"]
    return {
        "_id": doc_id,
        "name": info["name"],
        "search": info["search"],
        "size": info["size"],
        "kind": info["kind"],
        "file_id": info["file_id"],
        "src_chat": src_chat,
        "src_msg": src_msg,
    }
 
 
def _channel_allowed(chat):
    if not CHANNELS:
        return True
    return chat.id in CHANNELS or (chat.username and f"@{chat.username}" in CHANNELS)
 
 
async def channel_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.channel_post
    if not msg or not _channel_allowed(msg.chat):
        return
    doc = _build_doc(msg)
    if not doc:
        return
    try:
        is_new = await asyncio.to_thread(db.save_song, doc)
        logger.info("channel song %s: %s", "saved" if is_new else "duplicate", doc["name"])
    except Exception as e:
        logger.exception("channel save failed: %s", e)
 
 
async def pm_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ADMINS only: songs sent or forwarded in PM get saved."""
    msg, user = update.effective_message, update.effective_user
    if not msg or not user or user.id not in ADMINS:
        return
    doc = _build_doc(msg)
    if not doc:
        return
    try:
        is_new = await asyncio.to_thread(db.save_song, doc)
    except Exception as e:
        logger.exception("pm save failed: %s", e)
        await msg.reply_text(f"⚠️ Not saved: {e}")
        return
    # Many songs can be forwarded at once, so react instead of replying with text (no spam)
    try:
        await msg.set_reaction("👍" if is_new else "👌")
    except Exception:
        pass
 
