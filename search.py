"""Song search (group + private), pagination, and the song download button."""
 
import asyncio
import html
import logging
 
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes
 
import database as db
from config import PAGE_SIZE, GROUP_SEARCH, PLAY_NEEDS_MENTION, ACTIVITY_LOG_CHANNEL
from utils import normalize, human_size, clip, pick_best, play_query, activity_text
from handlers.common import send_song, fsub_gate, send_activity
 
logger = logging.getLogger(__name__)
 
 
def _build_results(items, total, qid, page, query_text, in_group):
    rows = []
    for s in items:
        label = f"🎵 {human_size(s.get('size'))} • {clip(s.get('name'), 48)}"
        rows.append([InlineKeyboardButton(label, callback_data=f"d|{s['_id']}")])
 
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"p|{qid}|{page - 1}"))
        nav.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
        if page + 1 < total_pages:
            nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"p|{qid}|{page + 1}"))
        rows.append(nav)
 
    shown = f"{total}+" if total >= 500 else str(total)
    text = f"🎧 <b>{shown}</b> songs found: <i>{html.escape(clip(query_text, 60))}</i>"
    if in_group:
        text += "\n\n👇 Tap a song and it will be sent right here in the group."
    return text, InlineKeyboardMarkup(rows)
 
 
async def _request_markup(text, user_id):
    """'Request this song' button for not-found replies (only if ACTIVITY_LOG_CHANNEL is set)."""
    if not ACTIVITY_LOG_CHANNEL:
        return None
    qid = await asyncio.to_thread(db.make_query, text, user_id)
    return InlineKeyboardMarkup([[InlineKeyboardButton("📩 Request this song", callback_data=f"r|{qid}")]])
 
 
async def search_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, user, chat = update.effective_message, update.effective_user, update.effective_chat
    if not msg or not msg.text or not user or user.is_bot:
        return
 
    is_group = chat.type in ("group", "supergroup")
 
    # If written as "@Bot /play song name", handle it like /play
    if "/play" in msg.text.lower() and play_query(msg.text, context.bot.username) is not None:
        parsed = play_query(msg.text, context.bot.username)
        if parsed[0] or not is_group:
            await _play(update, context, parsed[1])
        return
 
    if is_group and not GROUP_SEARCH:
        return
    if "http" in msg.text.lower():
        return
 
    query = normalize(msg.text)
    if len(query) < (3 if is_group else 2):
        return
    if await asyncio.to_thread(db.is_banned, user.id):
        return
 
    await asyncio.to_thread(db.add_user, user.id)
    items, total = await asyncio.to_thread(db.search_songs, query, 0, PAGE_SIZE)
    raw = clip(msg.text.strip(), 200)
    chat_title = chat.title if is_group else None
    if not items:
        if not is_group:  # in groups, stay silent if nothing is found (no spam)
            await msg.reply_text(
                "😕 No songs found. Try different words or check the spelling.",
                reply_markup=await _request_markup(raw, user.id),
            )
        await send_activity(context.bot, activity_text("❌ SONG NOT FOUND", user, raw, chat_title))
        return
 
    qid = await asyncio.to_thread(db.make_query, query, user.id)
    text, kb = _build_results(items, total, qid, 0, query, is_group)
    await msg.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await send_activity(context.bot, activity_text("🔎 SONG SEARCH", user, raw, chat_title))
 
 
async def page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    try:
        _, qid, page_s = q.data.split("|")
        page = int(page_s)
    except ValueError:
        await q.answer()
        return
 
    doc = await asyncio.to_thread(db.get_query, qid)
    if not doc:
        await q.answer("This search has expired. Please type your search again.", show_alert=True)
        return
    if doc["user_id"] != q.from_user.id:
        await q.answer("This isn't your search. Type a song name yourself 🙂", show_alert=True)
        return
 
    items, total = await asyncio.to_thread(db.search_songs, doc["q"], page, PAGE_SIZE)
    in_group = q.message.chat.type in ("group", "supergroup")
    text, kb = _build_results(items, total, qid, page, doc["q"], in_group)
    try:
        await q.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            logger.warning("page edit failed: %s", e)
    await q.answer()
 
 
