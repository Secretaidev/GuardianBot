"""
bot/modules/bans.py
───────────────────
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — Ban / Kick module.

Commands
--------
/ban   <user> [reason] — Permanently ban a user, delete the command message.
/tban  <user> <time> [reason] — Temporary ban (e.g. 3d, 2h, 30m).
/unban <user>          — Remove a user's ban.
/sban  <user>          — Silent ban (no confirmation message).
/kick  <user> [reason] — Kick user (they can rejoin).
/kickme                — User kicks themselves out of the group.

All ban actions post an inline [🔓 ᴜɴʙᴀɴ] button callback so admins can
quickly reverse the action without typing a command.
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

from bot.database import chats_db, users_db
from bot.fonts import sc
from bot.helpers.decorators import admin_required, bot_admin_required, group_only
from bot.helpers.extractors import extract_user_and_reason
from bot.helpers.time_parser import format_duration, parse_time
from bot.logger import log_action

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _unban_button(user_id: int) -> InlineKeyboardMarkup:
    """Return an inline keyboard with a single [🔓 ᴜɴʙᴀɴ] button."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(
            text="🔓 ᴜɴʙᴀɴ",
            callback_data=f"unban:{user_id}",
        )]]
    )


async def _is_protected(
    chat: Chat, user: User, bot_id: int, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """
    Return True if *user* is an admin, creator, or the bot itself.
    Protected users cannot be banned or kicked.
    """
    if user.id == bot_id:
        return True
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        )
    except TelegramError:
        return False


def _mention_html(user: User) -> str:
    """Return an HTML mention string for *user*."""
    import html
    name = html.escape(user.full_name)
    return f'<a href="tg://user?id={user.id}">{name}</a>'


# ─────────────────────────────────────────────────────────────────────────────
# /ban
# ─────────────────────────────────────────────────────────────────────────────

@group_only
@admin_required
@bot_admin_required
async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Permanently ban a user from the group."""
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
        await msg.reply_text(
            f"❌ {sc('i cannot ban admins or myself.')}"
        )
        return

    try:
        await context.bot.ban_chat_member(chat.id, target.id)
    except TelegramError as exc:
        await msg.reply_text(f"❌ {sc('failed to ban:')} <code>{exc}</code>", parse_mode="HTML")
        return

    # Store user in database
    await users_db.upsert_user(
        target.id,
        username=target.username,
        first_name=target.first_name,
        last_name=target.last_name,
    )

    reason_line = f"\n📝 <b>{sc('reason')}:</b> {reason}" if reason else ""
    text = (
        f"🔨 <b>{sc('banned')}</b>\n"
        f"👤 {_mention_html(target)} (<code>{target.id}</code>)"
        f"{reason_line}"
    )
    await msg.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=_unban_button(target.id),
    )

    # Delete the command message silently
    try:
        await msg.delete()
    except TelegramError:
        pass

    await log_action(
        context.bot,
        chat_id=chat.id,
        action="ban",
        admin=actor,
        target=target,
        reason=reason,
    )


# ─────────────────────────────────────────────────────────────────────────────
# /tban
# ─────────────────────────────────────────────────────────────────────────────

@group_only
@admin_required
@bot_admin_required
async def tban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Temporarily ban a user for a specified duration."""
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
        await msg.reply_text(f"❌ {sc('i cannot ban admins or myself.')}")
        return

    # When user was resolved from a reply, args[0] should be the time.
    # When resolved from mention, args[1] should be the time (args[0] was the mention).
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
            f"❌ {sc('usage:')} /tban <user> <time> [reason]\n"
            f"{sc('example:')} /tban @user 2h spam"
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
        await context.bot.ban_chat_member(
            chat.id, target.id, until_date=until_date
        )
    except TelegramError as exc:
        await msg.reply_text(
            f"❌ {sc('failed to temporarily ban:')} <code>{exc}</code>",
            parse_mode="HTML",
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
        f"⏳ <b>{sc('temporarily banned')}</b>\n"
        f"👤 {_mention_html(target)} (<code>{target.id}</code>)\n"
        f"⏱ <b>{sc('duration')}:</b> {sc(duration_str)}"
        f"{reason_line}"
    )
    await msg.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=_unban_button(target.id),
    )

    try:
        await msg.delete()
    except TelegramError:
        pass

    await log_action(
        context.bot,
        chat_id=chat.id,
        action="tban",
        admin=actor,
        target=target,
        reason=reason,
        extra=f"duration: {duration_str}",
    )


# ─────────────────────────────────────────────────────────────────────────────
# /unban
# ─────────────────────────────────────────────────────────────────────────────

