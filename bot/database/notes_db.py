"""
bot/database/notes_db.py
────────────────────────
Per-chat saved notes (custom commands / keyword replies).

Collection : notes
Index      : (chat_id, note_name) unique compound

note_data dict may contain any of:
    {
        "type"    : str   – 'text' | 'photo' | 'video' | 'audio' | 'document' | 'sticker' | 'animation'
        "content" : str   – text content or file_id
        "caption" : str   – optional caption for media notes
        "buttons" : list  – list of inline button rows [ [{text, url}] ]
        "parse_mode": str – 'HTML' | 'Markdown' | None
    }
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from pymongo import ReturnDocument

from bot.database.mongo import get_collection

logger = logging.getLogger(__name__)


def _col():
    return get_collection("notes")


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

async def save_note(
    chat_id: int,
    note_name: str,
    note_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Create or overwrite a note for a chat.

    Parameters
    ----------
    chat_id   : Telegram group chat ID
    note_name : trigger keyword (case-folded on save for consistent retrieval)
    note_data : dict containing type, content, buttons, etc.

    Returns
    -------
    dict – the saved note document
    """
    # Normalise the key so retrieval is always case-insensitive
    note_name_lower = note_name.strip().lower()
    now = datetime.now(timezone.utc)

    doc = await _col().find_one_and_update(
        {"chat_id": chat_id, "note_name": note_name_lower},
        {
            "$set": {
                "chat_id": chat_id,
                "note_name": note_name_lower,
                "note_data": note_data,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    logger.info("Saved note '%s' for chat %s.", note_name_lower, chat_id)
    return doc


async def get_note(
    chat_id: int,
    note_name: str,
) -> Optional[dict[str, Any]]:
    """
    Fetch a single note document by name.

    Lookup is case-insensitive because note_name is stored lowercase.
    Returns None if no matching note exists.
    """
    note_name_lower = note_name.strip().lower()
    doc = await _col().find_one(
        {"chat_id": chat_id, "note_name": note_name_lower},
        {"_id": 0},
    )
    return doc


async def get_all_notes(chat_id: int) -> list[str]:
    """
    Return a sorted list of all note names registered for a chat.
    """
    cursor = _col().find({"chat_id": chat_id}, {"_id": 0, "note_name": 1})
    names: list[str] = []
    async for doc in cursor:
        names.append(doc["note_name"])
    names.sort()
    return names


async def delete_note(chat_id: int, note_name: str) -> bool:
    """
    Delete a note by name.

    Returns True if the note existed and was deleted.
    """
    note_name_lower = note_name.strip().lower()
    result = await _col().delete_one(
        {"chat_id": chat_id, "note_name": note_name_lower}
    )
    deleted = result.deleted_count > 0
    if deleted:
        logger.info("Deleted note '%s' from chat %s.", note_name_lower, chat_id)
    else:
        logger.warning(
            "Note '%s' not found in chat %s – nothing deleted.",
            note_name_lower,
            chat_id,
        )
    return deleted


async def delete_all_notes(chat_id: int) -> int:
    """
    Remove all notes for a chat.

    Returns the number of notes deleted.
    """
    result = await _col().delete_many({"chat_id": chat_id})
    count = result.deleted_count
    logger.info("Deleted %s note(s) from chat %s.", count, chat_id)
    return count
