"""
bot/modules/users.py
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — User tracking and /info module.

Responsibilities
----------------
• Passive message handler — silently upserts every sender into the DB
• ChatMember update handler — records users who join / leave groups
• /info command — display a formatted user information card
• /id   command — show user + chat IDs (shared with start.py guard, safe dup)
"""

from __future__ import annotations

import logging
from typing import Optional

from telegram import ChatMemberUpdated, Message, Update, User
from telegram.constants import ChatMemberStatus, ChatType, ParseMode
from telegram.ext import (
    Application,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.database.chats_db import upsert_chat
from bot.database.users_db import get_user, upsert_user
from bot.fonts import sc
from bot.helpers.extractors import extract_user
from bot.helpers.permissions import get_user_status

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Passive tracking helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _track_user(user: User) -> None:
    """Upsert a single user into the database silently."""
    try:
        await upsert_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )
    except Exception as exc:
        logger.warning("_track_user(%s) failed: %s", user.id, exc)


async def _track_chat(message: Message) -> None:
    """Upsert the chat that produced *message* into the database silently."""
    chat = message.chat
    if chat.type not in ("group", "supergroup"):
        return
    try:
        await upsert_chat(
            chat_id=chat.id,
            chat_name=chat.title or str(chat.id),
            chat_type=chat.type,
        )
    except Exception as exc:
        logger.warning("_track_chat(%s) failed: %s", chat.id, exc)


# ─────────────────────────────────────────────────────────────────────────────
# Message handler — track every sender
# ─────────────────────────────────────────────────────────────────────────────

async def handler_track_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Passive handler that runs on every non-command message in groups.

    Upserts the sender and the chat into the database.  The handler has no
    visible side-effect for the user.
    """
    msg = update.effective_message
    user = update.effective_user

    if msg is None or user is None or user.is_bot:
        return

    await _track_user(user)
    if msg.chat.type in ("group", "supergroup"):
        await _track_chat(msg)


# ─────────────────────────────────────────────────────────────────────────────
# ChatMember handler — track joins / leaves
# ─────────────────────────────────────────────────────────────────────────────

async def handler_chat_member_update(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Track users who join or leave a group by listening to ChatMember updates.

    Records the new member in the database and upserts the chat document so
    the group is always reflected in our DB.
    """
    if update.chat_member is None:
        return

    change: ChatMemberUpdated = update.chat_member
    new_member = change.new_chat_member
    chat = change.chat

    # Only care about users entering the group
    if new_member.status in (
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.CREATOR,
    ):
        user = new_member.user
        if not user.is_bot:
            await _track_user(user)

    # Always keep the chat document fresh
    try:
        await upsert_chat(
            chat_id=chat.id,
            chat_name=chat.title or str(chat.id),
            chat_type=chat.type,
        )
    except Exception as exc:
        logger.warning("handler_chat_member_update upsert_chat failed: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# /info command
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Display a formatted information card for the target user.

    Target resolution priority:
      1. Replied-to message author
      2. @username or numeric ID in command arguments
      3. The command sender themselves (fallback)

    Displayed information:
      • Full name
      • User ID
      • Username (if any)
      • Admin status in the current chat
      • Number of warns (if in a group)
      • Last seen (from DB, if available)
    """
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if msg is None or chat is None or user is None:
        return

    # ── Resolve target user ──────────────────────────────────────────────────
    extracted = await extract_user(update, context)

    if extracted.user is not None:
        target: User = extracted.user
    else:
        # Fall back to the command sender when no specifier was given
        target = user

    # ── Fetch DB record ──────────────────────────────────────────────────────
    db_doc: Optional[dict] = None
    try:
        db_doc = await get_user(target.id)
    except Exception as exc:
        logger.warning("cmd_info get_user(%s) failed: %s", target.id, exc)

    # ── Determine admin status ───────────────────────────────────────────────
    status_label = sc("member")
    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        raw_status = await get_user_status(chat.id, target.id, context.bot)
        if raw_status == ChatMemberStatus.CREATOR:
            status_label = f"👑 {sc('owner')}"
        elif raw_status == ChatMemberStatus.ADMINISTRATOR:
            status_label = f"🛡 {sc('admin')}"
        elif raw_status == ChatMemberStatus.BANNED:
            status_label = f"🚫 {sc('banned')}"
        elif raw_status == ChatMemberStatus.LEFT:
            status_label = f"🚪 {sc('left')}"
        else:
            status_label = f"👤 {sc('member')}"
    else:
        status_label = f"👤 {sc('user')}"

    # ── Build name and username fields ───────────────────────────────────────
    full_name = target.full_name or sc("unknown")
    username_line = (
        f"@{target.username}"
        if target.username
        else sc("none")
    )

    # ── Build mention link ────────────────────────────────────────────────────
    mention = f'<a href="tg://user?id={target.id}">{full_name}</a>'

    # ── Last seen from DB ─────────────────────────────────────────────────────
    if db_doc and db_doc.get("updated_at"):
        last_seen_dt = db_doc["updated_at"]
        last_seen_str = last_seen_dt.strftime("%Y-%m-%d %H:%M UTC")
    else:
        last_seen_str = sc("unknown")

    # ── Compose the card ──────────────────────────────────────────────────────
    card = (
        f"╔══════════════════════╗\n"
        f"║  <b>{sc('user information')}</b>   ║\n"
        f"╚══════════════════════╝\n\n"
        f"👤 {sc('name')}: {mention}\n"
        f"🆔 {sc('id')}: <code>{target.id}</code>\n"
        f"🔗 {sc('username')}: {username_line}\n"
        f"📊 {sc('status')}: {status_label}\n"
        f"🕐 {sc('last seen')}: {last_seen_str}\n"
    )

    # Add a "forward to get info" note if the user is not in DB
    if db_doc is None:
        card += f"\n⚠️ <i>{sc('this user has not interacted with me yet.')}</i>"

    await msg.reply_text(
        card,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# /id command (group-focused, complements start.py)
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show the user ID of the sender and the chat ID of the current chat.

    If the command is a reply, also show the replied-to user's ID.
    """
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if msg is None or user is None or chat is None:
        return

    lines: list[str] = []

    if chat.type == ChatType.PRIVATE:
        lines.append(f"👤 {sc('your user id')}: <code>{user.id}</code>")
    else:
        lines.append(f"💬 {sc('chat id')}: <code>{chat.id}</code>")
        lines.append(f"👤 {sc('your user id')}: <code>{user.id}</code>")
        if msg.reply_to_message and msg.reply_to_message.from_user:
            target = msg.reply_to_message.from_user
            lines.append(
                f"🔎 {sc('replied user')}: <b>{target.full_name}</b> — <code>{target.id}</code>"
            )

    await msg.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


# ─────────────────────────────────────────────────────────────────────────────
# Handler registration
# ─────────────────────────────────────────────────────────────────────────────

def register_handlers(app: Application) -> None:
    """
    Register all handlers defined in this module with the PTB Application.

    Args:
        app: The :class:`telegram.ext.Application` instance.
    """
    # Passive tracking — every non-command group message
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & ~filters.COMMAND,
            handler_track_message,
        ),
        group=1,  # Low-priority group so commands run first
    )

    # Track chat member updates (joins / leaves / promotions)
    app.add_handler(
        ChatMemberHandler(
            handler_chat_member_update,
            ChatMemberHandler.CHAT_MEMBER,
        )
    )

    app.add_handler(CommandHandler("info", cmd_info))
    app.add_handler(CommandHandler("id", cmd_id))

    logger.info("users.py handlers registered.")
