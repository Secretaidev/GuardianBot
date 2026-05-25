"""
bot/modules/warns.py
────────────────────
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — Warning system module.

Commands
--------
/warn      <user> [reason]  — Warn a user; auto-action on limit.
/warns     <user>           — Show a user's current warn list.
/resetwarn <user>           — Reset all warnings for one user.
/resetallwarns              — Reset all warnings in the current chat.
/warnlimit <num>            — Set the warn limit (1–99).
/warnmode  <ban|kick|mute>  — Set the action taken when limit is reached.
/warnlist                   — Show current warn settings for this chat.

Warn messages display a graphical progress bar and inline action buttons:
  [⚠️ ᴡᴀʀɴ ʟɪꜱᴛ]  [🔄 ʀᴇꜱᴇᴛ]
"""

from __future__ import annotations

import html
import logging

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

from bot.database import chats_db, users_db, warns_db
from bot.fonts import sc
from bot.helpers.decorators import admin_required, bot_admin_required, group_only
from bot.helpers.extractors import extract_user, extract_user_and_reason
from bot.logger import log_action

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _mention_html(user: User) -> str:
    name = html.escape(user.full_name)
    return f'<a href="tg://user?id={user.id}">{name}</a>'


def _progress_bar(current: int, total: int, length: int = 8) -> str:
    """
    Generate a Unicode block progress bar.

    Example: _progress_bar(3, 5) → '████░░░░ 3/5'
    """
    filled = int(round(length * current / max(total, 1)))
    bar = "█" * filled + "░" * (length - filled)
    return f"{bar} {current}/{total}"


def _warn_action_buttons(user_id: int) -> InlineKeyboardMarkup:
    """Return the standard warn action inline keyboard."""
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton(
                text="⚠️ ᴡᴀʀɴ ʟɪꜱᴛ",
                callback_data=f"warnlist:{user_id}",
            ),
            InlineKeyboardButton(
                text="🔄 ʀᴇꜱᴇᴛ",
                callback_data=f"warnreset:{user_id}",
            ),
        ]]
    )


async def _is_protected(
    chat: Chat, user: User, bot_id: int, context: ContextTypes.DEFAULT_TYPE
) -> bool:
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
)