@group_only
@admin_required
@bot_admin_required
async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unban a previously banned user."""
    chat = update.effective_chat
    actor = update.effective_user
    msg = update.effective_message

    extracted = await extract_user_and_reason(update, context)
    if extracted.error or extracted.user is None:
        await msg.reply_text(f"❌ {sc(extracted.error or 'could not resolve user.')}")
        return

    target = extracted.user

    try:
        await context.bot.unban_chat_member(chat.id, target.id, only_if_banned=True)
    except TelegramError as exc:
        await msg.reply_text(
            f"❌ {sc('failed to unban:')} <code>{exc}</code>", parse_mode="HTML"
        )
        return

    text = (
        f"✅ <b>{sc('unbanned')}</b>\n"
        f"👤 {_mention_html(target)} (<code>{target.id}</code>)"
    )
    await msg.reply_text(text, parse_mode="HTML")

    await log_action(
        context.bot, chat_id=chat.id, action="unban", admin=actor, target=target
    )


# ─────────────────────────────────────────────────────────────────────────────
# /sban  (silent ban)
# ─────────────────────────────────────────────────────────────────────────────

@group_only
@admin_required
@bot_admin_required
async def sban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Silently ban a user — delete both command and any reply confirmation."""
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
        # Even the error we delete for stealth
        err = await msg.reply_text(f"❌ {sc('i cannot ban admins or myself.')}")
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
        await context.bot.ban_chat_member(chat.id, target.id)
    except TelegramError as exc:
        await msg.reply_text(
            f"❌ {sc('failed to ban:')} <code>{exc}</code>", parse_mode="HTML"
        )
        return

    await users_db.upsert_user(
        target.id,
        username=target.username,
        first_name=target.first_name,
        last_name=target.last_name,
    )

    # Delete command message silently
    try:
        await msg.delete()
    except TelegramError:
        pass

    await log_action(
        context.bot,
        chat_id=chat.id,
        action="sban",
        admin=actor,
        target=target,
        reason=reason,
        extra="silent ban",
    )


# ─────────────────────────────────────────────────────────────────────────────
# /kick
# ─────────────────────────────────────────────────────────────────────────────

@group_only
@admin_required
@bot_admin_required
async def kick_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kick a user from the group (they may rejoin via invite link)."""
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
        await msg.reply_text(f"❌ {sc('i cannot kick admins or myself.')}")
        return

    try:
        # Ban then immediately unban = kick (user can rejoin)
        await context.bot.ban_chat_member(chat.id, target.id)
        await context.bot.unban_chat_member(chat.id, target.id)
    except TelegramError as exc:
        await msg.reply_text(
            f"❌ {sc('failed to kick:')} <code>{exc}</code>", parse_mode="HTML"
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
        f"👢 <b>{sc('kicked')}</b>\n"
        f"👤 {_mention_html(target)} (<code>{target.id}</code>)"
        f"{reason_line}"
    )
    await msg.reply_text(text, parse_mode="HTML")

    await log_action(
        context.bot, chat_id=chat.id, action="kick", admin=actor, target=target, reason=reason
    )


# ─────────────────────────────────────────────────────────────────────────────
# /kickme
# ─────────────────────────────────────────────────────────────────────────────

@group_only
@bot_admin_required
async def kickme_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Allow a user to kick themselves out of the group."""
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    # Make sure we do not kick an admin
    if await _is_protected(chat, user, context.bot.id, context):
        await msg.reply_text(f"❌ {sc('i cannot kick an admin, even at their own request.')}")
        return

    try:
        await context.bot.ban_chat_member(chat.id, user.id)
        await context.bot.unban_chat_member(chat.id, user.id)
    except TelegramError as exc:
        await msg.reply_text(
            f"❌ {sc('could not kick you:')} <code>{exc}</code>", parse_mode="HTML"
        )
        return

    await msg.reply_text(f"👋 {sc('see you around!')} {_mention_html(user)}", parse_mode="HTML")


# ─────────────────────────────────────────────────────────────────────────────
# Callback: [🔓 ᴜɴʙᴀɴ] button
# ─────────────────────────────────────────────────────────────────────────────

async def unban_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the [🔓 ᴜɴʙᴀɴ] inline button press."""
    query = update.callback_query
    await query.answer()

    chat = update.effective_chat
    actor = update.effective_user

    # Verify the presser is an admin
    try:
        member = await context.bot.get_chat_member(chat.id, actor.id)
        if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
            await query.answer(sc("only admins can unban."), show_alert=True)
            return
    except TelegramError:
        await query.answer(sc("could not verify your admin status."), show_alert=True)
        return

    # Parse the target user ID from callback_data
    try:
        _, user_id_str = query.data.split(":")
        user_id = int(user_id_str)
    except (ValueError, AttributeError):
        await query.answer(sc("invalid callback data."), show_alert=True)
        return

    try:
        await context.bot.unban_chat_member(chat.id, user_id, only_if_banned=True)
    except TelegramError as exc:
        await query.answer(f"{sc('failed to unban:')} {exc}", show_alert=True)
        return

    # Update the original message to remove the button
    import html as _html
    original_text = query.message.text or query.message.caption or ""
    new_text = original_text + f"\n\n✅ <b>{sc('unbanned by')}</b> {_mention_html(actor)}"
    try:
        await query.edit_message_text(new_text, parse_mode="HTML", reply_markup=None)
    except TelegramError:
        pass

    await log_action(
        context.bot,
        chat_id=chat.id,
        action="unban (callback)",
        admin=actor,
        target=None,
        extra=f"user_id={user_id}",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Handler registration
# ─────────────────────────────────────────────────────────────────────────────

def register_handlers(app) -> None:
    """Register all ban/kick command and callback handlers with the Application."""
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("tban", tban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("sban", sban_cmd))
    app.add_handler(CommandHandler("kick", kick_cmd))
    app.add_handler(CommandHandler("kickme", kickme_cmd))
    app.add_handler(CallbackQueryHandler(unban_callback, pattern=r"^unban:\d+$"))
    logger.info("bans module registered.")
