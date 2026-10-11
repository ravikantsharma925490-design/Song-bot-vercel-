"""Small helper functions (they work without Telegram)."""
 
import re
import unicodedata
 
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
 
