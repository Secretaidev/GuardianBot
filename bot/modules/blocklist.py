"""
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — ʙʟᴏᴄᴋʟɪꜱᴛ ᴍᴏᴅᴜʟᴇ
Word/phrase blocklist with regex support and configurable actions.
"""
from __future__ import annotations

import html
import logging
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, CallbackQueryHandler, filters

from bot.fonts import sc
from bot.helpers.decorators import admin_required, group_only
from bot.database import blocklist_db, chats_db, warns_db
from bot.logger import log_action

logger = logging.getLogger(__name__)

VALID_MODES = ("delete", "warn", "mute", "kick", "ban")


async def _is_admin(chat_id: int, user_id: int, bot) -> bool:
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────────────────
# /blocklist  — show all triggers
# ──────────────────────────────────────────────────────────────────────────────
@group_only
async def blocklist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat

    items = await blocklist_db.get_blocklist(chat.id)
    mode  = await blocklist_db.get_blocklist_mode(chat.id)

    if not items:
        await message.reply_text(
            f"📋 {sc('no blocklist triggers set.')}\n"
            f"{sc('add one with /addblock <word>')}"
        )
        return

    mode_display = sc(mode or "delete")
    text = f"<b>🚫 {sc('blocklist')} — {html.escape(chat.title or '')}</b>\n"
    text += f"⚙️ {sc('mode')}: <b>{mode_display}</b>\n\n"
    for i, item in enumerate(items, 1):
        trigger = html.escape(item["trigger"])
        text += f"{i}. <code>{trigger}</code>\n"

    await message.reply_text(text, parse_mode=ParseMode.HTML)


# ──────────────────────────────────────────────────────────────────────────────
# /addblock  — add trigger
# ──────────────────────────────────────────────────────────────────────────────
@group_only
@admin_required
async def addblock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat

    if not context.args:
        await message.reply_text(
            f"⚠️ {sc('usage')}: /addblock &lt;word or phrase&gt;\n"
            f"{sc('wrap multi-word triggers in quotes.')}",
            parse_mode=ParseMode.HTML,
        )
        return

    trigger = " ".join(context.args).lower().strip()
    mode    = await blocklist_db.get_blocklist_mode(chat.id) or "delete"

    await blocklist_db.add_to_blocklist(chat.id, trigger, mode)
    await message.reply_text(
        f"✅ {sc('added to blocklist')}: <code>{html.escape(trigger)}</code>",
        parse_mode=ParseMode.HTML,
    )


# ──────────────────────────────────────────────────────────────────────────────
# /rmblock  — remove trigger
# ──────────────────────────────────────────────────────────────────────────────
@group_only
@admin_required
async def rmblock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat

    if not context.args:
        await message.reply_text(
            f"⚠️ {sc('usage')}: /rmblock &lt;word or phrase&gt;",
            parse_mode=ParseMode.HTML,
        )
        return

    trigger = " ".join(context.args).lower().strip()
    removed = await blocklist_db.remove_from_blocklist(chat.id, trigger)

    if removed:
        await message.reply_text(
            f"✅ {sc('removed from blocklist')}: <code>{html.escape(trigger)}</code>",
            parse_mode=ParseMode.HTML,
        )
    else:
        await message.reply_text(
            f"❓ {sc('trigger not found in blocklist')}: <code>{html.escape(trigger)}</code>",
            parse_mode=ParseMode.HTML,
        )


# ──────────────────────────────────────────────────────────────────────────────
# /blockmode  — set action
# ──────────────────────────────────────────────────────────────────────────────
@group_only
@admin_required
async def blockmode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat

    if not context.args or context.args[0].lower() not in VALID_MODES:
        modes_str = " | ".join(f"<code>{m}</code>" for m in VALID_MODES)
        current   = await blocklist_db.get_blocklist_mode(chat.id) or "delete"
        await message.reply_text(
            f"⚙️ {sc('current block mode')}: <b>{sc(current)}</b>\n\n"
            f"{sc('available modes')}: {modes_str}\n"
            f"{sc('usage')}: /blockmode &lt;mode&gt;",
            parse_mode=ParseMode.HTML,
        )
        return

    mode = context.args[0].lower()
    await blocklist_db.set_blocklist_mode(chat.id, mode)
    await message.reply_text(
        f"✅ {sc('block mode set to')}: <b>{sc(mode)}</b>",
        parse_mode=ParseMode.HTML,
    )


# ──────────────────────────────────────────────────────────────────────────────
# /clearblock  — clear all triggers (with confirm)
# ──────────────────────────────────────────────────────────────────────────────
@group_only
@admin_required
async def clearblock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(f"✅ {sc('yes, clear all')}", callback_data=f"clearblock_yes:{chat.id}"),
        InlineKeyboardButton(f"❌ {sc('cancel')}", callback_data="clearblock_no"),
    ]])
    await update.effective_message.reply_text(
        f"⚠️ {sc('clear all blocklist triggers?')}",
        reply_markup=kb,
    )


