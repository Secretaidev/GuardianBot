"""
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — ᴀᴅᴍɪɴ ᴍᴏᴅᴜʟᴇ
Admin management: promote, demote, adminlist, title, group settings.
"""
from __future__ import annotations

import html
import logging
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ChatMemberAdministrator,
)
from telegram.constants import ChatMemberStatus, ParseMode
from telegram.ext import CommandHandler, ContextTypes, CallbackQueryHandler

from bot.fonts import sc
from bot.helpers.decorators import admin_required, bot_admin_required, group_only
from bot.helpers.extractors import extract_user, extract_user_and_reason
from bot.logger import log_action

logger = logging.getLogger(__name__)


def _mention(user) -> str:
    return f"<a href='tg://user?id={user.id}'>{html.escape(user.full_name)}</a>"


# ──────────────────────────────────────────────────────────────────────────────
# /promote
# ──────────────────────────────────────────────────────────────────────────────
@group_only
@admin_required
@bot_admin_required
async def promote_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    msg  = update.effective_message
    actor = update.effective_user

    extracted = await extract_user_and_reason(update, context)
    if not extracted.user:
        await msg.reply_text(f"⚠️ {sc('reply to a user or provide a username/id.')}")
        return

    target = extracted.user
    if target.id == context.bot.id:
        await msg.reply_text(f"🤖 {sc('i cannot promote myself!')}")
        return

    try:
        member = await chat.get_member(target.id)
    except Exception:
        await msg.reply_text(f"❌ {sc('user not found.')}")
        return

    if member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
        await msg.reply_text(f"ℹ️ {sc('user is already an admin.')}")
        return

    custom_title = extracted.reason or ""
    try:
        await context.bot.promote_chat_member(
            chat_id=chat.id, user_id=target.id,
            can_change_info=True, can_delete_messages=True,
            can_invite_users=True, can_restrict_members=True,
            can_pin_messages=True, can_manage_chat=True,
            can_manage_video_chats=True,
        )
        if custom_title:
            try:
                await context.bot.set_chat_administrator_custom_title(
                    chat_id=chat.id, user_id=target.id, custom_title=custom_title[:16]
                )
            except Exception:
                pass

        title_line = f"\n🏷️ {sc('title')}: <code>{html.escape(custom_title)}</code>" if custom_title else ""
        await msg.reply_text(
            f"⭐ {sc('promoted successfully!')}\n👤 {sc('user')}: {_mention(target)}{title_line}",
            parse_mode=ParseMode.HTML,
        )
        await log_action(
            context.bot, action="promote", chat_id=chat.id,
            chat_title=chat.title or "", target_user_id=target.id,
            target_username=target.full_name, performed_by_id=actor.id,
            performed_by_username=actor.full_name,
            reason=custom_title or sc("no title"),
        )
    except Exception as e:
        await msg.reply_text(f"❌ {sc('failed')}: <code>{html.escape(str(e))}</code>", parse_mode=ParseMode.HTML)


# ──────────────────────────────────────────────────────────────────────────────
# /demote
# ──────────────────────────────────────────────────────────────────────────────
@group_only
@admin_required
@bot_admin_required
async def demote_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat  = update.effective_chat
    msg   = update.effective_message
    actor = update.effective_user

    extracted = await extract_user(update, context)
    if not extracted.user:
        await msg.reply_text(f"⚠️ {sc('reply to a user or provide a username/id.')}")
        return

    target = extracted.user
    try:
        await context.bot.promote_chat_member(
            chat_id=chat.id, user_id=target.id,
            can_change_info=False, can_delete_messages=False,
            can_invite_users=False, can_restrict_members=False,
            can_pin_messages=False, can_manage_chat=False,
            can_manage_video_chats=False,
        )
        await msg.reply_text(
            f"⬇️ {sc('demoted successfully!')}\n👤 {_mention(target)}",
            parse_mode=ParseMode.HTML,
        )
        await log_action(
            context.bot, action="demote", chat_id=chat.id,
            chat_title=chat.title or "", target_user_id=target.id,
            target_username=target.full_name, performed_by_id=actor.id,
            performed_by_username=actor.full_name,
        )
    except Exception as e:
        await msg.reply_text(f"❌ {sc('failed')}: <code>{html.escape(str(e))}</code>", parse_mode=ParseMode.HTML)


