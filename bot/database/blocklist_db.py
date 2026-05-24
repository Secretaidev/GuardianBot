"""
bot/database/blocklist_db.py
────────────────────────────
Per-chat blocklist (banned words / phrases).

Collection : blocklist
Index      : (chat_id, trigger) unique compound

The blocklist mode is stored per-chat in the 'chats' collection (key:
'blocklist_mode') to keep the architecture consistent with other settings.
Individual trigger documents carry their own mode so they can override the
chat-wide default if needed.

block_mode values
─────────────────
'delete'     – silently delete the offending message
'warn'       – warn the user (uses warns_db)
'mute'       – indefinitely mute the user
'kick'       – kick the user from the group
'ban'        – permanently ban the user
'tban:<N>'   – temporarily ban for N seconds
'tmute:<N>'  – temporarily mute for N seconds
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from pymongo import ReturnDocument

from bot.database.mongo import get_collection

logger = logging.getLogger(__name__)

_DEFAULT_MODE = "delete"


def _bl_col():
    return get_collection("blocklist")


def _ch_col():
    return get_collection("chats")


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

async def add_to_blocklist(
    chat_id: int,
    trigger: str,
    block_mode: str = _DEFAULT_MODE,
) -> dict[str, Any]:
    """
    Add or update a blocked trigger for a chat.

    Parameters
    ----------
    chat_id    : Telegram group chat ID
    trigger    : word/phrase to block (stored and matched case-insensitively)
    block_mode : action to take when trigger is matched (default 'delete')

    Returns
    -------
    dict – the upserted blocklist document
    """
    trigger_lower = trigger.strip().lower()
    now = datetime.now(timezone.utc)

    doc = await _bl_col().find_one_and_update(
        {"chat_id": chat_id, "trigger": trigger_lower},
        {
            "$set": {
                "chat_id": chat_id,
                "trigger": trigger_lower,
                "mode": block_mode,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    logger.info(
        "Added blocklist trigger '%s' (mode=%s) for chat %s.",
        trigger_lower, block_mode, chat_id,
    )
    return doc


async def remove_from_blocklist(chat_id: int, trigger: str) -> bool:
    """
    Remove a blocked trigger.

    Returns True if the trigger existed and was removed.
    """
    trigger_lower = trigger.strip().lower()
    result = await _bl_col().delete_one(
        {"chat_id": chat_id, "trigger": trigger_lower}
    )
    removed = result.deleted_count > 0
    if removed:
        logger.info("Removed blocklist trigger '%s' from chat %s.", trigger_lower, chat_id)
    else:
        logger.warning(
            "Trigger '%s' not in blocklist for chat %s.", trigger_lower, chat_id
        )
    return removed


async def get_blocklist(chat_id: int) -> list[dict[str, Any]]:
    """
    Return all blocklist entries for a chat as a list of
    {'trigger': str, 'mode': str} dicts, sorted by trigger.
    """
    cursor = _bl_col().find(
        {"chat_id": chat_id},
        {"_id": 0, "trigger": 1, "mode": 1},
    )
    entries: list[dict[str, Any]] = []
    async for doc in cursor:
        entries.append({"trigger": doc["trigger"], "mode": doc["mode"]})
    entries.sort(key=lambda x: x["trigger"])
    return entries


async def clear_blocklist(chat_id: int) -> int:
    """
    Remove every trigger from the blocklist for a chat.

    Returns the number of triggers deleted.
    """
    result = await _bl_col().delete_many({"chat_id": chat_id})
    count = result.deleted_count
    logger.info("Cleared %s blocklist entry/entries from chat %s.", count, chat_id)
    return count


async def get_blocklist_mode(chat_id: int) -> str:
    """
    Return the default blocklist action mode for a chat.

    Falls back to 'delete' if the chat document or setting does not exist.
    """
    doc = await _ch_col().find_one(
        {"chat_id": chat_id},
        {"_id": 0, "blocklist_mode": 1},
    )
    if doc:
        return doc.get("blocklist_mode", _DEFAULT_MODE)
    return _DEFAULT_MODE


async def set_blocklist_mode(chat_id: int, mode: str) -> None:
    """
    Set the default blocklist action mode for a chat.

    Parameters
    ----------
    chat_id : Telegram group chat ID
    mode    : 'delete' | 'warn' | 'mute' | 'kick' | 'ban' | 'tban:<N>' | 'tmute:<N>'
    """
    await _ch_col().update_one(
        {"chat_id": chat_id},
        {
            "$set": {
                "blocklist_mode": mode,
                "updated_at": datetime.now(timezone.utc),
            },
            "$setOnInsert": {"chat_id": chat_id},
        },
        upsert=True,
    )
    logger.info("Blocklist mode for chat %s set to '%s'.", chat_id, mode)


async def match_blocklist(chat_id: int, text: str) -> Optional[dict[str, Any]]:
    """
    Check whether `text` contains any blocked trigger for the chat.

    The check is case-insensitive. Returns the first matching entry dict
    {'trigger': str, 'mode': str} or None if no match.

    Tip: for busy groups, cache the trigger list in memory and invalidate on
    add/remove operations to reduce round-trips.
    """
    text_lower = text.lower()
    entries = await get_blocklist(chat_id)
    for entry in entries:
        if entry["trigger"] in text_lower:
            return entry
    return None
