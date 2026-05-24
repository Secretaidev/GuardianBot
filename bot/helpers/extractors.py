"""
bot/helpers/extractors.py
─────────────────────────
Helpers to resolve a target user from an incoming Telegram Update.

Supported resolution strategies (in priority order):
  1. Replied-to message author
  2. @username mention in the command arguments
  3. Numeric user ID in the command arguments

Both ``extract_user`` and ``extract_user_and_reason`` return lightweight
dataclasses so callers never need to deal with raw tuples.

Also provides note/welcome button parsing:
  extract_text_and_buttons(raw_text) → (clean_text, [(label, url), ...])
  build_buttons(button_list)         → InlineKeyboardMarkup | None
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update, User
from telegram.error import TelegramError
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Button-syntax regex:  [Label](url)  or  [Label](buttonurl:url)
# ─────────────────────────────────────────────────────────────────────────────
_BUTTON_RE = re.compile(
    r"\[([^\[\]]+?)\]\(((?:buttonurl:|https?://|tg://)[^\)]+?)\)",
    re.IGNORECASE,
)


# ─────────────────────────────────────────────────────────────────────────────
# Return-value containers
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ExtractedUser:
    """Holds a resolved Telegram user together with any leftover text."""

    user: Optional[User]
    """The resolved User object, or *None* if resolution failed."""

    remaining_args: list[str] = field(default_factory=list)
    """Command arguments that were not consumed during user resolution."""

    error: Optional[str] = None
    """Human-readable error message (small-caps ready) if resolution failed."""


@dataclass
class ExtractedUserAndReason:
    """Holds a resolved user plus an optional free-text reason."""

    user: Optional[User]
    reason: Optional[str]
    error: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _user_from_username(username: str, bot) -> Optional[User]:
    """
    Try to fetch a User object by @username via get_chat().
    Returns None on any API error.
    """
    try:
        chat = await bot.get_chat(username)
        # get_chat on a user returns a Chat object; rebuild a minimal User
        return User(
            id=chat.id,
            first_name=chat.first_name or "",
            is_bot=False,
            last_name=chat.last_name,
            username=chat.username,
        )
    except TelegramError as exc:
        logger.debug("_user_from_username(%s) failed: %s", username, exc)
        return None


async def _user_from_id(user_id: int, bot, chat_id: int) -> Optional[User]:
    """
    Try to fetch a User object by numeric ID via get_chat_member().
    Returns None on any API error.
    """
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.user
    except TelegramError as exc:
        logger.debug("_user_from_id(%s) failed: %s", user_id, exc)
        # Fall back to get_chat for the user ID directly
        try:
            chat = await bot.get_chat(user_id)
            return User(
                id=chat.id,
                first_name=chat.first_name or str(user_id),
                is_bot=False,
                last_name=chat.last_name,
                username=chat.username,
            )
        except TelegramError:
            return None


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

async def extract_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> ExtractedUser:
    """
    Resolve the target user from *update*.

    Resolution order:
      1. Replied-to message author (args are preserved as remaining_args)
      2. First argument is @username  → fetch via API
      3. First argument is numeric ID → fetch via API

    Returns an :class:`ExtractedUser` where ``.user`` is *None* and
    ``.error`` is set if no user could be resolved.
    """
    msg: Optional[Message] = update.effective_message
    bot = context.bot
    chat_id = update.effective_chat.id if update.effective_chat else 0
    args: list[str] = context.args or []

    # ── Strategy 1: reply ────────────────────────────────────────────────────
    if msg and msg.reply_to_message and msg.reply_to_message.from_user:
        return ExtractedUser(
            user=msg.reply_to_message.from_user,
            remaining_args=args,  # keep all args for the caller
        )

    # ── Strategy 2 & 3: from first argument ──────────────────────────────────
    if not args:
        return ExtractedUser(
            user=None,
            error="please reply to a user or provide a username / user ID.",
        )

    target_arg = args[0]
    remaining = args[1:]

    if target_arg.startswith("@"):
        user = await _user_from_username(target_arg, bot)
        if user is None:
            return ExtractedUser(
                user=None,
                error=f"could not find user {target_arg}.",
            )
        return ExtractedUser(user=user, remaining_args=remaining)

    if target_arg.lstrip("-").isdigit():
        user_id = int(target_arg)
        user = await _user_from_id(user_id, bot, chat_id)
        if user is None:
            return ExtractedUser(
                user=None,
                error=f"could not find user with ID {user_id}.",
            )
        return ExtractedUser(user=user, remaining_args=remaining)

    return ExtractedUser(
        user=None,
        error="please reply to a user or provide a valid @username / user ID.",
    )


async def extract_user_and_reason(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> ExtractedUserAndReason:
    """
    Resolve the target user **and** an optional reason string.

    The reason is everything after the user specifier joined by spaces.
    When the user is resolved via a reply, the entire args list is the reason.

    Returns an :class:`ExtractedUserAndReason`.
    """
    extracted = await extract_user(update, context)

    if extracted.error or extracted.user is None:
        return ExtractedUserAndReason(
            user=None,
            reason=None,
            error=extracted.error,
        )

    msg: Optional[Message] = update.effective_message
    args: list[str] = context.args or []

    # When resolved via reply the full args list is the reason.
    if msg and msg.reply_to_message and msg.reply_to_message.from_user:
        reason = " ".join(args).strip() or None
    else:
        # The first arg was consumed as the user specifier.
        reason = " ".join(extracted.remaining_args).strip() or None

    return ExtractedUserAndReason(
        user=extracted.user,
        reason=reason,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Note / welcome text + button parsing
# ─────────────────────────────────────────────────────────────────────────────

def extract_text_and_buttons(
    raw_text: str,
) -> Tuple[str, List[Tuple[str, str]]]:
    """
    Parse a raw note / welcome string that may contain inline button
    definitions in the form ``[Label](url)`` or ``[Label](buttonurl:url)``.

    Returns ``(clean_text, button_list)`` where *button_list* is a list of
    ``(label, url)`` tuples in order of appearance, and *clean_text* has all
    button definitions stripped out.

    Example::

        raw = "Hello! [Website](https://example.com) [Docs](https://docs.example.com)"
        text, buttons = extract_text_and_buttons(raw)
        # text    → "Hello!"
        # buttons → [("Website", "https://example.com"), ("Docs", "https://docs.example.com")]
    """
    buttons: List[Tuple[str, str]] = []

    def _collect(match: re.Match) -> str:
        label = match.group(1).strip()
        url = match.group(2).strip()
        # Strip the 'buttonurl:' prefix if present
        if url.lower().startswith("buttonurl:"):
            url = url[len("buttonurl:"):]
        buttons.append((label, url))
        return ""  # Remove the button definition from the surrounding text

    clean_text = _BUTTON_RE.sub(_collect, raw_text)
    # Collapse leftover triple-newlines and strip leading/trailing whitespace
    clean_text = re.sub(r"\n{3,}", "\n\n", clean_text).strip()

    return clean_text, buttons


def build_buttons(
    button_list: List[Tuple[str, str]],
    buttons_per_row: int = 2,
) -> Optional[InlineKeyboardMarkup]:
    """
    Convert a list of ``(label, url)`` tuples into an
    :class:`telegram.InlineKeyboardMarkup`.

    Buttons are arranged in rows of *buttons_per_row* columns.
    Returns *None* if *button_list* is empty.

    Example::

        markup = build_buttons([("Google", "https://google.com"), ("Bing", "https://bing.com")])
        # → InlineKeyboardMarkup with one row: [Google] [Bing]
    """
    if not button_list:
        return None

    keyboard: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []

    for label, url in button_list:
        row.append(InlineKeyboardButton(text=label, url=url))
        if len(row) >= buttons_per_row:
            keyboard.append(row)
            row = []

    if row:  # Flush any remaining buttons in the last partial row
        keyboard.append(row)

    return InlineKeyboardMarkup(keyboard)


# ─────────────────────────────────────────────────────────────────────────────
# Button parsing helpers
# ─────────────────────────────────────────────────────────────────────────────

import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Pattern: [Button Text](url) or [Button Text](buttonurl:url) — optionally :same suffix
_BUTTON_PATTERN = re.compile(
    r"\[(?P<text>[^\[\]]+)\]\((?:buttonurl:)?(?P<url>https?://[^\s\)]+)(?P<same>:same)?\)"
)


def extract_text_and_buttons(
    raw_text: str,
) -> tuple[str, list[dict]]:
    """
    Parse *raw_text* for inline button syntax and split it into:
      - clean text (button markup removed)
      - list of button dicts: {"text": str, "url": str, "same_row": bool}

    Button syntax supported:
      [Button Label](https://example.com)
      [Button Label](buttonurl:https://example.com)
      [Button Label](buttonurl:https://example.com:same)   ← same row as previous

    Parameters
    ----------
    raw_text : str
        The raw message / note / welcome text that may contain button syntax.

    Returns
    -------
    (clean_text, buttons)
        clean_text : raw_text with all button markup stripped out
        buttons    : ordered list of button dicts
    """
    buttons: list[dict] = []
    for match in _BUTTON_PATTERN.finditer(raw_text):
        buttons.append(
            {
                "text": match.group("text").strip(),
                "url": match.group("url").strip(),
                "same_row": match.group("same") is not None,
            }
        )

    # Strip button markdown from the message text
    clean_text = _BUTTON_PATTERN.sub("", raw_text).strip()
    return clean_text, buttons


def build_buttons(
    buttons: list[dict],
) -> Optional[InlineKeyboardMarkup]:
    """
    Convert a list of button dicts (as produced by
    :func:`extract_text_and_buttons`) into a :class:`InlineKeyboardMarkup`.

    Buttons whose ``same_row`` flag is *True* are placed on the same row as
    the preceding button.  The first button always starts a new row.

    Parameters
    ----------
    buttons : list of dicts with keys "text", "url", "same_row"

    Returns
    -------
    InlineKeyboardMarkup | None
        Returns *None* when *buttons* is empty.
    """
    if not buttons:
        return None

    rows: list[list[InlineKeyboardButton]] = []
    current_row: list[InlineKeyboardButton] = []

    for btn in buttons:
        ib = InlineKeyboardButton(text=btn["text"], url=btn["url"])
        if btn.get("same_row") and current_row:
            current_row.append(ib)
        else:
            if current_row:
                rows.append(current_row)
            current_row = [ib]

    if current_row:
        rows.append(current_row)

    return InlineKeyboardMarkup(rows) if rows else None
