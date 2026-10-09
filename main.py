"""Bot ka application banata hai (webhook ke liye — Vercel par polling nahi chalti)."""

import logging

from telegram import BotCommand, BotCommandScopeChat, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters,
)

from config import BOT_TOKEN, ADMINS
from handlers.start import start_command, help_command
from handlers.search import search_message, page_callback, download_callback, noop_callback, play_command
from handlers.save import channel_save, pm_save
from handlers.admin import (
    stats_command, delete_command, delete_callback, deleteall_command,
    deleteall_callback, ban_command, unban_command,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s")


async def _post_init(application):
    """Commands ki list Telegram ko batata hai (/api/setup se ek baar chalta hai)."""
    await application.bot.set_my_commands([
        BotCommand("start", "Bot shuru karein"),
        BotCommand("help", "Kaise use karein"),
        BotCommand("play", "Song bajao: /play song ka naam"),
    ])
    admin_cmds = [
        BotCommand("start", "Bot shuru karein"),
        BotCommand("help", "Kaise use karein"),
        BotCommand("play", "Song bajao: /play song ka naam"),
        BotCommand("stats", "Songs aur users ki ginti"),
        BotCommand("delete", "Song delete karein"),
        BotCommand("deleteall", "Saare songs delete karein"),
        BotCommand("ban", "User ko ban karein"),
        BotCommand("unban", "User ko unban karein"),
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
    app.add_handler(CommandHandler("delete", delete_command))
    app.add_handler(CommandHandler("deleteall", deleteall_command))
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))

    app.add_handler(CallbackQueryHandler(page_callback, pattern=r"^p\|"))
    app.add_handler(CallbackQueryHandler(download_callback, pattern=r"^d\|"))
    app.add_handler(CallbackQueryHandler(delete_callback, pattern=r"^x\|"))
    app.add_handler(CallbackQueryHandler(deleteall_callback, pattern=r"^xa\|"))
    app.add_handler(CallbackQueryHandler(noop_callback, pattern=r"^noop$"))

    # Songs save karna
    app.add_handler(MessageHandler(
        filters.UpdateType.CHANNEL_POST & (filters.AUDIO | filters.Document.ALL), channel_save))
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & (filters.AUDIO | filters.Document.ALL), pm_save))

    # Baaki har text = song search
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_message))
    return app
