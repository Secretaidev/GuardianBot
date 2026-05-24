"""
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — ᴘɪɴꜱ ᴍᴏᴅᴜʟᴇ
Message pinning: pin, unpin, unpinall, pinned.
"""
from __future__ import annotations

import html
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes, CallbackQueryHandler

from bot.fonts import sc
from bot.helpers.decorators import admin_required, bot_admin_required, group_only
from bot.logger import log_action

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# /pin
# ──────────────────────────────────────────────────────────────────────────────
@group_only
@admin_required
@bot_admin_required
async def pin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat

    if not message.reply_to_message:
        await message.reply_text(f"📌 {sc('reply to a message to pin it.')}")
        return

    silent = "silent" in (context.args or []) or "notify" not in (context.args or [])
    try:
        await context.bot.pin_chat_message(
            chat_id=chat.id,
            message_id=message.reply_to_message.message_id,
            disable_notification=silent,
        )
        await message.reply_text(f"📌 {sc('message pinned successfully!')}")
        await log_action(
            context.bot, action=sc("pinned a message"), chat_id=chat.id,
            chat_title=chat.title or '', target_user_id=update.effective_user.id,
            target_username=update.effective_user.full_name,
            performed_by_id=update.effective_user.id,
            performed_by_username=update.effective_user.full_name,
        )
    except Exception as e:
        await message.reply_text(
            f"❌ {sc('failed to pin')}: <code>{html.escape(str(e))}</code>",
            parse_mode=ParseMode.HTML,
        )


# ──────────────────────────────────────────────────────────────────────────────
# /unpin
# ──────────────────────────────────────────────────────────────────────────────
@group_only
@admin_required
@bot_admin_required
async def unpin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat

    try:
        if message.reply_to_message:
            await context.bot.unpin_chat_message(
                chat_id=chat.id,
                message_id=message.reply_to_message.message_id,
            )
        else:
            await context.bot.unpin_chat_message(chat_id=chat.id)
        await message.reply_text(f"📍 {sc('message unpinned.')}")
    except Exception as e:
        await message.reply_text(
            f"❌ {sc('failed to unpin')}: <code>{html.escape(str(e))}</code>",
            parse_mode=ParseMode.HTML,
        )


# ──────────────────────────────────────────────────────────────────────────────
# /unpinall
# ──────────────────────────────────────────────────────────────────────────────
@group_only
@admin_required
@bot_admin_required
async def unpinall_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"✅ {sc('yes, unpin all')}", callback_data=f"unpinall_confirm:{chat.id}"),
            InlineKeyboardButton(f"❌ {sc('cancel')}", callback_data="unpinall_cancel"),
        ]
    ])
    await message.reply_text(
        f"⚠️ {sc('are you sure you want to unpin ALL pinned messages?')}\n"
        f"{sc('this action cannot be undone.')}",
        reply_markup=keyboard,
    )


async def unpinall_confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user

    if not await _is_admin_in_cb(query, context):
        await query.answer(sc("you must be an admin to do this."), show_alert=True)
        return

    chat_id = int(query.data.split(":")[1])
    await query.answer(sc("unpinning all messages..."))
    try:
        await context.bot.unpin_all_chat_messages(chat_id=chat_id)
        await query.edit_message_text(f"✅ {sc('all messages unpinned successfully!')}")
        await log_action(
            context.bot, action=sc("unpinned all messages"), chat_id=chat_id,
            chat_title='', target_user_id=user.id,
            target_username=user.full_name, performed_by_id=user.id,
            performed_by_username=user.full_name,
        )
    except Exception as e:
        await query.edit_message_text(
            f"❌ {sc('failed')}: <code>{html.escape(str(e))}</code>",
            parse_mode=ParseMode.HTML,
        )


async def unpinall_cancel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer(sc("cancelled."))
    await query.edit_message_text(f"❌ {sc('unpin all cancelled.')}")


async def _is_admin_in_cb(query, context) -> bool:
    """Check if the callback query sender is an admin."""
    try:
        member = await context.bot.get_chat_member(
            query.message.chat_id, query.from_user.id
        )
        return member.status in ("administrator", "creator")
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────────────────
# /pinned
# ──────────────────────────────────────────────────────────────────────────────
@group_only
async def pinned_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat

    try:
        chat_obj = await context.bot.get_chat(chat.id)
        if chat_obj.pinned_message:
            pm = chat_obj.pinned_message
            link = f"https://t.me/c/{str(chat.id).replace('-100', '')}/{pm.message_id}"
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(f"📌 {sc('go to pinned')}", url=link)
            ]])
            await message.reply_text(
                f"📌 {sc('pinned message')}:",
                reply_markup=keyboard,
            )
        else:
            await message.reply_text(f"📍 {sc('no pinned message in this chat.')}")
    except Exception as e:
        await message.reply_text(
            f"❌ {sc('failed')}: <code>{html.escape(str(e))}</code>",
            parse_mode=ParseMode.HTML,
        )


# ──────────────────────────────────────────────────────────────────────────────
# HELP TEXT
# ──────────────────────────────────────────────────────────────────────────────
PINS_HELP = (
    f"<b>📌 {sc('pins commands')}</b>\n\n"
    f"<b>/pin</b> — {sc('reply to a message to pin it')}\n"
    f"<b>/pin silent</b> — {sc('pin without notification')}\n"
    f"<b>/unpin</b> — {sc('unpin the current/replied pinned message')}\n"
    f"<b>/unpinall</b> — {sc('unpin all messages (with confirmation)')}\n"
    f"<b>/pinned</b> — {sc('show link to current pinned message')}\n"
)


# ──────────────────────────────────────────────────────────────────────────────
# REGISTER
# ──────────────────────────────────────────────────────────────────────────────
def register_handlers(app) -> None:
    app.add_handler(CommandHandler("pin", pin_cmd, block=False))
    app.add_handler(CommandHandler("unpin", unpin_cmd, block=False))
    app.add_handler(CommandHandler("unpinall", unpinall_cmd, block=False))
    app.add_handler(CommandHandler("pinned", pinned_cmd, block=False))
    app.add_handler(CallbackQueryHandler(unpinall_confirm_cb, pattern=r"^unpinall_confirm:"))
    app.add_handler(CallbackQueryHandler(unpinall_cancel_cb, pattern=r"^unpinall_cancel$"))
