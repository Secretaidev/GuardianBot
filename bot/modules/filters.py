"""
bot/modules/filters.py
──────────────────────
Auto-reply keyword filters module for ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ.

Commands
--------
/filter <keyword> <reply>     – Add a text filter
/filter "multi word" <reply>  – Multi-word keyword filter (quoted)
/filter <keyword>             – (reply to media) Add a media filter
/filters                      – List all active filters with delete buttons
/stop <keyword>               – Remove a specific filter
/stopall                      – Remove all filters (with confirmation)

Message handler checks every incoming group message against active filters.
Matching is case-insensitive whole-word regex.

Filter reply types: text, photo, video, document, audio, animation, sticker.
Button syntax: [Label](url) or [Label](buttonurl:url:same)
"""

from __future__ import annotations

import html
import logging
import re
from typing import Optional

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters as tg_filters,
)

from bot.database import filters_db
from bot.fonts import sc
from bot.helpers.decorators import admin_required, group_only
from bot.helpers.extractors import build_buttons, extract_text_and_buttons

logger = logging.getLogger(__name__)

# Number of filters to display per page in /filters list
_FILTERS_PER_PAGE = 10


# ─────────────────────────────────────────────────────────────────────────────
# Helper: detect filter keyword match in a message
# ─────────────────────────────────────────────────────────────────────────────

def _keyword_matches(keyword: str, text: str) -> bool:
    """
    Return True if *keyword* appears in *text* as a whole-word match
    (case-insensitive).  Single-character keywords use simple containment.
    """
    if not text:
        return False
    pattern = re.compile(
        r"(?<!\w)" + re.escape(keyword) + r"(?!\w)",
        re.IGNORECASE,
    )
    return bool(pattern.search(text))


# ─────────────────────────────────────────────────────────────────────────────
# Helper: send filter reply
# ─────────────────────────────────────────────────────────────────────────────

