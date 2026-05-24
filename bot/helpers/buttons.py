"""
bot/helpers/buttons.py
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — Advanced inline keyboard builder utilities.

Provides:
  - build_menu()          — Generic grid-layout keyboard builder
  - back_button()         — Standard "back" button factory
  - paginate()            — Pagination button row generator
  - confirm_keyboard()    — Yes / No confirmation keyboard
  - main_menu_keyboard()  — Pre-built /help main-menu keyboard
  - module_help_keyboard()— Pre-built per-module help keyboard with back button
"""

from __future__ import annotations

import math
from typing import Any, List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.fonts import sc


# ─────────────────────────────────────────────────────────────────────────────
# Generic grid builder
# ─────────────────────────────────────────────────────────────────────────────

def build_menu(
    buttons: List[InlineKeyboardButton],
    n_cols: int,
    header_buttons: Optional[List[InlineKeyboardButton]] = None,
    footer_buttons: Optional[List[InlineKeyboardButton]] = None,
) -> List[List[InlineKeyboardButton]]:
    """
    Arrange *buttons* into rows of *n_cols* columns.

    Optionally prepend *header_buttons* as a standalone first row and append
    *footer_buttons* as a standalone last row.

    Returns the raw ``[[InlineKeyboardButton, ...], ...]`` list that can be
    passed directly to :class:`telegram.InlineKeyboardMarkup`.

    Example::

        btns = [InlineKeyboardButton(text=str(i), callback_data=str(i)) for i in range(6)]
        menu = build_menu(btns, n_cols=3)
        # → [[btn0, btn1, btn2], [btn3, btn4, btn5]]
        markup = InlineKeyboardMarkup(menu)
    """
    rows: List[List[InlineKeyboardButton]] = []

    if header_buttons:
        rows.append(header_buttons)

    # Split the flat button list into chunks of n_cols
    for i in range(0, len(buttons), n_cols):
        rows.append(buttons[i : i + n_cols])

    if footer_buttons:
        rows.append(footer_buttons)

    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Standard back button
# ─────────────────────────────────────────────────────────────────────────────

def back_button(callback_data: str) -> InlineKeyboardButton:
    """
    Return a single "🔙 ʙᴀᴄᴋ" :class:`telegram.InlineKeyboardButton` that
    triggers *callback_data* when pressed.
    """
    return InlineKeyboardButton(
        text=f"🔙 {sc('back')}",
        callback_data=callback_data,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Pagination
# ─────────────────────────────────────────────────────────────────────────────

def paginate(
    items: List[Any],
    page: int,
    page_size: int,
    callback_prefix: str,
) -> List[InlineKeyboardButton]:
    """
    Build a row of pagination navigation buttons for *items*.

    Args:
        items:           The full collection being paginated.
        page:            The current 0-based page index.
        page_size:       How many items appear per page.
        callback_prefix: String prefix for callback data.
                         Buttons emit ``{callback_prefix}:{page_number}``.

    Returns a list of up to three buttons: [⬅ ᴘʀᴇᴠ] [Page x/y] [ɴᴇxᴛ ➡].
    The current-page indicator button is non-interactive (callback_data=".").

    Example::

        btns = paginate(my_list, page=1, page_size=5, callback_prefix="page")
        # → [⬅ ᴘʀᴇᴠ btn, "2/4" btn, ɴᴇxᴛ ➡ btn]
    """
    total_pages = max(1, math.ceil(len(items) / page_size))
    nav_buttons: List[InlineKeyboardButton] = []

    # Previous page
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                text=f"⬅ {sc('prev')}",
                callback_data=f"{callback_prefix}:{page - 1}",
            )
        )

    # Current page indicator  (non-clickable — callback "." is a no-op)
    nav_buttons.append(
        InlineKeyboardButton(
            text=f"{page + 1}/{total_pages}",
            callback_data=".",
        )
    )

    # Next page
    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text=f"{sc('next')} ➡",
                callback_data=f"{callback_prefix}:{page + 1}",
            )
        )

    return nav_buttons


# ─────────────────────────────────────────────────────────────────────────────
# Yes / No confirmation keyboard
# ─────────────────────────────────────────────────────────────────────────────

def confirm_keyboard(
    yes_callback: str,
    no_callback: str,
) -> InlineKeyboardMarkup:
    """
    Return a two-button ✅ ʏᴇꜱ / ❌ ɴᴏ confirmation keyboard.

    Args:
        yes_callback: Callback data emitted when the user confirms.
        no_callback:  Callback data emitted when the user cancels.
    """
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=f"✅ {sc('yes')}",
                    callback_data=yes_callback,
                ),
                InlineKeyboardButton(
                    text=f"❌ {sc('no')}",
                    callback_data=no_callback,
                ),
            ]
        ]
    )


# ─────────────────────────────────────────────────────────────────────────────
# Pre-built /help navigation keyboards
# ─────────────────────────────────────────────────────────────────────────────

# All module names available in GuardianBot's help system
_MODULES: List[str] = [
    "ADMIN",
    "BANS",
    "MUTES",
    "WARNS",
    "WELCOME",
    "FILTERS",
    "NOTES",
    "LOCKS",
    "BLOCKLIST",
    "ANTIFLOOD",
    "REPORTS",
    "PINS",
    "PURGE",
    "RULES",
    "FEDERATION",
]


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Build the main /help menu keyboard.

    Each module in ``_MODULES`` becomes a button arranged in a 3-column grid.
    Pressing a button emits the callback ``help:MODULE_NAME``.
    """
    module_buttons: List[InlineKeyboardButton] = [
        InlineKeyboardButton(
            text=sc(name.lower()),
            callback_data=f"help:{name}",
        )
        for name in _MODULES
    ]

    rows = build_menu(module_buttons, n_cols=3)
    return InlineKeyboardMarkup(rows)


def module_help_keyboard(module_name: str) -> InlineKeyboardMarkup:
    """
    Build the per-module help keyboard.

    Contains a single "🔙 ʙᴀᴄᴋ" button that returns the user to the main
    help menu (callback data ``help:main``).

    Args:
        module_name: The module whose help page is currently being shown.
                     (Not used in the keyboard itself, kept for symmetry.)
    """
    return InlineKeyboardMarkup(
        [[back_button("help:main")]]
    )
