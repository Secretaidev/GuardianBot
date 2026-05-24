"""
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — Inline keyboard builders with nested category sub-menus.
Crafted by 𝐒𝐄𝐂𝐑𝐄𝐓
"""
from __future__ import annotations

import math
from typing import Any, List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.fonts import sc


# ── generic grid builder ─────────────────────────────────────────────────────

def build_menu(
    buttons: list[InlineKeyboardButton],
    n_cols: int,
    header_buttons: list[InlineKeyboardButton] | None = None,
    footer_buttons: list[InlineKeyboardButton] | None = None,
) -> list[list[InlineKeyboardButton]]:
    """Chunk buttons into rows of n_cols."""
    rows: list[list[InlineKeyboardButton]] = []
    if header_buttons:
        rows.append(header_buttons)
    for i in range(0, len(buttons), n_cols):
        rows.append(buttons[i : i + n_cols])
    if footer_buttons:
        rows.append(footer_buttons)
    return rows


def back_button(callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=f"🔙 {sc('back')}", callback_data=callback_data)


def close_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(text=f"❌ {sc('close')}", callback_data="help:close")


# ── pagination ───────────────────────────────────────────────────────────────

def paginate(
    items: list[Any], page: int, page_size: int, callback_prefix: str,
) -> list[InlineKeyboardButton]:
    total_pages = max(1, math.ceil(len(items) / page_size))
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(f"⬅ {sc('prev')}", callback_data=f"{callback_prefix}:{page - 1}"))
    nav.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="."))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(f"{sc('next')} ➡", callback_data=f"{callback_prefix}:{page + 1}"))
    return nav


# ── yes / no confirm ─────────────────────────────────────────────────────────

def confirm_keyboard(yes_callback: str, no_callback: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(f"✅ {sc('yes')}", callback_data=yes_callback),
        InlineKeyboardButton(f"❌ {sc('no')}", callback_data=no_callback),
    ]])


# ── category definitions ─────────────────────────────────────────────────────

CATEGORIES = {
    "mod": {
        "label": f"⚔️ {sc('moderation')}",
        "modules": [
            ("🛡", "admin",   "ADMIN"),
            ("🚫", "bans",    "BANS"),
            ("🔇", "mutes",   "MUTES"),
            ("⚠️", "warns",   "WARNS"),
            ("📣", "reports", "REPORTS"),
            ("📌", "pins",    "PINS"),
            ("🗑", "purge",   "PURGE"),
        ],
    },
    "auto": {
        "label": f"🤖 {sc('automation')}",
        "modules": [
            ("👋", "welcome",   "WELCOME"),
            ("🔍", "filters",   "FILTERS"),
            ("📝", "notes",     "NOTES"),
            ("🔒", "locks",     "LOCKS"),
            ("🚷", "blocklist", "BLOCKLIST"),
            ("🌊", "antiflood", "ANTIFLOOD"),
        ],
    },
    "adv": {
        "label": f"🌐 {sc('advanced')}",
        "modules": [
            ("📋", "rules",      "RULES"),
            ("🌐", "federation", "FEDERATION"),
            ("🔕", "disable",    "DISABLE"),
        ],
    },
    "owner": {
        "label": f"👑 {sc('owner')}",
        "modules": [
            ("📊", "stats",       "STATS"),
            ("🔧", "maintenance", "MAINTENANCE"),
            ("📡", "broadcast",   "BROADCAST"),
        ],
    },
}

# map MODULE_KEY -> category key for back navigation
_MODULE_TO_CAT: dict[str, str] = {}
for cat_key, cat_data in CATEGORIES.items():
    for _, _, mod_key in cat_data["modules"]:
        _MODULE_TO_CAT[mod_key] = cat_key


# ── main help menu (3 categories + owner + close) ────────────────────────────

def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(CATEGORIES["mod"]["label"],  callback_data="helpcat:mod"),
            InlineKeyboardButton(CATEGORIES["auto"]["label"], callback_data="helpcat:auto"),
        ],
        [
            InlineKeyboardButton(CATEGORIES["adv"]["label"],   callback_data="helpcat:adv"),
            InlineKeyboardButton(CATEGORIES["owner"]["label"], callback_data="helpcat:owner"),
        ],
        [close_button()],
    ])


# ── category sub-menu ────────────────────────────────────────────────────────

def category_keyboard(category: str) -> InlineKeyboardMarkup:
    """Build the sub-menu for a given category key (mod/auto/adv/owner)."""
    cat = CATEGORIES.get(category)
    if not cat:
        return InlineKeyboardMarkup([[back_button("help:main")]])

    btns = [
        InlineKeyboardButton(f"{emoji} {sc(name)}", callback_data=f"help:{key}")
        for emoji, name, key in cat["modules"]
    ]
    rows = build_menu(btns, n_cols=3, footer_buttons=[back_button("help:main")])
    return InlineKeyboardMarkup(rows)


# ── per-module help keyboard (back goes to parent category) ──────────────────

def module_help_keyboard(module_name: str) -> InlineKeyboardMarkup:
    cat_key = _MODULE_TO_CAT.get(module_name, "mod")
    return InlineKeyboardMarkup([
        [back_button(f"helpcat:{cat_key}"), close_button()],
    ])
