"""
Rose — Connections.
Manage group settings from PM by connecting to a group.
"""
from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from bot.config import OWNER_ID

logger = logging.getLogger(__name__)

# ── DB ────────────────────────────────────────────────────────────────────────

async def _get_col():
    from bot.database.mongo import get_collection
    return get_collection("connections")

_user_connections: dict[int, int] = {}  # user_id → chat_id

async def _connect(user_id: int, chat_id: int, chat_title: str):
    col = await _get_col()
    _user_connections[user_id] = chat_id
    await col.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id, "chat_id": chat_id, "chat_title": chat_title}},
        upsert=True,
    )

async def _disconnect(user_id: int):
    col = await _get_col()
    _user_connections.pop(user_id, None)
    await col.delete_one({"user_id": user_id})

async def _get_connection(user_id: int) -> dict | None:
    if user_id in _user_connections:
        col = await _get_col()
        doc = await col.find_one({"user_id": user_id})
        return doc
    col = await _get_col()
    doc = await col.find_one({"user_id": user_id})
    if doc:
        _user_connections[user_id] = doc["chat_id"]
    return doc

# Public helper for other modules
async def get_connected_chat(user_id: int) -> int | None:
    doc = await _get_connection(user_id)
    return doc["chat_id"] if doc else None


# ── Commands ──────────────────────────────────────────────────────────────────

async def cmd_connect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    args = context.args

    if chat.type != "private":
        # In group — connect user to this group
        try:
            member = await context.bot.get_chat_member(chat.id, user.id)
            from telegram.constants import ChatMemberStatus
            if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
                await msg.reply_text("❌ You must be an admin to connect.")
                return
        except Exception:
            await msg.reply_text("❌ Could not verify your admin status.")
            return

        await _connect(user.id, chat.id, chat.title or str(chat.id))
        await msg.reply_text(
            f"✅ Connected to <b>{chat.title}</b>.\n"
            "You can now manage this group from PM.",
            parse_mode=ParseMode.HTML,
        )
        return

    # In PM — need chat_id argument
    if not args:
        await msg.reply_text(
            "Usage: /connect <chat_id>\n"
            "Or use /connect in the group directly.",
        )
        return

    try:
        target_chat_id = int(args[0])
    except ValueError:
        await msg.reply_text("Please provide a valid chat ID (number).")
        return

    # Verify user is admin in target chat
    try:
        member = await context.bot.get_chat_member(target_chat_id, user.id)
        from telegram.constants import ChatMemberStatus
        if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
            if user.id != OWNER_ID:
                await msg.reply_text("❌ You must be an admin in that group.")
                return
    except Exception:
        await msg.reply_text("❌ I couldn't check that chat. Make sure I'm a member.")
        return

    try:
        target_chat = await context.bot.get_chat(target_chat_id)
        title = target_chat.title or str(target_chat_id)
    except Exception:
        title = str(target_chat_id)

    await _connect(user.id, target_chat_id, title)
    await msg.reply_text(
        f"✅ Connected to <b>{title}</b>.\n"
        "You can now manage this group from here.",
        parse_mode=ParseMode.HTML,
    )


async def cmd_disconnect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    doc = await _get_connection(user.id)

    if not doc:
        await update.effective_message.reply_text("You're not connected to any group.")
        return

    title = doc.get("chat_title", "Unknown")
    await _disconnect(user.id)
    await update.effective_message.reply_text(
        f"Disconnected from <b>{title}</b>.",
        parse_mode=ParseMode.HTML,
    )


async def cmd_connection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    doc = await _get_connection(user.id)

    if not doc:
        await update.effective_message.reply_text("You're not connected to any group.\nUse /connect <chat_id>")
        return

    title = doc.get("chat_title", "Unknown")
    chat_id = doc.get("chat_id", 0)
    await update.effective_message.reply_text(
        f"<b>Current connection:</b>\n"
        f"Group: {title}\n"
        f"ID: <code>{chat_id}</code>",
        parse_mode=ParseMode.HTML,
    )


def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("connect", cmd_connect))
    app.add_handler(CommandHandler("disconnect", cmd_disconnect))
    app.add_handler(CommandHandler("connection", cmd_connection))
