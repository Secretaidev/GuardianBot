"""
bot/database/filters_db.py
──────────────────────────
Per-chat keyword auto-reply filters.

Collection : filters
Indexes    : (chat_id, keyword) unique compound  |  chat_id

Keyword matching is case-insensitive: keywords are lowercased on save and all
lookups compare against the lower-cased form.

filter_data dict shape:
    {
        "reply"   : str | None  – text reply (may contain HTML/Markdown)
        "media"   : str | None  – file_id for an attached media item
        "media_type": str|None  – 'photo'|'video'|'document'|'audio'|'animation'|'sticker'
        "buttons" : list        – inline button rows [ [{text, url}] ]
        "parse_mode": str|None  – 'HTML' | 'Markdown' | None
    }
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from pymongo import ReturnDocument

from bot.database.mongo import get_collection

logger = logging.getLogger(__name__)


def _col():
    return get_collection("filters")


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

async def add_filter(
    chat_id: int,
    keyword: str,
    filter_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Add or overwrite a keyword filter for a chat.

    Parameters
    ----------
    chat_id     : Telegram group chat ID
    keyword     : trigger word/phrase (stored and matched case-insensitively)
    filter_data : dict with reply, media, buttons, etc.

    Returns
    -------
    dict – the saved filter document
    """
    keyword_lower = keyword.strip().lower()
    now = datetime.now(timezone.utc)

    doc = await _col().find_one_and_update(
        {"chat_id": chat_id, "keyword": keyword_lower},
        {
            "$set": {
                "chat_id": chat_id,
                "keyword": keyword_lower,
                "filter_data": filter_data,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    logger.info("Filter '%s' saved for chat %s.", keyword_lower, chat_id)
    return doc


async def get_filter(
    chat_id: int,
    keyword: str,
) -> Optional[dict[str, Any]]:
    """
    Fetch a filter document for a specific keyword.

    The lookup is case-insensitive (keyword is normalised before querying).
    Returns None if no matching filter exists.
    """
    keyword_lower = keyword.strip().lower()
    doc = await _col().find_one(
        {"chat_id": chat_id, "keyword": keyword_lower},
        {"_id": 0},
    )
    return doc


async def get_all_filters(chat_id: int) -> list[str]:
    """
    Return a sorted list of all filter keywords for a chat.
    """
    cursor = _col().find({"chat_id": chat_id}, {"_id": 0, "keyword": 1})
    keywords: list[str] = []
    async for doc in cursor:
        keywords.append(doc["keyword"])
    keywords.sort()
    return keywords


async def remove_filter(chat_id: int, keyword: str) -> bool:
    """
    Delete a filter by keyword.

    Returns True if the filter was found and removed.
    """
    keyword_lower = keyword.strip().lower()
    result = await _col().delete_one(
        {"chat_id": chat_id, "keyword": keyword_lower}
    )
    removed = result.deleted_count > 0
    if removed:
        logger.info("Removed filter '%s' from chat %s.", keyword_lower, chat_id)
    else:
        logger.warning(
            "Filter '%s' not found in chat %s.", keyword_lower, chat_id
        )
    return removed


async def remove_all_filters(chat_id: int) -> int:
    """
    Remove all filters for a chat.

    Returns the number of filters deleted.
    """
    result = await _col().delete_many({"chat_id": chat_id})
    count = result.deleted_count
    logger.info("Removed %s filter(s) from chat %s.", count, chat_id)
    return count


async def get_filter_by_text(chat_id: int, text: str) -> Optional[dict[str, Any]]:
    """
    Convenience helper – check whether `text` contains any registered keyword
    for the given chat and return the matching filter document.

    The check is case-insensitive. The first matching keyword wins.
    Returns None when no filter matches.

    Note: for high-throughput bots, consider caching the keyword list in memory
    and only hitting MongoDB when the cache is stale.
    """
    text_lower = text.lower()
    keywords = await get_all_filters(chat_id)
    for keyword in keywords:
        if keyword in text_lower:
            return await get_filter(chat_id, keyword)
    return None
