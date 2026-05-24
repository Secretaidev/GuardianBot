"""
bot/database/chats_db.py
────────────────────────
Per-chat settings – one document per Telegram group / supergroup.

Collection : chats
Index      : chat_id (unique)

Default document structure is defined in CHAT_DEFAULTS and merged with the
provided values on first insert so that every field always exists.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from pymongo import ReturnDocument

from bot.database.mongo import get_collection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default chat document template
# ---------------------------------------------------------------------------
CHAT_DEFAULTS: dict[str, Any] = {
    "welcome_enabled": True,
    "welcome_text": None,
    "goodbye_enabled": False,
    "goodbye_text": None,
    "clean_welcome": True,
    "clean_service": False,
    "rules": None,
    "private_rules": False,
    "report_setting": True,
    "log_channel": None,
    "antiflood_limit": 0,
    "antiflood_mode": "kick",
    "warn_limit": 3,
    "warn_mode": "mute",
    "locks": {},
}


def _col():
    """Return the 'chats' Motor collection."""
    return get_collection("chats")


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

async def upsert_chat(
    chat_id: int,
    chat_name: str,
    chat_type: str,
) -> dict[str, Any]:
    """
    Insert or update a chat document.

    On first insert the document is initialised with all CHAT_DEFAULTS values
    plus created_at.  On subsequent calls only chat_name and chat_type are
    updated so user-customised settings are never overwritten.

    Parameters
    ----------
    chat_id   : Telegram chat ID (negative for groups)
    chat_name : Human-readable group / channel title
    chat_type : 'group' | 'supergroup' | 'channel' | 'private'

    Returns
    -------
    dict – the updated chat document
    """
    now = datetime.now(timezone.utc)

    # Fields that are only set on the very first insert
    set_on_insert: dict[str, Any] = {
        "chat_id": chat_id,
        "created_at": now,
        **CHAT_DEFAULTS,
    }

    # Fields updated every time
    set_always: dict[str, Any] = {
        "chat_name": chat_name,
        "chat_type": chat_type,
        "updated_at": now,
    }

    doc = await _col().find_one_and_update(
        {"chat_id": chat_id},
        {
            "$set": set_always,
            "$setOnInsert": set_on_insert,
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return doc


async def get_chat(chat_id: int) -> Optional[dict[str, Any]]:
    """
    Fetch the settings document for a chat.

    Returns None if the chat has never been registered.
    """
    doc = await _col().find_one({"chat_id": chat_id}, {"_id": 0})
    return doc


async def update_chat_setting(chat_id: int, key: str, value: Any) -> dict[str, Any]:
    """
    Update a single settings key for a chat.

    The chat document is created with defaults if it does not exist yet
    (upsert). Returns the updated document.

    Parameters
    ----------
    chat_id : Telegram chat ID
    key     : settings field name (e.g. 'welcome_enabled', 'warn_limit')
    value   : new value for that field
    """
    now = datetime.now(timezone.utc)
    set_on_insert: dict[str, Any] = {
        "chat_id": chat_id,
        "created_at": now,
        **CHAT_DEFAULTS,
    }
    doc = await _col().find_one_and_update(
        {"chat_id": chat_id},
        {
            "$set": {key: value, "updated_at": now},
            "$setOnInsert": set_on_insert,
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    logger.debug("Updated chat %s setting '%s' → %r", chat_id, key, value)
    return doc


async def get_all_chats() -> list[dict[str, Any]]:
    """Return a list of all chat documents (without the _id field)."""
    cursor = _col().find({}, {"_id": 0})
    chats: list[dict[str, Any]] = []
    async for doc in cursor:
        chats.append(doc)
    return chats


async def get_chat_count() -> int:
    """Return the total number of chats stored in the database."""
    return await _col().count_documents({})