async def clearblock_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if query.data == "clearblock_no":
        await query.edit_message_text(f"❌ {sc('cancelled.')}")
        return
    chat_id = int(query.data.split(":")[1])
    await blocklist_db.clear_blocklist(chat_id)
    await query.edit_message_text(f"✅ {sc('blocklist cleared.')}")


# ──────────────────────────────────────────────────────────────────────────────
# Message watcher
# ──────────────────────────────────────────────────────────────────────────────
async def blocklist_watcher(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat
    user    = update.effective_user

    if not message or not user or not chat:
        return
    if user.is_bot:
        return
    if await _is_admin(chat.id, user.id, context.bot):
        return

    text = message.text or message.caption or ""
    if not text:
        return

    match = await blocklist_db.match_blocklist(chat.id, text)
    if not match:
        return

    trigger = match.get("trigger", "")
    mode    = match.get("mode", "delete")

    # Always delete the message first
    try:
        await message.delete()
    except Exception:
        pass

    mention = f"<a href='tg://user?id={user.id}'>{html.escape(user.full_name)}</a>"

    if mode == "delete":
        pass  # just deleted

    elif mode == "warn":
        warn_count, _ = await warns_db.add_warn(
            chat.id, user.id, f"blocklist: {trigger}", context.bot.id
        )
        settings   = await warns_db.get_warn_settings(chat.id)
        warn_limit = settings.get("limit", 3)
        warn_msg   = await message.chat.send_message(
            f"⚠️ {mention} {sc('warned for using a blocked word.')} [{warn_count}/{warn_limit}]",
            parse_mode=ParseMode.HTML,
        )
        # Auto-action if limit reached
        if warn_count >= warn_limit:
            warn_mode = settings.get("mode", "mute")
            if warn_mode == "ban":
                await context.bot.ban_chat_member(chat.id, user.id)
            elif warn_mode == "kick":
                await context.bot.ban_chat_member(chat.id, user.id)
                await context.bot.unban_chat_member(chat.id, user.id)
            elif warn_mode == "mute":
                await context.bot.restrict_chat_member(
                    chat.id, user.id, ChatPermissions(can_send_messages=False)
                )

    elif mode == "mute":
        try:
            await context.bot.restrict_chat_member(
                chat.id, user.id, ChatPermissions(can_send_messages=False)
            )
            await message.chat.send_message(
                f"🔇 {mention} {sc('muted for using a blocked word.')}",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

    elif mode == "kick":
        try:
            await context.bot.ban_chat_member(chat.id, user.id)
            await context.bot.unban_chat_member(chat.id, user.id)
            await message.chat.send_message(
                f"👢 {mention} {sc('kicked for using a blocked word.')}",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

    elif mode == "ban":
        try:
            await context.bot.ban_chat_member(chat.id, user.id)
            await message.chat.send_message(
                f"🔨 {mention} {sc('banned for using a blocked word.')}",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

    await log_action(
        context.bot, action=f"blocklist {mode}: {trigger}", chat_id=chat.id,
        chat_title=chat.title or '', target_user_id=user.id,
        target_username=user.full_name, performed_by_id=context.bot.id,
        performed_by_username="GuardianBot",
    )


# ──────────────────────────────────────────────────────────────────────────────
# HELP
# ──────────────────────────────────────────────────────────────────────────────
BLOCKLIST_HELP = (
    f"<b>🚫 {sc('blocklist commands')}</b>\n\n"
    f"<b>/blocklist</b> — {sc('show all blocked triggers')}\n"
    f"<b>/addblock</b> &lt;word&gt; — {sc('add word/phrase to blocklist')}\n"
    f"<b>/rmblock</b> &lt;word&gt; — {sc('remove trigger from blocklist')}\n"
    f"<b>/blockmode</b> &lt;mode&gt; — {sc('set action: delete | warn | mute | kick | ban')}\n"
    f"<b>/clearblock</b> — {sc('clear entire blocklist')}\n\n"
    f"📌 {sc('admins are exempt from blocklist.')}"
)


# ──────────────────────────────────────────────────────────────────────────────
# REGISTER
# ──────────────────────────────────────────────────────────────────────────────
def register_handlers(app) -> None:
    app.add_handler(CommandHandler("blocklist",  blocklist_cmd, block=False))
    app.add_handler(CommandHandler("blacklist",  blocklist_cmd, block=False))
    app.add_handler(CommandHandler("addblock",   addblock_cmd,  block=False))
    app.add_handler(CommandHandler("rmblock",    rmblock_cmd,   block=False))
    app.add_handler(CommandHandler("unblock",    rmblock_cmd,   block=False))
    app.add_handler(CommandHandler("blockmode",  blockmode_cmd, block=False))
    app.add_handler(CommandHandler("clearblock", clearblock_cmd, block=False))
    app.add_handler(CallbackQueryHandler(clearblock_cb, pattern=r"^clearblock_"))
    app.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.GROUPS & ~filters.COMMAND,
        blocklist_watcher,
        block=False,
    ))
