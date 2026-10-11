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
 
 
