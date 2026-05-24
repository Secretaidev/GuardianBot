"""
bot/database/antiflood_db.py
─────────────────────────────
Anti-flood system: persistent settings in MongoDB + in-memory sliding-window
flood detection.

Persistent layer (MongoDB)
──────────────────────────
Collection : antiflood
Index      : chat_id (unique)

Document shape:
    {
        "chat_id"     : int,
        "limit"       : int   – max messages in the time window (0 = disabled)
        "mode"        : str   – 'kick' | 'ban' | 'mute' | 'tban' | 'tmute'
        "time_window" : int   – sliding window in seconds (default 10)
    }

In-memory layer (FloodTracker)
──────────────────────────────
A module-level singleton `flood_tracker` (instance of FloodTracker) provides
O(1) amortised flood checks using a nested defaultdict of deques.  Each deque
stores message timestamps for a (chat_id, user_id) pair.  Entries older than
`time_window` seconds are purged on every check so memory stays bounded.

Usage
─────
    from bot.database.antiflood_db import flood_tracker, get_flood_settings

    flooding = flood_tracker.check_flood(chat_id, user_id, limit, time_window)
    if flooding:
        flood_tracker.reset_user(chat_id, user_id)
        # take action …
"""

import logging
from collections import defaultdict, deque
from datetime import datetime, timezone
from time import monotonic
from typing import Any, Optional

from pymongo import ReturnDocument

from bot.database.mongo import get_collection

logger = logging.getLogger(__name__)

_DEFAULT_LIMIT = 0          # 0 means disabled
_DEFAULT_MODE = "kick"
_DEFAULT_WINDOW = 10        # seconds


def _col():
    return get_collection("antiflood")


# ─────────────────────────────────────────────────────────────────────────────
# Persistent settings API
# ─────────────────────────────────────────────────────────────────────────────

async def get_flood_settings(chat_id: int) -> dict[str, Any]:
    """
    Return flood settings for a chat.

    Returns
    -------
    dict with keys:
        limit       : int  – message count threshold (0 = antiflood disabled)
        mode        : str  – action on flood detection
        time_window : int  – sliding window in seconds
    """
    doc = await _col().find_one({"chat_id": chat_id}, {"_id": 0})
    if doc:
        return {
            "limit": doc.get("limit", _DEFAULT_LIMIT),
            "mode": doc.get("mode", _DEFAULT_MODE),
            "time_window": doc.get("time_window", _DEFAULT_WINDOW),
        }
    return {
        "limit": _DEFAULT_LIMIT,
        "mode": _DEFAULT_MODE,
        "time_window": _DEFAULT_WINDOW,
    }


async def set_flood_settings(
    chat_id: int,
    limit: int,
    mode: str,
    time_window: int = _DEFAULT_WINDOW,
) -> dict[str, Any]:
    """
    Persist flood settings for a chat.

    Parameters
    ----------
    chat_id     : Telegram group chat ID
    limit       : messages allowed in the window before action (0 disables)
    mode        : 'kick' | 'ban' | 'mute' | 'tban:<N>' | 'tmute:<N>'
    time_window : sliding window duration in seconds (default 10)

    Returns
    -------
    dict – the updated antiflood document
    """
    now = datetime.now(timezone.utc)
    doc = await _col().find_one_and_update(
        {"chat_id": chat_id},
        {
            "$set": {
                "limit": limit,
                "mode": mode,
                "time_window": time_window,
                "updated_at": now,
            },
            "$setOnInsert": {
                "chat_id": chat_id,
                "created_at": now,
            },
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    logger.info(
        "Antiflood settings for chat %s: limit=%s mode=%s window=%ss",
        chat_id, limit, mode, time_window,
    )
    return doc


# ─────────────────────────────────────────────────────────────────────────────
# In-memory flood tracker
# ─────────────────────────────────────────────────────────────────────────────

class FloodTracker:
    """
    Sliding-window message rate tracker using in-process memory.

    Data structure
    ──────────────
    _timestamps : dict[chat_id, dict[user_id, deque[float]]]

    Each deque holds monotonic timestamps (from time.monotonic()) of recent
    messages.  Old timestamps (outside the window) are pruned on every access
    so memory use is proportional to the number of messages in the current
    window, not to total historical traffic.

    Thread / async safety
    ─────────────────────
    The tracker is not thread-safe on its own; it is designed for use inside a
    single-threaded asyncio event loop.  If you run multiple workers, use a
    Redis-based tracker instead.
    """

    def __init__(self) -> None:
        # nested defaultdict: chat_id → user_id → deque of timestamps
        self._timestamps: dict[int, dict[int, deque]] = defaultdict(
            lambda: defaultdict(deque)
        )

    # ------------------------------------------------------------------
    def check_flood(
        self,
        chat_id: int,
        user_id: int,
        limit: int,
        time_window: int = _DEFAULT_WINDOW,
    ) -> bool:
        """
        Record a new message and check whether the user is flooding.

        Parameters
        ----------
        chat_id     : Telegram group chat ID
        user_id     : Telegram user ID
        limit       : max messages allowed within `time_window` seconds
        time_window : sliding window duration in seconds

        Returns
        -------
        True if the user has exceeded the flood limit, False otherwise.
        If limit == 0 antiflood is disabled and this always returns False.
        """
        if limit == 0:
            return False

        now = monotonic()
        dq: deque = self._timestamps[chat_id][user_id]

        # Remove timestamps outside the current window
        cutoff = now - time_window
        while dq and dq[0] < cutoff:
            dq.popleft()

        # Record this message
        dq.append(now)

        # Check against the limit
        return len(dq) > limit

    # ------------------------------------------------------------------
    def reset_user(self, chat_id: int, user_id: int) -> None:
        """
        Clear the flood counter for a specific user in a specific chat.

        Call this after taking action against a flooder so their counter
        resets and they get a clean slate.
        """
        try:
            del self._timestamps[chat_id][user_id]
        except KeyError:
            pass  # nothing to clear

    # ------------------------------------------------------------------
    def reset_chat(self, chat_id: int) -> None:
        """Clear flood counters for every user in a chat."""
        self._timestamps.pop(chat_id, None)

    # ------------------------------------------------------------------
    def get_message_count(self, chat_id: int, user_id: int) -> int:
        """
        Return the current number of messages recorded in the active window
        for a user without advancing the counter or taking any action.
        """
        dq = self._timestamps.get(chat_id, {}).get(user_id, deque())
        return len(dq)

    # ------------------------------------------------------------------
    def prune_all(self, time_window: int = _DEFAULT_WINDOW) -> None:
        """
        Global pruning pass – remove all expired timestamps across every
        (chat, user) pair.  Call this periodically from a background job if
        you want to reclaim memory proactively (optional, not required for
        correctness).
        """
        cutoff = monotonic() - time_window
        for chat_data in self._timestamps.values():
            for dq in chat_data.values():
                while dq and dq[0] < cutoff:
                    dq.popleft()


# Module-level singleton – import and use directly
flood_tracker = FloodTracker()
