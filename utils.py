"""Small helper functions (they work without Telegram)."""

import html
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone

AUDIO_EXT = (".mp3", ".m4a", ".flac", ".wav", ".ogg", ".opus", ".aac", ".wma", ".amr")


def normalize(text):
    """Lowercases and strips symbols, keeping only words.
    Hindi vowel signs (ि, ु, ा ...) are kept; English accents (ā -> a) are removed."""
    text = unicodedata.normalize("NFD", (text or "").lower())
    out = []
    for ch in text:
        if unicodedata.category(ch).startswith("M"):
            # only drop the accent when the previous letter is English (a-z)
            if out and not ("a" <= out[-1] <= "z"):
                out.append(ch)
        elif ch.isalnum():
            out.append(ch)
        else:
            out.append(" ")
    return re.sub(r"\s+", " ", "".join(out)).strip()


def human_size(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024


def clip(text, limit):
    text = text or ""
    return text if len(text) <= limit else text[: limit - 1] + "…"


def clean_title(name):
    """Removes the file extension and turns underscores into spaces for a clean title."""
    name = re.sub(r"\.(mp3|m4a|flac|wav|ogg|opus|aac|wma|amr)$", "", name or "", flags=re.I)
    return re.sub(r"\s+", " ", name.replace("_", " ")).strip()


def pick_best(items, query):
    """Picks the best song from several results: exact name match > starts-with match > shorter name."""
    nq = normalize(query)

    def key(s):
        n = normalize(s.get("name"))
        return (0 if n == nq else 1 if n.startswith(nq) else 2, len(n))

    return min(items, key=key) if items else None


def play_query(text, bot_username):
    """Parses '@Bot /play kesariya' or '/play@Bot kesariya' or '/play kesariya @Bot' into (is_mentioned, song_name).
    Returns None if the text doesn't start with /play or '@Bot /play'."""
    text = (text or "").strip()
    bot = (bot_username or "").lower()
    m = re.match(r"^@(\w+)\s+/play(?:@\w+)?(?:\s+(.*))?$", text, re.I | re.S)
    if m:
        return (m.group(1).lower() == bot, (m.group(2) or "").strip())
    m = re.match(r"^/play(?:@(\w+))?(?:\s+(.*))?$", text, re.I | re.S)
    if not m:
        return None
    mentioned = bool(m.group(1)) and m.group(1).lower() == bot
    rest = (m.group(2) or "")
    if re.search(rf"(?i)@{re.escape(bot)}\b", rest):
        mentioned = True
        rest = re.sub(rf"(?i)@{re.escape(bot)}\b", " ", rest)
    return (mentioned, re.sub(r"\s+", " ", rest).strip())


# ---------------- /status helpers ----------------

def format_uptime(seconds):
    seconds = int(max(seconds, 0))
    d, r = divmod(seconds, 86400)
    h, r = divmod(r, 3600)
    return f"{d}d {h}h {r // 60}m"


def process_ram():
    """(memory used by this process, total memory) in bytes, or (None, None) if unavailable."""
    rss = total = None
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    rss = int(line.split()[1]) * 1024
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1]) * 1024
    except Exception:
        pass
    return rss, total


def cpu_load_percent():
    """1-minute load average as a percentage of CPU cores, or None if unavailable."""
    try:
        return os.getloadavg()[0] / (os.cpu_count() or 1) * 100
    except Exception:
        return None


def status_text(users, groups, files, used, limit, uptime, rss, total, cpu):
    """Builds the /status message. Any value that is None is shown as N/A."""
    if used is None:
        used_s = free_s = "N/A"
    else:
        used_s = human_size(used)
        free_s = human_size(max(limit - used, 0))
    if rss is None:
        ram_s = "N/A"
    elif total:
        ram_s = f"{human_size(rss)} ({rss / total * 100:.1f}%)"
    else:
        ram_s = human_size(rss)
    cpu_s = "N/A" if cpu is None else f"{cpu:.1f}%"
    return (
        "╭────[ 🗃 ᴅᴀᴛᴀʙᴀsᴇ 🗃 ]────⍟\n"
        "│\n"
        f"├⋟ ᴀʟʟ ᴜsᴇʀs ⋟ {users}\n"
        f"├⋟ ᴀʟʟ ɢʀᴏᴜᴘs ⋟ {groups}\n"
        f"├⋟ ᴀʟʟ ꜰɪʟᴇs ⋟ {files}\n"
        f"├⋟ ᴜsᴇᴅ sᴛᴏʀᴀɢᴇ ⋟ {used_s}\n"
        f"├⋟ ꜰʀᴇᴇ sᴛᴏʀᴀɢᴇ ⋟ {free_s}\n"
        "│\n"
        "├────[ 🤖 ʙᴏᴛ ᴅᴇᴛᴀɪʟs 🤖 ]────⍟\n"
        "│\n"
        f"├⋟ ᴜᴘᴛɪᴍᴇ ⋟ {format_uptime(uptime)}\n"
        f"├⋟ ʀᴀᴍ ⋟ {ram_s}\n"
        f"├⋟ ᴄᴘᴜ ⋟ {cpu_s}\n"
        "│\n"
        "╰─────────────────────⍟"
    )


# ---------------- LOG_CHANNEL messages ----------------

IST = timezone(timedelta(hours=5, minutes=30))  # Asia/Kolkata


def restart_text(bot_name, version):
    now = datetime.now(IST)
    return (
        f"<b>{html.escape(bot_name)} Bᴏᴛ Rᴇsᴛᴀʀᴛᴇᴅ !</b>\n\n"
        f"📅 Dᴀᴛᴇ : <code>{now:%Y-%m-%d}</code>\n"
        f"⏰ Tɪᴍᴇ : <code>{now:%I:%M:%S %p}</code>\n"
        "🌐 Tɪᴍᴇᴢᴏɴᴇ : <code>Asia/Kolkata</code>\n"
        f"🛠️ Bᴜɪʟᴅ Sᴛᴀᴛᴜs: <code>{html.escape(version)} [ Sᴛᴀʙʟᴇ ]</code>"
    )


def new_user_text(user_id, name):
    return (
        "#NewUser\n\n"
        f"Iᴅ - <code>{user_id}</code>\n"
        f"Nᴀᴍᴇ - {html.escape(name or 'Unknown')}"
    )


def activity_text(title, user, query, chat_title=None):
    """Activity message, e.g. title='🔎 SONG SEARCH'. chat_title is shown only for group searches."""
    text = (
        f"<b>{html.escape(title)}</b>\n\n"
        f"👤 User: {html.escape(user.full_name or 'Unknown')}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"🔍 Search: <code>{html.escape(query)}</code>"
    )
    if chat_title:
        text += f"\n💬 Group: {html.escape(chat_title)}"
    return text
