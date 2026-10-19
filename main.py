"""Builds the bot application (for webhooks — polling doesn't run on Vercel)."""

import logging

from telegram import BotCommand, BotCommandScopeChat, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ChatMemberHandler, filters,
)

from config import BOT_TOKEN, ADMINS
from handlers.start import start_command, help_command, menu_callback, photo_id_handler
from handlers.status import status_command, track_group, bot_membership
from handlers.search import search_message, page_callback, download_callback, noop_callback, play_command, request_callback
from handlers.youtube import youtube_callback
from handlers.save import channel_save, pm_save
from handlers.admin import (
    stats_command, delete_command, delete_callback, deleteall_command,
    deleteall_callback, ban_command, unban_command,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s")
# httpx logs every request URL, which contains the bot token — keep those out of the logs
logging.getLogger("httpx").setLevel(logging.WARNING)


async def _post_init(application):
    """Tells Telegram the command list (runs once via /api/setup)."""
    await application.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("help", "How to use"),
        BotCommand("play", "Play a song: /play song name"),
    ])
    admin_cmds = [
        BotCommand("start", "Start the bot"),
        BotCommand("help", "How to use"),
        BotCommand("play", "Play a song: /play song name"),
        BotCommand("stats", "Song and user counts"),
        BotCommand("status", "Bot and database status"),
        BotCommand("delete", "Delete a song"),
        BotCommand("deleteall", "Delete all songs"),
        BotCommand("ban", "Ban a user"),
        BotCommand("unban", "Unban a user"),
    ]
    for admin_id in ADMINS:
        try:
            await application.bot.set_my_commands(admin_cmds, scope=BotCommandScopeChat(admin_id))
        except Exception as e:
            logging.getLogger(__name__).warning("admin commands failed for %s: %s", admin_id, e)


def build_application():
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .build()
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("play", play_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("delete", delete_command))
    app.add_handler(CommandHandler("deleteall", deleteall_command))
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))

    # Remember groups (runs first, never blocks the other handlers)
    app.add_handler(MessageHandler(filters.ChatType.GROUPS, track_group), group=-1)
    app.add_handler(ChatMemberHandler(bot_membership, ChatMemberHandler.MY_CHAT_MEMBER))

    app.add_handler(CallbackQueryHandler(page_callback, pattern=r"^p\|"))
    app.add_handler(CallbackQueryHandler(download_callback, pattern=r"^d\|"))
    app.add_handler(CallbackQueryHandler(delete_callback, pattern=r"^x\|"))
    app.add_handler(CallbackQueryHandler(deleteall_callback, pattern=r"^xa\|"))
    app.add_handler(CallbackQueryHandler(request_callback, pattern=r"^r\|"))
    app.add_handler(CallbackQueryHandler(youtube_callback, pattern=r"^y\|"))
    app.add_handler(CallbackQueryHandler(noop_callback, pattern=r"^noop$"))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^(help|home)$"))

    # Owner sends a photo in private -> bot replies with its file_id (for START_PHOTO)
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.PHOTO, photo_id_handler))

    # Saving songs
    app.add_handler(MessageHandler(
        filters.UpdateType.CHANNEL_POST & (filters.AUDIO | filters.Document.ALL), channel_save))
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & (filters.AUDIO | filters.Document.ALL), pm_save))

    # Every other text = song search
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_message))
    return app
