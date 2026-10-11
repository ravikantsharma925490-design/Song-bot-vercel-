"""/start (also handles song deep links) and /help."""
 
import asyncio
 
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
 
import database as db
from handlers.common import send_song, fsub_gate
 
WELCOME = (
    "🎶 <b>Hello {name}!</b>\n\n"
    "I'm a song bot. Just type a song name and I'll find it and send it to you.\n\n"
    "Example: <code>kesariya</code>\n\n"
    "Add me to a group and type: <code>/play@{bot} song name</code> — the song will be sent straight to the group."
)
 
HELP = (
    "ℹ️ <b>How to use</b>\n\n"
    "1. In private chat: type a song name, then tap a button.\n"
    "2. In a group: type <code>/play@BotName song name</code> and the song will be sent in the group.\n"
    "3. In a group, typing just a song name also shows buttons; tapping one sends the song in the group.\n\n"
    "Tip: use fewer words, like <code>arijit tum hi ho</code>."
)
 
 
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
 
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("➕ Add me to a group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    )
    await msg.reply_html(WELCOME.format(name=user.first_name or "friend", bot=context.bot.username), reply_markup=kb)
 
 
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_html(HELP)
 
