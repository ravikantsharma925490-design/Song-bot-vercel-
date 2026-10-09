"""Song search (group + private), pagination, aur song download button."""

import asyncio
import html
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

import database as db
from config import PAGE_SIZE, GROUP_SEARCH, PLAY_NEEDS_MENTION
from utils import normalize, human_size, clip, pick_best, play_query
from handlers.common import send_song, fsub_gate

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
            nav.append(InlineKeyboardButton("⬅️ Pehle", callback_data=f"p|{qid}|{page - 1}"))
        nav.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
        if page + 1 < total_pages:
            nav.append(InlineKeyboardButton("Aage ➡️", callback_data=f"p|{qid}|{page + 1}"))
        rows.append(nav)

    shown = f"{total}+" if total >= 500 else str(total)
    text = f"🎧 <b>{shown}</b> song mile: <i>{html.escape(clip(query_text, 60))}</i>"
    if in_group:
        text += "\n\n👇 Song dabayein, yahin group mein aa jayega."
    return text, InlineKeyboardMarkup(rows)


async def search_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, user, chat = update.effective_message, update.effective_user, update.effective_chat
    if not msg or not msg.text or not user or user.is_bot:
        return

    is_group = chat.type in ("group", "supergroup")

    # "@Bot /play song naam" likha ho to /play ki tarah chalao
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
    if not items:
        if not is_group:  # group mein na mile to chup rehte hain (spam nahi)
            await msg.reply_text("😕 Koi song nahi mila. Dusre shabd ya sahi spelling try karein.")
        return

    qid = await asyncio.to_thread(db.make_query, query, user.id)
    text, kb = _build_results(items, total, qid, 0, query, is_group)
    await msg.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)


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
        await q.answer("Ye search purana ho gaya, dobara likh kar search karein.", show_alert=True)
        return
    if doc["user_id"] != q.from_user.id:
        await q.answer("Ye aapka search nahi hai. Khud song ka naam likhein 🙂", show_alert=True)
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
    """Private chat mein song button (ya force-subscribe ke baad 'dobara try karo')."""
    q = update.callback_query
    user = q.from_user
    song_id = q.data.split("|", 1)[1]

    if await asyncio.to_thread(db.is_banned, user.id):
        await q.answer("Aap bot use nahi kar sakte.", show_alert=True)
        return

    gate = await fsub_gate(context.bot, user.id, f"d|{song_id}")
    if gate:
        await q.answer()
        await context.bot.send_message(q.message.chat.id, gate[0], reply_markup=gate[1])
        return

    song = await asyncio.to_thread(db.get_song, song_id)
    if not song:
        await q.answer("Ye song ab available nahi hai.", show_alert=True)
        return

    await q.answer("🎵 Bhej raha hoon...")
    ok = await send_song(context.bot, q.message.chat.id, song, reply_to=q.message.message_id)
    if not ok:
        await context.bot.send_message(
            q.message.chat.id,
            "⚠️ Song bhej nahi paya. Shayad channel se hata diya gaya hai.",
        )


async def noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()


async def _play(update: Update, context: ContextTypes.DEFAULT_TYPE, query_text):
    """/play song naam — sabse sahi song seedha usi chat (group ya private) mein bhejta hai."""
    msg, user, chat = update.effective_message, update.effective_user, update.effective_chat
    if not msg or not user or user.is_bot:
        return
    if await asyncio.to_thread(db.is_banned, user.id):
        return
    if not normalize(query_text):
        await msg.reply_text("🎵 Aise likhein: /play song ka naam\nExample: /play kesariya")
        return

    await asyncio.to_thread(db.add_user, user.id)
    items, _ = await asyncio.to_thread(db.search_songs, query_text, 0, 30)
    song = pick_best(items, query_text)
    if not song:
        await msg.reply_text("😕 Koi song nahi mila. Dusre shabd ya sahi spelling try karein.")
        return

    gate = await fsub_gate(context.bot, user.id, f"d|{song['_id']}")
    if gate:
        await msg.reply_text(gate[0], reply_markup=gate[1])
        return

    if not await send_song(context.bot, chat.id, song, reply_to=msg.message_id):
        await msg.reply_text("⚠️ Song bhej nahi paya. Shayad channel se hata diya gaya hai.")


async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/play@BotName song naam  (group mein bot ko mention karna zaroori hai, agar PLAY_NEEDS_MENTION=1)."""
    msg, chat = update.effective_message, update.effective_chat
    if not msg or not msg.text:
        return
    parsed = play_query(msg.text, context.bot.username)
    if parsed is None:
        return
    mentioned, query_text = parsed
    is_group = chat.type in ("group", "supergroup")
    if is_group and PLAY_NEEDS_MENTION and not mentioned:
        return  # mention nahi hai — shayad doosre bot ke liye hai, chup raho
    await _play(update, context, query_text)
