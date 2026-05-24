"""
bot/database/feds_db.py
───────────────────────
Federation system – cross-chat ban lists.

Collections
-----------
federations  : one document per federation
    { fed_id, fed_name, owner_id, created_at }

fed_chats    : one document per (fed_id, chat_id) membership
    { fed_id, chat_id, joined_at }

fed_bans     : one document per (fed_id, user_id) ban entry
    { fed_id, user_id, reason, banned_by, banned_at }

fed_admins   : one document per (fed_id, user_id) admin grant
    { fed_id, user_id, added_by, added_at }

Indexes defined in mongo.py.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pymongo import ReturnDocument

from bot.database.mongo import get_collection

logger = logging.getLogger(__name__)


def _feds():
    return get_collection("federations")


def _chats():
    return get_collection("fed_chats")


def _bans():
    return get_collection("fed_bans")


def _admins():
    return get_collection("fed_admins")


# ─────────────────────────────────────────────────────────────────────────────
# Federation CRUD
# ─────────────────────────────────────────────────────────────────────────────

async def create_fed(fed_name: str, owner_id: int) -> str:
    """
    Create a new federation.

    Parameters
    ----------
    fed_name : Human-readable name for the federation
    owner_id : Telegram user ID of the federation owner

    Returns
    -------
    str – UUID fed_id of the newly created federation
    """
    fed_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await _feds().insert_one(
        {
            "fed_id": fed_id,
            "fed_name": fed_name,
            "owner_id": owner_id,
            "created_at": now,
        }
    )
    logger.info("Created federation '%s' (id=%s) owner=%s.", fed_name, fed_id, owner_id)
    return fed_id


async def get_fed(fed_id: str) -> Optional[dict[str, Any]]:
    """Return the federation document or None if not found."""
    return await _feds().find_one({"fed_id": fed_id}, {"_id": 0})


async def get_fed_by_chat(chat_id: int) -> Optional[dict[str, Any]]:
    """
    Return the federation that a chat has joined, or None.

    Looks up the fed_chats membership and then returns the full federation doc.
    """
    membership = await _chats().find_one({"chat_id": chat_id}, {"_id": 0, "fed_id": 1})
    if membership is None:
        return None
    return await get_fed(membership["fed_id"])


async def get_user_feds(user_id: int) -> list[dict[str, Any]]:
    """
    Return all federations where the given user is the owner.
    """
    cursor = _feds().find({"owner_id": user_id}, {"_id": 0})
    result: list[dict[str, Any]] = []
    async for doc in cursor:
        result.append(doc)
    return result


async def delete_fed(fed_id: str) -> bool:
    """
    Delete a federation and all associated data (chats, bans, admins).

    Returns True if the federation existed and was deleted.
    """
    result = await _feds().delete_one({"fed_id": fed_id})
    if result.deleted_count == 0:
        logger.warning("Attempted to delete non-existent federation %s.", fed_id)
        return False

    # Cascade deletes
    await _chats().delete_many({"fed_id": fed_id})
    await _bans().delete_many({"fed_id": fed_id})
    await _admins().delete_many({"fed_id": fed_id})
    logger.info("Deleted federation %s and all related data.", fed_id)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Chat membership
# ─────────────────────────────────────────────────────────────────────────────

async def join_fed(fed_id: str, chat_id: int) -> bool:
    """
    Add a chat to a federation.

    A chat may only belong to one federation at a time.  If the chat is already
    in another federation it must leave first.

    Returns True if the chat successfully joined.
    """
    # Reject if the chat is already in any federation
    existing = await _chats().find_one({"chat_id": chat_id})
    if existing is not None:
        logger.warning(
            "Chat %s tried to join fed %s but is already in fed %s.",
            chat_id,
            fed_id,
            existing["fed_id"],
        )
        return False

    await _chats().insert_one(
        {
            "fed_id": fed_id,
            "chat_id": chat_id,
            "joined_at": datetime.now(timezone.utc),
        }
    )
    logger.info("Chat %s joined federation %s.", chat_id, fed_id)
    return True


async def leave_fed(fed_id: str, chat_id: int) -> bool:
    """
    Remove a chat from a federation.

    Returns True if the membership existed and was removed.
    """
    result = await _chats().delete_one({"fed_id": fed_id, "chat_id": chat_id})
    removed = result.deleted_count > 0
    if removed:
        logger.info("Chat %s left federation %s.", chat_id, fed_id)
    else:
        logger.warning("Chat %s was not in federation %s.", chat_id, fed_id)
    return removed


# ─────────────────────────────────────────────────────────────────────────────
# Federation bans
# ─────────────────────────────────────────────────────────────────────────────

async def fed_ban(
    fed_id: str,
    user_id: int,
    reason: Optional[str],
    banned_by: int,
) -> dict[str, Any]:
    """
    Add or update a federation ban for a user.

    Parameters
    ----------
    fed_id    : federation ID
    user_id   : Telegram ID of the user being banned
    reason    : optional ban reason text
    banned_by : Telegram ID of the admin issuing the ban

    Returns
    -------
    dict – the ban document (after upsert)
    """
    now = datetime.now(timezone.utc)
    doc = await _bans().find_one_and_update(
        {"fed_id": fed_id, "user_id": user_id},
        {
            "$set": {
                "reason": reason,
                "banned_by": banned_by,
                "banned_at": now,
            },
            "$setOnInsert": {
                "fed_id": fed_id,
                "user_id": user_id,
            },
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    logger.info(
        "Fed-ban: user=%s in fed=%s by=%s reason=%r",
        user_id, fed_id, banned_by, reason,
    )
    return doc


async def fed_unban(fed_id: str, user_id: int) -> bool:
    """
    Lift a federation ban.

    Returns True if the ban existed and was removed.
    """
    result = await _bans().delete_one({"fed_id": fed_id, "user_id": user_id})
    removed = result.deleted_count > 0
    if removed:
        logger.info("Fed-unban: user=%s in fed=%s.", user_id, fed_id)
    else:
        logger.warning("Fed-unban: user=%s was not banned in fed=%s.", user_id, fed_id)
    return removed


async def get_fed_bans(fed_id: str) -> list[dict[str, Any]]:
    """Return all ban documents for a federation, excluding MongoDB _id."""
    cursor = _bans().find({"fed_id": fed_id}, {"_id": 0})
    bans: list[dict[str, Any]] = []
    async for doc in cursor:
        bans.append(doc)
    return bans


async def is_fed_banned(fed_id: str, user_id: int) -> Optional[dict[str, Any]]:
    """
    Check whether a user is banned in a federation.

    Returns the ban document if banned, or None if not banned.
    """
    return await _bans().find_one(
        {"fed_id": fed_id, "user_id": user_id}, {"_id": 0}
    )


# ─────────────────────────────────────────────────────────────────────────────
# Federation admins
# ─────────────────────────────────────────────────────────────────────────────

async def add_fed_admin(fed_id: str, user_id: int, added_by: int) -> bool:
    """
    Grant federation-admin privileges to a user.

    Returns True if the user was newly added (False if already an admin).
    """
    existing = await _admins().find_one({"fed_id": fed_id, "user_id": user_id})
    if existing is not None:
        return False

    await _admins().insert_one(
        {
            "fed_id": fed_id,
            "user_id": user_id,
            "added_by": added_by,
            "added_at": datetime.now(timezone.utc),
        }
    )
    logger.info("Added user %s as admin of federation %s.", user_id, fed_id)
    return True


async def remove_fed_admin(fed_id: str, user_id: int) -> bool:
    """
    Revoke federation-admin privileges.

    Returns True if the admin record existed and was removed.
    """
    result = await _admins().delete_one({"fed_id": fed_id, "user_id": user_id})
    removed = result.deleted_count > 0
    if removed:
        logger.info("Removed user %s as admin of federation %s.", user_id, fed_id)
    else:
        logger.warning("User %s was not an admin of federation %s.", user_id, fed_id)
    return removed


async def get_fed_admins(fed_id: str) -> list[dict[str, Any]]:
    """Return all admin documents for a federation, excluding MongoDB _id."""
    cursor = _admins().find({"fed_id": fed_id}, {"_id": 0})
    admins: list[dict[str, Any]] = []
    async for doc in cursor:
        admins.append(doc)
    return admins


async def get_fed_chats(fed_id: str) -> list[dict[str, Any]]:
    """
    Return all chat membership documents for a federation.

    Each document has: fed_id, chat_id, joined_at.
    """
    cursor = _chats().find({"fed_id": fed_id}, {"_id": 0})
    chats: list[dict[str, Any]] = []
    async for doc in cursor:
        chats.append(doc)
    return chats


async def get_chat_membership(chat_id: int) -> Optional[dict[str, Any]]:
    """
    Return the federation membership document for a chat, or None.

    Returned dict has keys: fed_id, chat_id, joined_at.
    """
    return await _chats().find_one({"chat_id": chat_id}, {"_id": 0})


async def is_fed_admin(fed_id: str, user_id: int) -> bool:
    """Return True if user_id is an admin or owner of the given federation."""
    fed = await get_fed(fed_id)
    if fed and fed.get("owner_id") == user_id:
        return True
    admin_doc = await _admins().find_one({"fed_id": fed_id, "user_id": user_id})
    return admin_doc is not None

