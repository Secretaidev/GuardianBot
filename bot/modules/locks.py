"""
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — ʟᴏᴄᴋꜱ ᴍᴏᴅᴜʟᴇ
Content locking: lock/unlock message types, auto-delete locked content.
"""
from __future__ import annotations

import html
import logging
import re

from telegram import Update, Message
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters

from bot.fonts import sc
from bot.helpers.decorators import admin_required, bot_admin_required, group_only
from bot.database import chats_db
from bot.logger import log_action

logger = logging.getLogger(__name__)

# ── All supported lock types ──────────────────────────────────────────────────
LOCK_TYPES: dict[str, str] = {
    "text":      sc("plain text messages"),
    "media":     sc("all media (photos/videos)"),
    "photo":     sc("photos"),
    "video":     sc("videos"),
    "document":  sc("documents/files"),
    "audio":     sc("audio files"),
    "voice":     sc("voice messages"),
    "sticker":   sc("stickers"),
    "gif":       sc("gifs/animations"),
    "url":       sc("urls/links"),
    "bot":       sc("messages forwarded from bots"),
    "forward":   sc("all forwarded messages"),
    "game":      sc("game messages"),
    "poll":      sc("polls"),
    "contact":   sc("contact cards"),
    "location":  sc("location messages"),
    "email":     sc("email addresses in text"),
    "phone":     sc("phone numbers in text"),
    "inline":    sc("inline bot results"),
    "command":   sc("commands from non-admins"),
}

URL_REGEX  = re.compile(r"https?://|t\.me/|www\.", re.IGNORECASE)
EMAIL_RE   = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_RE   = re.compile(r"\+?\d[\d\s\-]{7,}\d")


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
async def _get_locks(chat_id: int) -> dict:
    chat_data = await chats_db.get_chat(chat_id)
    return chat_data.get("locks", {})


async def _set_lock(chat_id: int, lock_type: str, value: bool) -> None:
    chat_data = await chats_db.get_chat(chat_id)
    locks = chat_data.get("locks", {})
    locks[lock_type] = value
    await chats_db.update_chat_setting(chat_id, "locks", locks)


async def _is_admin(chat_id: int, user_id: int, bot) -> bool:
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR)
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────────────────
# /lock
# ──────────────────────────────────────────────────────────────────────────────
@group_only
@admin_required
async def lock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat

    if not context.args:
        await message.reply_text(
            f"⚠️ {sc('usage')}: /lock &lt;type&gt;\n"
            f"{sc('use /locktypes to see all lockable types.')}",
            parse_mode=ParseMode.HTML,
        )
        return

    lock_type = context.args[0].lower()
    if lock_type not in LOCK_TYPES:
        await message.reply_text(
            f"❓ {sc('unknown lock type')}: <code>{html.escape(lock_type)}</code>\n"
            f"{sc('use /locktypes to see all lockable types.')}",
            parse_mode=ParseMode.HTML,
        )
        return

    await _set_lock(chat.id, lock_type, True)
    await message.reply_text(
        f"🔒 {sc('locked')}: <b>{lock_type}</b> — {LOCK_TYPES[lock_type]}",
        parse_mode=ParseMode.HTML,
    )
    await log_action(
        context.bot, action=f"locked {lock_type}", chat_id=chat.id,
        chat_title=chat.title or '', target_user_id=update.effective_user.id,
        target_username=update.effective_user.full_name,
        performed_by_id=update.effective_user.id,
        performed_by_username=update.effective_user.full_name,
    )


