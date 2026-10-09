"""Chhote helper functions (Telegram ke bina bhi chalte hain)."""

import re
import unicodedata

AUDIO_EXT = (".mp3", ".m4a", ".flac", ".wav", ".ogg", ".opus", ".aac", ".wma", ".amr")


def normalize(text):
    """Lowercase + symbols hata kar sirf shabd rakhta hai.
    Hindi ki matras (ि, ु, ा ...) bani rehti hain; English ke accents (ā -> a) hat jaate hain."""
    text = unicodedata.normalize("NFD", (text or "").lower())
    out = []
    for ch in text:
        if unicodedata.category(ch).startswith("M"):
            # accent sirf tab hatao jab pichla akshar English (a-z) ho
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
    """File ka extension hata kar, underscore ko space bana kar sundar naam deta hai."""
    name = re.sub(r"\.(mp3|m4a|flac|wav|ogg|opus|aac|wma|amr)$", "", name or "", flags=re.I)
    return re.sub(r"\s+", " ", name.replace("_", " ")).strip()


def pick_best(items, query):
    """Kai results mein se sabse sahi song chunta hai: pura naam match > shuruat match > chhota naam."""
    nq = normalize(query)

    def key(s):
        n = normalize(s.get("name"))
        return (0 if n == nq else 1 if n.startswith(nq) else 2, len(n))

    return min(items, key=key) if items else None


def play_query(text, bot_username):
    """'@Bot /play kesariya' ya '/play@Bot kesariya' ya '/play kesariya @Bot' se (mention_hai, song_naam) nikalta hai.
    Text /play se shuru ya '@Bot /play' se shuru na ho to None."""
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
