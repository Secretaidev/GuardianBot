"""
bot/modules/start.py
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — /start, /help, /id, /ping module.

Responsibilities
----------------
• /start  — welcome message in PM with action keyboard
• /help   — paginated module list with inline buttons
• Callback handler for module-specific help pages
• /id     — show chat ID and user ID
• /ping   — show bot latency in milliseconds
"""

from __future__ import annotations

import logging
import time

from telegram import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from bot.config import Config
from bot.fonts import sc
from bot.helpers.buttons import main_menu_keyboard, module_help_keyboard

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Module help texts (small caps, sent in response to callback queries)
# ─────────────────────────────────────────────────────────────────────────────

_MODULE_HELP: dict[str, str] = {
    "ADMIN": (
        f"🛡 <b>{sc('admin commands')}</b>\n\n"
        f"• <code>/promote</code> — {sc('promote a user to admin')}\n"
        f"• <code>/demote</code> — {sc('demote an admin to member')}\n"
        f"• <code>/title</code> — {sc('set a custom admin title')}\n"
        f"• <code>/settitle</code> — {sc('alias for /title')}\n"
        f"• <code>/adminlist</code> — {sc('list all current admins')}\n"
        f"• <code>/pin</code> — {sc('pin a message (reply to it)')}\n"
        f"• <code>/unpin</code> — {sc('unpin the pinned message')}\n"
        f"• <code>/unpinall</code> — {sc('unpin all pinned messages')}\n"
    ),
    "BANS": (
        f"🚫 <b>{sc('ban commands')}</b>\n\n"
        f"• <code>/ban</code> — {sc('ban a user from the group')}\n"
        f"• <code>/unban</code> — {sc('unban a previously banned user')}\n"
        f"• <code>/kick</code> — {sc('kick a user (they can rejoin)')}\n"
        f"• <code>/kickme</code> — {sc('kick yourself from the group')}\n"
        f"• <code>/tempban</code> — {sc('temporarily ban a user (e.g. 2h, 1d)')}\n"
        f"• <code>/sban</code> — {sc('silent ban — deletes the command too')}\n"
    ),
    "MUTES": (
        f"🔇 <b>{sc('mute commands')}</b>\n\n"
        f"• <code>/mute</code> — {sc('mute a user (remove send-message right)')}\n"
        f"• <code>/unmute</code> — {sc('restore a muted user')}\n"
        f"• <code>/tmute</code> — {sc('temporarily mute a user (e.g. 30m, 6h)')}\n"
        f"• <code>/smute</code> — {sc('silent mute — deletes the command too')}\n"
    ),
    "WARNS": (
        f"⚠️ <b>{sc('warn commands')}</b>\n\n"
        f"• <code>/warn</code> — {sc('issue a warning to a user')}\n"
        f"• <code>/dwarn</code> — {sc('warn and delete the replied message')}\n"
        f"• <code>/unwarn</code> — {sc('remove the last warning from a user')}\n"
        f"• <code>/resetwarns</code> — {sc('clear all warnings for a user')}\n"
        f"• <code>/warns</code> — {sc('view warnings for a user')}\n"
        f"• <code>/warnlimit</code> — {sc('set warn limit (default 3)')}\n"
        f"• <code>/warnmode</code> — {sc('set action on limit: ban/kick/mute')}\n"
    ),
    "WELCOME": (
        f"👋 <b>{sc('welcome commands')}</b>\n\n"
        f"• <code>/setwelcome</code> — {sc('set a custom welcome message')}\n"
        f"• <code>/resetwelcome</code> — {sc('restore the default welcome')}\n"
        f"• <code>/welcome on|off</code> — {sc('toggle the welcome message')}\n"
        f"• <code>/setgoodbye</code> — {sc('set a goodbye message')}\n"
        f"• <code>/goodbye on|off</code> — {sc('toggle goodbye messages')}\n"
        f"• <code>/cleanwelcome on|off</code> — {sc('auto-delete old welcome messages')}\n\n"
        f"{sc('welcome messages support')}: {{first}}, {{last}}, {{fullname}}, {{username}}, {{mention}}, {{id}}, {{chatname}}\n"
        f"{sc('and button syntax')}: [ʟᴀʙᴇʟ](url)\n"
    ),
    "FILTERS": (
        f"🔍 <b>{sc('filter commands')}</b>\n\n"
        f"• <code>/filter keyword reply</code> — {sc('add a text filter')}\n"
        f"• <code>/stop keyword</code> — {sc('remove a filter')}\n"
        f"• <code>/filters</code> — {sc('list all active filters')}\n\n"
        f"{sc('filters support button syntax')}: [ʟᴀʙᴇʟ](url)\n"
    ),
    "NOTES": (
        f"📝 <b>{sc('notes commands')}</b>\n\n"
        f"• <code>/save name content</code> — {sc('save a note')}\n"
        f"• <code>#notename</code> — {sc('retrieve a saved note')}\n"
        f"• <code>/get name</code> — {sc('retrieve a saved note')}\n"
        f"• <code>/clear name</code> — {sc('delete a note')}\n"
        f"• <code>/notes</code> — {sc('list all notes in this chat')}\n"
        f"• <code>/clearall</code> — {sc('delete ALL notes (admin only)')}\n"
    ),
    "LOCKS": (
        f"🔒 <b>{sc('lock commands')}</b>\n\n"
        f"• <code>/lock type</code> — {sc('lock a message type')}\n"
        f"• <code>/unlock type</code> — {sc('unlock a message type')}\n"
        f"• <code>/locks</code> — {sc('show current lock status')}\n\n"
        f"{sc('lockable types')}: text, media, sticker, gif, url, bot, forward, game, poll, photo, video, voice, audio, document, contact, location\n"
    ),
    "BLOCKLIST": (
        f"🚷 <b>{sc('blocklist commands')}</b>\n\n"
        f"• <code>/addblocklist word</code> — {sc('add a word to the blocklist')}\n"
        f"• <code>/rmblocklist word</code> — {sc('remove a word')}\n"
        f"• <code>/blocklist</code> — {sc('view all blocked words')}\n"
        f"• <code>/setblocklistmode action</code> — {sc('action: delete/warn/ban/kick/mute')}\n"
    ),
    "ANTIFLOOD": (
        f"🌊 <b>{sc('antiflood commands')}</b>\n\n"
        f"• <code>/setflood n</code> — {sc('set flood limit (0 = disabled)')}\n"
        f"• <code>/setfloodmode action</code> — {sc('action: ban/kick/mute/tban/tmute')}\n"
        f"• <code>/flood</code> — {sc('show current antiflood settings')}\n"
    ),
    "REPORTS": (
        f"📣 <b>{sc('report commands')}</b>\n\n"
        f"• <code>@admin</code> — {sc('report a message to admins (reply to it)')}\n"
        f"• <code>/reports on|off</code> — {sc('toggle report notifications for yourself (admins)')}\n"
    ),
    "PINS": (
        f"📌 <b>{sc('pin commands')}</b>\n\n"
        f"• <code>/pin</code> — {sc('pin the replied message')}\n"
        f"• <code>/pin loud</code> — {sc('pin and notify all members')}\n"
        f"• <code>/unpin</code> — {sc('unpin the current pinned message')}\n"
        f"• <code>/unpinall</code> — {sc('remove ALL pinned messages')}\n"
        f"• <code>/pinned</code> — {sc('show the current pinned message')}\n"
    ),
    "PURGE": (
        f"🗑 <b>{sc('purge commands')}</b>\n\n"
        f"• <code>/purge</code> — {sc('delete messages from reply up to this message')}\n"
        f"• <code>/purge n</code> — {sc('delete the last n messages')}\n"
        f"• <code>/del</code> — {sc('delete the replied message')}\n"
    ),
    "RULES": (
        f"📋 <b>{sc('rules commands')}</b>\n\n"
        f"• <code>/setrules text</code> — {sc('set group rules')}\n"
        f"• <code>/rules</code> — {sc('show group rules')}\n"
        f"• <code>/clearrules</code> — {sc('delete the group rules')}\n"
        f"• <code>/privaterules on|off</code> — {sc('send rules via PM instead of in group')}\n"
    ),
    "FEDERATION": (
        f"🌐 <b>{sc('federation commands')}</b>\n\n"
        f"• <code>/newfed name</code> — {sc('create a new federation')}\n"
        f"• <code>/joinfed fed_id</code> — {sc('join a federation (group admin)')}\n"
        f"• <code>/leavefed</code> — {sc('leave the current federation')}\n"
        f"• <code>/fban user reason</code> — {sc('federation-ban a user')}\n"
        f"• <code>/unfban user</code> — {sc('remove a federation ban')}\n"
        f"• <code>/fedinfo fed_id</code> — {sc('show federation info')}\n"
        f"• <code>/fedadmins</code> — {sc('list federation admins')}\n"
        f"• <code>/addfedadmin user</code> — {sc('add a federation admin')}\n"
        f"• <code>/rmfedadmin user</code> — {sc('remove a federation admin')}\n"
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# /start handler
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Send the GuardianBot welcome message.

    In a private chat a full welcome card with an action keyboard is sent.
    In a group chat a brief acknowledgement with a "ᴘᴍ ᴍᴇ" button is sent.
    """
    user = update.effective_user
    chat = update.effective_chat
    if user is None or chat is None:
        return

    bot_username = Config.BOT_USERNAME

    if chat.type == "private":
        text = (
            f"👋 {sc('hello')} <b>{user.first_name}</b>!\n\n"
            f"🤖 {sc('i am')} <b>ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ</b> — {sc('your all-in-one telegram group management assistant.')}\n\n"
            f"🛡 {sc('i can help you manage your groups with advanced moderation tools including bans, mutes, warns, filters, notes, welcome messages, anti-flood, federation bans, and much more.')}\n\n"
            f"📖 {sc('press')} <b>{sc('help')}</b> {sc('to explore all available commands.')}"
        )

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=f"📊 {sc('stats')}",
                        callback_data="start:stats",
                    ),
                    InlineKeyboardButton(
                        text=f"❓ {sc('help')}",
                        callback_data="help:main",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=f"➕ {sc('add to group')}",
                        url=f"https://t.me/{bot_username}?startgroup=start",
                    ),
                    InlineKeyboardButton(
                        text=f"📢 {sc('support')}",
                        url="https://t.me/GuardianBotSupport",
                    ),
                ],
            ]
        )

        await update.effective_message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )

    else:
        # Group chat — keep it brief, avoid spam
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=f"📖 {sc('help')}",
                        url=f"https://t.me/{bot_username}?start=help",
                    )
                ]
            ]
        )
        await update.effective_message.reply_text(
            f"👋 {sc('hey')} <b>{user.first_name}</b>! {sc('pm me for help with all my commands.')}",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )


# ─────────────────────────────────────────────────────────────────────────────
# /help handler
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show the paginated module list.

    In a group chat a button is sent directing the user to PM.
    In a private chat the full help menu is shown.
    """
    chat = update.effective_chat
    if chat is None:
        return

    if chat.type != "private":
        bot_username = Config.BOT_USERNAME
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=f"📖 {sc('open help in pm')}",
                        url=f"https://t.me/{bot_username}?start=help",
                    )
                ]
            ]
        )
        await update.effective_message.reply_text(
            f"📖 {sc('click below to view all my commands in pm.')}",
            reply_markup=keyboard,
        )
        return

    await _send_help_main(update)


