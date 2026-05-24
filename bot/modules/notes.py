"""
bot/modules/notes.py
────────────────────
Saved notes module for ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ.

Commands
--------
/save <name> <content>     – Save a text note
/save <name>               – (reply to media) Save a media note
#<name>                    – Retrieve a note in any message
/get <name>                – Retrieve a note via command
/notes                     – List all notes (paginated, with delete buttons)
/clear <name>              – Delete a specific note
/clearall                  – Delete all notes (with confirmation)

Note types: text, photo, video, document, audio, sticker, animation.
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

from bot.database import notes_db
from bot.fonts import sc
from bot.helpers.decorators import admin_required, group_only
from bot.helpers.extractors import build_buttons, extract_text_and_buttons

logger = logging.getLogger(__name__)

# Notes per page in the /notes list
_NOTES_PER_PAGE = 15

# Pattern to detect #notename in messages
_HASH_NOTE_PATTERN = re.compile(r"(?<!\S)#([a-zA-Z0-9_]+)", re.UNICODE)


# ─────────────────────────────────────────────────────────────────────────────
# Helper: send a saved note to a chat
# ─────────────────────────────────────────────────────────────────────────────

async def _send_note(
    message: Message,
    note_doc: dict,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Send a saved note document as a reply to *message*.

    note_doc["note_data"] has:
      type       : str  – 'text'|'photo'|'video'|'document'|'audio'|'sticker'|'animation'
      content    : str  – text or file_id
      caption    : str|None – caption for media
      buttons    : list – button dicts
    """
    nd: dict = note_doc.get("note_data", {})
    note_type: str = nd.get("type", "text")
    content: Optional[str] = nd.get("content")
    caption: Optional[str] = nd.get("caption")
    buttons: list[dict] = nd.get("buttons", [])
    markup = build_buttons(buttons)

    try:
        if note_type == "text":
            await message.reply_text(
                text=content or sc("(empty note)"),
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
                disable_web_page_preview=True,
            )
        elif note_type == "photo":
            await message.reply_photo(
                photo=content,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
        elif note_type == "video":
            await message.reply_video(
                video=content,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
        elif note_type == "document":
            await message.reply_document(
                document=content,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
        elif note_type == "audio":
            await message.reply_audio(
                audio=content,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
        elif note_type == "sticker":
            await message.reply_sticker(sticker=content)
        elif note_type == "animation":
            await message.reply_animation(
                animation=content,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
        else:
            await message.reply_text(
                text=content or sc("(empty note)"),
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
    except TelegramError as exc:
        logger.warning("Failed to send note: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Command: /save
# ─────────────────────────────────────────────────────────────────────────────

@group_only
@admin_required
async def cmd_save(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """/save <name> [content] — Save a note, optionally replying to media."""
    msg = update.effective_message
    chat = update.effective_chat

    if not context.args:
        await msg.reply_text(
            f"<b>{sc('usage')}:</b>\n"
            f"<code>/save notename note text here</code>\n"
            f"<i>{sc('or reply to media with')} /save notename</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    note_name = context.args[0].lower().strip()
    if not re.match(r"^[a-zA-Z0-9_]+$", note_name):
        await msg.reply_text(
            sc("note names can only contain letters, numbers, and underscores.")
        )
        return

    content_text = " ".join(context.args[1:]) if len(context.args) > 1 else None
    replied = msg.reply_to_message
    note_data: dict = {}

    # Determine note type from replied-to media
    if replied:
        if replied.photo:
            caption, buttons = extract_text_and_buttons(
                content_text or replied.caption or ""
            )
            note_data = {
                "type": "photo",
                "content": replied.photo[-1].file_id,
                "caption": caption or None,
                "buttons": buttons,
            }
        elif replied.video:
            caption, buttons = extract_text_and_buttons(
                content_text or replied.caption or ""
            )
            note_data = {
                "type": "video",
                "content": replied.video.file_id,
                "caption": caption or None,
                "buttons": buttons,
            }
        elif replied.document:
            caption, buttons = extract_text_and_buttons(
                content_text or replied.caption or ""
            )
            note_data = {
                "type": "document",
                "content": replied.document.file_id,
                "caption": caption or None,
                "buttons": buttons,
            }
        elif replied.audio:
            caption, buttons = extract_text_and_buttons(
                content_text or replied.caption or ""
            )
            note_data = {
                "type": "audio",
                "content": replied.audio.file_id,
                "caption": caption or None,
                "buttons": buttons,
            }
        elif replied.sticker:
            note_data = {
                "type": "sticker",
                "content": replied.sticker.file_id,
                "caption": None,
                "buttons": [],
            }
        elif replied.animation:
            caption, buttons = extract_text_and_buttons(
                content_text or replied.caption or ""
            )
            note_data = {
                "type": "animation",
                "content": replied.animation.file_id,
                "caption": caption or None,
                "buttons": buttons,
            }
        elif replied.text and not content_text:
            clean, buttons = extract_text_and_buttons(replied.text)
            note_data = {
                "type": "text",
                "content": clean,
                "caption": None,
                "buttons": buttons,
            }

    if not note_data and content_text:
        clean, buttons = extract_text_and_buttons(content_text)
        note_data = {
            "type": "text",
            "content": clean,
            "caption": None,
            "buttons": buttons,
        }

    if not note_data:
        await msg.reply_text(
            sc("please provide content or reply to a message to save as a note.")
        )
        return

    await notes_db.save_note(chat.id, note_name, note_data)
    await msg.reply_text(
        f"✅ {sc('note')} <code>{html.escape(note_name)}</code> {sc('saved!')}",
        parse_mode=ParseMode.HTML,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Command: /get
# ─────────────────────────────────────────────────────────────────────────────

@group_only
async def cmd_get(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """/get <name> — Retrieve and display a saved note."""
    msg = update.effective_message
    chat = update.effective_chat

    if not context.args:
        await msg.reply_text(sc("usage: /get <note name>"))
        return

    note_name = context.args[0].lower().strip()
    note_doc = await notes_db.get_note(chat.id, note_name)
    if not note_doc:
        await msg.reply_text(
            f"❌ {sc('no note found with name')} <code>{html.escape(note_name)}</code>.",
            parse_mode=ParseMode.HTML,
        )
        return

    await _send_note(msg, note_doc, context)


# ─────────────────────────────────────────────────────────────────────────────
# Message handler: #notename trigger
# ─────────────────────────────────────────────────────────────────────────────

async def handle_hash_note(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Detect #notename in any group message and reply with the note."""
    msg = update.effective_message
    chat = update.effective_chat
    if not msg or not chat:
        return

    text = msg.text or msg.caption or ""
    matches = _HASH_NOTE_PATTERN.findall(text)
    if not matches:
        return

    # Only respond to the first matching note per message
    for note_name in matches:
        note_doc = await notes_db.get_note(chat.id, note_name.lower())
        if note_doc:
            await _send_note(msg, note_doc, context)
            break


# ─────────────────────────────────────────────────────────────────────────────
# Command: /notes
# ─────────────────────────────────────────────────────────────────────────────

@group_only
async def cmd_notes(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """/notes — Show a paginated list of all saved notes."""
    msg = update.effective_message
    chat = update.effective_chat

    note_names = await notes_db.get_all_notes(chat.id)
    if not note_names:
        await msg.reply_text(sc("no notes saved in this chat."))
        return

    await _send_notes_page(msg, chat.id, note_names, page=0)


async def _send_notes_page(
    msg: Message,
    chat_id: int,
    note_names: list[str],
    page: int,
) -> None:
    """Render and send one page of the notes list."""
    total = len(note_names)
    start = page * _NOTES_PER_PAGE
    end = start + _NOTES_PER_PAGE
    page_names = note_names[start:end]

    lines = [f"<b>📝 {sc('notes in this chat')} ({total})</b>\n"]
    for i, name in enumerate(page_names, start=start + 1):
        lines.append(f"{i}. <code>#{html.escape(name)}</code>")

    text = "\n".join(lines)

    keyboard: list[list[InlineKeyboardButton]] = []
    # Delete buttons for each note on this page
    for name in page_names:
        keyboard.append([
            InlineKeyboardButton(
                f"🗑 #{name}",
                callback_data=f"note_del:{chat_id}:{name}",
            )
        ])

    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton("⬅️", callback_data=f"note_page:{chat_id}:{page - 1}")
        )
    if end < total:
        nav_row.append(
            InlineKeyboardButton("➡️", callback_data=f"note_page:{chat_id}:{page + 1}")
        )
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([
        InlineKeyboardButton(
            f"🗑 {sc('clear all')}",
            callback_data=f"note_clearall:{chat_id}",
        )
    ])

    markup = InlineKeyboardMarkup(keyboard)
    await msg.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)


# ─────────────────────────────────────────────────────────────────────────────
# Callback: paginate / delete notes
# ─────────────────────────────────────────────────────────────────────────────

async def cb_notes(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle inline button callbacks for the notes list."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    data = query.data or ""

    if data.startswith("note_del:"):
        _, chat_id_str, note_name = data.split(":", 2)
        chat_id = int(chat_id_str)
        deleted = await notes_db.delete_note(chat_id, note_name)
        if deleted:
            note_names = await notes_db.get_all_notes(chat_id)
            if note_names:
                await _edit_notes_page(query, chat_id, note_names, 0)
            else:
                await query.edit_message_text(sc("all notes have been removed."))
        else:
            await query.answer(sc("note not found."), show_alert=True)

    elif data.startswith("note_page:"):
        _, chat_id_str, page_str = data.split(":")
        chat_id = int(chat_id_str)
        page = int(page_str)
        note_names = await notes_db.get_all_notes(chat_id)
        await _edit_notes_page(query, chat_id, note_names, page)

    elif data.startswith("note_clearall:"):
        _, chat_id_str = data.split(":", 1)
        chat_id = int(chat_id_str)
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    f"✅ {sc('yes, clear all')}",
                    callback_data=f"note_clearall_confirm:{chat_id}",
                ),
                InlineKeyboardButton(
                    f"❌ {sc('cancel')}",
                    callback_data=f"note_clearall_cancel:{chat_id}",
                ),
            ]
        ])
        await query.edit_message_text(
            sc("are you sure you want to delete all notes?"),
            reply_markup=keyboard,
        )

    elif data.startswith("note_clearall_confirm:"):
        _, chat_id_str = data.split(":", 1)
        chat_id = int(chat_id_str)
        count = await notes_db.delete_all_notes(chat_id)
        await query.edit_message_text(
            f"✅ {sc('deleted')} {count} {sc('note(s).')}"
        )

    elif data.startswith("note_clearall_cancel:"):
        await query.edit_message_text(sc("operation cancelled."))


async def _edit_notes_page(query, chat_id: int, note_names: list[str], page: int) -> None:
    """Edit the current message to show a different page of notes."""
    total = len(note_names)
    start = page * _NOTES_PER_PAGE
    end = start + _NOTES_PER_PAGE
    page_names = note_names[start:end]

    lines = [f"<b>📝 {sc('notes in this chat')} ({total})</b>\n"]
    for i, name in enumerate(page_names, start=start + 1):
        lines.append(f"{i}. <code>#{html.escape(name)}</code>")

    text = "\n".join(lines)

    keyboard: list[list[InlineKeyboardButton]] = []
    for name in page_names:
        keyboard.append([
            InlineKeyboardButton(
                f"🗑 #{name}",
                callback_data=f"note_del:{chat_id}:{name}",
            )
        ])

    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton("⬅️", callback_data=f"note_page:{chat_id}:{page - 1}")
        )
    if end < total:
        nav_row.append(
            InlineKeyboardButton("➡️", callback_data=f"note_page:{chat_id}:{page + 1}")
        )
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([
        InlineKeyboardButton(
            f"🗑 {sc('clear all')}",
            callback_data=f"note_clearall:{chat_id}",
        )
    ])

    markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)


# ─────────────────────────────────────────────────────────────────────────────
# Command: /clear
# ─────────────────────────────────────────────────────────────────────────────

@group_only
@admin_required
async def cmd_clear(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """/clear <name> — Delete a specific note."""
    msg = update.effective_message
    chat = update.effective_chat

    if not context.args:
        await msg.reply_text(sc("usage: /clear <note name>"))
        return

    note_name = context.args[0].lower().strip()
    deleted = await notes_db.delete_note(chat.id, note_name)
    if deleted:
        await msg.reply_text(
            f"✅ {sc('note')} <code>{html.escape(note_name)}</code> {sc('deleted.')}",
            parse_mode=ParseMode.HTML,
        )
    else:
        await msg.reply_text(
            f"❌ {sc('note')} <code>{html.escape(note_name)}</code> {sc('not found.')}",
            parse_mode=ParseMode.HTML,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Command: /clearall
# ─────────────────────────────────────────────────────────────────────────────

@group_only
@admin_required
async def cmd_clearall(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """/clearall — Delete all saved notes (with confirmation)."""
    msg = update.effective_message
    chat = update.effective_chat

    note_names = await notes_db.get_all_notes(chat.id)
    if not note_names:
        await msg.reply_text(sc("no notes to clear."))
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"✅ {sc('yes, clear all')}",
                callback_data=f"note_clearall_confirm:{chat.id}",
            ),
            InlineKeyboardButton(
                f"❌ {sc('cancel')}",
                callback_data=f"note_clearall_cancel:{chat.id}",
            ),
        ]
    ])
    await msg.reply_text(
        f"⚠️ {sc('this will delete all')} {len(note_names)} {sc('notes. continue?')}",
        reply_markup=keyboard,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Handler registration
# ─────────────────────────────────────────────────────────────────────────────

def register_handlers(app) -> None:
    """Register all notes handlers with the Application."""
    app.add_handler(CommandHandler("save", cmd_save))
    app.add_handler(CommandHandler("get", cmd_get))
    app.add_handler(CommandHandler("notes", cmd_notes))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("clearall", cmd_clearall))

    app.add_handler(CallbackQueryHandler(cb_notes, pattern=r"^note_"))

    # #notename handler for all group text messages
    app.add_handler(
        MessageHandler(
            tg_filters.ChatType.GROUPS & tg_filters.TEXT & ~tg_filters.COMMAND,
            handle_hash_note,
        ),
        group=11,
    )

    logger.info("Notes module handlers registered.")
