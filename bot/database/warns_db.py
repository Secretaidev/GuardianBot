"""
bot/database/warns_db.py
────────────────────────
Per-user warning tracking within a chat.

Collection : warns
Indexes    : (chat_id, user_id) compound  |  warn_id  |  chat_id

Each warning is stored as a sub-document inside an array field so that the
full warn history is always accessible in a single document read.

Document shape
--------------
{
    "chat_id"  : int,
    "user_id"  : int,
    "warns"    : [
        {
            "warn_id"   : str (UUID),
            "reason"    : str | None,
            "warned_by" : int (admin user_id),
            "date"      : datetime
        },
        ...
    ]
}

Warn settings are stored in 'chats' collection and accessed via chats_db, but
convenience read helpers are provided here so callers can avoid the import.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pymongo import ReturnDocument

from bot.database.mongo import get_collection

logger = logging.getLogger(__name__)


def _warns_col():
    return get_collection("warns")


def _chats_col():
    return get_collection("chats")


# ─────────────────────────────────────────────────────────────────────────────
# Public API – warning CRUD
# ─────────────────────────────────────────────────────────────────────────────

async def add_warn(
    chat_id: int,
    user_id: int,
    reason: Optional[str],
    warned_by: int,
) -> tuple[int, str]:
    """
    Append a warning to a user's warn list inside a chat.

    Parameters
    ----------
    chat_id   : Telegram group chat ID
    user_id   : Telegram user ID of the person being warned
    reason    : optional text reason
    warned_by : Telegram user ID of the admin issuing the warning

    Returns
    -------
    (warn_count, warn_id)
        warn_count – total number of active warnings after this addition
        warn_id    – UUID string identifying this specific warning
    """
    warn_id = str(uuid.uuid4())
    warn_doc = {
        "warn_id": warn_id,
        "reason": reason,
        "warned_by": warned_by,
        "date": datetime.now(timezone.utc),
    }

    updated = await _warns_col().find_one_and_update(
        {"chat_id": chat_id, "user_id": user_id},
        {
            "$push": {"warns": warn_doc},
            "$setOnInsert": {
                "chat_id": chat_id,
                "user_id": user_id,
            },
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )

    warn_count = len(updated.get("warns", []))
    logger.info(
        "Warn added – chat=%s user=%s count=%s warn_id=%s",
        chat_id,
        user_id,
        warn_count,
        warn_id,
    )
    return warn_count, warn_id


async def remove_warn(chat_id: int, warn_id: str) -> bool:
    """
    Remove a single warning by its UUID.

    Returns True if the warning was found and removed.
    """
    result = await _warns_col().update_one(
        {"chat_id": chat_id},
        {"$pull": {"warns": {"warn_id": warn_id}}},
    )
    removed = result.modified_count > 0
    if removed:
        logger.info("Removed warn %s from chat %s.", warn_id, chat_id)
    else:
        logger.warning("Warn %s not found in chat %s.", warn_id, chat_id)
    return removed


async def get_warns(chat_id: int, user_id: int) -> list[dict[str, Any]]:
    """
    Return all active warnings for a user in a chat as a list of dicts.
    Each dict has: warn_id, reason, warned_by, date.
    Returns an empty list if the user has no warnings.
    """
    doc = await _warns_col().find_one(
        {"chat_id": chat_id, "user_id": user_id},
        {"_id": 0, "warns": 1},
    )
    if doc is None:
        return []
    return doc.get("warns", [])


async def get_warn_count(chat_id: int, user_id: int) -> int:
    """Return the number of active warnings for a user in a chat."""
    warns = await get_warns(chat_id, user_id)
    return len(warns)


async def reset_warns(chat_id: int, user_id: int) -> bool:
    """
    Clear all warnings for a specific user in a chat.

    Returns True if a document was found and modified.
    """
    result = await _warns_col().update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {"$set": {"warns": []}},
    )
    reset_ok = result.matched_count > 0
    if reset_ok:
        logger.info("Reset warns for user %s in chat %s.", user_id, chat_id)
    return reset_ok


async def reset_all_warns(chat_id: int) -> int:
    """
    Clear all warnings for every user in a chat.

    Returns the number of user-warn-documents cleared.
    """
    result = await _warns_col().update_many(
        {"chat_id": chat_id},
        {"$set": {"warns": []}},
    )
    count = result.modified_count
    logger.info("Reset all warns in chat %s – %s user records cleared.", chat_id, count)
    return count


# ─────────────────────────────────────────────────────────────────────────────
# Warn settings (stored in chats collection for consistency)
# ─────────────────────────────────────────────────────────────────────────────

async def get_warn_settings(chat_id: int) -> dict[str, Any]:
    """
    Return warn settings for a chat: {'limit': int, 'mode': str}.

    Defaults to limit=3, mode='mute' if the chat document does not exist.
    """
    doc = await _chats_col().find_one(
        {"chat_id": chat_id},
        {"_id": 0, "warn_limit": 1, "warn_mode": 1},
    )
    if doc:
        return {
            "limit": doc.get("warn_limit", 3),
            "mode": doc.get("warn_mode", "mute"),
        }
    return {"limit": 3, "mode": "mute"}


async def set_warn_settings(chat_id: int, limit: int, mode: str) -> None:
    """
    Persist warn settings for a chat.

    Parameters
    ----------
    chat_id : Telegram group chat ID
    limit   : number of warns before action (e.g. 3)
    mode    : action to take – 'mute' | 'kick' | 'ban' | 'tban' | 'tmute'
    """
    await _chats_col().update_one(
        {"chat_id": chat_id},
        {
            "$set": {
                "warn_limit": limit,
                "warn_mode": mode,
                "updated_at": datetime.now(timezone.utc),
            },
            "$setOnInsert": {"chat_id": chat_id},
        },
        upsert=True,
    )
    logger.info(
        "Warn settings updated for chat %s: limit=%s mode=%s", chat_id, limit, mode
    )
