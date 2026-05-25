"""
bot/modules/welcome.py
──────────────────────
Welcome / goodbye module for ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ.

Commands
--------
/welcome on|off          – Toggle welcome messages
/welcome                 – Show current welcome settings
/setwelcome <text>       – Set welcome message (supports template vars + buttons)
/resetwelcome            – Reset to default welcome
/goodbye on|off          – Toggle goodbye messages
/goodbye                 – Show current goodbye settings
/setgoodbye <text>       – Set goodbye message
/resetgoodbye            – Reset to default goodbye
/cleanwelcome on|off     – Auto-delete previous welcome message on new join
/cleanservice on|off     – Auto-delete Telegram service messages (join/left)

Template variables in welcome/goodbye text
------------------------------------------
  {first}     – user's first name
  {last}      – user's last name (empty string if absent)
  {fullname}  – full name
  {username}  – @username or first name if no username
  {id}        – user's numeric ID
  {chatname}  – the group's title
  {count}     – number of group members

Button syntax (same line → same row)
-------------------------------------
  [Button Text](https://example.com)
  [Button Text](buttonurl:https://example.com:same)
"""

from __future__ import annotations

import html
import logging
from typing import Optional

from telegram import (
    ChatMember,
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    Update,
)
from telegram.constants import ChatMemberStatus, ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    filters,
)

from bot.database import chats_db
from bot.fonts import sc
from bot.helpers.decorators import admin_required, bot_admin_required, group_only
from bot.helpers.extractors import build_buttons, extract_text_and_buttons
from bot.logger import log_action

logger = logging.getLogger(__name__)

# ── Default welcome / goodbye templates ───────────────────────────────────────
_DEFAULT_WELCOME = "ʜᴇʏ {first}! ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ {chatname}! 🎉"
_DEFAULT_GOODBYE = sc("goodbye {first}, we'll miss you!")


# ─────────────────────────────────────────────────────────────────────────────
# Template rendering
# ─────────────────────────────────────────────────────────────────────────────

async def _render_template(
    template: str,
    user,
    chat,
    bot,
) -> str:
    """Replace all template variables in *template* with live values."""
    first = html.escape(user.first_name or "")
    last = html.escape(user.last_name or "")
    fullname = html.escape(user.full_name or "")
    username = f"@{user.username}" if user.username else first

    try:
        member_count = await chat.get_member_count()
    except TelegramError:
        member_count = "?"

    return (
        template
        .replace("{first}", first)
        .replace("{last}", last)
        .replace("{fullname}", fullname)
        .replace("{username}", username)
        .replace("{id}", str(user.id))
        .replace("{chatname}", html.escape(chat.title or ""))
        .replace("{count}", str(member_count))
    )


# ─────────────────────────────────────────────────────────────────────────────
# Welcome / goodbye sender
# ─────────────────────────────────────────────────────────────────────────────

async def _send_welcome(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user,
    chat,
    is_welcome: bool,
) -> None:
    """
    Fetch settings and send the welcome or goodbye message.
    Handles cleanwelcome (delete old welcome) and cleanservice logic.
    """
    if is_welcome:
        settings = await chats_db.get_chat(chat.id) or {}
        enabled = settings.get("welcome_enabled", True)
        template = settings.get("welcome_text") or _DEFAULT_WELCOME
        buttons_data: list[dict] = settings.get("welcome_buttons", [])
        clean = settings.get("clean_welcome", True)
        last_msg_id = settings.get("last_welcome_msg_id")
    else:
        settings = await chats_db.get_chat(chat.id) or {}
        enabled = settings.get("goodbye_enabled", False)
        template = settings.get("goodbye_text") or _DEFAULT_GOODBYE
        buttons_data = []
        clean = False
        last_msg_id = None

    if not enabled:
        return

    # Delete the previous welcome/goodbye message if cleanwelcome is on
    if clean and last_msg_id and is_welcome:
        try:
            await context.bot.delete_message(chat_id=chat.id, message_id=last_msg_id)
        except TelegramError:
            pass

    text = await _render_template(template, user, chat, context.bot)
    markup = build_buttons(buttons_data) if buttons_data else None

    try:
        sent = await context.bot.send_message(
            chat_id=chat.id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=markup,
            disable_web_page_preview=True,
        )
        if is_welcome and clean:
            await chats_db.update_chat_setting(
                chat.id, "last_welcome_msg_id", sent.message_id
            )
    except TelegramError as exc:
        logger.warning("Failed to send %s to chat %s: %s",
                       "welcome" if is_welcome else "goodbye", chat.id, exc)


# ─────────────────────────────────────────────────────────────────────────────
# chat_member update handler
# ─────────────────────────────────────────────────────────────────────────────

