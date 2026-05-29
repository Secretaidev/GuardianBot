"""
Rose — Clean Commands & Clean Service.
Auto-delete bot commands and service messages.
"""
from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from bot.helpers.decorators import admin_required, group_only

logger = logging.getLogger(__name__)

# ── DB ────────────────────────────────────────────────────────────────────────

_cache: dict[int, dict] = {}

async def _get_col():
    from bot.database.mongo import get_collection
    return get_collection("clean_settings")

async def _get_settings(chat_id: int) -> dict:
    if chat_id in _cache:
        return _cache[chat_id]
    col = await _get_col()
    doc = await col.find_one({"chat_id": chat_id})
    settings = {
        "clean_cmds": doc.get("clean_cmds", False) if doc else False,
        "clean_service": doc.get("clean_service", False) if doc else False,
    }
    _cache[chat_id] = settings
    return settings

async def _save(chat_id: int, settings: dict):
    col = await _get_col()
    _cache[chat_id] = settings
    await col.update_one(
        {"chat_id": chat_id},
        {"$set": {**settings, "chat_id": chat_id}},
        upsert=True,
    )

# public check for other modules
async def should_clean_cmds(chat_id: int) -> bool:
    s = await _get_settings(chat_id)
    return s["clean_cmds"]


# ── Commands ──────────────────────────────────────────────────────────────────

@group_only
@admin_required
async def cmd_cleancmds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    args = context.args
    settings = await _get_settings(chat.id)

    if not args:
        status = "enabled ✅" if settings["clean_cmds"] else "disabled ❌"
        await msg.reply_text(f"Clean commands: {status}")
        return

    val = args[0].lower()
    if val in ("on", "yes", "true"):
        settings["clean_cmds"] = True
        await _save(chat.id, settings)
        await msg.reply_text("✅ Bot command messages will be auto-deleted.")
    elif val in ("off", "no", "false"):
        settings["clean_cmds"] = False
        await _save(chat.id, settings)
        await msg.reply_text("❌ Clean commands disabled.")
    else:
        await msg.reply_text("Usage: /cleancmds on|off")


@group_only
@admin_required
async def cmd_cleanservice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    args = context.args
    settings = await _get_settings(chat.id)

    if not args:
        status = "enabled ✅" if settings["clean_service"] else "disabled ❌"
        await msg.reply_text(f"Clean service messages: {status}")
        return

    val = args[0].lower()
    if val in ("on", "yes", "true"):
        settings["clean_service"] = True
        await _save(chat.id, settings)
        await msg.reply_text("✅ Service messages (joined/left) will be auto-deleted.")
    elif val in ("off", "no", "false"):
        settings["clean_service"] = False
        await _save(chat.id, settings)
        await msg.reply_text("❌ Clean service disabled.")
    else:
        await msg.reply_text("Usage: /cleanservice on|off")


# ── Auto-delete service messages handler ──────────────────────────────────────

async def _clean_service_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    if not msg or not chat:
        return

    settings = await _get_settings(chat.id)
    if settings["clean_service"]:
        try:
            await msg.delete()
        except Exception:
            pass


def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("cleancmds", cmd_cleancmds))
    app.add_handler(CommandHandler("cleanservice", cmd_cleanservice))
    app.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER,
        _clean_service_handler,
    ), group=99)
