"""
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — ʀᴜʟᴇꜱ ᴍᴏᴅᴜʟᴇ
Group rules management with private/public display toggle.
"""
from __future__ import annotations

import html
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes, CallbackQueryHandler

from bot.fonts import sc
from bot.helpers.decorators import admin_required, group_only
from bot.database import chats_db

logger = logging.getLogger(__name__)


def _format_rules(rules_text: str, chat_title: str) -> str:
    return (
        f"📜 <b>{sc('rules')} — {html.escape(chat_title)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{rules_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>{sc('please follow the rules to keep the community clean.')}</i>"
    )


# ──────────────────────────────────────────────────────────────────────────────
# /rules
# ──────────────────────────────────────────────────────────────────────────────
@group_only
async def rules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat
    user    = update.effective_user

    chat_data    = await chats_db.get_chat(chat.id)
    rules_text   = chat_data.get("rules")
    private_mode = chat_data.get("private_rules", False)

    if not rules_text:
        await message.reply_text(
            f"📜 {sc('no rules have been set for this group.')}\n"
            f"{sc('admins can set rules with /setrules <text>')}"
        )
        return

    formatted = _format_rules(rules_text, chat.title or "")

    if private_mode:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                f"📜 {sc('view rules')}",
                url=f"https://t.me/{context.bot.username}?start=rules_{chat.id}"
            )
        ]])
        await message.reply_text(
            f"📬 {sc('rules have been sent to your private messages!')}",
            reply_markup=keyboard,
        )
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text=formatted,
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            await message.reply_text(
                f"⚠️ {sc('could not send rules in pm. please start the bot first.')}",
            )
    else:
        await message.reply_text(formatted, parse_mode=ParseMode.HTML)


# ──────────────────────────────────────────────────────────────────────────────
# /setrules
# ──────────────────────────────────────────────────────────────────────────────
@group_only
@admin_required
async def setrules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat

    # Support reply-to-message as rules text
    if message.reply_to_message and message.reply_to_message.text:
        rules_text = message.reply_to_message.text
    elif context.args:
        rules_text = " ".join(context.args)
    else:
        await message.reply_text(
            f"⚠️ {sc('usage')}: /setrules &lt;rules text&gt;\n"
            f"{sc('or reply to a message containing the rules.')}",
            parse_mode=ParseMode.HTML,
        )
        return

    await chats_db.update_chat_setting(chat.id, "rules", rules_text)
    await message.reply_text(
        f"✅ {sc('rules updated successfully!')}\n"
        f"{sc('use /rules to view them.')}",
    )


# ──────────────────────────────────────────────────────────────────────────────
# /clearrules
# ──────────────────────────────────────────────────────────────────────────────
@group_only
@admin_required
async def clearrules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(f"✅ {sc('yes, clear')}", callback_data=f"clearrules_yes:{chat.id}"),
        InlineKeyboardButton(f"❌ {sc('cancel')}", callback_data="clearrules_no"),
    ]])
    await update.effective_message.reply_text(
        f"⚠️ {sc('are you sure you want to clear all rules?')}",
        reply_markup=kb,
    )


async def clearrules_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if query.data == "clearrules_no":
        await query.edit_message_text(f"❌ {sc('cancelled.')}")
        return
    chat_id = int(query.data.split(":")[1])
    await chats_db.update_chat_setting(chat_id, "rules", None)
    await query.edit_message_text(f"✅ {sc('rules cleared.')}")


# ──────────────────────────────────────────────────────────────────────────────
# /privaterules on/off
# ──────────────────────────────────────────────────────────────────────────────
@group_only
@admin_required
async def privaterules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat

    if not context.args:
        chat_data = await chats_db.get_chat(chat.id)
        status    = sc("on") if chat_data.get("private_rules") else sc("off")
        await message.reply_text(
            f"📬 {sc('private rules')}: <b>{status}</b>\n"
            f"{sc('toggle with /privaterules on or off')}",
            parse_mode=ParseMode.HTML,
        )
        return

    setting = context.args[0].lower()
    if setting == "on":
        await chats_db.update_chat_setting(chat.id, "private_rules", True)
        await message.reply_text(
            f"✅ {sc('private rules enabled.')} "
            f"{sc('rules will be sent in pm when users run /rules.')}"
        )
    elif setting == "off":
        await chats_db.update_chat_setting(chat.id, "private_rules", False)
        await message.reply_text(f"✅ {sc('private rules disabled. rules will show in group.')}")
    else:
        await message.reply_text(f"⚠️ {sc('use /privaterules on or off.')}")


# ──────────────────────────────────────────────────────────────────────────────
# Start handler for rules in PM
# ──────────────────────────────────────────────────────────────────────────────
async def rules_start_pm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start rules_<chat_id> in PM."""
    args = context.args
    if not args or not args[0].startswith("rules_"):
        return
    try:
        chat_id = int(args[0].replace("rules_", ""))
    except ValueError:
        return

    chat_data  = await chats_db.get_chat(chat_id)
    rules_text = chat_data.get("rules")
    if not rules_text:
        await update.effective_message.reply_text(f"📜 {sc('no rules set for that group.')}")
        return

    try:
        chat_obj = await context.bot.get_chat(chat_id)
        title    = chat_obj.title or str(chat_id)
    except Exception:
        title = str(chat_id)

    await update.effective_message.reply_text(
        _format_rules(rules_text, title),
        parse_mode=ParseMode.HTML,
    )


# ──────────────────────────────────────────────────────────────────────────────
# HELP
# ──────────────────────────────────────────────────────────────────────────────
RULES_HELP = (
    f"<b>📜 {sc('rules commands')}</b>\n\n"
    f"<b>/rules</b> — {sc('show group rules')}\n"
    f"<b>/setrules</b> &lt;text&gt; — {sc('set group rules (or reply to message)')}\n"
    f"<b>/clearrules</b> — {sc('clear rules')}\n"
    f"<b>/privaterules on/off</b> — {sc('send rules in pm instead of group')}\n"
)


# ──────────────────────────────────────────────────────────────────────────────
# REGISTER
# ──────────────────────────────────────────────────────────────────────────────
def register_handlers(app) -> None:
    app.add_handler(CommandHandler("rules",        rules_cmd,       block=False))
    app.add_handler(CommandHandler("setrules",     setrules_cmd,    block=False))
    app.add_handler(CommandHandler("clearrules",   clearrules_cmd,  block=False))
    app.add_handler(CommandHandler("privaterules", privaterules_cmd, block=False))
    app.add_handler(CallbackQueryHandler(clearrules_cb, pattern=r"^clearrules_"))
