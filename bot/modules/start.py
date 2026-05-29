"""
Rose — /start, /help, /id, /ping, /about, /setcommands
Clean Rose-style 3-level help navigation.
Crafted by 𝐒𝐄𝐂𝐑𝐄𝐓
"""
from __future__ import annotations

import html
import logging
import time
import sys

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, BotCommand
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes,
)

from bot.config import BOT_USERNAME, BOT_NAME, OWNER_ID
from bot.helpers.buttons import (
    main_menu_keyboard, module_help_keyboard, command_detail_keyboard,
    get_command_detail, get_module_header, MODULES,
)

logger = logging.getLogger(__name__)

SUPPORT_GROUP = "SecretzBotz"


def _uname(context) -> str:
    if context and context.bot and context.bot.username:
        return context.bot.username
    return BOT_USERNAME or "RoseManagementBot"


# ═══════════════════════════════════════════════════════════════════════════════
# /start
# ═══════════════════════════════════════════════════════════════════════════════

PM_START_TEXT = (
    "Hey there! My name is <b>Rose</b>.\n\n"
    "I'm a <b>group management bot</b> that helps you manage and protect "
    "your Telegram groups with powerful tools.\n\n"
    "Hit <b>Help</b> to find out more about how to use me to my full potential.\n\n"
    "<b>Crafted by</b> 𝐒𝐄𝐂𝐑𝐄𝐓"
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    if chat.type == "private":
        if context.args and context.args[0] == "help":
            return await _send_help_main(update, context)

        uname = _uname(context)
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Help", callback_data="help:main"),
                InlineKeyboardButton("Support", url=f"https://t.me/{SUPPORT_GROUP}"),
            ],
            [
                InlineKeyboardButton("Add to Group", url=f"https://t.me/{uname}?startgroup=start"),
            ],
        ])
        await update.effective_message.reply_text(
            PM_START_TEXT, parse_mode=ParseMode.HTML, reply_markup=kb,
        )
    else:
        uname = _uname(context)
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("Help", url=f"https://t.me/{uname}?start=help"),
        ]])
        await update.effective_message.reply_text(
            f"Hey <b>{html.escape(user.first_name)}</b>! PM me for help.",
            parse_mode=ParseMode.HTML, reply_markup=kb,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# /help
# ═══════════════════════════════════════════════════════════════════════════════

HELP_HEADER = (
    "<b>Hey there! My name is Rose.</b>\n\n"
    "I have a bunch of useful features, such as flood control, a warning system, "
    "a note keeping system, and even predetermined replies on certain keywords.\n\n"
    "<b>Main commands:</b>\n"
    " • /help — this message\n"
    " • /start — check if I'm alive\n"
    " • /id — get user/chat ID\n"
    " • /ping — check latency\n\n"
    "<i>All commands can be used with / or !</i>\n\n"
    "<b>Tap any button below to learn more about each module.</b>"
)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not chat:
        return
    if chat.type != "private":
        uname = _uname(context)
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("Open help in PM", url=f"https://t.me/{uname}?start=help"),
        ]])
        await update.effective_message.reply_text(
            "Tap the button below to get help in PM.",
            reply_markup=kb,
        )
        return
    await _send_help_main(update, context)


async def _send_help_main(update: Update, context=None):
    await update.effective_message.reply_text(
        HELP_HEADER,
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_keyboard(),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Callback query router
# ═══════════════════════════════════════════════════════════════════════════════

async def _callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    data = query.data

    # ── help:close → delete the message ───────────────────────────────────
    if data == "help:close":
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    # ── start:stats → quick stats ─────────────────────────────────────────
    if data == "start:stats":
        from bot.database.users_db import get_user_count
        from bot.database.chats_db import get_chat_count
        try:
            uc = await get_user_count()
            cc = await get_chat_count()
        except Exception:
            uc = cc = 0

        try:
            import os
            from datetime import datetime, timezone
            _start = getattr(sys.modules[__name__], '_BOT_START', None)
            if not _start:
                _start = datetime.now(timezone.utc)
                sys.modules[__name__]._BOT_START = _start
            delta = datetime.now(timezone.utc) - _start
            hours, rem = divmod(int(delta.total_seconds()), 3600)
            mins, secs = divmod(rem, 60)
            uptime_str = f"{hours}h {mins}m {secs}s"
            try:
                import psutil
                proc = psutil.Process(os.getpid())
                mem_mb = f"{proc.memory_info().rss / 1024 / 1024:.1f}"
            except Exception:
                mem_mb = "?"
            extra = (
                f"⏱ Uptime: <code>{uptime_str}</code>\n"
                f"💾 Memory: <code>{mem_mb} MB</code>\n"
                f"🐍 Python: <code>{sys.version.split()[0]}</code>\n"
            )
        except Exception:
            extra = ""

        text = (
            f"<b>📊 Bot Stats</b>\n\n"
            f"👤 Users: <code>{uc}</code>\n"
            f"💬 Groups: <code>{cc}</code>\n"
            f"{extra}\n"
            f"<b>Crafted by</b> 𝐒𝐄𝐂𝐑𝐄𝐓"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("« Back", callback_data="start:main"),
        ]])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    # ── start:main → back to /start screen ────────────────────────────────
    if data == "start:main":
        uname = _uname(context)
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Help", callback_data="help:main"),
                InlineKeyboardButton("Support", url=f"https://t.me/{SUPPORT_GROUP}"),
            ],
            [
                InlineKeyboardButton("Add to Group", url=f"https://t.me/{uname}?startgroup=start"),
            ],
        ])
        await query.edit_message_text(
            PM_START_TEXT, parse_mode=ParseMode.HTML, reply_markup=kb,
        )
        return

    # ── help:main → main help page ────────────────────────────────────────
    if data == "help:main":
        await query.edit_message_text(
            HELP_HEADER, parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard(),
        )
        return

    # ── help:<MOD> → module sub-menu ──────────────────────────────────────
    if data.startswith("help:"):
        mod_name = data.split(":", 1)[1].upper()
        if mod_name in MODULES:
            text = get_module_header(mod_name)
            kb = module_help_keyboard(mod_name)
            await query.edit_message_text(
                text, parse_mode=ParseMode.HTML, reply_markup=kb,
            )
        return

    # ── cmd:<MOD>:<CMD> → command detail ──────────────────────────────────
    if data.startswith("cmd:"):
        parts = data.split(":", 2)
        if len(parts) == 3:
            mod_name, cmd_name = parts[1], parts[2]
            detail = get_command_detail(mod_name, cmd_name)
            if detail:
                label = MODULES.get(mod_name, {}).get("label", mod_name)
                text = (
                    f"<b>{label} — /{cmd_name}</b>\n\n"
                    f"{html.escape(detail)}"
                )
                kb = command_detail_keyboard(mod_name)
                await query.edit_message_text(
                    text, parse_mode=ParseMode.HTML, reply_markup=kb,
                )
        return

    # ── noop ──────────────────────────────────────────────────────────────
    if data == ".":
        return


