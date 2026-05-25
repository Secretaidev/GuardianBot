"""
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — ʀᴇᴘᴏʀᴛꜱ ᴍᴏᴅᴜʟᴇ
User reporting system with admin action buttons.
"""
from __future__ import annotations

import html
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, CallbackQueryHandler, filters

from bot.fonts import sc
from bot.helpers.decorators import group_only
from bot.database import chats_db
from bot.logger import log_action

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# /reports on/off
# ──────────────────────────────────────────────────────────────────────────────
@group_only
async def reports_setting_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    # Check admin
    try:
        member = await chat.get_member(user.id)
        if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
            await message.reply_text(f"❌ {sc('only admins can change report settings.')}")
            return
    except Exception:
        return

    if not context.args:
        chat_data = await chats_db.get_chat(chat.id)
        status = sc("enabled") if chat_data.get("report_setting", True) else sc("disabled")
        await message.reply_text(
            f"📊 {sc('report setting')}: <b>{status}</b>\n"
            f"{sc('use /reports on or /reports off to change.')}",
            parse_mode=ParseMode.HTML,
        )
        return

    setting = context.args[0].lower()
    if setting == "on":
        await chats_db.update_chat_setting(chat.id, "report_setting", True)
        await message.reply_text(f"✅ {sc('reports enabled. users can now use /report or @admin.')}")
    elif setting == "off":
        await chats_db.update_chat_setting(chat.id, "report_setting", False)
        await message.reply_text(f"🔕 {sc('reports disabled.')}")
    else:
        await message.reply_text(f"⚠️ {sc('use /reports on or /reports off.')}")


# ──────────────────────────────────────────────────────────────────────────────
# /report or @admin trigger
# ──────────────────────────────────────────────────────────────────────────────
@group_only
async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat
    reporter = update.effective_user

    chat_data = await chats_db.get_chat(chat.id)
    if not chat_data.get("report_setting", True):
        return

    if not message.reply_to_message:
        await message.reply_text(
            f"⚠️ {sc('reply to a message to report it to the admins.')}"
        )
        return

    reported_msg = message.reply_to_message
    reported_user = reported_msg.from_user
    if not reported_user:
        await message.reply_text(f"⚠️ {sc('cannot identify the user to report.')}")
        return

    if reported_user.id == reporter.id:
        await message.reply_text(f"🤔 {sc('you cannot report yourself.')}")
        return
    if reported_user.is_bot:
        await message.reply_text(f"🤖 {sc('you cannot report bots.')}")
        return

    # Build reason from args
    reason_text = " ".join(context.args) if context.args else sc("no reason provided")

    # Fetch admins
    try:
        admins = await chat.get_administrators()
    except Exception:
        await message.reply_text(f"❌ {sc('failed to fetch admin list.')}")
        return

    reporter_mention = f"<a href='tg://user?id={reporter.id}'>{html.escape(reporter.full_name)}</a>"
    reported_mention = f"<a href='tg://user?id={reported_user.id}'>{html.escape(reported_user.full_name)}</a>"

    msg_link = ""
    try:
        msg_link = f"https://t.me/c/{str(chat.id).replace('-100', '')}/{reported_msg.message_id}"
    except Exception:
        pass

    report_text = (
        f"🚨 <b>{sc('user report')}</b>\n\n"
        f"👤 {sc('reported by')}: {reporter_mention}\n"
        f"⚠️ {sc('reported user')}: {reported_mention} (<code>{reported_user.id}</code>)\n"
        f"💬 {sc('chat')}: <b>{html.escape(chat.title or '')}</b>\n"
        f"📝 {sc('reason')}: {html.escape(reason_text)}"
    )

    action_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"⚠️ {sc('warn')}", callback_data=f"report_warn:{chat.id}:{reported_user.id}"),
            InlineKeyboardButton(f"🔇 {sc('mute')}", callback_data=f"report_mute:{chat.id}:{reported_user.id}"),
            InlineKeyboardButton(f"🔨 {sc('ban')}", callback_data=f"report_ban:{chat.id}:{reported_user.id}"),
        ],
        [
            InlineKeyboardButton(f"🗑️ {sc('delete msg')}", callback_data=f"report_del:{chat.id}:{reported_msg.message_id}"),
            InlineKeyboardButton(f"✅ {sc('dismiss')}", callback_data="report_dismiss"),
        ],
    ])
    if msg_link:
        action_keyboard.inline_keyboard.insert(0, [
            InlineKeyboardButton(f"🔗 {sc('go to message')}", url=msg_link)
        ])

    # Notify each admin
    notified = 0
    for admin in admins:
        if admin.user.is_bot:
            continue
        try:
            await context.bot.send_message(
                chat_id=admin.user.id,
                text=report_text,
                parse_mode=ParseMode.HTML,
                reply_markup=action_keyboard,
            )
            notified += 1
        except Exception:
            pass  # Admin has bot blocked or never started it

    if notified:
        await message.reply_text(
            f"✅ {sc('report sent to')} <b>{notified}</b> {sc('admin(s).')}",
            parse_mode=ParseMode.HTML,
        )
    else:
        await message.reply_text(
            f"⚠️ {sc('could not notify any admins. admins must start the bot in pm first.')}"
        )

    await log_action(
        context.bot,
        action=sc("reported user"),
        chat_id=chat.id,
        chat_title=chat.title or '',
        target_user_id=reported_user.id,
        target_username=reported_user.full_name,
        performed_by_id=reporter.id,
        performed_by_username=reporter.full_name,
        reason=reason_text,
    )


