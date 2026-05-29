"""
Rose — Log Channels.
Log admin actions to a dedicated channel per group.
"""
from __future__ import annotations

import html
import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.ext import Application, CommandHandler, ContextTypes

from bot.config import OWNER_ID
from bot.helpers.decorators import admin_required, group_only

logger = logging.getLogger(__name__)

# ── DB ────────────────────────────────────────────────────────────────────────

_cache: dict[int, int | None] = {}

async def _get_col():
    from bot.database.mongo import get_collection
    return get_collection("log_channels")

async def get_log_channel(chat_id: int) -> int | None:
    if chat_id in _cache:
        return _cache[chat_id]
    col = await _get_col()
    doc = await col.find_one({"chat_id": chat_id})
    channel = doc.get("log_channel_id") if doc else None
    _cache[chat_id] = channel
    return channel

async def _set_log_channel(chat_id: int, channel_id: int):
    col = await _get_col()
    _cache[chat_id] = channel_id
    await col.update_one(
        {"chat_id": chat_id},
        {"$set": {"chat_id": chat_id, "log_channel_id": channel_id}},
        upsert=True,
    )

async def _unset_log_channel(chat_id: int):
    col = await _get_col()
    _cache[chat_id] = None
    await col.delete_one({"chat_id": chat_id})


# ── Public logging function for other modules ─────────────────────────────────

async def send_log(bot, chat_id: int, log_text: str):
    """Send a log message to the group's log channel (if set)."""
    channel_id = await get_log_channel(chat_id)
    if not channel_id:
        return
    try:
        await bot.send_message(
            channel_id, log_text, parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.debug("Log channel send failed for %d: %s", chat_id, e)


# ── Commands ──────────────────────────────────────────────────────────────────

@group_only
@admin_required
async def cmd_logchannel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    channel = await get_log_channel(chat.id)

    if channel:
        await update.effective_message.reply_text(
            f"Log channel: <code>{channel}</code>",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.effective_message.reply_text("No log channel set.\nUse /setlog in a channel.")


@group_only
@admin_required
async def cmd_setlog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    args = context.args

    if not args:
        await msg.reply_text(
            "Usage: /setlog <channel_id>\n"
            "Get the channel ID by forwarding a message from the channel to @userinfobot",
        )
        return

    try:
        channel_id = int(args[0])
    except ValueError:
        await msg.reply_text("Please provide a valid channel ID (number).")
        return

    # Test if bot can send to channel
    try:
        test = await context.bot.send_message(
            channel_id,
            f"✅ Log channel set for <b>{html.escape(chat.title or str(chat.id))}</b>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await msg.reply_text(
            f"❌ Can't send to that channel. Make sure I'm an admin there.\nError: {e}",
        )
        return

    await _set_log_channel(chat.id, channel_id)
    await msg.reply_text(
        f"✅ Log channel set to <code>{channel_id}</code>.\n"
        "All admin actions will be logged there.",
        parse_mode=ParseMode.HTML,
    )


@group_only
@admin_required
async def cmd_unsetlog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    channel = await get_log_channel(chat.id)

    if not channel:
        await update.effective_message.reply_text("No log channel was set.")
        return

    await _unset_log_channel(chat.id)
    await update.effective_message.reply_text("✅ Log channel removed.")


def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("logchannel", cmd_logchannel))
    app.add_handler(CommandHandler("setlog", cmd_setlog))
    app.add_handler(CommandHandler("unsetlog", cmd_unsetlog))
