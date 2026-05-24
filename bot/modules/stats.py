"""
bot/modules/stats.py
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — Bot statistics and broadcast module.

Responsibilities
----------------
• /stats  (owner + sudo) — display live bot statistics:
    - Total users, groups, messages processed
    - Bot uptime
    - Memory usage (RSS)
    - MongoDB connectivity status
• /broadcast (owner only) — send a message to every known chat
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes

from bot.database.chats_db import get_all_chats, get_chat_count
from bot.database.mongo import db as mongo_db
from bot.database.users_db import get_user_count
from bot.fonts import sc
from bot.helpers.decorators import dev_only, owner_only

logger = logging.getLogger(__name__)

# Module-level startup timestamp — set when this module is first imported.
_START_TIME: float = time.time()


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_uptime() -> str:
    """Return a human-readable uptime string since bot start."""
    elapsed = int(time.time() - _START_TIME)
    days, remainder = divmod(elapsed, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes, seconds = divmod(remainder, 60)

    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")

    return " ".join(parts) or "0s"


def _get_memory_mb() -> float:
    """
    Return the current process Resident Set Size in megabytes.

    Uses ``/proc/self/status`` on Linux and falls back to the ``psutil``
    library if available, or 0.0 if neither is accessible.
    """
    # Linux fast path
    try:
        with open("/proc/self/status") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    kb = int(line.split()[1])
                    return kb / 1024.0
    except (FileNotFoundError, IndexError, ValueError):
        pass

    # psutil fallback (Windows / macOS)
    try:
        import psutil  # type: ignore

        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    except Exception:
        pass

    return 0.0


async def _check_mongo() -> str:
    """Return a short status string for the MongoDB connection."""
    if mongo_db is None:
        return f"❌ {sc('not connected')}"
    try:
        await mongo_db.command("ping")
        return f"✅ {sc('connected')}"
    except Exception as exc:
        logger.warning("MongoDB ping failed: %s", exc)
        return f"❌ {sc('error')}: {exc}"


# ─────────────────────────────────────────────────────────────────────────────
# /stats command
# ─────────────────────────────────────────────────────────────────────────────

@dev_only
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Display comprehensive bot statistics.

    Accessible by the bot owner and all SUDO_USERS.

    Statistics shown:
      • Total registered users
      • Total registered groups
      • Bot uptime since last restart
      • Memory consumption (RSS)
      • MongoDB connectivity status
    """
    msg = update.effective_message
    if msg is None:
        return

    # Show a "loading" placeholder while we fetch async data
    placeholder = await msg.reply_text(f"📊 {sc('fetching stats')}...")

    # Fetch counts and status concurrently for speed
    user_count, chat_count, mongo_status = await asyncio.gather(
        _async_get_user_count(),
        _async_get_chat_count(),
        _check_mongo(),
    )

    uptime_str = _get_uptime()
    memory_mb = _get_memory_mb()

    now_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    text = (
        f"<b>📊 ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — {sc('statistics')}</b>\n"
        f"<code>{'─' * 30}</code>\n\n"
        f"👤 {sc('total users')}: <code>{user_count:,}</code>\n"
        f"💬 {sc('total groups')}: <code>{chat_count:,}</code>\n\n"
        f"⏱ {sc('uptime')}: <code>{uptime_str}</code>\n"
        f"🧠 {sc('memory')}: <code>{memory_mb:.1f} MB</code>\n\n"
        f"🗄 {sc('mongodb')}: {mongo_status}\n\n"
        f"🕐 {sc('generated at')}: <code>{now_str}</code>"
    )

    await placeholder.edit_text(text, parse_mode=ParseMode.HTML)


async def _async_get_user_count() -> int:
    """Safe wrapper around get_user_count that returns 0 on error."""
    try:
        return await get_user_count()
    except Exception as exc:
        logger.warning("get_user_count failed: %s", exc)
        return 0


