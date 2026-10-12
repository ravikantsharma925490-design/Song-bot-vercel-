"""
Config — all settings come from Vercel Environment Variables.
Required: BOT_TOKEN, MONGO_URI, ADMINS, WEBHOOK_SECRET
"""
 
import os
 
 
def _ids(value):
    """Turns '-1001 -1002 @mychannel' or a comma-separated string into a list."""
    out = []
    for part in (value or "").replace(",", " ").split():
        try:
            out.append(int(part))
        except ValueError:
            out.append(part)  # @username
    return out
 
 
def _flag(name, default):
    return os.environ.get(name, default).strip().lower() not in ("0", "false", "no", "off", "")
 
 
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MONGO_URI = os.environ.get("MONGO_URI", "")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "songbot")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
 
# Your Telegram user ID (you can give several, separated by spaces)
ADMINS = [i for i in _ids(os.environ.get("ADMINS", "")) if isinstance(i, int)]
 
# Song channel(s) — new songs posted here are saved automatically. Empty = any channel where the bot is admin.
CHANNELS = _ids(os.environ.get("CHANNELS", ""))
 
# Force-subscribe channel(s) (empty = off). The bot must be an admin in these channels.
FSUB_CHANNELS = _ids(os.environ.get("FSUB_CHANNELS", ""))
# Optional: join links (same order as FSUB_CHANNELS), for private channels
FSUB_LINKS = os.environ.get("FSUB_LINKS", "").split()
 
PAGE_SIZE = int(os.environ.get("PAGE_SIZE", "8"))
GROUP_SEARCH = _flag("GROUP_SEARCH", "1")          # search when text is typed in a group
PROTECT_CONTENT = _flag("PROTECT_CONTENT", "0")    # 1 = songs can't be forwarded or saved
# In groups, /play works only when the bot is @mentioned (avoids clashing with other music bots). 0 = works without a mention too
PLAY_NEEDS_MENTION = _flag("PLAY_NEEDS_MENTION", "1")
# "➕ Add me to a group" button under songs. 0 = off
ADD_BUTTON = _flag("ADD_BUTTON", "1")
 
 
# Optional links for the /start buttons (already set below; you can override them in Vercel Environment Variables), e.g. https://t.me/yourchannel
UPDATES_URL = os.environ.get("UPDATES_URL", "https://t.me/cinemagyanupdates").strip()
SUPPORT_URL = os.environ.get("SUPPORT_URL", "https://t.me/+xfk1QS-y50RmOTc1").strip()
 
# Storage plan size in MB for /status (MongoDB Atlas free plan = 512)
STORAGE_LIMIT_MB = int(os.environ.get("STORAGE_LIMIT_MB", "512"))
 
# Photo shown on /start: a Telegram file_id (best) or an https image link. Empty = text only.
START_PHOTO = os.environ.get("START_PHOTO", "").strip()
 
# Private channel where the bot posts "restarted" and "#NewUser" messages (ID like -1001234567890 or @username). Empty = off.
LOG_CHANNEL = (_ids(os.environ.get("LOG_CHANNEL", "")) or [None])[0]
BOT_NAME = os.environ.get("BOT_NAME", "MyTunes Bot 🎶")
BOT_VERSION = os.environ.get("BOT_VERSION", "v1.0")
 
