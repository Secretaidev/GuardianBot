"""
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — ꜰᴇᴅᴇʀᴀᴛɪᴏɴ ᴍᴏᴅᴜʟᴇ
Cross-group federation ban system.
"""
from __future__ import annotations

import html
import logging
import uuid

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.ext import CommandHandler, ContextTypes

from bot.fonts import sc
from bot.helpers.decorators import group_only
from bot.helpers.extractors import extract_user_and_reason, extract_user
from bot.database import feds_db
from bot.logger import log_action

logger = logging.getLogger(__name__)


async def _is_admin(chat_id: int, user_id: int, bot) -> bool:
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False


async def _is_fed_owner_or_admin(fed: dict, user_id: int) -> bool:
    if fed.get("owner_id") == user_id:
        return True
    admins = fed.get("admins", [])
    return user_id in admins


# ──────────────────────────────────────────────────────────────────────────────
# /newfed <name>
# ──────────────────────────────────────────────────────────────────────────────
async def newfed_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    user    = update.effective_user

    if not context.args:
        await message.reply_text(
            f"⚠️ {sc('usage')}: /newfed &lt;federation name&gt;",
            parse_mode=ParseMode.HTML,
        )
        return

    fed_name = " ".join(context.args)
    fed_id   = await feds_db.create_fed(fed_name, user.id)

    await message.reply_text(
        f"🌐 <b>{sc('federation created!')}</b>\n\n"
        f"📛 {sc('name')}: <b>{html.escape(fed_name)}</b>\n"
        f"🆔 {sc('fed id')}: <code>{fed_id}</code>\n\n"
        f"📌 {sc('use /joinfed')} <code>{fed_id}</code> {sc('in a group to link it.')}\n"
        f"{sc('keep this id safe — it is your federation key.')}",
        parse_mode=ParseMode.HTML,
    )


# ──────────────────────────────────────────────────────────────────────────────
# /delfed
# ──────────────────────────────────────────────────────────────────────────────
async def delfed_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    user    = update.effective_user
    chat    = update.effective_chat

    fed = await feds_db.get_fed_by_chat(chat.id)
    if not fed:
        await message.reply_text(f"❌ {sc('this chat is not in any federation.')}")
        return

    if fed.get("owner_id") != user.id:
        await message.reply_text(f"❌ {sc('only the federation owner can delete it.')}")
        return

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(f"✅ {sc('yes, delete')}", callback_data=f"delfed_yes:{fed['fed_id']}"),
        InlineKeyboardButton(f"❌ {sc('cancel')}",     callback_data="delfed_no"),
    ]])
    await message.reply_text(
        f"⚠️ {sc('delete federation')} <b>{html.escape(fed['name'])}</b>?\n"
        f"{sc('this will unlink all chats and remove all fed bans.')}",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )


from telegram.ext import CallbackQueryHandler

async def delfed_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if query.data == "delfed_no":
        await query.edit_message_text(f"❌ {sc('deletion cancelled.')}")
        return
    fed_id = query.data.split(":")[1]
    await feds_db.delete_fed(fed_id)
    await query.edit_message_text(f"✅ {sc('federation deleted and all chats unlinked.')}")


# ──────────────────────────────────────────────────────────────────────────────
# /joinfed <fed_id>
# ──────────────────────────────────────────────────────────────────────────────
@group_only
async def joinfed_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat
    user    = update.effective_user

    if not await _is_admin(chat.id, user.id, context.bot):
        await message.reply_text(f"❌ {sc('only admins can join a federation.')}")
        return

    if not context.args:
        await message.reply_text(
            f"⚠️ {sc('usage')}: /joinfed &lt;fed_id&gt;",
            parse_mode=ParseMode.HTML,
        )
        return

    fed_id = context.args[0].strip()
    fed    = await feds_db.get_fed(fed_id)
    if not fed:
        await message.reply_text(f"❌ {sc('federation not found. check the fed id.')}")
        return

    existing = await feds_db.get_fed_by_chat(chat.id)
    if existing:
        await message.reply_text(
            f"⚠️ {sc('this chat is already in federation')} <b>{html.escape(existing['name'])}</b>.\n"
            f"{sc('leave it first with /leavefed.')}",
            parse_mode=ParseMode.HTML,
        )
        return

    await feds_db.join_fed(fed_id, chat.id)
    await message.reply_text(
        f"✅ <b>{html.escape(chat.title or '')}</b> {sc('joined federation')} <b>{html.escape(fed['name'])}</b>!\n"
        f"🔗 {sc('all fed bans will now apply to this chat.')}",
        parse_mode=ParseMode.HTML,
    )
    await log_action(context.bot, chat_id=chat.id, action=f"joined federation {fed['name']}", by_user=user)


