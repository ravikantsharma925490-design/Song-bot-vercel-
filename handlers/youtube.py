"""
YouTube download.
When a song is not in the database the bot:
  1) searches YouTube and downloads the audio (m4a),
  2) sends it to the user FIRST,
  3) then posts it to the songs channel and saves it in the database (so next time it comes from the database).
"""

import asyncio
import glob
import html
import logging
import os
import re
import shutil
import tempfile

import database as db
from config import (
    YOUTUBE_COOKIES, YT_MAX_MINUTES, YT_SAVE_CHANNEL, PROTECT_CONTENT,
)
from handlers.common import add_to_group_markup, fsub_gate, send_activity, send_log, send_song
from utils import normalize, clip, clean_title, activity_text

logger = logging.getLogger(__name__)

MAX_BYTES = 49 * 1024 * 1024          # Telegram bots can upload up to 50 MB
MAX_SECONDS = YT_MAX_MINUTES * 60
SEARCH_TIMEOUT = 30                   # seconds
DOWNLOAD_TIMEOUT = 170                # seconds (Vercel allows up to 300 in total)

_URL_RE = re.compile(r"(?:youtu\.be/|youtube\.com/(?:watch\?(?:\S*&)?v=|shorts/|embed/|live/))([\w-]{11})")


# ---------------- yt-dlp (blocking code, always run in a thread) ----------------

def _cookie_file(workdir):
    """Writes the cookies from the YOUTUBE_COOKIES env variable to a temp file. None if not set."""
    text = (YOUTUBE_COOKIES or "").strip()
    if not text:
        return None
    text = text.replace("\\n", "\n").replace("\\t", "\t")  # in case it was pasted as one line
    path = os.path.join(workdir, "cookies.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    return path


def _base_opts(cookie_file):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 20,
        "retries": 2,
        "cachedir": False,  # Vercel's disk is read-only except /tmp
    }
    if cookie_file:
        opts["cookiefile"] = cookie_file
    return opts


def yt_search(query, cookie_file):
    """Returns the first usable result {id, title, uploader, duration} or None."""
    import yt_dlp

    opts = _base_opts(cookie_file)
    opts["extract_flat"] = True
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch5:{query}", download=False)
    for e in (info or {}).get("entries") or []:
        if not e or not e.get("id"):
            continue
        if e.get("live_status") in ("is_live", "is_upcoming"):
            continue
        dur = e.get("duration")
        if not dur or dur > MAX_SECONDS:
            continue
        return {
            "id": e["id"],
            "title": e.get("title") or "",
            "uploader": e.get("channel") or e.get("uploader") or "",
            "duration": int(dur),
        }
    return None


def yt_download(video_id, workdir, cookie_file):
    """Downloads the audio of one video into workdir. Returns (file_path, info)."""
    import yt_dlp
    from yt_dlp.utils import match_filter_func

    opts = _base_opts(cookie_file)
    opts.update({
        # m4a plays in Telegram's music player; fall back to any audio if m4a isn't offered
        "format": "bestaudio[ext=m4a]/bestaudio[acodec^=mp4a]/bestaudio",
        "outtmpl": os.path.join(workdir, "%(id)s.%(ext)s"),
        "max_filesize": MAX_BYTES,
        "match_filter": match_filter_func(f"duration <= {MAX_SECONDS} & !is_live"),
    })
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
    if not info:
        raise ValueError("TOO_BIG")
    files = [p for p in glob.glob(os.path.join(workdir, f"{video_id}.*")) if not p.endswith((".part", ".ytdl"))]
    if not files:
        raise ValueError("TOO_BIG")
    return max(files, key=os.path.getsize), info


# ---------------- helpers ----------------

def _safe_name(title):
    name = re.sub(r'[\\/:*?"<>|]+', " ", title or "").strip()
    return re.sub(r"\s+", " ", name)[:80] or "song"


async def _edit(msg, text, markup=None):
    if not msg:
        return
    try:
        await msg.edit_text(text, reply_markup=markup)
    except Exception:
        pass


