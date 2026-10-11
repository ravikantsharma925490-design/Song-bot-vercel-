"""/start (also handles song deep links), /help, and the Help / Back buttons."""
 
import asyncio
import html
 
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
 
import database as db
from config import UPDATES_URL, SUPPORT_URL
from handlers.common import send_song, fsub_gate
 
WELCOME = (
    "👋 Hello {name}! Welcome to MyTunes Bot 🎧\n\n"
    "I can find any song for you and send it directly as an MP3 file.\n\n"
    "📌 Use the command below to download:\n"
    "👉 /download [Song name or Link]\n\n"
    "(Example: /download Tu Hai Kahan)\n\n"
    "If you face any problem, type /help!"
)
 
HELP = (
    "ℹ️ <b>Help &amp; Commands</b>\n\n"
    "1. In private chat: type a song name, then tap a button.\n"
    "2. In a group: type <code>/play@BotName song name</code> and the song will be sent in the group.\n"
    "3. In a group, typing just a song name also shows buttons; tapping one sends the song in the group.\n\n"
    "<b>Commands</b>\n"
    "/start — Start the bot\n"
    "/help — How to use\n"
    "/play song name — Play a song\n\n"
    "Tip: use fewer words, like <code>arijit tum hi ho</code>."
)
 
 
def _btn(text, url=None, cb=None, style=None):
    """Button with optional color: style = 'primary' (blue), 'success' (green), 'danger' (red)."""
    return InlineKeyboardButton(
        text, url=url, callback_data=cb,
        api_kwargs={"style": style} if style else None,
    )
 
 
def home_markup(bot):
    rows = [
        [_btn("➕ Add Me To Your Group", url=f"https://t.me/{bot.username}?startgroup=true", style="success")],
        [_btn("ℹ️ Help & Commands", cb="help", style="primary")],
    ]
    last = []
    if UPDATES_URL:
        last.append(_btn("📢 Updates", url=UPDATES_URL, style="danger"))
    if SUPPORT_URL:
        last.append(_btn("💬 Support", url=SUPPORT_URL, style="success"))
    if last:
        rows.append(last)
    return InlineKeyboardMarkup(rows)
 
 
def welcome_text(user):
    return WELCOME.format(name=html.escape(user.first_name or "friend"))
 
 
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, user, chat = update.effective_message, update.effective_user, update.effective_chat
 
    if chat.type != "private":
        await msg.reply_text("🎶 Type a song name and I'll find it. For more help, send /start to me in private.")
        return
 
    await asyncio.to_thread(db.add_user, user.id)
    if await asyncio.to_thread(db.is_banned, user.id):
        return
 
    payload = context.args[0] if context.args else ""
    if payload.startswith("s_"):
        song_id = payload[2:]
        gate = await fsub_gate(context.bot, user.id, f"d|{song_id}")
        if gate:
            await msg.reply_text(gate[0], reply_markup=gate[1])
            return
        song = await asyncio.to_thread(db.get_song, song_id)
        if not song:
            await msg.reply_text("😕 This song is no longer available.")
            return
        if not await send_song(context.bot, chat.id, song):
            await msg.reply_text("⚠️ Couldn't send the song. It may have been removed from the channel.")
        return
 
    await msg.reply_html(welcome_text(user), reply_markup=home_markup(context.bot))
 
 
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_html(HELP)
 
 
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'Help & Commands' button shows help; 'Back' returns to the welcome message."""
    q = update.callback_query
    await q.answer()
    if q.data == "help":
        text = HELP
        kb = InlineKeyboardMarkup([[_btn("⬅️ Back", cb="home", style="primary")]])
    else:
        text = welcome_text(update.effective_user)
        kb = home_markup(context.bot)
    try:
        await q.edit_message_text(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
    except Exception:
        pass  # e.g. message not modified
 
