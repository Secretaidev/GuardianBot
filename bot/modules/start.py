"""
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — /start, /help, /id, /ping
3-level interactive help: Main → Module (sub-buttons) → Command detail
Crafted by 𝐒𝐄𝐂𝐑𝐄𝐓
"""
from __future__ import annotations

import html
import logging
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes,
)

from bot.config import BOT_USERNAME, BOT_NAME, OWNER_ID
from bot.fonts import sc
from bot.helpers.buttons import (
    main_menu_keyboard, module_help_keyboard, command_detail_keyboard,
    get_command_detail, get_module_header, MODULES,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# /start
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    if chat.type == "private":
        # check deep-link: /start help
        if context.args and context.args[0] == "help":
            return await _send_help_main(update)

        text = (
            f"👋 {sc('hello')} <b>{html.escape(user.first_name)}</b>!\n\n"
            f"🛡️ {sc('i am')} <b>ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ</b> — {sc('the most powerful telegram group management bot.')}\n\n"
            f"⚡ {sc('features')}: {sc('bans, mutes, warns, filters, notes, welcome, locks, blocklist, anti-flood, federation, rules, reports, and more.')}\n\n"
            f"📖 {sc('tap')} <b>❓ {sc('help')}</b> {sc('to explore all commands.')}\n\n"
            f"🔥 {sc('crafted by')} <b>𝐒𝐄𝐂𝐑𝐄𝐓</b>"
        )
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"📊 {sc('stats')}", callback_data="start:stats"),
                InlineKeyboardButton(f"❓ {sc('help')}", callback_data="help:main"),
            ],
            [
                InlineKeyboardButton(f"➕ {sc('add to group')}", url=f"https://t.me/{BOT_USERNAME}?startgroup=start"),
                InlineKeyboardButton(f"👑 {sc('owner')}", url="https://t.me/RoseManagementBot"),
            ],
        ])
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

    else:
        # group — brief msg with PM button
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(f"📖 {sc('help')}", url=f"https://t.me/{BOT_USERNAME}?start=help"),
        ]])
        await update.effective_message.reply_text(
            f"👋 {sc('hey')} <b>{html.escape(user.first_name)}</b>! {sc('pm me for help.')}",
            parse_mode=ParseMode.HTML, reply_markup=kb,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# /help
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not chat:
        return
    if chat.type != "private":
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(f"📖 {sc('open help in pm')}", url=f"https://t.me/{BOT_USERNAME}?start=help"),
        ]])
        await update.effective_message.reply_text(
            f"📖 {sc('click below to view all commands in pm.')}",
            reply_markup=kb,
        )
        return
    await _send_help_main(update)


async def _send_help_main(update: Update) -> None:
    text = (
        f"<b>🛡️ ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — {sc('help menu')}</b>\n\n"
        f"{sc('tap any module to see its commands')} 👇"
    )
    kb = main_menu_keyboard()
    msg = update.effective_message
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await msg.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


