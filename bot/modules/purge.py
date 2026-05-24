"""
bot/modules/purge.py
────────────────────
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — Message purge module.

Commands
--------
/purge              — Reply to a message; deletes from that message up to
                      (and including) the /purge command message.
/del                — Delete the single message you replied to.
/purgefrom <msg_id> — Purge from a specific message ID to the current message.

After purging, a temporary status message is sent showing the count of
deleted messages. It self-deletes after 5 seconds.
"""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import CommandHandler, ContextTypes

from bot.fonts import sc
from bot.helpers.decorators import admin_required, bot_admin_required, group_only
from bot.logger import log_action

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _delete_range(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    start_id: int,
    end_id: int,
) -> int:
    """
    Delete all messages in the range [start_id, end_id] (inclusive).

    Skips messages that cannot be deleted (already deleted, pinned with no
    permission, service messages, etc.) and counts only successful deletions.

    Returns the number of messages successfully deleted.
    """
    deleted = 0
    # Telegram allows bulk deletion of up to 100 message IDs at a time
    # using deleteMessages (Bot API 6.9+).  We'll try the bulk method first
    # and fall back to individual deletes for compatibility.
    all_ids = list(range(start_id, end_id + 1))

    # Process in chunks of 100 (API limit for deleteMessages)
    chunk_size = 100
    for chunk_start in range(0, len(all_ids), chunk_size):
        chunk = all_ids[chunk_start : chunk_start + chunk_size]
        try:
            # python-telegram-bot v20.3+ exposes bot.delete_messages()
            await context.bot.delete_messages(chat_id=chat_id, message_ids=chunk)
            deleted += len(chunk)
        except TelegramError:
            # Fall back to individual deletions for this chunk
            for msg_id in chunk:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                    deleted += 1
                except TelegramError:
                    # Message may already be deleted or inaccessible — skip
                    pass
        # Small sleep between chunks to avoid hitting rate limits
        await asyncio.sleep(0.05)

    return deleted


async def _send_temp_status(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    text: str,
    delay: float = 5.0,
) -> None:
    """Send a status message to *chat_id* and delete it after *delay* seconds."""
    try:
        status_msg = await context.bot.send_message(chat_id=chat_id, text=text)
        await asyncio.sleep(delay)
        await context.bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
    except TelegramError as exc:
        logger.debug("_send_temp_status: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# /purge
# ─────────────────────────────────────────────────────────────────────────────

@group_only
@admin_required
@bot_admin_required
async def purge_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Purge messages from the replied-to message up to the current one."""
    chat = update.effective_chat
    actor = update.effective_user
    msg = update.effective_message

    if not msg.reply_to_message:
        await msg.reply_text(
            f"❌ {sc('reply to the message you want to start purging from.')}"
        )
        return

    start_id = msg.reply_to_message.message_id
    end_id = msg.message_id  # includes the /purge command itself

    # Delete the command message immediately so users see only the status
    try:
        await msg.delete()
    except TelegramError:
        pass

    deleted = await _delete_range(context, chat.id, start_id, end_id)

    # Send a temporary status message
    asyncio.create_task(
        _send_temp_status(
            context,
            chat.id,
            f"🗑 {sc(f'purged {deleted} message(s).')}",
        )
    )

    await log_action(
        context.bot,
        chat_id=chat.id,
        action="purge",
        admin=actor,
        target=None,
        extra=f"deleted {deleted} messages (IDs {start_id}–{end_id})",
    )


# ─────────────────────────────────────────────────────────────────────────────
# /del
# ─────────────────────────────────────────────────────────────────────────────

@group_only
@admin_required
@bot_admin_required
async def del_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete the single message that was replied to."""
    chat = update.effective_chat
    actor = update.effective_user
    msg = update.effective_message

    if not msg.reply_to_message:
        await msg.reply_text(
            f"❌ {sc('reply to the message you want to delete.')}"
        )
        return

    target_id = msg.reply_to_message.message_id

    # Delete both the target and the /del command
    for mid in (target_id, msg.message_id):
        try:
            await context.bot.delete_message(chat_id=chat.id, message_id=mid)
        except TelegramError:
            pass

    await log_action(
        context.bot,
        chat_id=chat.id,
        action="del",
        admin=actor,
        target=None,
        extra=f"deleted message_id={target_id}",
    )


# ─────────────────────────────────────────────────────────────────────────────
# /purgefrom
# ─────────────────────────────────────────────────────────────────────────────

@group_only
@admin_required
@bot_admin_required
async def purgefrom_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Purge messages starting from a specific message ID to the current message."""
    chat = update.effective_chat
    actor = update.effective_user
    msg = update.effective_message
    args = context.args or []

    if not args:
        await msg.reply_text(
            f"❌ {sc('usage:')} /purgefrom <message_id>\n"
            f"{sc('example:')} /purgefrom 12345"
        )
        return

    try:
        start_id = int(args[0])
    except ValueError:
        await msg.reply_text(f"❌ {sc('please provide a valid message ID (number).')}")
        return

    end_id = msg.message_id

    if start_id >= end_id:
        await msg.reply_text(
            f"❌ {sc('start message ID must be earlier than the current message.')}"
        )
        return

    if end_id - start_id > 5000:
        await msg.reply_text(
            f"❌ {sc('cannot purge more than 5000 messages at once.')}"
        )
        return

    # Delete the command message first
    try:
        await msg.delete()
    except TelegramError:
        pass

    deleted = await _delete_range(context, chat.id, start_id, end_id)

    asyncio.create_task(
        _send_temp_status(
            context,
            chat.id,
            f"🗑 {sc(f'purged {deleted} message(s) from id {start_id}.')}",
        )
    )

    await log_action(
        context.bot,
        chat_id=chat.id,
        action="purgefrom",
        admin=actor,
        target=None,
        extra=f"deleted {deleted} messages (IDs {start_id}–{end_id})",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Handler registration
# ─────────────────────────────────────────────────────────────────────────────

def register_handlers(app) -> None:
    """Register all purge-related command handlers with the Application."""
    app.add_handler(CommandHandler("purge", purge_cmd))
    app.add_handler(CommandHandler("del", del_cmd))
    app.add_handler(CommandHandler("purgefrom", purgefrom_cmd))
    logger.info("purge module registered.")
