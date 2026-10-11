"""
Database — MongoDB. Collections:
  songs   : one record per song (name, search text, where to send it from)
  users   : bot users + ban status
  chats   : groups the bot is in (for /status)
  queries : temporary search record (for pagination, auto-deleted after 24 hours)
"""

import re
import uuid
from datetime import datetime

from pymongo import MongoClient

from config import MONGO_URI, MONGO_DB_NAME
from utils import normalize

_db = None


def init_db():
    global _db
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
    _db = client[MONGO_DB_NAME]
    _db.queries.create_index("created", expireAfterSeconds=86400)
    _db.users.create_index("user_id", unique=True)


# ---------------- Songs ----------------

def save_song(doc):
    """True = new song saved, False = already existed."""
    doc = dict(doc)
    _id = doc.pop("_id")
    doc["added"] = datetime.utcnow()
    res = _db.songs.update_one({"_id": _id}, {"$setOnInsert": doc}, upsert=True)
    return res.upserted_id is not None


def search_songs(query, page, page_size):
    tokens = normalize(query).split()[:6]
    if not tokens:
        return [], 0
    flt = {"$and": [{"search": {"$regex": re.escape(t)}} for t in tokens]}
    total = _db.songs.count_documents(flt, limit=500)
    items = list(
        _db.songs.find(flt).sort("name", 1).skip(page * page_size).limit(page_size)
    )
    return items, total


def get_song(song_id):
    return _db.songs.find_one({"_id": song_id})


def delete_song(song_id):
    return _db.songs.delete_one({"_id": song_id}).deleted_count


def delete_all_songs():
    return _db.songs.delete_many({}).deleted_count


def find_for_delete(query, limit=10):
    tokens = normalize(query).split()[:6]
    if not tokens:
        return []
    flt = {"$and": [{"search": {"$regex": re.escape(t)}} for t in tokens]}
    return list(_db.songs.find(flt).limit(limit))


def count_songs():
    return _db.songs.count_documents({})


# ---------------- Users ----------------

def add_user(user_id):
    _db.users.update_one(
        {"user_id": user_id},
        {"$setOnInsert": {"user_id": user_id, "joined": datetime.utcnow(), "banned": False}},
        upsert=True,
    )


def is_banned(user_id):
    return _db.users.find_one({"user_id": user_id, "banned": True}, {"_id": 1}) is not None


def set_ban(user_id, banned):
    _db.users.update_one(
        {"user_id": user_id},
        {"$set": {"banned": banned}, "$setOnInsert": {"user_id": user_id, "joined": datetime.utcnow()}},
        upsert=True,
    )


def count_users():
    return _db.users.count_documents({})


# ---------------- Search queries (pagination) ----------------

def make_query(text, user_id):
    qid = uuid.uuid4().hex[:10]
    _db.queries.insert_one(
        {"_id": qid, "q": text, "user_id": user_id, "created": datetime.utcnow()}
    )
    return qid


def get_query(qid):
    return _db.queries.find_one({"_id": qid})


# ---------------- Groups (for /status) ----------------

def track_chat(chat_id, title=""):
    _db.chats.update_one(
        {"_id": chat_id},
        {"$set": {"title": title or ""}, "$setOnInsert": {"added": datetime.utcnow()}},
        upsert=True,
    )


def remove_chat(chat_id):
    _db.chats.delete_one({"_id": chat_id})


def count_groups():
    return _db.chats.count_documents({})


def storage_used():
    """Bytes used by the database (data + indexes), or None if it can't be read."""
    try:
        st = _db.command("dbstats")
        return int(st.get("storageSize", 0) + st.get("indexSize", 0))
    except Exception:
        return None
