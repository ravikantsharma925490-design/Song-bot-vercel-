"""/start (deep link se song bhi) aur /help."""

import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import database as db
from handlers.common import send_song, fsub_gate

WELCOME = (
    "🎶 <b>Namaste {name}!</b>\n\n"
    "Main ek song bot hoon. Bas song ka naam likhiye, main dhoondh kar bhej dunga.\n\n"
    "Example: <code>kesariya</code>\n\n"
    "Group mein add karein aur likhein: <code>/play@{bot} song ka naam</code> — song seedha group mein aa jayega."
)

HELP = (
    "ℹ️ <b>Kaise use karein</b>\n\n"
    "1. Private mein: song ka naam likhein, phir button dabayein.\n"
    "2. Group mein: <code>/play@BotName song ka naam</code> likhein, song group mein hi aayega.\n"
    "3. Group mein sirf song ka naam likhne par buttons bhi aate hain, button dabane par song group mein aata hai.\n\n"
    "Tip: kam shabd likhein, jaise <code>arijit tum hi ho</code>."
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, user, chat = update.effective_message, update.effective_user, update.effective_chat

    if chat.type != "private":
        await msg.reply_text("🎶 Song ka naam likhiye, main dhoondh dunga. Zyada help ke liye mujhe private mein /start karein.")
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
            await msg.reply_text("😕 Ye song ab available nahi hai.")
            return
        if not await send_song(context.bot, chat.id, song):
            await msg.reply_text("⚠️ Song bhej nahi paya. Shayad channel se hata diya gaya hai.")
        return

    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("➕ Mujhe group mein add karein", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    )
    await msg.reply_html(WELCOME.format(name=user.first_name or "dost", bot=context.bot.username), reply_markup=kb)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_html(HELP)