# ═══════════════════════════════════════════════════════════════════════════════
# /id
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg or not user:
        return

    if msg.reply_to_message:
        target = msg.reply_to_message.from_user
        if target:
            text = (
                f"<b>{html.escape(target.first_name)}</b>'s ID: "
                f"<code>{target.id}</code>"
            )
        else:
            text = "Could not get user info."
    else:
        text = f"Your ID: <code>{user.id}</code>"
        if chat and chat.type != "private":
            text += f"\nChat ID: <code>{chat.id}</code>"

    await msg.reply_text(text, parse_mode=ParseMode.HTML)


# ═══════════════════════════════════════════════════════════════════════════════
# /ping
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    start = time.monotonic()
    sent = await update.effective_message.reply_text("Pong!")
    ms = (time.monotonic() - start) * 1000
    await sent.edit_text(f"Pong! <code>{ms:.0f}ms</code>", parse_mode=ParseMode.HTML)


# ═══════════════════════════════════════════════════════════════════════════════
# /about
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "<b>🌹 Rose</b>\n\n"
        "🐍 Language: Python 3.11+\n"
        "📦 Framework: python-telegram-bot\n"
        "🗄 Database: MongoDB\n"
        f"👑 Owner: <b>𝐒𝐄𝐂𝐑𝐄𝐓</b> (@its_me_secret)\n"
        f"📢 Support: @{SUPPORT_GROUP}\n"
        "🤖 Bot: @RoseManagementBot\n"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


# ═══════════════════════════════════════════════════════════════════════════════
# /setcommands — register with BotFather (owner only)
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_setcommands(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or user.id != OWNER_ID:
        await update.effective_message.reply_text("❌ Owner only.")
        return

    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Get help"),
        BotCommand("id", "Get user/chat ID"),
        BotCommand("ping", "Check bot latency"),
        BotCommand("about", "About this bot"),
        BotCommand("ban", "Ban a user"),
        BotCommand("tban", "Temp ban a user"),
        BotCommand("unban", "Unban a user"),
        BotCommand("kick", "Kick a user"),
        BotCommand("mute", "Mute a user"),
        BotCommand("tmute", "Temp mute a user"),
        BotCommand("unmute", "Unmute a user"),
        BotCommand("warn", "Warn a user"),
        BotCommand("unwarn", "Remove last warning"),
        BotCommand("warns", "View user warnings"),
        BotCommand("warnlimit", "Set warn limit"),
        BotCommand("promote", "Promote to admin"),
        BotCommand("demote", "Demote an admin"),
        BotCommand("adminlist", "List all admins"),
        BotCommand("pin", "Pin a message"),
        BotCommand("unpin", "Unpin a message"),
        BotCommand("purge", "Bulk delete messages"),
        BotCommand("filter", "Set a filter"),
        BotCommand("filters", "List all filters"),
        BotCommand("save", "Save a note"),
        BotCommand("notes", "List all notes"),
        BotCommand("rules", "View group rules"),
        BotCommand("setrules", "Set group rules"),
        BotCommand("setwelcome", "Set welcome message"),
        BotCommand("welcome", "Toggle welcome"),
        BotCommand("lock", "Lock a permission"),
        BotCommand("unlock", "Unlock a permission"),
        BotCommand("locks", "View lock status"),
        BotCommand("setflood", "Set flood limit"),
        BotCommand("report", "Report to admins"),
        BotCommand("approve", "Approve a user"),
        BotCommand("approved", "List approved users"),
        BotCommand("captcha", "Toggle CAPTCHA"),
        BotCommand("antiraid", "Toggle anti-raid"),
        BotCommand("connect", "Connect from PM"),
        BotCommand("info", "User information"),
        BotCommand("stats", "Bot statistics"),
    ]

    await context.bot.set_my_commands(commands)
    await update.effective_message.reply_text(
        f"✅ Registered <b>{len(commands)}</b> commands with BotFather.",
        parse_mode=ParseMode.HTML,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Handler registration
# ═══════════════════════════════════════════════════════════════════════════════

def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("about", cmd_about))
    app.add_handler(CommandHandler("setcommands", cmd_setcommands))
    app.add_handler(CallbackQueryHandler(
        _callback_handler,
        pattern=r"^(help:|cmd:|start:)",
    ))