# ═══════════════════════════════════════════════════════════════════════════════
# CALLBACK ROUTER — handles all 3 levels
# ═══════════════════════════════════════════════════════════════════════════════

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Single router for all help/start/cmd callbacks."""
    query = update.callback_query
    await query.answer()
    data = query.data or ""

    # ── LEVEL 1: help:main → show all modules ────────────────────────────────
    if data == "help:main":
        await _send_help_main(update)
        return

    # ── LEVEL 2: help:MODULE → show module commands as sub-buttons ────────────
    if data.startswith("help:") and not data.startswith("help:close"):
        mod_key = data[5:]  # e.g. "BANS"
        if mod_key in MODULES:
            header = get_module_header(mod_key)
            kb = module_help_keyboard(mod_key)
            await query.edit_message_text(header, parse_mode=ParseMode.HTML, reply_markup=kb)
            return

    # ── LEVEL 3: cmd:MODULE:command → show command detail ────────────────────
    if data.startswith("cmd:"):
        parts = data.split(":", 2)  # cmd:BANS:ban
        if len(parts) == 3:
            mod_key, cmd = parts[1], parts[2]
            detail = get_command_detail(mod_key, cmd)
            if detail:
                mod = MODULES.get(mod_key, {})
                emoji = mod.get("emoji", "📌")
                text = (
                    f"{emoji} <b>/{cmd}</b>\n\n"
                    f"{detail}"
                )
                kb = command_detail_keyboard(mod_key)
                await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
                return

    # ── start:stats → quick stats card ───────────────────────────────────────
    if data == "start:stats":
        from bot.database.users_db import get_user_count
        from bot.database.chats_db import get_chat_count
        try:
            uc = await get_user_count()
            cc = await get_chat_count()
        except Exception:
            uc = cc = 0

        try:
            from bot.helpers.autodelete import get_server_stats
            s = get_server_stats()
            extra = (
                f"⏱️ {sc('uptime')}: <code>{s.get('uptime', '?')}</code>\n"
                f"💾 {sc('memory')}: <code>{s.get('mem_rss_mb', '?')} MB</code>\n"
                f"🐍 {sc('python')}: <code>{s.get('python', '?')}</code>\n"
            )
        except Exception:
            extra = ""

        text = (
            f"<b>📊 {sc('bot stats')}</b>\n\n"
            f"👤 {sc('users')}: <code>{uc}</code>\n"
            f"💬 {sc('groups')}: <code>{cc}</code>\n"
            f"{extra}\n"
            f"🔥 {sc('crafted by')} <b>𝐒𝐄𝐂𝐑𝐄𝐓</b>"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(f"🔙 {sc('back')}", callback_data="start:main"),
        ]])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    # ── start:main → back to /start screen ───────────────────────────────────
    if data == "start:main":
        user = update.effective_user
        text = (
            f"👋 {sc('hello')} <b>{html.escape(user.first_name)}</b>!\n\n"
            f"🛡️ {sc('i am')} <b>ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ</b> — {sc('the most powerful telegram group management bot.')}\n\n"
            f"📖 {sc('tap')} <b>❓ {sc('help')}</b> {sc('to explore all commands.')}\n\n"
            f"🔥 {sc('crafted by')} <b>𝐒𝐄𝐂𝐑𝐄𝐓</b>"
        )
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"📊 {sc('stats')}", callback_data="start:stats"),
                InlineKeyboardButton(f"❓ {sc('help')}", callback_data="help:main"),
            ],
            [
                InlineKeyboardButton(f"➕ {sc('add to group')}", url=f"https://t.me/{BOT_USERNAME}?startgroup=start"),
                InlineKeyboardButton(f"👑 {sc('owner')}", url="https://t.me/RoseManagementBot"),
            ],
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    # ── help:close → delete the help message ─────────────────────────────────
    if data == "help:close":
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    # ── no-op for page indicator buttons ─────────────────────────────────────
    if data == ".":
        return


# ═══════════════════════════════════════════════════════════════════════════════
# /id
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if not msg or not user or not chat:
        return

    lines = []
    if chat.type == "private":
        lines.append(f"👤 {sc('your id')}: <code>{user.id}</code>")
    else:
        lines.append(f"💬 {sc('chat id')}: <code>{chat.id}</code>")
        lines.append(f"👤 {sc('your id')}: <code>{user.id}</code>")
        if msg.reply_to_message and msg.reply_to_message.from_user:
            t = msg.reply_to_message.from_user
            lines.append(f"🔎 {sc('replied user')}: <b>{html.escape(t.full_name)}</b> — <code>{t.id}</code>")

    await msg.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


# ═══════════════════════════════════════════════════════════════════════════════
# /ping
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg:
        return
    t0 = time.perf_counter()
    sent = await msg.reply_text(f"🏓 {sc('pinging')}...")
    ms = (time.perf_counter() - t0) * 1000
    await sent.edit_text(
        f"🏓 {sc('pong')}!\n⚡ {sc('latency')}: <code>{ms:.1f} ms</code>",
        parse_mode=ParseMode.HTML,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# /about
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        f"<b>🛡️ ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ</b>\n\n"
        f"👑 {sc('owner')}: <b>𝐒𝐄𝐂𝐑𝐄𝐓</b> (@its_me_secret)\n"
        f"🐍 {sc('language')}: Python 3.11+\n"
        f"📦 {sc('framework')}: python-telegram-bot\n"
        f"🗄️ {sc('database')}: MongoDB\n"
        f"🔗 {sc('source')}: <a href='https://github.com/Secretaidev/GuardianBot'>GitHub</a>\n"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


# ═══════════════════════════════════════════════════════════════════════════════
# Handler registration
# ═══════════════════════════════════════════════════════════════════════════════

def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("about", cmd_about))

    # single router for ALL callback patterns
    app.add_handler(CallbackQueryHandler(
        callback_router,
        pattern=r"^(help:|start:|cmd:|\.)",
    ))

    logger.info("start.py handlers registered.")
