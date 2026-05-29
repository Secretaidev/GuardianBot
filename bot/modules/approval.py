"""
Rose — Approval system.
Approved users bypass locks, blocklist, and antiflood.
"""
from __future__ import annotations

import html
import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from bot.config import OWNER_ID
from bot.helpers.decorators import admin_required, group_only

logger = logging.getLogger(__name__)


# ── DB helpers ────────────────────────────────────────────────────────────────

async def _get_col():
    from bot.database.mongo import get_collection
    return get_collection("approvals")


async def _is_approved(chat_id: int, user_id: int) -> bool:
    col = await _get_col()
    doc = await col.find_one({"chat_id": chat_id, "user_id": user_id})
    return doc is not None


async def _add_approval(chat_id: int, user_id: int, name: str):
    col = await _get_col()
    await col.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {"$set": {"chat_id": chat_id, "user_id": user_id, "name": name}},
        upsert=True,
    )


async def _remove_approval(chat_id: int, user_id: int):
    col = await _get_col()
    await col.delete_one({"chat_id": chat_id, "user_id": user_id})


async def _get_approved(chat_id: int) -> list[dict]:
    col = await _get_col()
    return await col.find({"chat_id": chat_id}).to_list(length=200)


# public check used by other modules
async def is_approved(chat_id: int, user_id: int) -> bool:
    return await _is_approved(chat_id, user_id)


# ── Commands ──────────────────────────────────────────────────────────────────

@group_only
@admin_required
async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat

    if msg.reply_to_message:
        target = msg.reply_to_message.from_user
    elif context.args:
        try:
            from bot.helpers.extractors import extract_user
            target = await extract_user(msg, context.args)
        except Exception:
            target = None
    else:
        target = None

    if not target:
        await msg.reply_text("Reply to a user or provide a user ID/username.")
        return

    if await _is_approved(chat.id, target.id):
        await msg.reply_text(
            f"<b>{html.escape(target.first_name)}</b> is already approved.",
            parse_mode=ParseMode.HTML,
        )
        return

    await _add_approval(chat.id, target.id, target.first_name)
    await msg.reply_text(
        f"✅ <b>{html.escape(target.first_name)}</b> has been approved. "
        "They will now bypass locks, blocklist, and antiflood.",
        parse_mode=ParseMode.HTML,
    )


@group_only
@admin_required
async def cmd_unapprove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat

    if msg.reply_to_message:
        target = msg.reply_to_message.from_user
    elif context.args:
        try:
            from bot.helpers.extractors import extract_user
            target = await extract_user(msg, context.args)
        except Exception:
            target = None
    else:
        target = None

    if not target:
        await msg.reply_text("Reply to a user or provide a user ID/username.")
        return

    if not await _is_approved(chat.id, target.id):
        await msg.reply_text(
            f"<b>{html.escape(target.first_name)}</b> is not approved.",
            parse_mode=ParseMode.HTML,
        )
        return

    await _remove_approval(chat.id, target.id)
    await msg.reply_text(
        f"❌ <b>{html.escape(target.first_name)}</b> is no longer approved.",
        parse_mode=ParseMode.HTML,
    )


@group_only
@admin_required
async def cmd_approved(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    approved = await _get_approved(chat.id)

    if not approved:
        await update.effective_message.reply_text("No approved users in this chat.")
        return

    lines = ["<b>Approved users:</b>\n"]
    for i, doc in enumerate(approved, 1):
        name = html.escape(doc.get("name", "Unknown"))
        uid = doc.get("user_id", 0)
        lines.append(f" {i}. {name} (<code>{uid}</code>)")

    await update.effective_message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.HTML,
    )


def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("approve", cmd_approve))
    app.add_handler(CommandHandler("unapprove", cmd_unapprove))
    app.add_handler(CommandHandler("approved", cmd_approved))