async def _send_help_main(update: Update) -> None:
    """Send (or edit) the main help menu."""
    text = (
        f"<b>🤖 ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — {sc('help menu')}</b>\n\n"
        f"{sc('select a module below to view its commands')}:"
    )
    keyboard = main_menu_keyboard()

    msg = update.effective_message
    if msg is None:
        return

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
    else:
        await msg.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Callback query handler — help pages
# ─────────────────────────────────────────────────────────────────────────────

async def callback_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle ``help:*`` and ``start:*`` callback queries.

    Routing:
      help:main         → show the module list (main help menu)
      help:MODULE_NAME  → show per-module help text
      start:stats       → show brief bot stats
    """
    query: CallbackQuery = update.callback_query
    await query.answer()  # Stop the loading spinner on the client

    data: str = query.data or ""

    # ── Main help menu ──────────────────────────────────────────────────────
    if data == "help:main":
        await _send_help_main(update)
        return

    # ── Per-module help ─────────────────────────────────────────────────────
    if data.startswith("help:"):
        module_name = data[len("help:"):]
        help_text = _MODULE_HELP.get(module_name)

        if help_text is None:
            await query.edit_message_text(
                f"❌ {sc('no help found for module')} <code>{module_name}</code>.",
                parse_mode=ParseMode.HTML,
            )
            return

        keyboard = module_help_keyboard(module_name)
        await query.edit_message_text(
            help_text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
        return

    # ── Stats shortcut from /start keyboard ────────────────────────────────
    if data == "start:stats":
        from bot.database.users_db import get_user_count
        from bot.database.chats_db import get_chat_count

        try:
            user_count = await get_user_count()
            chat_count = await get_chat_count()
        except Exception:
            user_count = chat_count = 0

        text = (
            f"<b>📊 {sc('guardian bot stats')}</b>\n\n"
            f"👤 {sc('users')}: <code>{user_count}</code>\n"
            f"💬 {sc('groups')}: <code>{chat_count}</code>\n"
        )
        back_keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(text=f"🔙 {sc('back')}", callback_data="start:main")]]
        )
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=back_keyboard,
        )
        return

    # ── Back to /start main screen ──────────────────────────────────────────
    if data == "start:main":
        user = update.effective_user
        bot_username = Config.BOT_USERNAME
        text = (
            f"👋 {sc('hello')} <b>{user.first_name}</b>!\n\n"
            f"🤖 {sc('i am')} <b>ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ</b> — {sc('your all-in-one telegram group management assistant.')}\n\n"
            f"📖 {sc('press')} <b>{sc('help')}</b> {sc('to explore all available commands.')}"
        )
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(text=f"📊 {sc('stats')}", callback_data="start:stats"),
                    InlineKeyboardButton(text=f"❓ {sc('help')}", callback_data="help:main"),
                ],
                [
                    InlineKeyboardButton(
                        text=f"➕ {sc('add to group')}",
                        url=f"https://t.me/{bot_username}?startgroup=start",
                    ),
                    InlineKeyboardButton(
                        text=f"📢 {sc('support')}",
                        url="https://t.me/GuardianBotSupport",
                    ),
                ],
            ]
        )
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
        return

    # Unknown callback — silently ignore
    logger.debug("callback_help: unhandled data=%r", data)


# ─────────────────────────────────────────────────────────────────────────────
# /id handler
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show user and chat IDs.

    • In private: shows the sender's user ID.
    • In a group: shows the group chat ID, the sender's user ID, and if the
      command is a reply, the replied-to user's ID.
    """
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if msg is None or user is None or chat is None:
        return

    lines: list[str] = []

    if chat.type == "private":
        lines.append(f"👤 {sc('your user id')}: <code>{user.id}</code>")
    else:
        lines.append(f"💬 {sc('chat id')}: <code>{chat.id}</code>")
        lines.append(f"👤 {sc('your user id')}: <code>{user.id}</code>")

        if msg.reply_to_message and msg.reply_to_message.from_user:
            target = msg.reply_to_message.from_user
            name = target.full_name
            lines.append(
                f"🔎 {sc('replied user')}: <b>{name}</b> — <code>{target.id}</code>"
            )

    await msg.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
    )


# ─────────────────────────────────────────────────────────────────────────────
# /ping handler
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Measure and display the round-trip latency between the bot and Telegram.

    Sends a placeholder message, measures how long the API call took, then
    edits the message with the measured ping time.
    """
    msg = update.effective_message
    if msg is None:
        return

    start = time.perf_counter()
    sent = await msg.reply_text(f"🏓 {sc('pinging')}...")
    elapsed_ms = (time.perf_counter() - start) * 1000

    await sent.edit_text(
        f"🏓 {sc('pong')}!\n"
        f"⚡ {sc('latency')}: <code>{elapsed_ms:.2f} ms</code>",
        parse_mode=ParseMode.HTML,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Handler registration
# ─────────────────────────────────────────────────────────────────────────────

def register_handlers(app: Application) -> None:
    """
    Register all handlers defined in this module with the PTB Application.

    Call this once during bot initialisation.

    Args:
        app: The :class:`telegram.ext.Application` instance.
    """
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("ping", cmd_ping))

    # Handle all help:* and start:* callback queries
    app.add_handler(
        CallbackQueryHandler(
            callback_help,
            pattern=r"^(help:|start:)",
        )
    )

    logger.info("start.py handlers registered.")