async def _delete(msg):
    if not msg:
        return
    try:
        await msg.delete()
    except Exception:
        pass


async def _save_to_channel(bot, sent, title, query, video_id, size):
    """Posts the song to the songs channel (if set) and saves it in the database."""
    obj = sent.audio or sent.document
    file_id = obj.file_id
    is_audio = bool(sent.audio)
    src_chat = src_msg = None
    doc_id = f"yt_{video_id}"

    if YT_SAVE_CHANNEL:
        try:
            if is_audio:
                posted = await bot.send_audio(YT_SAVE_CHANNEL, file_id)
            else:
                posted = await bot.send_document(YT_SAVE_CHANNEL, file_id)
            src_chat, src_msg = posted.chat.id, posted.message_id
            doc_id = f"{abs(src_chat)}_{src_msg}"
            file_id = (posted.audio or posted.document).file_id
        except Exception as e:
            logger.warning("posting to the songs channel failed: %s", e)
            await send_log(bot, f"⚠️ <b>Couldn't post a downloaded song to the songs channel</b>\n"
                                f"<code>{html.escape(clip(str(e), 300))}</code>\n"
                                "Make the bot an admin of that channel with permission to post.")

    doc = {
        "_id": doc_id,
        "name": clean_title(title),
        "search": normalize(f"{title} {query}"),
        "size": size,
        "kind": "audio" if is_audio else "document",
        "file_id": file_id,
        "src_chat": src_chat,
        "src_msg": src_msg,
        "yt_id": video_id,
    }
    await asyncio.to_thread(db.save_yt_song, doc)


# ---------------- the main flow ----------------

