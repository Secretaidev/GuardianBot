"""
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ
Owner-only kill switch. Flips the bot into maintenance and broadcasts everywhere.
"""
from __future__ import annotations

import asyncio
import html
import logging
from datetime import datetime, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

from bot.config import OWNER_ID, BOT_NAME
from bot.fonts import sc

logger = logging.getLogger(__name__)

# ── in-memory flag — zero-cost check per message ─────────────────────────────
_MAINTENANCE = False
_MAINTENANCE_REASON = ""
_MAINTENANCE_SINCE: str | None = None

BANNER = (
    "🔧 <b>{name} {status}</b>\n\n"
    "⏳ {msg}\n\n"
    "👑 <b>{sc_owner}: 𝐒𝐄𝐂𝐑𝐄𝐓</b>"
)


def is_maintenance() -> bool:
    return _MAINTENANCE


# ── /maintenance on [reason] ─────────────────────────────────────────────────
async def maintenance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _MAINTENANCE, _MAINTENANCE_REASON, _MAINTENANCE_SINCE

    user = update.effective_user
    if not user or user.id != OWNER_ID:
        await update.effective_message.reply_text(f"❌ {sc('owner only.')}")
        return

    args = context.args or []
    if not args:
        status = sc("enabled") if _MAINTENANCE else sc("disabled")
        await update.effective_message.reply_text(
            f"🔧 {sc('maintenance mode')}: <b>{status}</b>\n"
            f"{sc('usage')}: /maintenance on [reason] | off",
            parse_mode=ParseMode.HTML,
        )
        return

    action = args[0].lower()

    if action == "on":
        _MAINTENANCE = True
        _MAINTENANCE_REASON = " ".join(args[1:]) if len(args) > 1 else sc("scheduled maintenance")
        _MAINTENANCE_SINCE = datetime.now(timezone.utc).strftime("%H:%M UTC")

        banner = BANNER.format(
            name=BOT_NAME,
            status=sc("is under maintenance"),
            msg=f"{sc('reason')}: {_MAINTENANCE_REASON}\n⏰ {sc('since')}: {_MAINTENANCE_SINCE}",
            sc_owner=sc("owner"),
        )

        await update.effective_message.reply_text(
            f"✅ {sc('maintenance mode activated.')}\n{sc('broadcasting to all chats...')}",
            parse_mode=ParseMode.HTML,
        )

        # broadcast to all groups + DMs
        asyncio.create_task(_broadcast_maintenance(context.bot, banner, going_down=True))

    elif action == "off":
        if not _MAINTENANCE:
            await update.effective_message.reply_text(f"ℹ️ {sc('maintenance is already off.')}")
            return

        _MAINTENANCE = False
        _MAINTENANCE_REASON = ""
        _MAINTENANCE_SINCE = None

        banner = BANNER.format(
            name=BOT_NAME,
            status=sc("is back online!"),
            msg=f"✅ {sc('all systems operational. thanks for waiting!')}",
            sc_owner=sc("owner"),
        )

        await update.effective_message.reply_text(
            f"✅ {sc('maintenance mode deactivated. broadcasting...')}",
            parse_mode=ParseMode.HTML,
        )

        asyncio.create_task(_broadcast_maintenance(context.bot, banner, going_down=False))

    elif action == "status":
        if _MAINTENANCE:
            await update.effective_message.reply_text(
                f"🔧 <b>{sc('maintenance active')}</b>\n"
                f"📝 {_MAINTENANCE_REASON}\n"
                f"⏰ {sc('since')}: {_MAINTENANCE_SINCE}",
                parse_mode=ParseMode.HTML,
            )
        else:
            await update.effective_message.reply_text(f"✅ {sc('bot is running normally.')}")
    else:
        await update.effective_message.reply_text(
            f"⚠️ {sc('usage')}: /maintenance on [reason] | off | status"
        )


async def _broadcast_maintenance(bot, banner_text: str, going_down: bool) -> None:
    """Best-effort broadcast to all known chats and users."""
    sent, failed = 0, 0
    try:
        from bot.database.chats_db import get_all_chats
        chats = await get_all_chats()
        for chat_doc in chats:
            cid = chat_doc.get("chat_id")
            if not cid:
                continue
            try:
                await bot.send_message(cid, banner_text, parse_mode=ParseMode.HTML)
                sent += 1
                await asyncio.sleep(0.05)  # stay under flood limits
            except Exception:
                failed += 1
    except Exception as e:
        logger.warning("Maintenance broadcast (chats) failed: %s", e)

    try:
        from bot.database.users_db import get_all_users
        users = await get_all_users()
        for user_doc in users:
            uid = user_doc.get("user_id")
            if not uid:
                continue
            try:
                await bot.send_message(uid, banner_text, parse_mode=ParseMode.HTML)
                sent += 1
                await asyncio.sleep(0.05)
            except Exception:
                failed += 1
    except Exception as e:
        logger.warning("Maintenance broadcast (users) failed: %s", e)

    logger.info("Maintenance broadcast: sent=%d failed=%d", sent, failed)


# ── pre-processor: block commands during maintenance ─────────────────────────
async def maintenance_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """If maintenance is on, reply with banner and stop processing.
    Owner is always exempt."""
    if not _MAINTENANCE:
        return
    user = update.effective_user
    if user and user.id == OWNER_ID:
        return  # owner bypasses

    msg = update.effective_message
    if msg and (msg.text or "").startswith("/"):
        banner = BANNER.format(
            name=BOT_NAME,
            status=sc("is under maintenance"),
            msg=f"📝 {_MAINTENANCE_REASON}\n⏰ {sc('since')}: {_MAINTENANCE_SINCE or '?'}",
            sc_owner=sc("owner"),
        )
        await msg.reply_text(banner, parse_mode=ParseMode.HTML)
        raise ApplicationHandlerStop()


# import here to avoid circular at module level
from telegram.ext import ApplicationHandlerStop


MAINTENANCE_HELP = (
    f"<b>🔧 {sc('maintenance commands')}</b>\n\n"
    f"<b>/maintenance on</b> [reason] — {sc('enable maintenance mode')}\n"
    f"<b>/maintenance off</b> — {sc('disable maintenance mode')}\n"
    f"<b>/maintenance status</b> — {sc('check current status')}\n\n"
    f"📌 {sc('owner only. broadcasts to all chats and dms.')}"
)


def register_handlers(app) -> None:
    # gate runs FIRST at highest priority — group -999
    app.add_handler(
        MessageHandler(filters.COMMAND & ~filters.Regex(r"^/maintenance"), maintenance_gate),
        group=-999,
    )
    app.add_handler(CommandHandler("maintenance", maintenance_cmd, block=False))