async def _send_filter_reply(
    message: Message,
    filter_doc: dict,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Send the appropriate reply for a matched filter document.

    The filter_data sub-dict from the DB has:
      reply      – text reply (may be None if media-only)
      media      – file_id (or None)
      media_type – 'photo'|'video'|'document'|'audio'|'animation'|'sticker'
      buttons    – list of button dicts
    """
    fd: dict = filter_doc.get("filter_data", {})
    reply_text: Optional[str] = fd.get("reply") or None
    media: Optional[str] = fd.get("media") or None
    media_type: Optional[str] = fd.get("media_type") or None
    buttons: list[dict] = fd.get("buttons", [])
    markup = build_buttons(buttons)

    try:
        if media and media_type == "photo":
            await message.reply_photo(
                photo=media,
                caption=reply_text,
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
        elif media and media_type == "video":
            await message.reply_video(
                video=media,
                caption=reply_text,
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
        elif media and media_type == "document":
            await message.reply_document(
                document=media,
                caption=reply_text,
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
        elif media and media_type == "audio":
            await message.reply_audio(
                audio=media,
                caption=reply_text,
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
        elif media and media_type == "animation":
            await message.reply_animation(
                animation=media,
                caption=reply_text,
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
        elif media and media_type == "sticker":
            await message.reply_sticker(sticker=media)
        elif reply_text:
            await message.reply_text(
                text=reply_text,
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
                disable_web_page_preview=True,
            )
    except TelegramError as exc:
        logger.warning("Filter reply failed: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Message handler: auto-filter check
# ─────────────────────────────────────────────────────────────────────────────

async def handle_filter_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Check every group message against saved filters and reply if matched."""
    msg = update.effective_message
    chat = update.effective_chat
    if not msg or not chat:
        return

    text = msg.text or msg.caption or ""
    if not text:
        return

    keywords = await filters_db.get_all_filters(chat.id)
    for keyword in keywords:
        if _keyword_matches(keyword, text):
            filter_doc = await filters_db.get_filter(chat.id, keyword)
            if filter_doc:
                await _send_filter_reply(msg, filter_doc, context)
                # Only trigger the first matched filter to avoid spam
                break


# ─────────────────────────────────────────────────────────────────────────────
# Command: /filter
# ─────────────────────────────────────────────────────────────────────────────

@group_only
@admin_required
async def cmd_filter(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """/filter <keyword> <reply> — Add a keyword filter."""
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    # Parse the full command text (after /filter)
    full_text = msg.text or ""
    # Remove the /filter command prefix
    after_cmd = full_text.split(None, 1)[1] if len(full_text.split(None, 1)) > 1 else ""

    if not after_cmd:
        await msg.reply_text(
            f"<b>{sc('usage')}:</b>\n"
            f"<code>/filter keyword reply text</code>\n"
            f"<code>/filter \"multi word\" reply text</code>\n"
            f"<i>{sc('or reply to media with')} /filter keyword</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    # Extract keyword (quoted or single word)
    keyword: str
    reply_part: str

    if after_cmd.startswith('"'):
        # Quoted keyword
        end_quote = after_cmd.find('"', 1)
        if end_quote == -1:
            await msg.reply_text(sc("missing closing quote for keyword."))
            return
        keyword = after_cmd[1:end_quote].strip()
        reply_part = after_cmd[end_quote + 1:].strip()
    else:
        parts = after_cmd.split(None, 1)
        keyword = parts[0]
        reply_part = parts[1] if len(parts) > 1 else ""

    if not keyword:
        await msg.reply_text(sc("keyword cannot be empty."))
        return

    # Determine filter data
    filter_data: dict = {}

    # Check if replying to media
    replied = msg.reply_to_message
    if replied:
        if replied.photo:
            filter_data = {
                "reply": reply_part or None,
                "media": replied.photo[-1].file_id,
                "media_type": "photo",
                "buttons": [],
            }
        elif replied.video:
            filter_data = {
                "reply": reply_part or None,
                "media": replied.video.file_id,
                "media_type": "video",
                "buttons": [],
            }
        elif replied.document:
            filter_data = {
                "reply": reply_part or None,
                "media": replied.document.file_id,
                "media_type": "document",
                "buttons": [],
            }
        elif replied.audio:
            filter_data = {
                "reply": reply_part or None,
                "media": replied.audio.file_id,
                "media_type": "audio",
                "buttons": [],
            }
        elif replied.animation:
            filter_data = {
                "reply": reply_part or None,
                "media": replied.animation.file_id,
                "media_type": "animation",
                "buttons": [],
            }
        elif replied.sticker:
            filter_data = {
                "reply": None,
                "media": replied.sticker.file_id,
                "media_type": "sticker",
                "buttons": [],
            }
        elif replied.text:
            clean, buttons = extract_text_and_buttons(replied.text)
            filter_data = {
                "reply": clean,
                "media": None,
                "media_type": None,
                "buttons": buttons,
            }

    if not filter_data and reply_part:
        clean, buttons = extract_text_and_buttons(reply_part)
        filter_data = {
            "reply": clean,
            "media": None,
            "media_type": None,
            "buttons": buttons,
        }

    if not filter_data:
        await msg.reply_text(
            sc("please provide a reply text or reply to a media message.")
        )
        return

    await filters_db.add_filter(chat.id, keyword, filter_data)
    await msg.reply_text(
        f"✅ {sc('filter')} <code>{html.escape(keyword)}</code> {sc('saved.')}",
        parse_mode=ParseMode.HTML,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Command: /filters
# ─────────────────────────────────────────────────────────────────────────────

@group_only
async def cmd_filters(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """/filters — List all active filters for this chat."""
    msg = update.effective_message
    chat = update.effective_chat

    keywords = await filters_db.get_all_filters(chat.id)
    if not keywords:
        await msg.reply_text(sc("no filters set in this chat."))
        return

    page = 0
    await _send_filters_page(msg, chat.id, keywords, page)


async def _send_filters_page(
    msg: Message,
    chat_id: int,
    keywords: list[str],
    page: int,
) -> None:
    """Send one page of the filters list with navigation and delete buttons."""
    total = len(keywords)
    total_pages = (total - 1) // _FILTERS_PER_PAGE + 1
    start = page * _FILTERS_PER_PAGE
    end = start + _FILTERS_PER_PAGE
    page_keywords = keywords[start:end]

    lines = [f"<b>🔧 {sc('filters for this chat')} ({total})</b>\n"]
    for i, kw in enumerate(page_keywords, start=start + 1):
        lines.append(f"{i}. <code>{html.escape(kw)}</code>")

    text = "\n".join(lines)

    # Build keyboard: delete buttons + navigation
    keyboard: list[list[InlineKeyboardButton]] = []
    for kw in page_keywords:
        keyboard.append([
            InlineKeyboardButton(
                f"🗑 {kw}",
                callback_data=f"filter_del:{chat_id}:{kw}",
            )
        ])

    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton("⬅️", callback_data=f"filter_page:{chat_id}:{page - 1}")
        )
    if end < total:
        nav_row.append(
            InlineKeyboardButton("➡️", callback_data=f"filter_page:{chat_id}:{page + 1}")
        )
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([
        InlineKeyboardButton(
            f"🗑 {sc('stop all')}",
            callback_data=f"filter_stopall:{chat_id}",
        )
    ])

    markup = InlineKeyboardMarkup(keyboard)
    await msg.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)


# ─────────────────────────────────────────────────────────────────────────────
# Callback: pagination / delete
# ─────────────────────────────────────────────────────────────────────────────

async def cb_filter(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle inline button callbacks for the filters list."""
    query = update.callback_query
    user = update.effective_user
    if not query:
        return
    await query.answer()

    data = query.data or ""

    if data.startswith("filter_del:"):
        _, chat_id_str, keyword = data.split(":", 2)
        chat_id = int(chat_id_str)
        removed = await filters_db.remove_filter(chat_id, keyword)
        if removed:
            keywords = await filters_db.get_all_filters(chat_id)
            if keywords:
                await _edit_filters_page(query, chat_id, keywords, 0)
            else:
                await query.edit_message_text(sc("all filters have been removed."))
        else:
            await query.answer(sc("filter not found."), show_alert=True)

    elif data.startswith("filter_page:"):
        _, chat_id_str, page_str = data.split(":")
        chat_id = int(chat_id_str)
        page = int(page_str)
        keywords = await filters_db.get_all_filters(chat_id)
        await _edit_filters_page(query, chat_id, keywords, page)

    elif data.startswith("filter_stopall:"):
        _, chat_id_str = data.split(":", 1)
        chat_id = int(chat_id_str)
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    f"✅ {sc('yes, delete all')}",
                    callback_data=f"filter_stopall_confirm:{chat_id}",
                ),
                InlineKeyboardButton(
                    f"❌ {sc('cancel')}",
                    callback_data=f"filter_stopall_cancel:{chat_id}",
                ),
            ]
        ])
        await query.edit_message_text(
            sc("are you sure you want to remove all filters?"),
            reply_markup=keyboard,
        )

    elif data.startswith("filter_stopall_confirm:"):
        _, chat_id_str = data.split(":", 1)
        chat_id = int(chat_id_str)
        count = await filters_db.remove_all_filters(chat_id)
        await query.edit_message_text(
            f"✅ {sc('removed')} {count} {sc('filter(s).')}"
        )

    elif data.startswith("filter_stopall_cancel:"):
        await query.edit_message_text(sc("operation cancelled."))


async def _edit_filters_page(query, chat_id: int, keywords: list[str], page: int) -> None:
    """Edit the current message to show a different page of filters."""
    total = len(keywords)
    total_pages = (total - 1) // _FILTERS_PER_PAGE + 1
    start = page * _FILTERS_PER_PAGE
    end = start + _FILTERS_PER_PAGE
    page_keywords = keywords[start:end]

    lines = [f"<b>🔧 {sc('filters for this chat')} ({total})</b>\n"]
    for i, kw in enumerate(page_keywords, start=start + 1):
        lines.append(f"{i}. <code>{html.escape(kw)}</code>")

    text = "\n".join(lines)
    keyboard: list[list[InlineKeyboardButton]] = []
    for kw in page_keywords:
        keyboard.append([
            InlineKeyboardButton(
                f"🗑 {kw}",
                callback_data=f"filter_del:{chat_id}:{kw}",
            )
        ])

    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton("⬅️", callback_data=f"filter_page:{chat_id}:{page - 1}")
        )
    if end < total:
        nav_row.append(
            InlineKeyboardButton("➡️", callback_data=f"filter_page:{chat_id}:{page + 1}")
        )
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([
        InlineKeyboardButton(
            f"🗑 {sc('stop all')}",
            callback_data=f"filter_stopall:{chat_id}",
        )
    ])

    markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)


# ─────────────────────────────────────────────────────────────────────────────
# Command: /stop
# ─────────────────────────────────────────────────────────────────────────────

@group_only
@admin_required
async def cmd_stop(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """/stop <keyword> — Remove a keyword filter."""
    msg = update.effective_message
    chat = update.effective_chat

    if not context.args:
        await msg.reply_text(sc("usage: /stop <keyword>"))
        return

    keyword = " ".join(context.args)
    removed = await filters_db.remove_filter(chat.id, keyword)
    if removed:
        await msg.reply_text(
            f"✅ {sc('filter')} <code>{html.escape(keyword)}</code> {sc('removed.')}",
            parse_mode=ParseMode.HTML,
        )
    else:
        await msg.reply_text(
            f"❌ {sc('no filter found for')} <code>{html.escape(keyword)}</code>.",
            parse_mode=ParseMode.HTML,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Command: /stopall
# ─────────────────────────────────────────────────────────────────────────────

@group_only
@admin_required
async def cmd_stopall(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """/stopall — Remove all filters (with confirmation keyboard)."""
    msg = update.effective_message
    chat = update.effective_chat

    keywords = await filters_db.get_all_filters(chat.id)
    if not keywords:
        await msg.reply_text(sc("no filters to remove."))
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"✅ {sc('yes, remove all')}",
                callback_data=f"filter_stopall_confirm:{chat.id}",
            ),
            InlineKeyboardButton(
                f"❌ {sc('cancel')}",
                callback_data=f"filter_stopall_cancel:{chat.id}",
            ),
        ]
    ])
    await msg.reply_text(
        f"⚠️ {sc('this will remove all')} {len(keywords)} {sc('filters. are you sure?')}",
        reply_markup=keyboard,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Handler registration
# ─────────────────────────────────────────────────────────────────────────────

def register_handlers(app) -> None:
    """Register all filters handlers with the Application."""
    # Commands
    app.add_handler(CommandHandler("filter", cmd_filter))
    app.add_handler(CommandHandler("filters", cmd_filters))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("stopall", cmd_stopall))

    # Callback queries from inline buttons
    app.add_handler(CallbackQueryHandler(cb_filter, pattern=r"^filter_"))

    # Message handler (group text messages, low priority)
    app.add_handler(
        MessageHandler(
            tg_filters.ChatType.GROUPS & tg_filters.TEXT & ~tg_filters.COMMAND,
            handle_filter_message,
        ),
        group=10,
    )

    logger.info("Filters module handlers registered.")
