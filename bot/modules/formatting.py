"""
Rose — Formatting help.
Shows users how to format text in Telegram.
"""
from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

logger = logging.getLogger(__name__)

MARKDOWN_HELP = (
    "<b>Formatting Guide</b>\n\n"
    "Rose supports the following formatting in notes, filters, and welcome messages:\n\n"
    "<b>Bold:</b>\n"
    "<code>*bold text*</code> → <b>bold text</b>\n\n"
    "<b>Italic:</b>\n"
    "<code>_italic text_</code> → <i>italic text</i>\n\n"
    "<b>Code:</b>\n"
    "<code>`inline code`</code> → <code>inline code</code>\n\n"
    "<b>Code Block:</b>\n"
    "<code>```\nmultiline\ncode\n```</code>\n\n"
    "<b>Link:</b>\n"
    "<code>[text](url)</code> → clickable link\n\n"
    "<b>Buttons:</b>\n"
    "<code>[button text](buttonurl://example.com)</code>\n"
    "Creates an inline button.\n\n"
    "<b>Same Row Buttons:</b>\n"
    "<code>[btn1](buttonurl://url1)\n[btn2](buttonurl://url2:same)</code>\n"
    "The <code>:same</code> suffix puts buttons on the same row.\n\n"
    "<b>Variables (for welcome/notes):</b>\n"
    " • <code>{first}</code> — user's first name\n"
    " • <code>{last}</code> — user's last name\n"
    " • <code>{fullname}</code> — full name\n"
    " • <code>{username}</code> — @username\n"
    " • <code>{mention}</code> — mention with name\n"
    " • <code>{id}</code> — user ID\n"
    " • <code>{chatname}</code> — group name\n"
    " • <code>{count}</code> — member count\n"
)


async def cmd_markdownhelp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat and chat.type != "private":
        await update.effective_message.reply_text(
            "Tap below to see formatting help in PM.",
        )
        return

    await update.effective_message.reply_text(
        MARKDOWN_HELP, parse_mode=ParseMode.HTML,
    )


def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("markdownhelp", cmd_markdownhelp))
