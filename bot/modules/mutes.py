"""
bot/modules/mutes.py
────────────────────
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — Mute module.

Commands
--------
/mute   <user> [reason] — Permanently restrict a user (cannot send messages).
/tmute  <user> <time> [reason] — Temporary mute with duration (3d, 2h, 30m).
/unmute <user>          — Remove mute restrictions from a user.
/smute  <user>          — Silent mute (no public confirmation message).

Muted users have ALL ChatPermissions set to False.
All mute actions display an inline [🔊 ᴜɴᴍᴜᴛᴇ] button for quick reversal.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from telegram import (
    Chat,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    User,
)
from telegram.constants import ChatMemberStatus
from telegram.error import TelegramError
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from bot.database import users_db
from bot.fonts import sc
from bot.helpers.decorators import admin_required, bot_admin_required, group_only
from bot.helpers.extractors import extract_user_and_reason
from bot.helpers.time_parser import format_duration, parse_time
from bot.logger import log_action

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Shared constants
# ─────────────────────────────────────────────────────────────────────────────

# All permissions revoked — used when muting a user
_MUTE_PERMISSIONS = ChatPermissions(
    can_send_messages=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
    can_change_info=False,
    can_invite_users=False,
    can_pin_messages=False,
    can_manage_topics=False,
)

# Full permissions — used when restoring a muted user
_UNMUTE_PERMISSIONS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_change_info=False,   # leave group-management flags alone
    can_invite_users=True,
    can_pin_messages=False,
    can_manage_topics=False,
)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _unmute_button(user_id: int) -> InlineKeyboardMarkup:
    """Return an inline keyboard with a single [🔊 ᴜɴᴍᴜᴛᴇ] button."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(
            text="🔊 ᴜɴᴍᴜᴛᴇ",
            callback_data=f"unmute:{user_id}",
        )]]
    )


def _mention_html(user: User) -> str:
    import html
    name = html.escape(user.full_name)
    return f'<a href="tg://user?id={user.id}">{name}</a>'