# ──────────────────────────────────────────────────────────────────────────────
# /leavefed
# ──────────────────────────────────────────────────────────────────────────────
@group_only
async def leavefed_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat
    user    = update.effective_user

    if not await _is_admin(chat.id, user.id, context.bot):
        await message.reply_text(f"❌ {sc('only admins can leave a federation.')}")
        return

    fed = await feds_db.get_fed_by_chat(chat.id)
    if not fed:
        await message.reply_text(f"❌ {sc('this chat is not in any federation.')}")
        return

    await feds_db.leave_fed(fed["fed_id"], chat.id)
    await message.reply_text(
        f"✅ {sc('left federation')} <b>{html.escape(fed['name'])}</b>.",
        parse_mode=ParseMode.HTML,
    )


# ──────────────────────────────────────────────────────────────────────────────
# /fedinfo [fed_id]
# ──────────────────────────────────────────────────────────────────────────────
async def fedinfo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat

    if context.args:
        fed = await feds_db.get_fed(context.args[0])
    else:
        fed = await feds_db.get_fed_by_chat(chat.id)

    if not fed:
        await message.reply_text(f"❌ {sc('no federation found. provide a fed id or use in a fed chat.')}")
        return

    chats_in_fed = fed.get("chats", [])
    bans_count   = len(await feds_db.get_fed_bans(fed["fed_id"]))
    admins_count = len(fed.get("admins", []))

    await message.reply_text(
        f"🌐 <b>{sc('federation info')}</b>\n\n"
        f"📛 {sc('name')}: <b>{html.escape(fed['name'])}</b>\n"
        f"🆔 {sc('fed id')}: <code>{fed['fed_id']}</code>\n"
        f"👑 {sc('owner')}: <code>{fed['owner_id']}</code>\n"
        f"💬 {sc('chats')}: <b>{len(chats_in_fed)}</b>\n"
        f"⭐ {sc('admins')}: <b>{admins_count}</b>\n"
        f"🚫 {sc('fed bans')}: <b>{bans_count}</b>",
        parse_mode=ParseMode.HTML,
    )


# ──────────────────────────────────────────────────────────────────────────────
# /fedban <user> [reason]
# ──────────────────────────────────────────────────────────────────────────────
async def fedban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat
    user    = update.effective_user

    fed = await feds_db.get_fed_by_chat(chat.id)
    if not fed:
        await message.reply_text(f"❌ {sc('this chat is not in any federation.')}")
        return

    if not await _is_fed_owner_or_admin(fed, user.id):
        await message.reply_text(f"❌ {sc('only federation admins can use fedban.')}")
        return

    extracted = await extract_user_and_reason(update, context)
    if not extracted.user:
        await message.reply_text(f"⚠️ {sc('reply to a user or provide their id to fedban.')}")
        return

    target_id = extracted.user.id
    reason = extracted.reason or sc("no reason provided")
    await feds_db.fed_ban(fed["fed_id"], target_id, reason, user.id)

    # Apply ban across all chats in fed
    ban_count = 0
    for c_id in fed.get("chats", []):
        try:
            await context.bot.ban_chat_member(c_id, target_id)
            ban_count += 1
        except Exception:
            pass

    await message.reply_text(
        f"🚫 <b>{sc('federation ban applied!')}</b>\n\n"
        f"👤 {sc('user id')}: <code>{target_id}</code>\n"
        f"🌐 {sc('federation')}: <b>{html.escape(fed['name'])}</b>\n"
        f"💬 {sc('banned in')}: <b>{ban_count}</b> {sc('chats')}\n"
        f"📝 {sc('reason')}: {html.escape(str(reason))}",
        parse_mode=ParseMode.HTML,
    )
    await log_action(
        context.bot, action=f"fedban in {fed['name']}", chat_id=chat.id,
        chat_title=chat.title or '', target_user_id=target_id,
        target_username=str(target_id), performed_by_id=user.id,
        performed_by_username=user.full_name, reason=str(reason),
    )


