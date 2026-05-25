"""
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ
Owner-only kill switch. Broadcasts maintenance status to all chats.
Crafted by 𝐒𝐄𝐂𝐑𝐄𝐓
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationHandlerStop, CommandHandler, ContextTypes,
    MessageHandler, filters,
)

from bot.config import OWNER_ID, BOT_NAME
from bot.fonts import sc

logger = logging.getLogger(__name__)

# in-memory flag — zero cost per message check
_MAINTENANCE = False
_MAINTENANCE_REASON = ""
_MAINTENANCE_SINCE: str | None = None

_BANNER = (
    "🔧 <b>{name} {status}</b>\n\n"
    "⏳ {msg}\n\n"
    "👑 <b>{owner_label}: 𝐒𝐄𝐂𝐑𝐄𝐓</b>"
)


def is_maintenance() -> bool:
    return _MAINTENANCE


async def maintenance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _MAINTENANCE, _MAINTENANCE_REASON, _MAINTENANCE_SINCE

    user = update.effective_user
    if not user or user.id != OWNER_ID:
        await update.effective_message.reply_text(f"❌ {sc('owner only.')}")
        return

    args = context.args or []
    if not args:
        st = sc("enabled") if _MAINTENANCE else sc("disabled")
        await update.effective_message.reply_text(
            f"🔧 {sc('maintenance mode')}: <b>{st}</b>\n"
            f"{sc('usage')}: /maintenance on [reason] | off | status",
            parse_mode=ParseMode.HTML,
        )
        return

    action = args[0].lower()

    if action == "on":
        _MAINTENANCE = True
        _MAINTENANCE_REASON = " ".join(args[1:]) if len(args) > 1 else sc("scheduled maintenance")
        _MAINTENANCE_SINCE = datetime.now(timezone.utc).strftime("%H:%M UTC")

        banner = _BANNER.format(
            name=BOT_NAME, status=sc("is under maintenance"),
            msg=f"{sc('reason')}: {_MAINTENANCE_REASON}\n⏰ {sc('since')}: {_MAINTENANCE_SINCE}",
            owner_label=sc("owner"),
        )
        await update.effective_message.reply_text(
            f"✅ {sc('maintenance mode activated. broadcasting...')}",
            parse_mode=ParseMode.HTML,
        )
        asyncio.create_task(_broadcast(context.bot, banner))

    elif action == "off":
        if not _MAINTENANCE:
            await update.effective_message.reply_text(f"ℹ️ {sc('maintenance is already off.')}")
            return
        _MAINTENANCE = False
        _MAINTENANCE_REASON = ""
        _MAINTENANCE_SINCE = None

        banner = _BANNER.format(
            name=BOT_NAME, status=sc("is back online!"),
            msg=f"✅ {sc('all systems operational. thanks for waiting!')}",
            owner_label=sc("owner"),
        )
        await update.effective_message.reply_text(
            f"✅ {sc('maintenance off. broadcasting...')}",
            parse_mode=ParseMode.HTML,
        )
        asyncio.create_task(_broadcast(context.bot, banner))

    elif action == "status":
        if _MAINTENANCE:
            await update.effective_message.reply_text(
                f"🔧 <b>{sc('maintenance active')}</b>\n"
                f"📝 {_MAINTENANCE_REASON}\n⏰ {sc('since')}: {_MAINTENANCE_SINCE}",
                parse_mode=ParseMode.HTML,
            )
        else:
            await update.effective_message.reply_text(f"✅ {sc('bot is running normally.')}")
    else:
        await update.effective_message.reply_text(
            f"⚠️ {sc('usage')}: /maintenance on [reason] | off | status"
        )


async def _broadcast(bot, text: str) -> None:
    """Best-effort broadcast to all known chats."""
    sent = failed = 0
    try:
        from bot.database.chats_db import get_all_chats
        for doc in await get_all_chats():
            cid = doc.get("chat_id")
            if not cid:
                continue
            try:
                await bot.send_message(cid, text, parse_mode=ParseMode.HTML)
                sent += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.04)
    except Exception as e:
        logger.warning("Broadcast (chats) err: %s", e)

    try:
        from bot.database.users_db import get_all_users
        for doc in await get_all_users():
            uid = doc.get("user_id")
            if not uid:
                continue
            try:
                await bot.send_message(uid, text, parse_mode=ParseMode.HTML)
                sent += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.04)
    except Exception as e:
        logger.warning("Broadcast (users) err: %s", e)

    logger.info("Maintenance broadcast done: sent=%d failed=%d", sent, failed)


async def maintenance_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Block all commands during maintenance. Owner bypasses."""
    if not _MAINTENANCE:
        return
    user = update.effective_user
    if user and user.id == OWNER_ID:
        return

    msg = update.effective_message
    if msg and (msg.text or "").startswith("/"):
        banner = _BANNER.format(
            name=BOT_NAME, status=sc("is under maintenance"),
            msg=f"📝 {_MAINTENANCE_REASON}\n⏰ {sc('since')}: {_MAINTENANCE_SINCE or '?'}",
            owner_label=sc("owner"),
        )
        await msg.reply_text(banner, parse_mode=ParseMode.HTML)
        raise ApplicationHandlerStop()


def register_handlers(app) -> None:
    app.add_handler(
        MessageHandler(filters.COMMAND & ~filters.Regex(r"^/maintenance"), maintenance_gate),
        group=-999,
    )
    app.add_handler(CommandHandler("maintenance", maintenance_cmd, block=False))
