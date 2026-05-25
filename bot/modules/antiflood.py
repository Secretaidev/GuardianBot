"""
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — ᴀɴᴛɪꜰʟᴏᴏᴅ ᴍᴏᴅᴜʟᴇ
Anti-flood protection with sliding window and configurable actions.
"""
from __future__ import annotations

import html
import logging

from telegram import Update, ChatPermissions
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters

from bot.fonts import sc
from bot.helpers.decorators import admin_required, group_only
from bot.database.antiflood_db import get_flood_settings, set_flood_settings, flood_tracker
from bot.logger import log_action

logger = logging.getLogger(__name__)

VALID_MODES = ("ban", "kick", "mute", "tban", "tmute")


async def _is_admin(chat_id: int, user_id: int, bot) -> bool:
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR)
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────────────────
# /setflood
# ──────────────────────────────────────────────────────────────────────────────
@group_only
@admin_required
async def setflood_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat

    if not context.args or not context.args[0].isdigit():
        await message.reply_text(
            f"⚠️ {sc('usage')}: /setflood &lt;number&gt;\n"
            f"{sc('use 0 to disable anti-flood.')}",
            parse_mode=ParseMode.HTML,
        )
        return

    limit = int(context.args[0])
    if limit < 0:
        await message.reply_text(f"⚠️ {sc('flood limit must be 0 or higher.')}")
        return

    settings = await get_flood_settings(chat.id)
    mode     = settings.get("mode", "kick")
    await set_flood_settings(chat.id, limit, mode)

    if limit == 0:
        await message.reply_text(f"✅ {sc('anti-flood disabled.')}")
    else:
        await message.reply_text(
            f"✅ {sc('anti-flood set to')} <b>{limit}</b> {sc('messages.')}\n"
            f"⚙️ {sc('action')}: <b>{sc(mode)}</b>",
            parse_mode=ParseMode.HTML,
        )


# ──────────────────────────────────────────────────────────────────────────────
# /flood  — show settings
# ──────────────────────────────────────────────────────────────────────────────
@group_only
async def flood_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message  = update.effective_message
    chat     = update.effective_chat
    settings = await get_flood_settings(chat.id)
    limit    = settings.get("limit", 0)
    mode     = settings.get("mode", "kick")

    if limit == 0:
        status = sc("disabled")
        await message.reply_text(
            f"🌊 {sc('anti-flood')}: <b>{status}</b>\n"
            f"{sc('enable with /setflood <number>')}",
            parse_mode=ParseMode.HTML,
        )
    else:
        await message.reply_text(
            f"🌊 <b>{sc('anti-flood settings')}</b>\n\n"
            f"📊 {sc('limit')}: <b>{limit}</b> {sc('messages / 5 seconds')}\n"
            f"⚙️ {sc('action')}: <b>{sc(mode)}</b>\n\n"
            f"{sc('change limit')}: /setflood &lt;num&gt;\n"
            f"{sc('change action')}: /setfloodmode &lt;mode&gt;",
            parse_mode=ParseMode.HTML,
        )


# ──────────────────────────────────────────────────────────────────────────────
# /setfloodmode
# ──────────────────────────────────────────────────────────────────────────────
@group_only
@admin_required
async def setfloodmode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat

    if not context.args or context.args[0].lower() not in VALID_MODES:
        modes_str = " | ".join(f"<code>{m}</code>" for m in VALID_MODES)
        await message.reply_text(
            f"⚠️ {sc('valid modes')}: {modes_str}\n"
            f"{sc('usage')}: /setfloodmode &lt;mode&gt;",
            parse_mode=ParseMode.HTML,
        )
        return

    mode     = context.args[0].lower()
    settings = await get_flood_settings(chat.id)
    limit    = settings.get("limit", 0)
    await set_flood_settings(chat.id, limit, mode)

    await message.reply_text(
        f"✅ {sc('flood action set to')}: <b>{sc(mode)}</b>",
        parse_mode=ParseMode.HTML,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Message watcher — enforce flood limits
# ──────────────────────────────────────────────────────────────────────────────
async def flood_watcher(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat
    user    = update.effective_user

    if not message or not user or not chat:
        return
    if user.is_bot:
        return
    if await _is_admin(chat.id, user.id, context.bot):
        return

    settings = await get_flood_settings(chat.id)
    limit    = settings.get("limit", 0)
    mode     = settings.get("mode", "kick")

    if limit == 0:
        return

    flooding = flood_tracker.check_flood(chat.id, user.id, limit=limit, time_window=5)
    if not flooding:
        return

    flood_tracker.reset_user(chat.id, user.id)
    mention = f"<a href='tg://user?id={user.id}'>{html.escape(user.full_name)}</a>"

    try:
        if mode == "ban":
            await context.bot.ban_chat_member(chat.id, user.id)
            action_text = sc("banned")
        elif mode == "kick":
            await context.bot.ban_chat_member(chat.id, user.id)
            await context.bot.unban_chat_member(chat.id, user.id)
            action_text = sc("kicked")
        elif mode == "mute":
            await context.bot.restrict_chat_member(
                chat.id, user.id,
                ChatPermissions(can_send_messages=False)
            )
            action_text = sc("muted")
        elif mode == "tban":
            from datetime import datetime, timedelta
            until = datetime.utcnow() + timedelta(hours=1)
            await context.bot.ban_chat_member(chat.id, user.id, until_date=until)
            action_text = sc("temp banned (1h)")
        elif mode == "tmute":
            from datetime import datetime, timedelta
            until = datetime.utcnow() + timedelta(hours=1)
            await context.bot.restrict_chat_member(
                chat.id, user.id,
                ChatPermissions(can_send_messages=False),
                until_date=until,
            )
            action_text = sc("temp muted (1h)")
        else:
            action_text = sc("actioned")

        await message.reply_text(
            f"🌊 {mention} {sc('was')} <b>{action_text}</b> {sc('for flooding!')}",
            parse_mode=ParseMode.HTML,
        )
        await log_action(
            context.bot, action=f"anti-flood: {mode}", chat_id=chat.id,
            chat_title=chat.title or '', target_user_id=user.id,
            target_username=user.full_name, performed_by_id=context.bot.id,
            performed_by_username="RoseManagementBot",
        )
    except Exception as e:
        logger.warning(f"Anti-flood action failed: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# HELP
# ──────────────────────────────────────────────────────────────────────────────
ANTIFLOOD_HELP = (
    f"<b>🌊 {sc('anti-flood commands')}</b>\n\n"
    f"<b>/setflood</b> &lt;num&gt; — {sc('set max messages per 5 seconds (0 = off)')}\n"
    f"<b>/flood</b> — {sc('show current flood settings')}\n"
    f"<b>/setfloodmode</b> &lt;mode&gt; — {sc('set action: ban | kick | mute | tban | tmute')}\n\n"
    f"📌 {sc('admins are always exempt from flood limits.')}"
)


# ──────────────────────────────────────────────────────────────────────────────
# REGISTER
# ──────────────────────────────────────────────────────────────────────────────
def register_handlers(app) -> None:
    app.add_handler(CommandHandler("setflood",     setflood_cmd,     block=False))
    app.add_handler(CommandHandler("flood",        flood_cmd,        block=False))
    app.add_handler(CommandHandler("setfloodmode", setfloodmode_cmd, block=False))
    app.add_handler(MessageHandler(
        filters.ALL & filters.ChatType.GROUPS,
        flood_watcher,
        block=False,
    ))
