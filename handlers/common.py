"""Shared helpers: song bhejna, force subscribe check."""
 
import logging
 
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
 
from config import FSUB_CHANNELS, FSUB_LINKS, PROTECT_CONTENT, ADD_BUTTON
 
logger = logging.getLogger(__name__)
 
 
def add_to_group_markup(bot):
    """Song ke neeche '➕ Add me to a group' button (ADD_BUTTON=0 se band)."""
    if not ADD_BUTTON or not bot.username:
        return None
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("➕ Add me to a group", url=f"https://t.me/{bot.username}?startgroup=true")]]
    )
 
 
async def send_song(bot, chat_id, song, reply_to=None):
    """Song bhejta hai. Pehle channel se copy (sabse reliable), fail ho to file_id. True = gaya."""
    markup = add_to_group_markup(bot)
    src_chat, src_msg = song.get("src_chat"), song.get("src_msg")
    if src_chat and src_msg:
        try:
            await bot.copy_message(
                chat_id, src_chat, src_msg, protect_content=PROTECT_CONTENT,
                reply_to_message_id=reply_to, allow_sending_without_reply=True,
                reply_markup=markup,
            )
            return True
        except Exception as e:
            logger.warning("copy_message failed for %s: %s", song.get("_id"), e)
 
    file_id = song.get("file_id")
    if file_id:
        try:
            if song.get("kind") == "audio":
                await bot.send_audio(chat_id, file_id, protect_content=PROTECT_CONTENT,
                                     reply_to_message_id=reply_to, allow_sending_without_reply=True,
                                     reply_markup=markup)
            else:
                await bot.send_document(chat_id, file_id, protect_content=PROTECT_CONTENT,
                                        reply_to_message_id=reply_to, allow_sending_without_reply=True,
                                     reply_markup=markup)
            return True
        except Exception as e:
            logger.warning("send by file_id failed for %s: %s", song.get("_id"), e)
    return False
 
 
def _is_member(m):
    if m.status in ("left", "kicked"):
        return False
    if m.status == "restricted" and not getattr(m, "is_member", True):
        return False
    return True
 
 
async def missing_channels(bot, user_id):
    """Un FSUB channels ki list jinhe user ne join nahi kiya."""
    missing = []
    for ch in FSUB_CHANNELS:
        try:
            member = await bot.get_chat_member(ch, user_id)
            if not _is_member(member):
                missing.append(ch)
        except Exception as e:
            # Bot channel mein admin nahi / galat ID — user ko block mat karo, bas log karo
            logger.warning("fsub check failed for %s: %s", ch, e)
    return missing
 
 
async def _join_link(bot, ch, index):
    if index < len(FSUB_LINKS):
        return FSUB_LINKS[index]
    if isinstance(ch, str) and ch.startswith("@"):
        return f"https://t.me/{ch[1:]}"
    try:
        chat = await bot.get_chat(ch)
        if chat.username:
            return f"https://t.me/{chat.username}"
        if chat.invite_link:
            return chat.invite_link
        return await bot.export_chat_invite_link(ch)
    except Exception as e:
        logger.warning("join link failed for %s: %s", ch, e)
        return None
 
 
async def fsub_gate(bot, user_id, retry_data):
    """Agar user ne join nahi kiya to (text, keyboard) deta hai, warna None."""
    missing = await missing_channels(bot, user_id)
    if not missing:
        return None
    rows = []
    for ch in missing:
        link = await _join_link(bot, ch, FSUB_CHANNELS.index(ch))
        if link:
            rows.append([InlineKeyboardButton("📢 Channel Join Karo", url=link)])
    rows.append([InlineKeyboardButton("✅ Join kar liya, dobara try karo", callback_data=retry_data)])
    return (
        "🔒 Song paane ke liye pehle neeche wala channel join karein, phir 'dobara try karo' dabayein.",
        InlineKeyboardMarkup(rows),
    )
 
