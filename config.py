"""
Config — saari settings Vercel ke Environment Variables se aati hain.
Zaroori: BOT_TOKEN, MONGO_URI, ADMINS, WEBHOOK_SECRET
"""
 
import os
 
 
def _ids(value):
    """'-1001 -1002 @mychannel' ya comma wali string ko list mein badalta hai."""
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
 
# Aapki Telegram user ID (space se alag karke kai ID de sakte hain)
ADMINS = [i for i in _ids(os.environ.get("ADMINS", "")) if isinstance(i, int)]
 
# Songs wale channel(s) — inme naya song aate hi auto save hoga. Khaali = bot jis bhi channel mein admin hai wahan se.
CHANNELS = _ids(os.environ.get("CHANNELS", ""))
 
# Force subscribe channel(s) (khaali = band). Bot in channels mein admin hona chahiye.
FSUB_CHANNELS = _ids(os.environ.get("FSUB_CHANNELS", ""))
# Optional: join links (FSUB_CHANNELS ke order mein), private channel ke liye
FSUB_LINKS = os.environ.get("FSUB_LINKS", "").split()
 
PAGE_SIZE = int(os.environ.get("PAGE_SIZE", "8"))
GROUP_SEARCH = _flag("GROUP_SEARCH", "1")          # group mein text likhne par search
PROTECT_CONTENT = _flag("PROTECT_CONTENT", "0")    # 1 = song forward/save nahi hoga
# Group mein /play tabhi chale jab bot ko @mention kiya ho (doosre music bots se takraav na ho). 0 = bina mention ke bhi chale
PLAY_NEEDS_MENTION = _flag("PLAY_NEEDS_MENTION", "1")
# Song ke neeche "➕ Add me to a group" button. 0 = band
ADD_BUTTON = _flag("ADD_BUTTON", "1")
 