# ──────────────────────────────────────────────────────────────────────────────
# /unfedban <user>
# ──────────────────────────────────────────────────────────────────────────────
async def unfedban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat
    user    = update.effective_user

    fed = await feds_db.get_fed_by_chat(chat.id)
    if not fed:
        await message.reply_text(f"❌ {sc('this chat is not in any federation.')}")
        return

    if not await _is_fed_owner_or_admin(fed, user.id):
        await message.reply_text(f"❌ {sc('only federation admins can use unfedban.')}")
        return

    extracted = await extract_user(update, context)
    if not extracted.user:
        await message.reply_text(f"⚠️ {sc('reply to a user or provide their id.')}")
        return
    target_id = extracted.user.id

    await feds_db.fed_unban(fed["fed_id"], target_id)

    unban_count = 0
    for c_id in fed.get("chats", []):
        try:
            await context.bot.unban_chat_member(c_id, target_id)
            unban_count += 1
        except Exception:
            pass

    await message.reply_text(
        f"✅ <b>{sc('federation ban removed!')}</b>\n"
        f"👤 {sc('user id')}: <code>{target_id}</code>\n"
        f"💬 {sc('unbanned in')}: <b>{unban_count}</b> {sc('chats')}",
        parse_mode=ParseMode.HTML,
    )


# ──────────────────────────────────────────────────────────────────────────────
# /fedbans
# ──────────────────────────────────────────────────────────────────────────────
async def fedbans_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat

    fed = await feds_db.get_fed_by_chat(chat.id)
    if not fed:
        await message.reply_text(f"❌ {sc('this chat is not in any federation.')}")
        return

    bans = await feds_db.get_fed_bans(fed["fed_id"])
    if not bans:
        await message.reply_text(f"✅ {sc('no federation bans.')}")
        return

    text = f"🚫 <b>{sc('fed bans')} — {html.escape(fed['name'])}</b>\n\n"
    for i, ban in enumerate(bans[:50], 1):
        uid    = ban.get("user_id", "?")
        reason = html.escape(str(ban.get("reason", sc("no reason"))))
        text  += f"{i}. <code>{uid}</code> — {reason}\n"

    if len(bans) > 50:
        text += f"\n{sc('and')} {len(bans) - 50} {sc('more...')}"

    await message.reply_text(text, parse_mode=ParseMode.HTML)


# ──────────────────────────────────────────────────────────────────────────────
# /fedadmins
# ──────────────────────────────────────────────────────────────────────────────
async def fedadmins_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat

    fed = await feds_db.get_fed_by_chat(chat.id)
    if not fed:
        await message.reply_text(f"❌ {sc('this chat is not in any federation.')}")
        return

    admins = await feds_db.get_fed_admins(fed["fed_id"])
    text   = f"⭐ <b>{sc('fed admins')} — {html.escape(fed['name'])}</b>\n\n"
    text  += f"👑 {sc('owner')}: <code>{fed['owner_id']}</code>\n"
    for uid in admins:
        text += f"⭐ <code>{uid}</code>\n"

    await message.reply_text(text, parse_mode=ParseMode.HTML)


# ──────────────────────────────────────────────────────────────────────────────
# /addfedadmin  /rmfedadmin
# ──────────────────────────────────────────────────────────────────────────────
async def addfedadmin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat
    user    = update.effective_user

    fed = await feds_db.get_fed_by_chat(chat.id)
    if not fed or fed.get("owner_id") != user.id:
        await message.reply_text(f"❌ {sc('only the federation owner can add admins.')}")
        return

    extracted = await extract_user(update, context)
    if not extracted.user:
        await message.reply_text(f"⚠️ {sc('provide a user id or reply to add as fed admin.')}")
        return
    target_id = extracted.user.id

    await feds_db.add_fed_admin(fed["fed_id"], target_id)
    await message.reply_text(
        f"✅ <code>{target_id}</code> {sc('added as federation admin.')}",
        parse_mode=ParseMode.HTML,
    )


