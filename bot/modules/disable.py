"""
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — ᴅɪꜱᴀʙʟᴇ ᴍᴏᴅᴜʟᴇ
Per-chat command disabling. Admins can disable specific bot commands.
"""
from __future__ import annotations

import html
import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

from bot.fonts import sc
from bot.helpers.decorators import admin_required, group_only
from bot.database import chats_db

logger = logging.getLogger(__name__)

# All commands that can be disabled
DISABLEABLE: set[str] = {
    "rules", "notes", "filters", "warns", "report",
    "blocklist", "flood", "locks", "id", "info", "adminlist",
    "pin", "pinned", "purge",
}


async def _get_disabled(chat_id: int) -> list:
    chat_data = await chats_db.get_chat(chat_id)
    return chat_data.get("disabled_commands", [])


async def _set_disabled(chat_id: int, disabled: list) -> None:
    await chats_db.update_chat_setting(chat_id, "disabled_commands", disabled)


# ──────────────────────────────────────────────────────────────────────────────
# /disable <command>
# ──────────────────────────────────────────────────────────────────────────────
@group_only
@admin_required
async def disable_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat

    if not context.args:
        await message.reply_text(
            f"⚠️ {sc('usage')}: /disable &lt;command&gt;\n"
            f"{sc('see /disableable for the full list.')}",
            parse_mode=ParseMode.HTML,
        )
        return

    cmd = context.args[0].lower().lstrip("/")
    if cmd not in DISABLEABLE:
        await message.reply_text(
            f"❓ <code>{html.escape(cmd)}</code> {sc('cannot be disabled.')}\n"
            f"{sc('use /disableable for the full list.')}",
            parse_mode=ParseMode.HTML,
        )
        return

    disabled = await _get_disabled(chat.id)
    if cmd in disabled:
        await message.reply_text(
            f"ℹ️ <code>{html.escape(cmd)}</code> {sc('is already disabled.')}",
            parse_mode=ParseMode.HTML,
        )
        return

    disabled.append(cmd)
    await _set_disabled(chat.id, disabled)
    await message.reply_text(
        f"🔕 /{html.escape(cmd)} {sc('has been disabled in this chat.')}",
        parse_mode=ParseMode.HTML,
    )


# ──────────────────────────────────────────────────────────────────────────────
# /enable <command>
# ──────────────────────────────────────────────────────────────────────────────
@group_only
@admin_required
async def enable_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat

    if not context.args:
        await message.reply_text(
            f"⚠️ {sc('usage')}: /enable &lt;command&gt;",
            parse_mode=ParseMode.HTML,
        )
        return

    cmd      = context.args[0].lower().lstrip("/")
    disabled = await _get_disabled(chat.id)

    if cmd not in disabled:
        await message.reply_text(
            f"ℹ️ <code>{html.escape(cmd)}</code> {sc('is not disabled.')}",
            parse_mode=ParseMode.HTML,
        )
        return

    disabled.remove(cmd)
    await _set_disabled(chat.id, disabled)
    await message.reply_text(
        f"✅ /{html.escape(cmd)} {sc('has been re-enabled.')}",
        parse_mode=ParseMode.HTML,
    )


# ──────────────────────────────────────────────────────────────────────────────
# /disabled  — list all disabled commands
# ──────────────────────────────────────────────────────────────────────────────
@group_only
async def disabled_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message  = update.effective_message
    chat     = update.effective_chat
    disabled = await _get_disabled(chat.id)

    if not disabled:
        await message.reply_text(
            f"✅ {sc('no commands are currently disabled in this chat.')}"
        )
        return

    lines = "\n".join(f"• <code>/{cmd}</code>" for cmd in sorted(disabled))
    await message.reply_text(
        f"<b>🔕 {sc('disabled commands')}</b>\n\n{lines}\n\n"
        f"{sc('re-enable with /enable &lt;command&gt;')}",
        parse_mode=ParseMode.HTML,
    )


# ──────────────────────────────────────────────────────────────────────────────
# /disableable  — show what can be disabled
# ──────────────────────────────────────────────────────────────────────────────
async def disableable_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lines = "\n".join(f"• <code>/{cmd}</code>" for cmd in sorted(DISABLEABLE))
    await update.effective_message.reply_text(
        f"<b>📋 {sc('disableable commands')}</b>\n\n{lines}",
        parse_mode=ParseMode.HTML,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Utility: check if a command is disabled (used by other modules)
# ──────────────────────────────────────────────────────────────────────────────
async def is_disabled(chat_id: int, command: str) -> bool:
    """Return True if the given command is disabled in this chat."""
    disabled = await _get_disabled(chat_id)
    return command.lower().lstrip("/") in disabled


# ──────────────────────────────────────────────────────────────────────────────
# HELP
# ──────────────────────────────────────────────────────────────────────────────
DISABLE_HELP = (
    f"<b>🔕 {sc('disable commands')}</b>\n\n"
    f"<b>/disable</b> &lt;command&gt; — {sc('disable a command in this chat')}\n"
    f"<b>/enable</b> &lt;command&gt; — {sc('re-enable a disabled command')}\n"
    f"<b>/disabled</b> — {sc('list all disabled commands')}\n"
    f"<b>/disableable</b> — {sc('list all commands that can be disabled')}\n"
)


# ──────────────────────────────────────────────────────────────────────────────
# REGISTER
# ──────────────────────────────────────────────────────────────────────────────
def register_handlers(app) -> None:
    app.add_handler(CommandHandler("disable",     disable_cmd,     block=False))
    app.add_handler(CommandHandler("enable",      enable_cmd,      block=False))
    app.add_handler(CommandHandler("disabled",    disabled_cmd,    block=False))
    app.add_handler(CommandHandler("disableable", disableable_cmd, block=False))