async def _apply_warn_action(
    context: ContextTypes.DEFAULT_TYPE,
    chat: Chat,
    target: User,
    mode: str,
) -> str:
    """
    Execute the configured action (mute/kick/ban) when the warn limit is reached.

    Returns a human-readable string describing what was done.
    """
    bot = context.bot

    if mode == "ban":
        try:
            await bot.ban_chat_member(chat.id, target.id)
            return sc("user was banned for reaching the warn limit.")
        except TelegramError as exc:
            logger.warning("Warn auto-ban failed: %s", exc)
            return sc(f"auto-ban failed: {exc}")

    if mode == "kick":
        try:
            await bot.ban_chat_member(chat.id, target.id)
            await bot.unban_chat_member(chat.id, target.id)
            return sc("user was kicked for reaching the warn limit.")
        except TelegramError as exc:
            logger.warning("Warn auto-kick failed: %s", exc)
            return sc(f"auto-kick failed: {exc}")

    # Default: mute
    try:
        await bot.restrict_chat_member(chat.id, target.id, permissions=_MUTE_PERMISSIONS)
        return sc("user was muted for reaching the warn limit.")
    except TelegramError as exc:
        logger.warning("Warn auto-mute failed: %s", exc)
        return sc(f"auto-mute failed: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# /warn
# ─────────────────────────────────────────────────────────────────────────────

@group_only
@admin_required
@bot_admin_required
async def warn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Warn a user, showing progress toward the warn limit."""
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
        await msg.reply_text(f"❌ {sc('i cannot warn admins or myself.')}")
        return

    # Add the warning to database
    warn_count, warn_id = await warns_db.add_warn(
        chat_id=chat.id,
        user_id=target.id,
        reason=reason,
        warned_by=actor.id,
    )

    # Fetch warn settings (limit & mode)
    settings = await warns_db.get_warn_settings(chat.id)
    warn_limit: int = settings["limit"]
    warn_mode: str = settings["mode"]

    # Store/update user in DB
    await users_db.upsert_user(
        target.id,
        username=target.username,
        first_name=target.first_name,
        last_name=target.last_name,
    )

    progress = _progress_bar(warn_count, warn_limit)
    reason_line = f"\n📝 <b>{sc('reason')}:</b> {html.escape(reason)}" if reason else ""

    # Check if limit is reached
    if warn_count >= warn_limit:
        action_result = await _apply_warn_action(context, chat, target, warn_mode)
        # Reset warns after action
        await warns_db.reset_warns(chat.id, target.id)

        text = (
            f"⚠️ <b>{sc('warn limit reached!')}</b>\n"
            f"👤 {_mention_html(target)}\n"
            f"📊 {progress}\n"
            f"⚡ {action_result}"
            f"{reason_line}"
        )
        await msg.reply_text(text, parse_mode="HTML")

        await log_action(
            context.bot,
            chat_id=chat.id,
            action=f"warn+{warn_mode}",
            admin=actor,
            target=target,
            reason=reason,
            extra=f"warn {warn_count}/{warn_limit} → {warn_mode}",
        )
        return

    text = (
        f"⚠️ <b>{sc('warned')}</b>\n"
        f"👤 {_mention_html(target)} (<code>{target.id}</code>)\n"
        f"📊 {sc('warns')}: {progress}"
        f"{reason_line}"
    )
    await msg.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=_warn_action_buttons(target.id),
    )

    await log_action(
        context.bot,
        chat_id=chat.id,
        action="warn",
        admin=actor,
        target=target,
        reason=reason,
        extra=f"warn {warn_count}/{warn_limit}",
    )


# ─────────────────────────────────────────────────────────────────────────────
# /warns
# ─────────────────────────────────────────────────────────────────────────────

@group_only
@admin_required
async def warns_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display the list of warnings for a user."""
    chat = update.effective_chat
    msg = update.effective_message

    extracted = await extract_user(update, context)
    if extracted.error or extracted.user is None:
        await msg.reply_text(f"❌ {sc(extracted.error or 'could not resolve user.')}")
        return

    target = extracted.user
    warn_list = await warns_db.get_warns(chat.id, target.id)
    settings = await warns_db.get_warn_settings(chat.id)
    warn_limit: int = settings["limit"]
    warn_count = len(warn_list)

    if warn_count == 0:
        await msg.reply_text(
            f"✅ {_mention_html(target)} {sc('has no warnings in this chat.')}",
            parse_mode="HTML",
        )
        return

    progress = _progress_bar(warn_count, warn_limit)
    lines = [
        f"⚠️ <b>{sc('warnings for')} {_mention_html(target)}:</b>",
        f"📊 {progress}",
        "",
    ]
    for i, w in enumerate(warn_list, start=1):
        reason_text = html.escape(w.get("reason") or sc("no reason given"))
        lines.append(f"  {i}. {reason_text}")

    await msg.reply_text("\n".join(lines), parse_mode="HTML")


# ─────────────────────────────────────────────────────────────────────────────
# /resetwarn
# ─────────────────────────────────────────────────────────────────────────────

@group_only
@admin_required
async def resetwarn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset all warnings for a specific user in this chat."""
    chat = update.effective_chat
    actor = update.effective_user
    msg = update.effective_message

    extracted = await extract_user(update, context)
    if extracted.error or extracted.user is None:
        await msg.reply_text(f"❌ {sc(extracted.error or 'could not resolve user.')}")
        return

    target = extracted.user
    await warns_db.reset_warns(chat.id, target.id)

    text = (
        f"🔄 <b>{sc('warns reset')}</b>\n"
        f"👤 {_mention_html(target)} (<code>{target.id}</code>)\n"
        f"ℹ️ {sc('all warnings have been cleared.')}"
    )
    await msg.reply_text(text, parse_mode="HTML")

    await log_action(
        context.bot, chat_id=chat.id, action="resetwarn", admin=actor, target=target
    )


# ─────────────────────────────────────────────────────────────────────────────
# /resetallwarns
# ─────────────────────────────────────────────────────────────────────────────

@group_only
@admin_required
async def resetallwarns_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset ALL warnings for every user in the current chat."""
    chat = update.effective_chat
    actor = update.effective_user
    msg = update.effective_message

    cleared = await warns_db.reset_all_warns(chat.id)
    await msg.reply_text(
        f"🔄 <b>{sc('all warns cleared')}</b>\n"
        f"ℹ️ {sc(f'reset warn records for {cleared} user(s) in this chat.')}",
        parse_mode="HTML",
    )

    await log_action(
        context.bot,
        chat_id=chat.id,
        action="resetallwarns",
        admin=actor,
        target=None,
        extra=f"{cleared} user records cleared",
    )


# ─────────────────────────────────────────────────────────────────────────────
# /warnlimit
# ─────────────────────────────────────────────────────────────────────────────

@group_only
@admin_required
async def warnlimit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set the number of warns before automatic action is taken."""
    chat = update.effective_chat
    msg = update.effective_message
    args = context.args or []

    if not args:
        settings = await warns_db.get_warn_settings(chat.id)
        await msg.reply_text(
            f"ℹ️ {sc('current warn limit:')} <b>{settings['limit']}</b>\n"
            f"{sc('usage:')} /warnlimit <1-99>",
            parse_mode="HTML",
        )
        return

    try:
        limit = int(args[0])
    except ValueError:
        await msg.reply_text(f"❌ {sc('please provide a valid number between 1 and 99.')}")
        return

    if not 1 <= limit <= 99:
        await msg.reply_text(f"❌ {sc('warn limit must be between 1 and 99.')}")
        return

    settings = await warns_db.get_warn_settings(chat.id)
    await warns_db.set_warn_settings(chat.id, limit=limit, mode=settings["mode"])

    await msg.reply_text(
        f"✅ {sc('warn limit set to')} <b>{limit}</b>.",
        parse_mode="HTML",
    )


# ─────────────────────────────────────────────────────────────────────────────
# /warnmode
# ─────────────────────────────────────────────────────────────────────────────

@group_only
@admin_required
async def warnmode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set the action performed when the warn limit is reached."""
    chat = update.effective_chat
    msg = update.effective_message
    args = context.args or []

    valid_modes = ("ban", "kick", "mute")
    if not args or args[0].lower() not in valid_modes:
        await msg.reply_text(
            f"❌ {sc('usage:')} /warnmode <ban|kick|mute>\n"
            f"{sc('valid modes:')} ban, kick, mute"
        )
        return

    mode = args[0].lower()
    settings = await warns_db.get_warn_settings(chat.id)
    await warns_db.set_warn_settings(chat.id, limit=settings["limit"], mode=mode)

    await msg.reply_text(
        f"✅ {sc('warn mode set to')} <b>{sc(mode)}</b>.",
        parse_mode="HTML",
    )


# ─────────────────────────────────────────────────────────────────────────────
# /warnlist
# ─────────────────────────────────────────────────────────────────────────────

@group_only
async def warnlist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current warn configuration for this chat."""
    chat = update.effective_chat
    msg = update.effective_message

    settings = await warns_db.get_warn_settings(chat.id)
    limit = settings["limit"]
    mode = settings["mode"]

    mode_emoji = {"ban": "🔨", "kick": "👢", "mute": "🔇"}.get(mode, "⚡")
    text = (
        f"⚙️ <b>{sc('warn settings')}</b>\n\n"
        f"📊 {sc('limit')}: <b>{limit}</b>\n"
        f"{mode_emoji} {sc('action on limit')}: <b>{sc(mode)}</b>"
    )
    await msg.reply_text(text, parse_mode="HTML")


# ─────────────────────────────────────────────────────────────────────────────
# Callback: [⚠️ ᴡᴀʀɴ ʟɪꜱᴛ] and [🔄 ʀᴇꜱᴇᴛ] buttons
# ─────────────────────────────────────────────────────────────────────────────

async def warnlist_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show warn list for a user via the inline button."""
    query = update.callback_query
    await query.answer()

    chat = update.effective_chat

    try:
        _, user_id_str = query.data.split(":")
        user_id = int(user_id_str)
    except (ValueError, AttributeError):
        await query.answer(sc("invalid callback data."), show_alert=True)
        return

    warn_list = await warns_db.get_warns(chat.id, user_id)
    settings = await warns_db.get_warn_settings(chat.id)
    warn_limit: int = settings["limit"]
    warn_count = len(warn_list)

    progress = _progress_bar(warn_count, warn_limit)

    if warn_count == 0:
        await query.answer(sc("this user has no active warnings."), show_alert=True)
        return

    lines = [f"⚠️ <b>{sc(f'warns for user {user_id}:')}</b>", f"📊 {progress}", ""]
    for i, w in enumerate(warn_list, start=1):
        reason_text = html.escape(w.get("reason") or sc("no reason given"))
        lines.append(f"  {i}. {reason_text}")

    try:
        await query.message.reply_text("\n".join(lines), parse_mode="HTML")
    except TelegramError:
        await query.answer(sc("could not display warn list."), show_alert=True)


async def warnreset_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset warns for a user via the inline button (admin only)."""
    query = update.callback_query
    await query.answer()

    chat = update.effective_chat
    actor = update.effective_user

    # Verify admin
    try:
        member = await context.bot.get_chat_member(chat.id, actor.id)
        if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
            await query.answer(sc("only admins can reset warns."), show_alert=True)
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

    await warns_db.reset_warns(chat.id, user_id)

    new_text = (
        (query.message.text or query.message.caption or "")
        + f"\n\n🔄 <b>{sc('warns reset by')}</b> {_mention_html(actor)}"
    )
    try:
        await query.edit_message_text(new_text, parse_mode="HTML", reply_markup=None)
    except TelegramError:
        pass

    await log_action(
        context.bot,
        chat_id=chat.id,
        action="resetwarn (callback)",
        admin=actor,
        target=None,
        extra=f"user_id={user_id}",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Handler registration
# ─────────────────────────────────────────────────────────────────────────────

def register_handlers(app) -> None:
    """Register all warn-system handlers with the Application."""
    app.add_handler(CommandHandler("warn", warn_cmd))
    app.add_handler(CommandHandler("warns", warns_cmd))
    app.add_handler(CommandHandler("resetwarn", resetwarn_cmd))
    app.add_handler(CommandHandler("resetallwarns", resetallwarns_cmd))
    app.add_handler(CommandHandler("warnlimit", warnlimit_cmd))
    app.add_handler(CommandHandler("warnmode", warnmode_cmd))
    app.add_handler(CommandHandler("warnlist", warnlist_cmd))
    app.add_handler(CallbackQueryHandler(warnlist_callback, pattern=r"^warnlist:\d+$"))
    app.add_handler(CallbackQueryHandler(warnreset_callback, pattern=r"^warnreset:\d+$"))
    logger.info("warns module registered.")
