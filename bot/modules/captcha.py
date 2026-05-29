"""
Rose — CAPTCHA verification for new members.
Button-based or math-based challenge.
"""
from __future__ import annotations

import logging
import random
import time
from collections import defaultdict

from telegram import (
    ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup, Update,
)
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ChatMemberHandler, ContextTypes,
)

from bot.config import OWNER_ID
from bot.helpers.decorators import admin_required, group_only

logger = logging.getLogger(__name__)

# ── In-memory pending verifications ───────────────────────────────────────────
_pending: dict[str, dict] = {}  # "chat_id:user_id" → {answer, msg_id, time}

# ── DB helpers ────────────────────────────────────────────────────────────────

async def _get_col():
    from bot.database.mongo import get_collection
    return get_collection("captcha_settings")

_cache: dict[int, dict] = {}

async def _get_settings(chat_id: int) -> dict:
    if chat_id in _cache:
        return _cache[chat_id]
    col = await _get_col()
    doc = await col.find_one({"chat_id": chat_id})
    settings = {
        "enabled": doc.get("enabled", False) if doc else False,
        "mode": doc.get("mode", "button") if doc else "button",
        "timeout": doc.get("timeout", 120) if doc else 120,
    }
    _cache[chat_id] = settings
    return settings

async def _save_settings(chat_id: int, settings: dict):
    col = await _get_col()
    _cache[chat_id] = settings
    await col.update_one(
        {"chat_id": chat_id},
        {"$set": {**settings, "chat_id": chat_id}},
        upsert=True,
    )


# ── Commands ──────────────────────────────────────────────────────────────────

@group_only
@admin_required
async def cmd_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    args = context.args

    settings = await _get_settings(chat.id)

    if not args:
        status = "enabled ✅" if settings["enabled"] else "disabled ❌"
        await msg.reply_text(
            f"<b>CAPTCHA Settings</b>\n\n"
            f"Status: {status}\n"
            f"Mode: <code>{settings['mode']}</code>\n"
            f"Timeout: <code>{settings['timeout']}s</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    val = args[0].lower()
    if val in ("on", "yes", "true"):
        settings["enabled"] = True
        await _save_settings(chat.id, settings)
        await msg.reply_text("✅ CAPTCHA enabled for new members.")
    elif val in ("off", "no", "false"):
        settings["enabled"] = False
        await _save_settings(chat.id, settings)
        await msg.reply_text("❌ CAPTCHA disabled.")
    else:
        await msg.reply_text("Usage: /captcha on|off")


@group_only
@admin_required
async def cmd_captchamode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    args = context.args

    if not args or args[0].lower() not in ("button", "math"):
        await msg.reply_text("Usage: /captchamode button|math")
        return

    mode = args[0].lower()
    settings = await _get_settings(chat.id)
    settings["mode"] = mode
    await _save_settings(chat.id, settings)
    await msg.reply_text(f"✅ CAPTCHA mode set to <b>{mode}</b>.", parse_mode=ParseMode.HTML)


@group_only
@admin_required
async def cmd_captchatime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    args = context.args

    if not args:
        await msg.reply_text("Usage: /captchatime <seconds>\nExample: /captchatime 120")
        return

    try:
        timeout = max(30, min(600, int(args[0])))
    except ValueError:
        await msg.reply_text("Please provide a valid number.")
        return

    settings = await _get_settings(chat.id)
    settings["timeout"] = timeout
    await _save_settings(chat.id, settings)
    await msg.reply_text(f"✅ CAPTCHA timeout set to <b>{timeout}s</b>.", parse_mode=ParseMode.HTML)


# ── On member join — send CAPTCHA ─────────────────────────────────────────────

async def _on_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    member = update.chat_member
    if not member:
        return

    chat = member.chat
    new = member.new_chat_member
    old = member.old_chat_member

    if not new or not old:
        return
    if new.status != ChatMemberStatus.MEMBER:
        return
    if old.status not in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
        return

    user = new.user
    if not user or user.is_bot:
        return

    settings = await _get_settings(chat.id)
    if not settings["enabled"]:
        return

    key = f"{chat.id}:{user.id}"

    # Restrict user until verified
    try:
        await context.bot.restrict_chat_member(
            chat.id, user.id,
            ChatPermissions(can_send_messages=False),
        )
    except Exception as e:
        logger.debug("CAPTCHA restrict failed: %s", e)
        return

    mode = settings["mode"]

    if mode == "math":
        a, b = random.randint(1, 20), random.randint(1, 20)
        answer = a + b
        text = (
            f"Welcome <b>{user.first_name}</b>!\n"
            f"Please solve: <b>{a} + {b} = ?</b>\n"
            f"Tap the correct answer to verify."
        )
        correct = answer
        options = {correct}
        while len(options) < 4:
            options.add(random.randint(max(1, answer - 10), answer + 10))
        options = sorted(options)

        btns = [
            InlineKeyboardButton(
                str(opt),
                callback_data=f"captcha:{chat.id}:{user.id}:{opt}",
            )
            for opt in options
        ]
        kb = InlineKeyboardMarkup([btns])
        _pending[key] = {"answer": str(correct), "time": time.time()}

    else:  # button mode
        text = (
            f"Welcome <b>{user.first_name}</b>!\n"
            f"Please tap the button below to verify you're human."
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "✅ I'm human",
                callback_data=f"captcha:{chat.id}:{user.id}:verify",
            ),
        ]])
        _pending[key] = {"answer": "verify", "time": time.time()}

    try:
        sent = await context.bot.send_message(
            chat.id, text, parse_mode=ParseMode.HTML, reply_markup=kb,
        )
        _pending[key]["msg_id"] = sent.message_id
    except Exception as e:
        logger.debug("CAPTCHA msg failed: %s", e)


# ── CAPTCHA button callback ──────────────────────────────────────────────────

async def _captcha_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return

    parts = query.data.split(":")
    if len(parts) != 4:
        return

    _, chat_id_str, user_id_str, answer = parts
    try:
        chat_id = int(chat_id_str)
        user_id = int(user_id_str)
    except ValueError:
        return

    clicker = query.from_user
    if not clicker or clicker.id != user_id:
        await query.answer("This isn't for you!", show_alert=True)
        return

    key = f"{chat_id}:{user_id}"
    pending = _pending.get(key)

    if not pending:
        await query.answer("Verification expired.", show_alert=True)
        return

    if answer == pending["answer"] or answer == "verify":
        # Verified — unrestrict
        try:
            await context.bot.restrict_chat_member(
                chat_id, user_id,
                ChatPermissions(
                    can_send_messages=True, can_send_other_messages=True,
                    can_add_web_page_previews=True, can_send_polls=True,
                    can_invite_users=True,
                ),
            )
        except Exception:
            pass

        await query.answer("✅ Verified! Welcome!")
        try:
            await query.message.delete()
        except Exception:
            pass
        _pending.pop(key, None)
    else:
        await query.answer("❌ Wrong answer! Try again.", show_alert=True)


def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("captcha", cmd_captcha))
    app.add_handler(CommandHandler("captchamode", cmd_captchamode))
    app.add_handler(CommandHandler("captchatime", cmd_captchatime))
    app.add_handler(ChatMemberHandler(_on_join, ChatMemberHandler.CHAT_MEMBER), group=16)
    app.add_handler(CallbackQueryHandler(_captcha_callback, pattern=r"^captcha:"))