async def youtube_flow(bot, chat_id, user, query, reply_to, update_id, chat_title=None, fail_markup=None):
    """Not in the database -> YouTube -> send to the user -> post to the channel + save in the database."""
    query = (query or "").strip()
    if not query:
        return

    # Telegram re-sends an update if the webhook is slow - never run the same update twice
    if not await asyncio.to_thread(db.claim, f"u{update_id}"):
        return
    # one download at a time per user (stops spam)
    if not await asyncio.to_thread(db.claim, f"user{user.id}"):
        await bot.send_message(
            chat_id, "⏳ Please wait, your previous song is still being prepared.",
            reply_to_message_id=reply_to, allow_sending_without_reply=True,
        )
        return

    workdir = tempfile.mkdtemp(prefix="yt_")
    status = None
    video_lock = None
    try:
        status = await bot.send_message(
            chat_id, "🔎 Not in my library. Searching YouTube…",
            reply_to_message_id=reply_to, allow_sending_without_reply=True,
        )
        cookie = _cookie_file(workdir)

        # 1) find the video
        m = _URL_RE.search(query)
        if m:
            result = {"id": m.group(1), "title": "", "uploader": "", "duration": 0}
        else:
            result = await asyncio.wait_for(asyncio.to_thread(yt_search, query, cookie), SEARCH_TIMEOUT)
        if not result:
            await _edit(status, "😕 I couldn't find a suitable song on YouTube. Try different words.", fail_markup)
            return
        video_id = result["id"]

        # 2) already downloaded before? send it from the database
        existing = await asyncio.to_thread(db.get_song_by_yt, video_id)
        if existing and await send_song(bot, chat_id, existing, reply_to=reply_to):
            await _delete(status)
            return

        # 3) only one download per video at a time
        if not await asyncio.to_thread(db.claim, f"yt{video_id}"):
            await _edit(status, "⏳ Someone just asked for this song. Please try again in a few seconds.")
            return
        video_lock = f"yt{video_id}"

        # 4) download
        shown = clip(result["title"], 60) if result["title"] else "your song"
        await _edit(status, f"⬇️ Downloading: {shown}")
        path, info = await asyncio.wait_for(
            asyncio.to_thread(yt_download, video_id, workdir, cookie), DOWNLOAD_TIMEOUT
        )
        size = os.path.getsize(path)
        if size > MAX_BYTES:
            raise ValueError("TOO_BIG")

        title = info.get("title") or result["title"] or "Unknown song"
        performer = re.sub(r"\s*-\s*Topic$", "", info.get("channel") or info.get("uploader") or result["uploader"] or "")
        duration = int(info.get("duration") or 0) or None
        ext = os.path.splitext(path)[1].lower()
        fname = f"{_safe_name(title)}{ext}"

        # 5) send to the user FIRST
        await _edit(status, "📤 Sending…")
        common = dict(
            reply_to_message_id=reply_to, allow_sending_without_reply=True,
            reply_markup=add_to_group_markup(bot), protect_content=PROTECT_CONTENT,
            read_timeout=120, write_timeout=120, connect_timeout=30,
        )
        with open(path, "rb") as fh:
            if ext in (".m4a", ".mp3"):
                sent = await bot.send_audio(
                    chat_id, fh, filename=fname, title=clip(title, 64),
                    performer=clip(performer, 64) or None, duration=duration, **common,
                )
            else:
                sent = await bot.send_document(chat_id, fh, filename=fname, **common)
        await _delete(status)
        status = None

        # 6) then the channel + database (the user already has the song, so this can't delay them)
        try:
            await _save_to_channel(bot, sent, title, "" if m else query, video_id, size)
        except Exception as e:
            logger.exception("saving the downloaded song failed: %s", e)
        await send_activity(bot, activity_text("🎬 YOUTUBE DOWNLOAD", user, query, chat_title))

    except asyncio.TimeoutError:
        await _edit(status, "⌛ This took too long. Please try again.", fail_markup)
        await send_log(bot, "⚠️ <b>YouTube download timed out</b>")
    except Exception as e:
        err = str(e)
        low = err.lower()
        logger.warning("youtube flow failed: %s", err)
        if "TOO_BIG" in err:
            await _edit(status, f"😕 That video is too long or too large (limit: {YT_MAX_MINUTES} minutes / 50 MB).", fail_markup)
        elif "sign in" in low or "not a bot" in low or "cookies" in low:
            await _edit(status, "⚠️ YouTube is blocking downloads right now. Please try again later.", fail_markup)
            await send_log(bot, "⚠️ <b>YouTube blocked a download</b>\nThe YOUTUBE_COOKIES may have expired - export fresh cookies "
                                "from the bot's YouTube account and update the variable in Vercel.\n"
                                f"<code>{html.escape(clip(err, 250))}</code>")
        else:
            await _edit(status, "⚠️ I couldn't download this song. Try different words.", fail_markup)
            await send_log(bot, f"⚠️ <b>YouTube download failed</b>\n<code>{html.escape(clip(err, 300))}</code>")
    finally:
        if video_lock:
            await asyncio.to_thread(db.release, video_lock)
        await asyncio.to_thread(db.release, f"user{user.id}")
        shutil.rmtree(workdir, ignore_errors=True)


async def youtube_callback(update, context):
    """'⬇️ Get it from YouTube' button (and 'try again' after force-subscribe)."""
    q = update.callback_query
    user = q.from_user
    doc = await asyncio.to_thread(db.get_query, q.data.split("|", 1)[1])
    if not doc:
        await q.answer("This has expired. Please search again.", show_alert=True)
        return
    if doc["user_id"] != user.id:
        await q.answer("This isn't your search. Type a song name yourself 🙂", show_alert=True)
        return
    if await asyncio.to_thread(db.is_banned, user.id):
        await q.answer("You can't use this bot.", show_alert=True)
        return
    gate = await fsub_gate(context.bot, user.id, q.data)
    if gate:
        await q.answer()
        await context.bot.send_message(q.message.chat.id, gate[0], reply_markup=gate[1])
        return
    await q.answer("🔎 Searching YouTube…")
    chat = q.message.chat
    await youtube_flow(
        context.bot, chat.id, user, doc["q"], q.message.message_id, update.update_id,
        chat_title=chat.title if chat.type in ("group", "supergroup") else None,
    )