# ──────────────────────────────────────────────────────────────────────────────
# /unlock
# ──────────────────────────────────────────────────────────────────────────────
@group_only
@admin_required
async def unlock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat

    if not context.args:
        await message.reply_text(
            f"⚠️ {sc('usage')}: /unlock &lt;type&gt;",
            parse_mode=ParseMode.HTML,
        )
        return

    lock_type = context.args[0].lower()
    if lock_type not in LOCK_TYPES:
        await message.reply_text(
            f"❓ {sc('unknown lock type')}: <code>{html.escape(lock_type)}</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    await _set_lock(chat.id, lock_type, False)
    await message.reply_text(
        f"🔓 {sc('unlocked')}: <b>{lock_type}</b>",
        parse_mode=ParseMode.HTML,
    )


# ──────────────────────────────────────────────────────────────────────────────
# /locks  — show status table
# ──────────────────────────────────────────────────────────────────────────────
@group_only
async def locks_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat

    locks = await _get_locks(chat.id)
    lines = [f"<b>🔒 {sc('lock status')} — {html.escape(chat.title or '')}</b>\n"]
    for lt, desc in LOCK_TYPES.items():
        icon = "🔒" if locks.get(lt) else "🔓"
        status = sc("locked") if locks.get(lt) else sc("unlocked")
        lines.append(f"{icon} <code>{lt:<12}</code> {status}")

    await message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


# ──────────────────────────────────────────────────────────────────────────────
# /locktypes
# ──────────────────────────────────────────────────────────────────────────────
async def locktypes_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lines = [f"<b>📋 {sc('lockable types')}</b>\n"]
    for lt, desc in LOCK_TYPES.items():
        lines.append(f"• <code>{lt}</code> — {desc}")
    await update.effective_message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


# ──────────────────────────────────────────────────────────────────────────────
# Message watcher — enforce locks
# ──────────────────────────────────────────────────────────────────────────────
async def lock_watcher(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat
    user    = update.effective_user

    if not message or not chat or not user:
        return
    if user.is_bot:
        return

    # Admins are exempt
    if await _is_admin(chat.id, user.id, context.bot):
        return

    locks = await _get_locks(chat.id)
    if not any(locks.values()):
        return

    should_delete = False

    def check(lt: str) -> bool:
        return bool(locks.get(lt))

    # Photo
    if check("photo") and message.photo:
        should_delete = True
    # Video
    elif check("video") and message.video:
        should_delete = True
    # Document
    elif check("document") and message.document:
        should_delete = True
    # Audio
    elif check("audio") and message.audio:
        should_delete = True
    # Voice
    elif check("voice") and message.voice:
        should_delete = True
    # Sticker
    elif check("sticker") and message.sticker:
        should_delete = True
    # GIF
    elif check("gif") and message.animation:
        should_delete = True
    # Game
    elif check("game") and message.game:
        should_delete = True
    # Contact
    elif check("contact") and message.contact:
        should_delete = True
    # Location
    elif check("location") and message.location:
        should_delete = True
    # Poll
    elif check("poll") and message.poll:
        should_delete = True
    # Forward
    elif check("forward") and message.forward_date:
        should_delete = True
    # Forward from bot
    elif check("bot") and message.forward_from and message.forward_from.is_bot:
        should_delete = True
    # Via inline bot
    elif check("inline") and message.via_bot:
        should_delete = True
    # Media (any)
    elif check("media") and (message.photo or message.video or message.animation or message.document):
        should_delete = True
    # Text-based checks
    elif message.text:
        text = message.text
        if check("url") and URL_REGEX.search(text):
            should_delete = True
        elif check("email") and EMAIL_RE.search(text):
            should_delete = True
        elif check("phone") and PHONE_RE.search(text):
            should_delete = True
        elif check("command") and text.startswith("/"):
            should_delete = True
        elif check("text") and not text.startswith("/"):
            should_delete = True

    if should_delete:
        try:
            await message.delete()
        except Exception as e:
            logger.debug(f"Lock delete failed: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# HELP
# ──────────────────────────────────────────────────────────────────────────────
LOCKS_HELP = (
    f"<b>🔒 {sc('locks commands')}</b>\n\n"
    f"<b>/lock</b> &lt;type&gt; — {sc('lock a content type')}\n"
    f"<b>/unlock</b> &lt;type&gt; — {sc('unlock a content type')}\n"
    f"<b>/locks</b> — {sc('show all lock statuses')}\n"
    f"<b>/locktypes</b> — {sc('list all lockable types')}\n\n"
    f"📌 {sc('locked content is automatically deleted. admins are exempt.')}"
)


# ──────────────────────────────────────────────────────────────────────────────
# REGISTER
# ──────────────────────────────────────────────────────────────────────────────
def register_handlers(app) -> None:
    app.add_handler(CommandHandler("lock", lock_cmd, block=False))
    app.add_handler(CommandHandler("unlock", unlock_cmd, block=False))
    app.add_handler(CommandHandler("locks", locks_status_cmd, block=False))
    app.add_handler(CommandHandler("locktypes", locktypes_cmd, block=False))
    app.add_handler(MessageHandler(
        (filters.ALL & filters.ChatType.GROUPS) & ~filters.COMMAND,
        lock_watcher,
        block=False,
    ))
