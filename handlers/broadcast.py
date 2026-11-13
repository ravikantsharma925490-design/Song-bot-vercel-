"""
/broadcast — sirf ADMINS (bot owner).

PRIVATE chat mein (sabko bhejne ke liye):
  /broadcast aapka text               -> text sabko jayega
  (kisi message par reply) /broadcast -> wo message (photo/video/formatting ke saath) sabko jayega
  Target: bot ke saare groups + saare users. Pehle preview aata hai, "Send" dabane par hi jata hai.
  Vercel ke time limit ki wajah se kaam chhote hisso mein hota hai; baaki bacha ho to "Continue" button aata hai.

GROUP mein (test ke liye):
  Group mein /broadcast likho to message SIRF usi group mein jayega, kisi aur ko nahi.
"""

import asyncio
import logging
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import RetryAfter, Forbidden, TelegramError
from telegram.ext import ContextTypes

import database as db
from config import ADMINS, BROADCAST_BATCH_SECONDS

log = logging.getLogger(__name__)

_SEND_GAP = 0.05   # do messages ke beech gap (Telegram flood limit se bachne ke liye)
_SAVE_EVERY = 20   # itne messages ke baad progress DB mein save


def _buttons(*pairs):
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=data) for label, data in pairs]])


def _report(job, done):
    total = len(job["targets"])
    head = "✅ Broadcast complete" if done else f"⏳ Broadcast: {job['pos']}/{total} bheja gaya"
    return (
        f"{head}\n\n"
        f"👥 Groups: {job['sent_g']} gaya, {job['fail_g']} fail\n"
        f"🙋 Users: {job['sent_u']} gaya, {job['fail_u']} fail, "
        f"{job['removed_u']} ne bot block kiya (list se hata diye)"
    )


async def _send_one(context, job, chat_id):
    """'ok' / 'forbidden' (blocked/kicked) / 'fail'."""
    for _ in range(2):
        try:
            if job.get("src_message_id"):
                await context.bot.copy_message(chat_id, job["src_chat_id"], job["src_message_id"])
            else:
                await context.bot.send_message(chat_id, job["text"])
            return "ok"
        except RetryAfter as e:
            wait = e.retry_after
            wait = wait.total_seconds() if hasattr(wait, "total_seconds") else wait
            await asyncio.sleep(min(float(wait), 5) + 0.5)
        except Forbidden:
            return "forbidden"
        except TelegramError:
            return "fail"
        except Exception:
            log.exception("broadcast send failed for %s", chat_id)
            return "fail"
    return "fail"


async def _run_batch(context, job):
    """Time budget tak bhejta hai. True = sab ho gaya."""
    start = time.monotonic()
    targets = job["targets"]
    pos = job["pos"]
    since_save = 0

    def _stats():
        return {k: job[k] for k in ("sent_g", "fail_g", "sent_u", "fail_u", "removed_u")}

    while pos < len(targets):
        if time.monotonic() - start >= BROADCAST_BATCH_SECONDS:
            break
        kind, cid = targets[pos]
        result = await _send_one(context, job, cid)
        if kind == "g":
            job["sent_g" if result == "ok" else "fail_g"] += 1
            if result == "forbidden":
                await asyncio.to_thread(db.remove_chat, cid)  # bot group se nikal diya gaya
        else:
            if result == "ok":
                job["sent_u"] += 1
            elif result == "forbidden":
                job["removed_u"] += 1
                await asyncio.to_thread(db.remove_user, cid)
            else:
                job["fail_u"] += 1
        pos += 1
        since_save += 1
        if since_save >= _SAVE_EVERY:
            await asyncio.to_thread(db.update_broadcast_job, pos=pos, **_stats())
            since_save = 0
        await asyncio.sleep(_SEND_GAP)

    job["pos"] = pos
    done = pos >= len(targets)
    await asyncio.to_thread(
        db.update_broadcast_job, pos=pos, status="done" if done else "running", locked_until=0, **_stats()
    )
    return done


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.effective_message
    chat = update.effective_chat
    if user is None or user.id not in ADMINS or msg is None:
        return  # baaki logon ko koi reply nahi

    src_id = msg.reply_to_message.message_id if msg.reply_to_message else None
    text = None
    if not src_id:
        parts = (msg.text or "").split(None, 1)
        if len(parts) < 2 or not parts[1].strip():
            await msg.reply_text(
                "📢 Broadcast\n\n"
                "• /broadcast aapka text\n"
                "• ya kisi message (text/photo/video) par reply karke /broadcast\n\n"
                "Private chat mein sabko jayega. Group mein likhoge to sirf usi group mein jayega (test ke liye)."
            )
            return
        text = parts[1].strip()

    # GROUP mein: sirf isi group mein bhejo
    if chat.type != "private":
        job = {"src_chat_id": chat.id, "src_message_id": src_id, "text": text}
        if await _send_one(context, job, chat.id) != "ok":
            await msg.reply_text("⚠️ Is group mein bhej nahi paya.")
        return

    # PRIVATE mein: sabko bhejne se pehle preview + confirm
    job = {
        "_id": "current", "status": "pending", "pos": 0,
        "sent_g": 0, "fail_g": 0, "sent_u": 0, "fail_u": 0, "removed_u": 0,
    }
    if src_id:
        job["src_chat_id"] = msg.chat_id
        job["src_message_id"] = src_id
        preview = "(jis message par reply kiya, wahi jayega)"
    else:
        job["text"] = text
        preview = text[:300]

    groups = await asyncio.to_thread(db.list_group_ids)
    users = [u for u in await asyncio.to_thread(db.list_user_ids) if u != user.id]
    job["targets"] = [["g", g] for g in groups] + [["u", u] for u in users]
    if not job["targets"]:
        await msg.reply_text("Abhi koi group ya user nahi mila jise bheja ja sake.")
        return

    await asyncio.to_thread(db.save_broadcast_job, job)
    await msg.reply_text(
        f"📢 Broadcast ready\n\n{preview}\n\n"
        f"👥 Groups: {len(groups)}\n🙋 Users: {len(users)}\n\nBhejna hai?",
        reply_markup=_buttons(("✅ Send", "bc_send"), ("❌ Cancel", "bc_cancel")),
    )


async def broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id not in ADMINS:
        await query.answer()
        return

    if query.data == "bc_cancel":
        await asyncio.to_thread(db.delete_broadcast_job)
        await query.answer("Cancel")
        try:
            await query.edit_message_text("❌ Broadcast cancel kar diya.")
        except Exception:
            pass
        return

    statuses = ["pending"] if query.data == "bc_send" else ["running"]
    job = await asyncio.to_thread(db.claim_broadcast_job, statuses, BROADCAST_BATCH_SECONDS + 15)
    if not job:
        await query.answer("Ye pehle se chal raha hai ya mila nahi.", show_alert=True)
        return

    await query.answer("Bhej raha hu…")
    done = await _run_batch(context, job)
    try:
        await query.edit_message_text(
            _report(job, done),
            reply_markup=None if done else _buttons(("▶️ Continue", "bc_continue"), ("❌ Cancel", "bc_cancel")),
        )
    except Exception:
        pass