async def _async_get_chat_count() -> int:
    """Safe wrapper around get_chat_count that returns 0 on error."""
    try:
        return await get_chat_count()
    except Exception as exc:
        logger.warning("get_chat_count failed: %s", exc)
        return 0


# ─────────────────────────────────────────────────────────────────────────────
# /broadcast command
# ─────────────────────────────────────────────────────────────────────────────

@owner_only
async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Broadcast a message to every chat in the database.

    Usage (reply to the message you want to broadcast, OR provide text)::

        /broadcast Your message here
        <reply to a message> /broadcast

    The broadcast is sent asynchronously with a short throttle between sends
    to avoid Telegram flood limits (30 messages/second per bot).

    Progress is reported by editing the acknowledgement message.

    Only the bot owner (OWNER_ID) can execute this command.
    """
    msg = update.effective_message
    if msg is None:
        return

    # ── Determine what to broadcast ──────────────────────────────────────────
    broadcast_text: str | None = None
    forward_message = None

    if msg.reply_to_message:
        # Forward the replied-to message to each chat
        forward_message = msg.reply_to_message
    elif context.args:
        broadcast_text = " ".join(context.args)
    else:
        await msg.reply_text(
            f"❌ {sc('please reply to a message or provide text to broadcast.')}",
        )
        return

    # ── Fetch all chats ──────────────────────────────────────────────────────
    try:
        all_chats = await get_all_chats()
    except Exception as exc:
        logger.error("broadcast: get_all_chats failed: %s", exc)
        await msg.reply_text(
            f"❌ {sc('failed to fetch chat list from database.')}",
        )
        return

    total = len(all_chats)
    if total == 0:
        await msg.reply_text(f"⚠️ {sc('no chats found in the database.')}")
        return

    progress = await msg.reply_text(
        f"📡 {sc('broadcasting to')} <code>{total}</code> {sc('chats')}...",
        parse_mode=ParseMode.HTML,
    )

    sent = 0
    failed = 0
    blocked = 0

    for i, chat_doc in enumerate(all_chats):
        chat_id: int = chat_doc["chat_id"]

        try:
            if forward_message is not None:
                await forward_message.forward(chat_id)
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=broadcast_text,
                    parse_mode=ParseMode.HTML,
                )
            sent += 1
        except TelegramError as exc:
            err_str = str(exc).lower()
            if any(kw in err_str for kw in ("blocked", "kicked", "not a member", "deactivated", "chat not found")):
                blocked += 1
            else:
                logger.warning("broadcast to %s failed: %s", chat_id, exc)
                failed += 1

        # Update progress every 25 chats to avoid editing too frequently
        if (i + 1) % 25 == 0:
            try:
                await progress.edit_text(
                    f"📡 {sc('broadcasting')}... <code>{i + 1}/{total}</code>",
                    parse_mode=ParseMode.HTML,
                )
            except TelegramError:
                pass  # Don't abort broadcast if the progress edit fails

        # Throttle: ~20 sends/second to stay well under the 30/s limit
        await asyncio.sleep(0.05)

    # ── Final report ─────────────────────────────────────────────────────────
    report = (
        f"<b>📡 {sc('broadcast complete')}</b>\n\n"
        f"✅ {sc('sent')}: <code>{sent}</code>\n"
        f"🚫 {sc('blocked / unreachable')}: <code>{blocked}</code>\n"
        f"❌ {sc('failed')}: <code>{failed}</code>\n"
        f"📊 {sc('total targeted')}: <code>{total}</code>"
    )

    await progress.edit_text(report, parse_mode=ParseMode.HTML)
    logger.info(
        "Broadcast finished — sent=%d blocked=%d failed=%d total=%d",
        sent, blocked, failed, total,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Handler registration
# ─────────────────────────────────────────────────────────────────────────────

def register_handlers(app: Application) -> None:
    """
    Register all handlers defined in this module with the PTB Application.

    Args:
        app: The :class:`telegram.ext.Application` instance.
    """
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))

    logger.info("stats.py handlers registered.")