# ──────────────────────────────────────────────────────────────────────────────
# /title
# ──────────────────────────────────────────────────────────────────────────────
@group_only
@admin_required
@bot_admin_required
async def set_title_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat

    extracted = await extract_user_and_reason(update, context)
    if not extracted.user or not extracted.reason:
        await msg.reply_text(
            f"⚠️ {sc('usage')}: /title &lt;user&gt; &lt;title&gt; ({sc('max 16 chars')})",
            parse_mode=ParseMode.HTML,
        )
        return

    title = extracted.reason[:16]
    try:
        await context.bot.set_chat_administrator_custom_title(
            chat_id=chat.id, user_id=extracted.user.id, custom_title=title
        )
        await msg.reply_text(
            f"🏷️ {sc('title set to')}: <code>{html.escape(title)}</code>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await msg.reply_text(f"❌ <code>{html.escape(str(e))}</code>", parse_mode=ParseMode.HTML)


# ──────────────────────────────────────────────────────────────────────────────
# /adminlist
# ──────────────────────────────────────────────────────────────────────────────
@group_only
async def adminlist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    msg  = update.effective_message
    try:
        admins = await chat.get_administrators()
    except Exception as e:
        await msg.reply_text(f"❌ {sc('failed to fetch admin list')}: {e}")
        return

    owner_lines, admin_lines = [], []
    for admin in admins:
        user = admin.user
        if user.is_bot:
            continue
        name    = html.escape(user.full_name)
        mention = f"<a href='tg://user?id={user.id}'>{name}</a>"
        ctitle  = ""
        if isinstance(admin, ChatMemberAdministrator) and admin.custom_title:
            ctitle = f" — <i>{html.escape(admin.custom_title)}</i>"
        if admin.status == ChatMemberStatus.CREATOR:
            owner_lines.append(f"👑 {mention}{ctitle}")
        else:
            admin_lines.append(f"⭐ {mention}{ctitle}")

    text = f"<b>🛡️ {sc('admin list')} — {html.escape(chat.title or '')}</b>\n\n"
    if owner_lines:
        text += f"<b>{sc('owner')}</b>\n" + "\n".join(owner_lines) + "\n\n"
    if admin_lines:
        text += f"<b>{sc('admins')}</b>\n" + "\n".join(admin_lines)

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(f"🔄 {sc('refresh')}", callback_data=f"adminlist_refresh:{chat.id}")
    ]])
    await msg.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def adminlist_refresh_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    chat_id = int(query.data.split(":")[1])
    await query.answer(sc("refreshing..."))
    try:
        admins = await context.bot.get_chat_administrators(chat_id)
    except Exception:
        await query.answer(sc("failed."), show_alert=True)
        return

    owner_lines, admin_lines = [], []
    for admin in admins:
        user = admin.user
        if user.is_bot:
            continue
        name    = html.escape(user.full_name)
        mention = f"<a href='tg://user?id={user.id}'>{name}</a>"
        ctitle  = ""
        if isinstance(admin, ChatMemberAdministrator) and admin.custom_title:
            ctitle = f" — <i>{html.escape(admin.custom_title)}</i>"
        if admin.status == ChatMemberStatus.CREATOR:
            owner_lines.append(f"👑 {mention}{ctitle}")
        else:
            admin_lines.append(f"⭐ {mention}{ctitle}")

    chat_obj = await context.bot.get_chat(chat_id)
    text = f"<b>🛡️ {sc('admin list')} — {html.escape(chat_obj.title or '')}</b>\n\n"
    if owner_lines:
        text += f"<b>{sc('owner')}</b>\n" + "\n".join(owner_lines) + "\n\n"
    if admin_lines:
        text += f"<b>{sc('admins')}</b>\n" + "\n".join(admin_lines)

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(f"🔄 {sc('refresh')}", callback_data=f"adminlist_refresh:{chat_id}")
    ]])
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