async def handle_chat_member(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle ChatMemberUpdated events to send welcome / goodbye / clean service."""
    result: Optional[ChatMemberUpdated] = update.chat_member
    if result is None:
        return

    chat = result.chat
    user = result.new_chat_member.user
    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status

    settings = await chats_db.get_chat(chat.id) or {}
    clean_service = settings.get("clean_service", False)

    # Detect join: was not a member → is now a member
    joined = (
        old_status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED)
        and new_status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR)
    )

    # Detect leave: was a member → is now left/banned/kicked
    left = (
        old_status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR)
        and new_status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED)
    )

    if joined:
        await _send_welcome(update, context, user, chat, is_welcome=True)

    elif left:
        await _send_welcome(update, context, user, chat, is_welcome=False)


# ─────────────────────────────────────────────────────────────────────────────
# Command handlers
# ─────────────────────────────────────────────────────────────────────────────

@group_only
@admin_required
async def cmd_welcome(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """/welcome [on|off] — Toggle or show current welcome settings."""
    msg = update.effective_message
    chat = update.effective_chat
    args = context.args or []

    if not args:
        # Show current settings
        settings = await chats_db.get_chat(chat.id) or {}
        enabled = settings.get("welcome_enabled", True)
        text_set = bool(settings.get("welcome_text"))
        clean = settings.get("clean_welcome", True)
        clean_svc = settings.get("clean_service", False)
        state = sc("enabled") if enabled else sc("disabled")
        template = settings.get("welcome_text") or _DEFAULT_WELCOME
        response = (
            f"<b>🎉 {sc('welcome settings')}</b>\n"
            f"<b>{sc('status')}:</b> {state}\n"
            f"<b>{sc('clean welcome')}:</b> {'✅' if clean else '❌'}\n"
            f"<b>{sc('clean service')}:</b> {'✅' if clean_svc else '❌'}\n\n"
            f"<b>{sc('current template')}:</b>\n<code>{html.escape(template)}</code>"
        )
        await msg.reply_text(response, parse_mode=ParseMode.HTML)
        return

    arg = args[0].lower()
    if arg == "on":
        await chats_db.update_chat_setting(chat.id, "welcome_enabled", True)
        await msg.reply_text(f"✅ {sc('welcome messages enabled.')}")
    elif arg == "off":
        await chats_db.update_chat_setting(chat.id, "welcome_enabled", False)
        await msg.reply_text(f"❌ {sc('welcome messages disabled.')}")
    else:
        await msg.reply_text(sc("usage: /welcome on|off"))


@group_only
@admin_required
async def cmd_setwelcome(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """/setwelcome <text> — Set the welcome message template."""
    msg = update.effective_message
    chat = update.effective_chat

    # Get text: from args or from reply
    raw_text: Optional[str] = None
    if msg.reply_to_message and msg.reply_to_message.text:
        raw_text = msg.reply_to_message.text
    elif context.args:
        raw_text = " ".join(context.args)

    if not raw_text:
        await msg.reply_text(
            sc("please provide the welcome text or reply to a message.")
        )
        return

    clean_text, buttons = extract_text_and_buttons(raw_text)
    await chats_db.update_chat_setting(chat.id, "welcome_text", clean_text)
    await chats_db.update_chat_setting(chat.id, "welcome_buttons", buttons)

    preview = await _render_template(
        clean_text, update.effective_user, chat, context.bot
    )
    markup = build_buttons(buttons)
    await msg.reply_text(
        f"✅ {sc('welcome message updated! preview:')}\n\n{preview}",
        parse_mode=ParseMode.HTML,
        reply_markup=markup,
        disable_web_page_preview=True,
    )


@group_only
@admin_required
async def cmd_resetwelcome(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """/resetwelcome — Reset the welcome message to the default."""
    chat = update.effective_chat
    await chats_db.update_chat_setting(chat.id, "welcome_text", None)
    await chats_db.update_chat_setting(chat.id, "welcome_buttons", [])
    await update.effective_message.reply_text(
        f"✅ {sc('welcome message reset to default.')}"
    )


@group_only
@admin_required
async def cmd_goodbye(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """/goodbye [on|off] — Toggle or show current goodbye settings."""
    msg = update.effective_message
    chat = update.effective_chat
    args = context.args or []

    if not args:
        settings = await chats_db.get_chat(chat.id) or {}
        enabled = settings.get("goodbye_enabled", False)
        template = settings.get("goodbye_text") or _DEFAULT_GOODBYE
        state = sc("enabled") if enabled else sc("disabled")
        response = (
            f"<b>👋 {sc('goodbye settings')}</b>\n"
            f"<b>{sc('status')}:</b> {state}\n\n"
            f"<b>{sc('current template')}:</b>\n<code>{html.escape(template)}</code>"
        )
        await msg.reply_text(response, parse_mode=ParseMode.HTML)
        return

    arg = args[0].lower()
    if arg == "on":
        await chats_db.update_chat_setting(chat.id, "goodbye_enabled", True)
        await msg.reply_text(f"✅ {sc('goodbye messages enabled.')}")
    elif arg == "off":
        await chats_db.update_chat_setting(chat.id, "goodbye_enabled", False)
        await msg.reply_text(f"❌ {sc('goodbye messages disabled.')}")
    else:
        await msg.reply_text(sc("usage: /goodbye on|off"))


@group_only
@admin_required
async def cmd_setgoodbye(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """/setgoodbye <text> — Set the goodbye message template."""
    msg = update.effective_message
    chat = update.effective_chat

    raw_text: Optional[str] = None
    if msg.reply_to_message and msg.reply_to_message.text:
        raw_text = msg.reply_to_message.text
    elif context.args:
        raw_text = " ".join(context.args)

    if not raw_text:
        await msg.reply_text(
            sc("please provide the goodbye text or reply to a message.")
        )
        return

    clean_text, buttons = extract_text_and_buttons(raw_text)
    await chats_db.update_chat_setting(chat.id, "goodbye_text", clean_text)
    await chats_db.update_chat_setting(chat.id, "goodbye_buttons", buttons)

    preview = await _render_template(
        clean_text, update.effective_user, chat, context.bot
    )
    markup = build_buttons(buttons)
    await msg.reply_text(
        f"✅ {sc('goodbye message updated! preview:')}\n\n{preview}",
        parse_mode=ParseMode.HTML,
        reply_markup=markup,
        disable_web_page_preview=True,
    )


@group_only
@admin_required
async def cmd_resetgoodbye(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """/resetgoodbye — Reset the goodbye message to default."""
    chat = update.effective_chat
    await chats_db.update_chat_setting(chat.id, "goodbye_text", None)
    await chats_db.update_chat_setting(chat.id, "goodbye_buttons", [])
    await update.effective_message.reply_text(
        f"✅ {sc('goodbye message reset to default.')}"
    )


@group_only
@admin_required
async def cmd_cleanwelcome(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """/cleanwelcome on|off — Auto-delete previous welcome message."""
    msg = update.effective_message
    chat = update.effective_chat
    args = context.args or []

    if not args or args[0].lower() not in ("on", "off"):
        await msg.reply_text(sc("usage: /cleanwelcome on|off"))
        return

    enabled = args[0].lower() == "on"
    await chats_db.update_chat_setting(chat.id, "clean_welcome", enabled)
    state = sc("enabled") if enabled else sc("disabled")
    await msg.reply_text(f"{'✅' if enabled else '❌'} {sc('clean welcome')} {state}.")


@group_only
@admin_required
async def cmd_cleanservice(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """/cleanservice on|off — Auto-delete Telegram service messages."""
    msg = update.effective_message
    chat = update.effective_chat
    args = context.args or []

    if not args or args[0].lower() not in ("on", "off"):
        await msg.reply_text(sc("usage: /cleanservice on|off"))
        return

    enabled = args[0].lower() == "on"
    await chats_db.update_chat_setting(chat.id, "clean_service", enabled)
    state = sc("enabled") if enabled else sc("disabled")
    await msg.reply_text(f"{'✅' if enabled else '❌'} {sc('clean service messages')} {state}.")


# ─────────────────────────────────────────────────────────────────────────────
# Handler registration
# ─────────────────────────────────────────────────────────────────────────────

def register_handlers(app) -> None:
    """Register all welcome/goodbye handlers with the Application."""
    # Chat member tracking for welcome/goodbye
    app.add_handler(
        ChatMemberHandler(handle_chat_member, ChatMemberHandler.CHAT_MEMBER)
    )

    # Commands
    app.add_handler(CommandHandler("welcome", cmd_welcome))
    app.add_handler(CommandHandler("setwelcome", cmd_setwelcome))
    app.add_handler(CommandHandler("resetwelcome", cmd_resetwelcome))
    app.add_handler(CommandHandler("goodbye", cmd_goodbye))
    app.add_handler(CommandHandler("setgoodbye", cmd_setgoodbye))
    app.add_handler(CommandHandler("resetgoodbye", cmd_resetgoodbye))
    app.add_handler(CommandHandler("cleanwelcome", cmd_cleanwelcome))
    app.add_handler(CommandHandler("cleanservice", cmd_cleanservice))

    logger.info("Welcome module handlers registered.")
