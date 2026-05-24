"""
bot/helpers/permissions.py
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — Async permission helper functions.

All functions perform live Telegram API calls and cache results where
appropriate to avoid hitting rate limits.  Admin lists are cached per
chat for 60 seconds.
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional, Tuple

from telegram import Bot
from telegram.constants import ChatMemberStatus
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Admin list cache
# Structure: { chat_id: (timestamp, [user_id, ...]) }
# ─────────────────────────────────────────────────────────────────────────────
_admin_cache: dict[int, Tuple[float, List[int]]] = {}
_CACHE_TTL: float = 60.0  # seconds


def _invalidate_admin_cache(chat_id: int) -> None:
    """Remove the cached admin list for a specific chat (call after promotions)."""
    _admin_cache.pop(chat_id, None)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

async def get_admin_list(chat_id: int, bot: Bot) -> List[int]:
    """
    Return a list of user IDs that are admins (or the creator) in *chat_id*.

    Results are cached for ``_CACHE_TTL`` seconds to prevent flooding the
    Telegram API with repeated getChatAdministrators calls.

    Returns an empty list on any API error.
    """
    now = time.monotonic()
    cached = _admin_cache.get(chat_id)
    if cached is not None:
        ts, admin_ids = cached
        if now - ts < _CACHE_TTL:
            return admin_ids

    try:
        admins = await bot.get_chat_administrators(chat_id)
        admin_ids = [member.user.id for member in admins]
        _admin_cache[chat_id] = (now, admin_ids)
        return admin_ids
    except TelegramError as exc:
        logger.warning("get_admin_list(%s) failed: %s", chat_id, exc)
        return []


async def is_user_admin(chat_id: int, user_id: int, bot: Bot) -> bool:
    """
    Return *True* if *user_id* holds an administrator or creator role in
    *chat_id*.

    The function uses the cached admin list for efficiency.
    """
    admin_ids = await get_admin_list(chat_id, bot)
    return user_id in admin_ids


async def is_bot_admin(chat_id: int, bot: Bot) -> bool:
    """
    Return *True* if the bot itself is an administrator in *chat_id*.

    Uses ``bot.id`` and delegates to :func:`is_user_admin`.
    """
    return await is_user_admin(chat_id, bot.id, bot)


async def _get_bot_member(chat_id: int, bot: Bot):
    """
    Internal helper — fetch the bot's ChatMember object for *chat_id*.

    Returns *None* on error.
    """
    try:
        return await bot.get_chat_member(chat_id, bot.id)
    except TelegramError as exc:
        logger.warning("_get_bot_member(%s) failed: %s", chat_id, exc)
        return None


async def can_bot_restrict(chat_id: int, bot: Bot) -> bool:
    """
    Return *True* if the bot has the ``can_restrict_members`` privilege in
    *chat_id*.

    The bot must be an administrator with that specific right.
    """
    member = await _get_bot_member(chat_id, bot)
    if member is None:
        return False
    if member.status != ChatMemberStatus.ADMINISTRATOR:
        return False
    return bool(getattr(member, "can_restrict_members", False))


async def can_bot_delete(chat_id: int, bot: Bot) -> bool:
    """
    Return *True* if the bot has the ``can_delete_messages`` privilege in
    *chat_id*.
    """
    member = await _get_bot_member(chat_id, bot)
    if member is None:
        return False
    if member.status != ChatMemberStatus.ADMINISTRATOR:
        return False
    return bool(getattr(member, "can_delete_messages", False))


async def can_bot_pin(chat_id: int, bot: Bot) -> bool:
    """
    Return *True* if the bot has the ``can_pin_messages`` privilege in
    *chat_id*.
    """
    member = await _get_bot_member(chat_id, bot)
    if member is None:
        return False
    if member.status != ChatMemberStatus.ADMINISTRATOR:
        return False
    return bool(getattr(member, "can_pin_messages", False))


async def get_user_status(chat_id: int, user_id: int, bot: Bot) -> Optional[str]:
    """
    Return the raw ChatMemberStatus string for *user_id* in *chat_id*, or
    *None* on error.
    """
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status
    except TelegramError as exc:
        logger.warning("get_user_status(%s, %s) failed: %s", chat_id, user_id, exc)
        return None
