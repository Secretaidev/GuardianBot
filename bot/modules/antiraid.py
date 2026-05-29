"""
Rose — Anti-Raid protection.
Detects mass joins and auto-restricts new members.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict

from telegram import Update
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.ext import Application, CommandHandler, ContextTypes, ChatMemberHandler

from bot.config import OWNER_ID
from bot.helpers.decorators import admin_required, group_only

logger = logging.getLogger(__name__)

# ── In-memory raid tracking ───────────────────────────────────────────────────

_raid_settings: dict[int, dict] = {}  # chat_id → {enabled, action, duration}
_join_log: dict[int, list[float]] = defaultdict(list)  # chat_id → [timestamps]
_raid_active: dict[int, float] = {}  # chat_id → raid_mode_expires_at

RAID_THRESHOLD = 10  # joins in 30 seconds = raid
RAID_WINDOW = 30
DEFAULT_DURATION = 300  # 5 minutes raid mode


# ── DB helpers ────────────────────────────────────────────────────────────────

async def _get_col():
    from bot.database.mongo import get_collection
    return get_collection("antiraid")


async def _get_settings(chat_id: int) -> dict:
    if chat_id in _raid_settings:
        return _raid_settings[chat_id]
    col = await _get_col()
    doc = await col.find_one({"chat_id": chat_id})
    settings = {
        "enabled": doc.get("enabled", False) if doc else False,
        "action": doc.get("action", "kick") if doc else "kick",
        "duration": doc.get("duration", DEFAULT_DURATION) if doc else DEFAULT_DURATION,
    }
    _raid_settings[chat_id] = settings
    return settings


async def _save_settings(chat_id: int, settings: dict):
    col = await _get_col()
    _raid_settings[chat_id] = settings
    await col.update_one(
        {"chat_id": chat_id},
        {"$set": {**settings, "chat_id": chat_id}},
        upsert=True,
    )


# ── Commands ──────────────────────────────────────────────────────────────────

@group_only
@admin_required
async def cmd_antiraid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    args = context.args

    if not args:
        settings = await _get_settings(chat.id)
        status = "enabled ✅" if settings["enabled"] else "disabled ❌"
        await msg.reply_text(
            f"<b>Anti-Raid</b>\n\n"
            f"Status: {status}\n"
            f"Action: <code>{settings['action']}</code>\n"
            f"Duration: <code>{settings['duration']}s</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    val = args[0].lower()
    settings = await _get_settings(chat.id)

    if val in ("on", "yes", "true"):
        settings["enabled"] = True
        await _save_settings(chat.id, settings)
        await msg.reply_text("✅ Anti-raid protection enabled.")
    elif val in ("off", "no", "false"):
        settings["enabled"] = False
        await _save_settings(chat.id, settings)
        _raid_active.pop(chat.id, None)
        await msg.reply_text("❌ Anti-raid protection disabled.")
    else:
        await msg.reply_text("Usage: /antiraid on|off")


@group_only
@admin_required
async def cmd_raidtime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    args = context.args

    if not args:
        await msg.reply_text("Usage: /raidtime <seconds>\nExample: /raidtime 600")
        return

    try:
        duration = int(args[0])
        if duration < 30:
            duration = 30
        if duration > 86400:
            duration = 86400
    except ValueError:
        await msg.reply_text("Please provide a valid number of seconds.")
        return

    settings = await _get_settings(chat.id)
    settings["duration"] = duration
    await _save_settings(chat.id, settings)
    await msg.reply_text(f"✅ Raid mode duration set to <b>{duration}s</b>.", parse_mode=ParseMode.HTML)


@group_only
@admin_required
async def cmd_raidactionmode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    args = context.args

    if not args or args[0].lower() not in ("ban", "kick", "mute"):
        await msg.reply_text("Usage: /raidactionmode ban|kick|mute")
        return

    action = args[0].lower()
    settings = await _get_settings(chat.id)
    settings["action"] = action
    await _save_settings(chat.id, settings)
    await msg.reply_text(f"✅ Raid action set to <b>{action}</b>.", parse_mode=ParseMode.HTML)


# ── Raid detection on member join ─────────────────────────────────────────────

async def _check_raid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    member = update.chat_member
    if not member:
        return

    chat = member.chat
    new = member.new_chat_member
    if not new or new.status != ChatMemberStatus.MEMBER:
        return

    user = new.user
    if not user or user.is_bot:
        return

    settings = await _get_settings(chat.id)
    if not settings["enabled"]:
        return

    now = time.time()

    # Check if raid mode is already active
    if chat.id in _raid_active:
        if now < _raid_active[chat.id]:
            # Raid active — take action
            try:
                action = settings["action"]
                if action == "ban":
                    await context.bot.ban_chat_member(chat.id, user.id)
                elif action == "kick":
                    await context.bot.ban_chat_member(chat.id, user.id)
                    await context.bot.unban_chat_member(chat.id, user.id)
                elif action == "mute":
                    from telegram import ChatPermissions
                    await context.bot.restrict_chat_member(
                        chat.id, user.id, ChatPermissions(can_send_messages=False),
                    )
            except Exception as e:
                logger.debug("Raid action failed: %s", e)
            return
        else:
            del _raid_active[chat.id]

    # Log the join
    _join_log[chat.id].append(now)
    # Clean old entries
    _join_log[chat.id] = [t for t in _join_log[chat.id] if now - t < RAID_WINDOW]

    # Check threshold
    if len(_join_log[chat.id]) >= RAID_THRESHOLD:
        _raid_active[chat.id] = now + settings["duration"]
        _join_log[chat.id].clear()

        try:
            await context.bot.send_message(
                chat.id,
                f"⚠️ <b>Raid detected!</b>\n"
                f"Anti-raid mode activated for {settings['duration']}s.\n"
                f"Action: <b>{settings['action']}</b> on new joins.",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

        logger.warning("Raid detected in chat %d — mode active for %ds", chat.id, settings["duration"])


def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("antiraid", cmd_antiraid))
    app.add_handler(CommandHandler("raidtime", cmd_raidtime))
    app.add_handler(CommandHandler("raidactionmode", cmd_raidactionmode))
    app.add_handler(ChatMemberHandler(_check_raid, ChatMemberHandler.CHAT_MEMBER), group=15)