async def _is_protected(
    chat: Chat, user: User, bot_id: int, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """Return True if *user* should not be muted (admin, creator, or bot itself)."""
    if user.id == bot_id:
        return True
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
    except TelegramError:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# /mute
# ─────────────────────────────────────────────────────────────────────────────

@group_only
@admin_required
@bot_admin_required
async def mute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Permanently restrict a user so they cannot send any messages."""
    chat = update.effective_chat
    actor = update.effective_user
    msg = update.effective_message

    extracted = await extract_user_and_reason(update, context)
    if extracted.error or extracted.user is None:
        await msg.reply_text(f"❌ {sc(extracted.error or 'could not resolve user.')}")
        return

    target = extracted.user
    reason = extracted.reason

    if await _is_protected(chat, target, context.bot.id, context):
        await msg.reply_text(f"❌ {sc('i cannot mute admins or myself.')}")
        return

    try:
        await context.bot.restrict_chat_member(
            chat.id, target.id, permissions=_MUTE_PERMISSIONS
        )
    except TelegramError as exc:
        await msg.reply_text(
            f"❌ {sc('failed to mute:')} <code>{exc}</code>", parse_mode="HTML"
        )
        return

    await users_db.upsert_user(
        target.id,
        username=target.username,
        first_name=target.first_name,
        last_name=target.last_name,
    )

    reason_line = f"\n📝 <b>{sc('reason')}:</b> {reason}" if reason else ""
    text = (
        f"🔇 <b>{sc('muted')}</b>\n"
        f"👤 {_mention_html(target)} (<code>{target.id}</code>)"
        f"{reason_line}"
    )
    await msg.reply_text(text, parse_mode="HTML", reply_markup=_unmute_button(target.id))

    await log_action(
        context.bot, chat_id=chat.id, action="mute", admin=actor, target=target, reason=reason
    )


# ─────────────────────────────────────────────────────────────────────────────
# /tmute
# ─────────────────────────────────────────────────────────────────────────────

@group_only
@admin_required
@bot_admin_required
async def tmute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Temporarily mute a user for a given duration."""
    chat = update.effective_chat
    actor = update.effective_user
    msg = update.effective_message
    args = context.args or []

    extracted = await extract_user_and_reason(update, context)
    if extracted.error or extracted.user is None:
        await msg.reply_text(f"❌ {sc(extracted.error or 'could not resolve user.')}")
        return

    target = extracted.user

    if await _is_protected(chat, target, context.bot.id, context):
        await msg.reply_text(f"❌ {sc('i cannot mute admins or myself.')}")
        return

    # Determine time arg position (differs for reply vs mention)
    is_reply = (
        msg.reply_to_message is not None and msg.reply_to_message.from_user is not None
    )
    if is_reply:
        time_arg = args[0] if args else None
        reason_parts = args[1:] if len(args) > 1 else []
    else:
        time_arg = args[1] if len(args) > 1 else None
        reason_parts = args[2:] if len(args) > 2 else []

    if not time_arg:
        await msg.reply_text(
            f"❌ {sc('usage:')} /tmute <user> <time> [reason]\n"
            f"{sc('example:')} /tmute @user 2h spam"
        )
        return

    delta = parse_time(time_arg)
    if delta is None:
        await msg.reply_text(
            f"❌ {sc('invalid time format. use: 30s, 5m, 2h, 1d, 1w')}"
        )
        return

    reason = " ".join(reason_parts).strip() or None
    until_date = datetime.now(timezone.utc) + delta

    try:
        await context.bot.restrict_chat_member(
            chat.id,
            target.id,
            permissions=_MUTE_PERMISSIONS,
            until_date=until_date,
        )
    except TelegramError as exc:
        await msg.reply_text(
            f"❌ {sc('failed to mute:')} <code>{exc}</code>", parse_mode="HTML"
        )
        return

    await users_db.upsert_user(
        target.id,
        username=target.username,
        first_name=target.first_name,
        last_name=target.last_name,
    )

    duration_str = format_duration(delta)
    reason_line = f"\n📝 <b>{sc('reason')}:</b> {reason}" if reason else ""
    text = (
        f"⏳ <b>{sc('temporarily muted')}</b>\n"
        f"👤 {_mention_html(target)} (<code>{target.id}</code>)\n"
        f"⏱ <b>{sc('duration')}:</b> {sc(duration_str)}"
        f"{reason_line}"
    )
    await msg.reply_text(text, parse_mode="HTML", reply_markup=_unmute_button(target.id))

    await log_action(
        context.bot,
        chat_id=chat.id,
        action="tmute",
        admin=actor,
        target=target,
        reason=reason,
        extra=f"duration: {duration_str}",
    )


# ─────────────────────────────────────────────────────────────────────────────
# /unmute
# ─────────────────────────────────────────────────────────────────────────────

@group_only
@admin_required
@bot_admin_required
async def unmute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Restore all messaging permissions for a muted user."""
    chat = update.effective_chat
    actor = update.effective_user
    msg = update.effective_message

    extracted = await extract_user_and_reason(update, context)
    if extracted.error or extracted.user is None:
        await msg.reply_text(f"❌ {sc(extracted.error or 'could not resolve user.')}")
        return

    target = extracted.user

    try:
        # Restore to full default group permissions
        await context.bot.restrict_chat_member(
            chat.id, target.id, permissions=_UNMUTE_PERMISSIONS
        )
    except TelegramError as exc:
        await msg.reply_text(
            f"❌ {sc('failed to unmute:')} <code>{exc}</code>", parse_mode="HTML"
        )
        return

    text = (
        f"🔊 <b>{sc('unmuted')}</b>\n"
        f"👤 {_mention_html(target)} (<code>{target.id}</code>)"
    )
    await msg.reply_text(text, parse_mode="HTML")

    await log_action(
        context.bot, chat_id=chat.id, action="unmute", admin=actor, target=target
    )


# ─────────────────────────────────────────────────────────────────────────────
# /smute  (silent mute)
# ─────────────────────────────────────────────────────────────────────────────

@group_only
@admin_required
@bot_admin_required
async def smute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Silently mute a user with no public announcement."""
    chat = update.effective_chat
    actor = update.effective_user
    msg = update.effective_message

    extracted = await extract_user_and_reason(update, context)
    if extracted.error or extracted.user is None:
        err = await msg.reply_text(f"❌ {sc(extracted.error or 'could not resolve user.')}")
        await asyncio.sleep(3)
        try:
            await err.delete()
        except TelegramError:
            pass
        try:
            await msg.delete()
        except TelegramError:
            pass
        return

    target = extracted.user
    reason = extracted.reason

    if await _is_protected(chat, target, context.bot.id, context):
        err = await msg.reply_text(f"❌ {sc('i cannot mute admins or myself.')}")
        await asyncio.sleep(3)
        try:
            await err.delete()
        except TelegramError:
            pass
        try:
            await msg.delete()
        except TelegramError:
            pass
        return

    try:
        await context.bot.restrict_chat_member(
            chat.id, target.id, permissions=_MUTE_PERMISSIONS
        )
    except TelegramError as exc:
        await msg.reply_text(
            f"❌ {sc('failed to mute:')} <code>{exc}</code>", parse_mode="HTML"
        )
        return

    await users_db.upsert_user(
        target.id,
        username=target.username,
        first_name=target.first_name,
        last_name=target.last_name,
    )

    # Delete the command message — silent mute leaves no trace
    try:
        await msg.delete()
    except TelegramError:
        pass

    await log_action(
        context.bot,
        chat_id=chat.id,
        action="smute",
        admin=actor,
        target=target,
        reason=reason,
        extra="silent mute",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Callback: [🔊 ᴜɴᴍᴜᴛᴇ] button
# ─────────────────────────────────────────────────────────────────────────────

async def unmute_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the [🔊 ᴜɴᴍᴜᴛᴇ] inline button press."""
    query = update.callback_query
    await query.answer()

    chat = update.effective_chat
    actor = update.effective_user

    # Verify the presser is an admin
    try:
        member = await context.bot.get_chat_member(chat.id, actor.id)
        if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            await query.answer(sc("only admins can unmute."), show_alert=True)
            return
    except TelegramError:
        await query.answer(sc("could not verify your admin status."), show_alert=True)
        return

    try:
        _, user_id_str = query.data.split(":")
        user_id = int(user_id_str)
    except (ValueError, AttributeError):
        await query.answer(sc("invalid callback data."), show_alert=True)
        return

    try:
        await context.bot.restrict_chat_member(
            chat.id, user_id, permissions=_UNMUTE_PERMISSIONS
        )
    except TelegramError as exc:
        await query.answer(f"{sc('failed to unmute:')} {exc}", show_alert=True)
        return

    import html as _html
    new_text = (
        (query.message.text or query.message.caption or "")
        + f"\n\n🔊 <b>{sc('unmuted by')}</b> {_mention_html(actor)}"
    )
    try:
        await query.edit_message_text(new_text, parse_mode="HTML", reply_markup=None)
    except TelegramError:
        pass

    await log_action(
        context.bot,
        chat_id=chat.id,
        action="unmute (callback)",
        admin=actor,
        target=None,
        extra=f"user_id={user_id}",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Handler registration
# ─────────────────────────────────────────────────────────────────────────────

def register_handlers(app) -> None:
    """Register all mute command and callback handlers with the Application."""
    app.add_handler(CommandHandler("mute", mute_cmd))
    app.add_handler(CommandHandler("tmute", tmute_cmd))
    app.add_handler(CommandHandler("unmute", unmute_cmd))
    app.add_handler(CommandHandler("smute", smute_cmd))
    app.add_handler(CallbackQueryHandler(unmute_callback, pattern=r"^unmute:\d+$"))
    logger.info("mutes module registered.")
