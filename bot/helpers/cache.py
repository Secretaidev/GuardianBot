"""In-memory TTL cache — keeps hot data off the DB wire."""

import time
from collections import defaultdict
from telegram.constants import ChatMemberStatus


class TTLDict:
    """Dead-simple key→value store with per-key expiry."""

    __slots__ = ("_store", "_default_ttl")

    def __init__(self, default_ttl: int = 60):
        self._store: dict = {}
        self._default_ttl = default_ttl

    def set(self, key, value, ttl: int | None = None):
        self._store[key] = (value, time.monotonic() + (ttl or self._default_ttl))

    def get(self, key, default=None):
        entry = self._store.get(key)
        if entry is None:
            return default
        val, expires = entry
        if time.monotonic() > expires:
            del self._store[key]
            return default
        return val

    def invalidate(self, key):
        self._store.pop(key, None)

    def clear(self):
        self._store.clear()

    def _sweep(self):
        now = time.monotonic()
        dead = [k for k, (_, exp) in self._store.items() if now > exp]
        for k in dead:
            del self._store[k]


# ── singleton caches ──────────────────────────────────────────────────────────
admin_cache = TTLDict(default_ttl=60)
settings_cache = TTLDict(default_ttl=30)
blocklist_cache = TTLDict(default_ttl=120)


async def get_cached_admins(chat_id: int, bot) -> list[int]:
    """Return admin user_ids for chat, cached 60s."""
    cached = admin_cache.get(chat_id)
    if cached is not None:
        return cached
    try:
        members = await bot.get_chat_administrators(chat_id)
        ids = [m.user.id for m in members]
        admin_cache.set(chat_id, ids)
        return ids
    except Exception:
        return []


def invalidate_admin_cache(chat_id: int):
    admin_cache.invalidate(chat_id)


async def get_cached_settings(chat_id: int) -> dict:
    """Return chat settings dict, cached 30s."""
    cached = settings_cache.get(chat_id)
    if cached is not None:
        return cached
    try:
        from bot.database.chats_db import get_chat
        data = await get_chat(chat_id)
        settings_cache.set(chat_id, data)
        return data
    except Exception:
        return {}


def invalidate_settings(chat_id: int):
    settings_cache.invalidate(chat_id)


async def get_cached_blocklist(chat_id: int) -> list[dict]:
    """Return blocklist entries, cached 120s."""
    cached = blocklist_cache.get(chat_id)
    if cached is not None:
        return cached
    try:
        from bot.database.blocklist_db import get_blocklist
        entries = await get_blocklist(chat_id)
        blocklist_cache.set(chat_id, entries)
        return entries
    except Exception:
        return []


def invalidate_blocklist(chat_id: int):
    blocklist_cache.invalidate(chat_id)