async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Song button in private chat (or 'try again' after force-subscribe)."""
    q = update.callback_query
    user = q.from_user
    song_id = q.data.split("|", 1)[1]
 
    if await asyncio.to_thread(db.is_banned, user.id):
        await q.answer("You can't use this bot.", show_alert=True)
        return
 
    gate = await fsub_gate(context.bot, user.id, f"d|{song_id}")
    if gate:
        await q.answer()
        await context.bot.send_message(q.message.chat.id, gate[0], reply_markup=gate[1])
        return
 
    song = await asyncio.to_thread(db.get_song, song_id)
    if not song:
        await q.answer("This song is no longer available.", show_alert=True)
        return
 
    await q.answer("🎵 Sending...")
    ok = await send_song(context.bot, q.message.chat.id, song, reply_to=q.message.message_id)
    if not ok:
        await context.bot.send_message(
            q.message.chat.id,
            "⚠️ Couldn't send the song. It may have been removed from the channel.",
        )
 
 
async def request_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'Request this song' button: sends the request to ACTIVITY_LOG_CHANNEL."""
    q = update.callback_query
    user = q.from_user
    if await asyncio.to_thread(db.is_banned, user.id):
        await q.answer("You can't use this bot.", show_alert=True)
        return
    doc = await asyncio.to_thread(db.get_query, q.data.split("|", 1)[1])
    if not doc:
        await q.answer("This request has expired. Please search again.", show_alert=True)
        return
    chat = q.message.chat
    chat_title = chat.title if chat.type in ("group", "supergroup") else None
    await send_activity(context.bot, activity_text("📩 SONG REQUEST", user, doc["q"], chat_title))
    await q.answer("✅ Request sent! We'll try to add this song.", show_alert=True)
    try:
        await q.edit_message_reply_markup(reply_markup=None)  # remove the button so it can't be sent twice
    except Exception:
        pass
 
 
async def noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
 
 
async def _play(update: Update, context: ContextTypes.DEFAULT_TYPE, query_text):
    """/play song name — sends the best match straight to the same chat (group or private)."""
    msg, user, chat = update.effective_message, update.effective_user, update.effective_chat
    if not msg or not user or user.is_bot:
        return
    if await asyncio.to_thread(db.is_banned, user.id):
        return
    if not normalize(query_text):
        await msg.reply_text("🎵 Use it like this: /play song name\nExample: /play kesariya")
        return
 
    await asyncio.to_thread(db.add_user, user.id)
    items, _ = await asyncio.to_thread(db.search_songs, query_text, 0, 30)
    song = pick_best(items, query_text)
    raw = clip(query_text.strip(), 200)
    chat_title = chat.title if chat.type in ("group", "supergroup") else None
    if not song:
        await msg.reply_text(
            "😕 No songs found. Try different words or check the spelling.",
            reply_markup=await _request_markup(raw, user.id),
        )
        await send_activity(context.bot, activity_text("❌ SONG NOT FOUND", user, raw, chat_title))
        return
 
    gate = await fsub_gate(context.bot, user.id, f"d|{song['_id']}")
    if gate:
        await msg.reply_text(gate[0], reply_markup=gate[1])
    elif not await send_song(context.bot, chat.id, song, reply_to=msg.message_id):
        await msg.reply_text("⚠️ Couldn't send the song. It may have been removed from the channel.")
    await send_activity(context.bot, activity_text("🔎 SONG SEARCH", user, raw, chat_title))
 
 
async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/play@BotName song name  (in groups the bot must be mentioned if PLAY_NEEDS_MENTION=1)."""
    msg, chat = update.effective_message, update.effective_chat
    if not msg or not msg.text:
        return
    parsed = play_query(msg.text, context.bot.username)
    if parsed is None:
        return
    mentioned, query_text = parsed
    is_group = chat.type in ("group", "supergroup")
    if is_group and PLAY_NEEDS_MENTION and not mentioned:
        return  # no mention — probably meant for another bot, stay silent
    await _play(update, context, query_text)
 