# ──────────────────────────────────────────────────────────────────────────────
# /invitelink  /revoke  /setgtitle  /setgdesc  /setgpic
# ──────────────────────────────────────────────────────────────────────────────
@group_only
@admin_required
@bot_admin_required
async def invitelink_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    try:
        link = await context.bot.export_chat_invite_link(chat.id)
        await update.effective_message.reply_text(
            f"🔗 {sc('invite link')}:\n\n<code>{link}</code>", parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await update.effective_message.reply_text(f"❌ <code>{html.escape(str(e))}</code>", parse_mode=ParseMode.HTML)


@group_only
@admin_required
@bot_admin_required
async def revoke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    try:
        link = await context.bot.export_chat_invite_link(chat.id)
        await update.effective_message.reply_text(
            f"🔄 {sc('new invite link generated')}:\n\n<code>{link}</code>", parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await update.effective_message.reply_text(f"❌ <code>{html.escape(str(e))}</code>", parse_mode=ParseMode.HTML)


@group_only
@admin_required
@bot_admin_required
async def setgtitle_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not context.args:
        await msg.reply_text(f"⚠️ /setgtitle &lt;new title&gt;", parse_mode=ParseMode.HTML)
        return
    try:
        await context.bot.set_chat_title(update.effective_chat.id, " ".join(context.args))
        await msg.reply_text(f"✅ {sc('group title updated.')}")
    except Exception as e:
        await msg.reply_text(f"❌ <code>{html.escape(str(e))}</code>", parse_mode=ParseMode.HTML)


@group_only
@admin_required
@bot_admin_required
async def setgdesc_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not context.args:
        await msg.reply_text(f"⚠️ /setgdesc &lt;description&gt;", parse_mode=ParseMode.HTML)
        return
    try:
        await context.bot.set_chat_description(update.effective_chat.id, " ".join(context.args))
        await msg.reply_text(f"✅ {sc('description updated.')}")
    except Exception as e:
        await msg.reply_text(f"❌ <code>{html.escape(str(e))}</code>", parse_mode=ParseMode.HTML)


@group_only
@admin_required
@bot_admin_required
async def setgpic_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg   = update.effective_message
    chat  = update.effective_chat
    photo = None
    if msg.reply_to_message and msg.reply_to_message.photo:
        photo = msg.reply_to_message.photo[-1]
    elif msg.photo:
        photo = msg.photo[-1]
    if not photo:
        await msg.reply_text(f"⚠️ {sc('reply to a photo to set the group picture.')}")
        return
    try:
        file = await context.bot.get_file(photo.file_id)
        data = await file.download_as_bytearray()
        import io
        from telegram import InputFile
        await context.bot.set_chat_photo(chat.id, InputFile(io.BytesIO(data)))
        await msg.reply_text(f"✅ {sc('group photo updated!')}")
    except Exception as e:
        await msg.reply_text(f"❌ <code>{html.escape(str(e))}</code>", parse_mode=ParseMode.HTML)


ADMIN_HELP = (
    f"<b>🛡️ {sc('admin commands')}</b>\n\n"
    f"<b>/promote</b> &lt;user&gt; [title] — {sc('promote user to admin')}\n"
    f"<b>/demote</b> &lt;user&gt; — {sc('demote admin to member')}\n"
    f"<b>/title</b> &lt;user&gt; &lt;title&gt; — {sc('set custom admin title')}\n"
    f"<b>/adminlist</b> — {sc('list all group admins')}\n"
    f"<b>/invitelink</b> — {sc('get group invite link')}\n"
    f"<b>/revoke</b> — {sc('revoke & regenerate invite link')}\n"
    f"<b>/setgtitle</b> &lt;text&gt; — {sc('change group title')}\n"
    f"<b>/setgdesc</b> &lt;text&gt; — {sc('change group description')}\n"
    f"<b>/setgpic</b> — {sc('reply to photo to set group picture')}\n"
)


def register_handlers(app) -> None:
    app.add_handler(CommandHandler("promote",     promote_cmd,       block=False))
    app.add_handler(CommandHandler("demote",      demote_cmd,        block=False))
    app.add_handler(CommandHandler("title",       set_title_cmd,     block=False))
    app.add_handler(CommandHandler("adminlist",   adminlist_cmd,     block=False))
    app.add_handler(CommandHandler("invitelink",  invitelink_cmd,    block=False))
    app.add_handler(CommandHandler("revoke",      revoke_cmd,        block=False))
    app.add_handler(CommandHandler("setgtitle",   setgtitle_cmd,     block=False))
    app.add_handler(CommandHandler("setgdesc",    setgdesc_cmd,      block=False))
    app.add_handler(CommandHandler("setgpic",     setgpic_cmd,       block=False))
    app.add_handler(CallbackQueryHandler(adminlist_refresh_cb, pattern=r"^adminlist_refresh:"))
