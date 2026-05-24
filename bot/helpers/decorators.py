"""
bot/helpers/decorators.py
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — Command access-control decorators.

All decorators wrap async handler functions and short-circuit execution
with a user-friendly small-caps error message when the required condition
is not satisfied.  They are fully compatible with python-telegram-bot v20+
async dispatcher patterns.
"""

from __future__ import annotations

import functools
import logging
from typing import Callable

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from bot.config import OWNER_ID as _OWNER_ID, SUDO_USERS as _SUDO_USERS
from bot.fonts import sc
from bot.helpers.permissions import is_bot_admin, is_user_admin

# Module-level aliases for brevity — read once at import time.
# These are intentionally resolved at import so that tests can monkeypatch Config.
OWNER_ID: int = _OWNER_ID
SUDO_USERS: set[int] = set(_SUDO_USERS)


logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helper
# ─────────────────────────────────────────────────────────────────────────────

async def _reply_error(update: Update, text: str) -> None:
    """Send a small-caps error reply to the triggering message."""
    if update.effective_message:
        await update.effective_message.reply_text(text)


# ─────────────────────────────────────────────────────────────────────────────
# @group_only
# ─────────────────────────────────────────────────────────────────────────────

def group_only(func: Callable) -> Callable:
    """
    Restrict the handler to group / supergroup chats only.
    Silently ignores the command when sent in a private chat.
    """
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        chat = update.effective_chat
        if chat is None:
            return
        if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            await _reply_error(
                update,
                f"❌ {sc('this command can only be used inside a group chat.')}",
            )
            return
        return await func(update, context, *args, **kwargs)

    return wrapper


# ─────────────────────────────────────────────────────────────────────────────
# @admin_required
# ─────────────────────────────────────────────────────────────────────────────

def admin_required(func: Callable) -> Callable:
    """
    Require the command sender to be an admin (or creator) in the current chat.
    Also transparently passes SUDO_USERS and the OWNER.
    """
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        chat = update.effective_chat

        if user is None or chat is None:
            return

        # Owner and sudo users always bypass the check
        if user.id == OWNER_ID or user.id in SUDO_USERS:
            return await func(update, context, *args, **kwargs)

        # In private chats the concept of "admin" doesn't apply — allow.
        if chat.type == ChatType.PRIVATE:
            return await func(update, context, *args, **kwargs)

        try:
            admin = await is_user_admin(chat.id, user.id, context.bot)
        except Exception as exc:
            logger.warning("admin_required check failed: %s", exc)
            admin = False

        if not admin:
            await _reply_error(
                update,
                f"❌ {sc('you need to be a group admin to use this command.')}",
            )
            return

        return await func(update, context, *args, **kwargs)

    return wrapper


# ─────────────────────────────────────────────────────────────────────────────
# @owner_only
# ─────────────────────────────────────────────────────────────────────────────

def owner_only(func: Callable) -> Callable:
    """
    Restrict the handler to the bot owner defined by OWNER_ID in config.
    """
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if user is None:
            return

        if user.id != OWNER_ID:
            await _reply_error(
                update,
                f"❌ {sc('this command is restricted to the bot owner only.')}",
            )
            return

        return await func(update, context, *args, **kwargs)

    return wrapper


# ─────────────────────────────────────────────────────────────────────────────
# @dev_only  (SUDO_USERS + OWNER)
# ─────────────────────────────────────────────────────────────────────────────

def dev_only(func: Callable) -> Callable:
    """
    Restrict the handler to SUDO_USERS (developers) and the bot owner.
    """
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if user is None:
            return

        allowed = {OWNER_ID} | set(SUDO_USERS)
        if user.id not in allowed:
            await _reply_error(
                update,
                f"❌ {sc('this command is reserved for bot developers only.')}",
            )
            return

        return await func(update, context, *args, **kwargs)

    return wrapper


# ─────────────────────────────────────────────────────────────────────────────
# @bot_admin_required
# ─────────────────────────────────────────────────────────────────────────────

def bot_admin_required(func: Callable) -> Callable:
    """
    Ensure the bot itself has administrator rights in the chat before
    proceeding.  Useful for commands that need ban / restrict / delete rights.
    """
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        chat = update.effective_chat
        if chat is None:
            return

        # In private chats the bot is always "admin".
        if chat.type == ChatType.PRIVATE:
            return await func(update, context, *args, **kwargs)

        try:
            bot_is_admin = await is_bot_admin(chat.id, context.bot)
        except Exception as exc:
            logger.warning("bot_admin_required check failed: %s", exc)
            bot_is_admin = False

        if not bot_is_admin:
            await _reply_error(
                update,
                f"❌ {sc('i need to be an admin in this group to perform that action.')}",
            )
            return

        return await func(update, context, *args, **kwargs)

    return wrapper
