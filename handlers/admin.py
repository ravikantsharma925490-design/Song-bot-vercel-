"""Admin commands: /stats /delete /deleteall /ban /unban (sirf ADMINS)."""

import asyncio
import html

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import database as db
from config import ADMINS
from utils import clip, human_size


def _is_admin(update):
    return update.effective_user is not None and update.effective_user.id in ADMINS


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        return
    songs = await asyncio.to_thread(db.count_songs)
    users = await asyncio.to_thread(db.count_users)
    await update.effective_message.reply_text(f"📊 Songs: {songs}\n👤 Users: {users}")


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        return
    msg = update.effective_message
    query = " ".join(context.args)
    if not query:
        await msg.reply_text("Use: /delete <song ka naam>\nPhir jo song hatana hai uske saamne ❌ dabayein.")
        return
    items = await asyncio.to_thread(db.find_for_delete, query, 10)
    if not items:
        await msg.reply_text("😕 Koi song nahi mila.")
        return
    rows = [
        [InlineKeyboardButton(f"❌ {human_size(s.get('size'))} • {clip(s.get('name'), 45)}", callback_data=f"x|{s['_id']}")]
        for s in items
    ]
    await msg.reply_text("Kaun sa song delete karna hai?", reply_markup=InlineKeyboardMarkup(rows))


async def delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id not in ADMINS:
        await q.answer("Sirf admin.", show_alert=True)
        return
    song_id = q.data.split("|", 1)[1]
    n = await asyncio.to_thread(db.delete_song, song_id)
    await q.answer("🗑 Delete ho gaya" if n else "Pehle hi delete ho chuka hai", show_alert=False)


async def deleteall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        return
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("⚠️ Haan, SAB songs delete karo", callback_data="xa|1")],
         [InlineKeyboardButton("Cancel", callback_data="xa|0")]]
    )
    await update.effective_message.reply_text("Pakka database ke SAARE songs delete karne hain?", reply_markup=kb)


async def deleteall_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id not in ADMINS:
        await q.answer("Sirf admin.", show_alert=True)
        return
    if q.data.endswith("|1"):
        n = await asyncio.to_thread(db.delete_all_songs)
        await q.edit_message_text(f"🗑 {n} songs delete ho gaye.")
    else:
        await q.edit_message_text("Cancel kar diya.")
    await q.answer()


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _set_ban(update, context, True)


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _set_ban(update, context, False)


async def _set_ban(update, context, banned):
    if not _is_admin(update):
        return
    msg = update.effective_message
    target = None
    if msg.reply_to_message and msg.reply_to_message.from_user:
        target = msg.reply_to_message.from_user.id
    elif context.args and context.args[0].lstrip("-").isdigit():
        target = int(context.args[0])
    if target is None:
        await msg.reply_text("Use: /ban <user_id> (ya kisi ke message par reply karke)")
        return
    if target in ADMINS:
        await msg.reply_text("Admin ko ban nahi kar sakte.")
        return
    await asyncio.to_thread(db.set_ban, target, banned)
    await msg.reply_text(f"{'🚫 Ban' if banned else '✅ Unban'} ho gaya: {html.escape(str(target))}")