# ──────────────────────────────────────────────────────────────────────────────
# @admin text trigger
# ──────────────────────────────────────────────────────────────────────────────
async def at_admin_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message or not message.text:
        return
    if "@admin" not in message.text.lower():
        return

    chat_data = await chats_db.get_chat(update.effective_chat.id)
    if not chat_data.get("report_setting", True):
        return

    # Reuse report logic by injecting as if /report was used
    await report_cmd(update, context)


# ──────────────────────────────────────────────────────────────────────────────
# Callback handlers for admin actions from report message
# ──────────────────────────────────────────────────────────────────────────────
async def report_action_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data
    acting_admin = query.from_user

    await query.answer()

    parts = data.split(":")
    action = parts[0]

    if action == "report_dismiss":
        await query.edit_message_text(
            query.message.text + f"\n\n✅ {sc('dismissed by')} {html.escape(acting_admin.full_name)}",
            parse_mode=ParseMode.HTML,
        )
        return

    if action == "report_del":
        chat_id = int(parts[1])
        msg_id = int(parts[2])
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            await query.edit_message_text(
                query.message.text + f"\n\n🗑️ {sc('message deleted by')} {html.escape(acting_admin.full_name)}",
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            await query.answer(f"Failed: {e}", show_alert=True)
        return

    chat_id = int(parts[1])
    user_id = int(parts[2])

    if action == "report_warn":
        try:
            from bot.database import warns_db
            from bot.database.chats_db import get_chat
            warn_count, _ = await warns_db.add_warn(chat_id, user_id, sc("reported by admin"), acting_admin.id)
            settings = await warns_db.get_warn_settings(chat_id)
            warn_limit = settings.get("limit", 3)
            await query.edit_message_text(
                query.message.text + f"\n\n⚠️ {sc('warned by')} {html.escape(acting_admin.full_name)} [{warn_count}/{warn_limit}]",
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            await query.answer(f"Failed: {e}", show_alert=True)

    elif action == "report_mute":
        try:
            from telegram import ChatPermissions
            await context.bot.restrict_chat_member(
                chat_id=chat_id, user_id=user_id, permissions=ChatPermissions(can_send_messages=False)
            )
            await query.edit_message_text(
                query.message.text + f"\n\n🔇 {sc('muted by')} {html.escape(acting_admin.full_name)}",
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            await query.answer(f"Failed: {e}", show_alert=True)

    elif action == "report_ban":
        try:
            await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            await query.edit_message_text(
                query.message.text + f"\n\n🔨 {sc('banned by')} {html.escape(acting_admin.full_name)}",
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            await query.answer(f"Failed: {e}", show_alert=True)


# ──────────────────────────────────────────────────────────────────────────────
# HELP TEXT
# ──────────────────────────────────────────────────────────────────────────────
REPORTS_HELP = (
    f"<b>🚨 {sc('reports commands')}</b>\n\n"
    f"<b>/report</b> — {sc('reply to a message to report it to admins')}\n"
    f"<b>@admin</b> — {sc('same as /report, mention @admin in message')}\n"
    f"<b>/reports on/off</b> — {sc('toggle reporting in this chat (admin only)')}\n\n"
    f"📌 {sc('admins receive a report with action buttons: warn / mute / ban / delete / dismiss.')}"
)


# ──────────────────────────────────────────────────────────────────────────────
# REGISTER
# ──────────────────────────────────────────────────────────────────────────────
def register_handlers(app) -> None:
    app.add_handler(CommandHandler("report", report_cmd, block=False))
    app.add_handler(CommandHandler("reports", reports_setting_cmd, block=False))
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r"(?i)@admin") & ~filters.COMMAND,
        at_admin_trigger,
        block=False,
    ))
    app.add_handler(CallbackQueryHandler(
        report_action_cb,
        pattern=r"^report_(warn|mute|ban|del|dismiss)",
    ))
