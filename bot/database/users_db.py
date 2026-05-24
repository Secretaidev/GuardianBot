"""
bot/database/users_db.py
────────────────────────
User tracking – stores every user that interacts with the bot or a group.

Collection : users
Indexes    : user_id (unique), username (sparse)
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from pymongo import ReturnDocument

from bot.database.mongo import get_collection

logger = logging.getLogger(__name__)


def _col():
    """Return the 'users' Motor collection."""
    return get_collection("users")


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

async def upsert_user(
    user_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
) -> dict[str, Any]:
    """
    Insert or update a user document.

    Parameters
    ----------
    user_id    : Telegram user ID (required)
    username   : @handle without the leading '@', may be None
    first_name : Telegram first name, may be None
    last_name  : Telegram last name, may be None

    Returns
    -------
    dict  – the updated user document
    """
    now = datetime.now(timezone.utc)
    set_on_insert = {
        "user_id": user_id,
        "created_at": now,
    }
    set_always: dict[str, Any] = {"updated_at": now}

    if username is not None:
        set_always["username"] = username
    if first_name is not None:
        set_always["first_name"] = first_name
    if last_name is not None:
        set_always["last_name"] = last_name

    doc = await _col().find_one_and_update(
        {"user_id": user_id},
        {
            "$set": set_always,
            "$setOnInsert": set_on_insert,
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return doc


async def get_user(user_id: int) -> Optional[dict[str, Any]]:
    """
    Fetch a single user document by Telegram user_id.

    Returns None if the user is not in the database.
    """
    doc = await _col().find_one({"user_id": user_id}, {"_id": 0})
    return doc


async def get_all_users() -> list[dict[str, Any]]:
    """
    Return a list of all user documents (without the internal _id field).
    """
    cursor = _col().find({}, {"_id": 0})
    users: list[dict[str, Any]] = []
    async for doc in cursor:
        users.append(doc)
    return users


async def get_user_count() -> int:
    """Return the total number of users stored in the database."""
    return await _col().count_documents({})


async def delete_user(user_id: int) -> bool:
    """
    Remove a user document from the database.

    Returns True if a document was deleted, False if the user was not found.
    """
    result = await _col().delete_one({"user_id": user_id})
    deleted = result.deleted_count > 0
    if deleted:
        logger.info("Deleted user %s from database.", user_id)
    else:
        logger.warning("Attempted to delete non-existent user %s.", user_id)
    return deleted