async def rmfedadmin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat
    user    = update.effective_user

    fed = await feds_db.get_fed_by_chat(chat.id)
    if not fed or fed.get("owner_id") != user.id:
        await message.reply_text(f"❌ {sc('only the federation owner can remove admins.')}")
        return

    extracted = await extract_user(update, context)
    if not extracted.user:
        await message.reply_text(f"⚠️ {sc('provide a user id or reply.')}")
        return
    target_id = extracted.user.id

    await feds_db.remove_fed_admin(fed["fed_id"], target_id)
    await message.reply_text(
        f"✅ <code>{target_id}</code> {sc('removed from federation admins.')}",
        parse_mode=ParseMode.HTML,
    )


# ──────────────────────────────────────────────────────────────────────────────
# /fedchats
# ──────────────────────────────────────────────────────────────────────────────
async def fedchats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat    = update.effective_chat

    fed = await feds_db.get_fed_by_chat(chat.id)
    if not fed:
        await message.reply_text(f"❌ {sc('this chat is not in any federation.')}")
        return

    chats = fed.get("chats", [])
    if not chats:
        await message.reply_text(f"💬 {sc('no chats linked to this federation.')}")
        return

    text = f"💬 <b>{sc('fed chats')} — {html.escape(fed['name'])}</b>\n\n"
    for i, c_id in enumerate(chats, 1):
        text += f"{i}. <code>{c_id}</code>\n"

    await message.reply_text(text, parse_mode=ParseMode.HTML)


# ──────────────────────────────────────────────────────────────────────────────
# HELP
# ──────────────────────────────────────────────────────────────────────────────
FEDERATION_HELP = (
    f"<b>🌐 {sc('federation commands')}</b>\n\n"
    f"<b>/newfed</b> &lt;name&gt; — {sc('create a new federation')}\n"
    f"<b>/delfed</b> — {sc('delete federation (owner only)')}\n"
    f"<b>/joinfed</b> &lt;fed_id&gt; — {sc('join chat to a federation')}\n"
    f"<b>/leavefed</b> — {sc('leave current federation')}\n"
    f"<b>/fedinfo</b> [fed_id] — {sc('show federation info')}\n"
    f"<b>/fedban</b> &lt;user&gt; [reason] — {sc('ban user across all fed chats')}\n"
    f"<b>/unfedban</b> &lt;user&gt; — {sc('unban from federation')}\n"
    f"<b>/fedbans</b> — {sc('list all fed bans')}\n"
    f"<b>/fedadmins</b> — {sc('list federation admins')}\n"
    f"<b>/addfedadmin</b> &lt;user&gt; — {sc('add federation admin')}\n"
    f"<b>/rmfedadmin</b> &lt;user&gt; — {sc('remove federation admin')}\n"
    f"<b>/fedchats</b> — {sc('list all chats in federation')}\n"
)


# ──────────────────────────────────────────────────────────────────────────────
# REGISTER
# ──────────────────────────────────────────────────────────────────────────────
def register_handlers(app) -> None:
    app.add_handler(CommandHandler("newfed",      newfed_cmd,      block=False))
    app.add_handler(CommandHandler("delfed",      delfed_cmd,      block=False))
    app.add_handler(CommandHandler("joinfed",     joinfed_cmd,     block=False))
    app.add_handler(CommandHandler("leavefed",    leavefed_cmd,    block=False))
    app.add_handler(CommandHandler("fedinfo",     fedinfo_cmd,     block=False))
    app.add_handler(CommandHandler("fedban",      fedban_cmd,      block=False))
    app.add_handler(CommandHandler("unfedban",    unfedban_cmd,    block=False))
    app.add_handler(CommandHandler("fedbans",     fedbans_cmd,     block=False))
    app.add_handler(CommandHandler("fedadmins",   fedadmins_cmd,   block=False))
    app.add_handler(CommandHandler("addfedadmin", addfedadmin_cmd, block=False))
    app.add_handler(CommandHandler("rmfedadmin",  rmfedadmin_cmd,  block=False))
    app.add_handler(CommandHandler("fedchats",    fedchats_cmd,    block=False))
    app.add_handler(CallbackQueryHandler(delfed_cb, pattern=r"^delfed_"))
