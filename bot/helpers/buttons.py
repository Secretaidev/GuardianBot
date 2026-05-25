"""
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — Interactive inline keyboard system.

3-level drill-down:
  Main Menu  →  Module (sub-buttons per command)  →  Command detail

Crafted by 𝐒𝐄𝐂𝐑𝐄𝐓
"""
from __future__ import annotations

import math
from typing import Any

from telegram import InlineKeyboardButton as Btn, InlineKeyboardMarkup

from bot.fonts import sc

# ── tiny helpers ──────────────────────────────────────────────────────────────

def _row(*btns): return list(btns)

def _back(cb: str) -> Btn:
    return Btn(f"🔙 {sc('back')}", callback_data=cb)

def _close() -> Btn:
    return Btn(f"❌ {sc('close')}", callback_data="help:close")


def build_menu(buttons: list[Btn], n_cols: int,
               header: list[Btn] | None = None,
               footer: list[Btn] | None = None) -> list[list[Btn]]:
    rows = []
    if header:
        rows.append(header)
    for i in range(0, len(buttons), n_cols):
        rows.append(buttons[i:i + n_cols])
    if footer:
        rows.append(footer)
    return rows


def paginate(items: list[Any], page: int, page_size: int, prefix: str) -> list[Btn]:
    pages = max(1, math.ceil(len(items) / page_size))
    nav = []
    if page > 0:
        nav.append(Btn(f"⬅ {sc('prev')}", callback_data=f"{prefix}:{page - 1}"))
    nav.append(Btn(f"{page + 1}/{pages}", callback_data="."))
    if page < pages - 1:
        nav.append(Btn(f"{sc('next')} ➡", callback_data=f"{prefix}:{page + 1}"))
    return nav


def confirm_keyboard(yes_cb: str, no_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [Btn(f"✅ {sc('yes')}", callback_data=yes_cb),
         Btn(f"❌ {sc('no')}", callback_data=no_cb)]
    ])


# ══════════════════════════════════════════════════════════════════════════════
# MODULE REGISTRY — each module has emoji, label, and sub-commands
# ══════════════════════════════════════════════════════════════════════════════

MODULES = {
    "BANS": {
        "emoji": "🚫",
        "cmds": {
            "ban":    "ʙᴀɴ ᴀ ᴜꜱᴇʀ ᴘᴇʀᴍᴀɴᴇɴᴛʟʏ.\nᴜꜱᴀɢᴇ: /ban <user> [reason]",
            "tban":   "ᴛᴇᴍᴘ ʙᴀɴ ꜰᴏʀ ᴀ ᴅᴜʀᴀᴛɪᴏɴ.\nᴜꜱᴀɢᴇ: /tban <user> <time> [reason]\nᴇx: /tban @user 2h spam",
            "unban":  "ᴜɴʙᴀɴ ᴀ ᴘʀᴇᴠɪᴏᴜꜱʟʏ ʙᴀɴɴᴇᴅ ᴜꜱᴇʀ.\nᴜꜱᴀɢᴇ: /unban <user>",
            "sban":   "ꜱɪʟᴇɴᴛ ʙᴀɴ — ᴅᴇʟᴇᴛᴇꜱ ᴛʜᴇ ᴄᴏᴍᴍᴀɴᴅ ᴍꜱɢ ᴛᴏᴏ.\nᴜꜱᴀɢᴇ: /sban <user>",
            "kick":   "ᴋɪᴄᴋ ᴀ ᴜꜱᴇʀ (ᴛʜᴇʏ ᴄᴀɴ ʀᴇᴊᴏɪɴ).\nᴜꜱᴀɢᴇ: /kick <user> [reason]",
            "kickme": "ᴋɪᴄᴋ ʏᴏᴜʀꜱᴇʟꜰ ꜰʀᴏᴍ ᴛʜᴇ ɢʀᴏᴜᴘ.",
        },
    },
    "MUTES": {
        "emoji": "🔇",
        "cmds": {
            "mute":   "ᴍᴜᴛᴇ ᴀ ᴜꜱᴇʀ ɪɴᴅᴇꜰɪɴɪᴛᴇʟʏ.\nᴜꜱᴀɢᴇ: /mute <user> [reason]",
            "tmute":  "ᴛᴇᴍᴘ ᴍᴜᴛᴇ ꜰᴏʀ ᴀ ᴅᴜʀᴀᴛɪᴏɴ.\nᴜꜱᴀɢᴇ: /tmute <user> <time>",
            "unmute": "ᴜɴᴍᴜᴛᴇ ᴀ ᴍᴜᴛᴇᴅ ᴜꜱᴇʀ.\nᴜꜱᴀɢᴇ: /unmute <user>",
            "smute":  "ꜱɪʟᴇɴᴛ ᴍᴜᴛᴇ — ɴᴏ ᴍᴇꜱꜱᴀɢᴇ, ᴊᴜꜱᴛ ᴍᴜᴛᴇ.\nᴜꜱᴀɢᴇ: /smute <user>",
        },
    },
    "WARNS": {
        "emoji": "⚠️",
        "cmds": {
            "warn":       "ɪꜱꜱᴜᴇ ᴀ ᴡᴀʀɴɪɴɢ.\nᴜꜱᴀɢᴇ: /warn <user> [reason]",
            "dwarn":      "ᴡᴀʀɴ + ᴅᴇʟᴇᴛᴇ ᴛʜᴇ ʀᴇᴘʟɪᴇᴅ ᴍꜱɢ.\nᴜꜱᴀɢᴇ: reply /dwarn [reason]",
            "unwarn":     "ʀᴇᴍᴏᴠᴇ ʟᴀꜱᴛ ᴡᴀʀɴɪɴɢ.\nᴜꜱᴀɢᴇ: /unwarn <user>",
            "resetwarns": "ᴄʟᴇᴀʀ ᴀʟʟ ᴡᴀʀɴꜱ ꜰᴏʀ ᴀ ᴜꜱᴇʀ.\nᴜꜱᴀɢᴇ: /resetwarns <user>",
            "warns":      "ᴠɪᴇᴡ ᴀ ᴜꜱᴇʀ'ꜱ ᴡᴀʀɴɪɴɢꜱ.\nᴜꜱᴀɢᴇ: /warns <user>",
            "warnlimit":  "ꜱᴇᴛ ᴡᴀʀɴ ʟɪᴍɪᴛ (ᴅᴇꜰᴀᴜʟᴛ 3).\nᴜꜱᴀɢᴇ: /warnlimit <n>",
            "warnmode":   "ꜱᴇᴛ ᴀᴄᴛɪᴏɴ ᴏɴ ʟɪᴍɪᴛ: ʙᴀɴ/ᴋɪᴄᴋ/ᴍᴜᴛᴇ.\nᴜꜱᴀɢᴇ: /warnmode <action>",
        },
    },
    "ADMIN": {
        "emoji": "🛡",
        "cmds": {
            "promote":   "ᴘʀᴏᴍᴏᴛᴇ ᴀ ᴜꜱᴇʀ ᴛᴏ ᴀᴅᴍɪɴ.\nᴜꜱᴀɢᴇ: /promote <user> [title]",
            "demote":    "ᴅᴇᴍᴏᴛᴇ ᴀɴ ᴀᴅᴍɪɴ.\nᴜꜱᴀɢᴇ: /demote <user>",
            "title":     "ꜱᴇᴛ ᴄᴜꜱᴛᴏᴍ ᴀᴅᴍɪɴ ᴛɪᴛʟᴇ (16 ᴄʜᴀʀ ᴍᴀx).\nᴜꜱᴀɢᴇ: /title <user> <title>",
            "adminlist": "ʟɪꜱᴛ ᴀʟʟ ᴀᴅᴍɪɴꜱ ɪɴ ᴛʜɪꜱ ɢʀᴏᴜᴘ.",
            "invitelink": "ɢᴇᴛ ᴛʜᴇ ɢʀᴏᴜᴘ ɪɴᴠɪᴛᴇ ʟɪɴᴋ.",
            "setgtitle": "ᴄʜᴀɴɢᴇ ɢʀᴏᴜᴘ ᴛɪᴛʟᴇ.\nᴜꜱᴀɢᴇ: /setgtitle <text>",
            "setgdesc":  "ᴄʜᴀɴɢᴇ ɢʀᴏᴜᴘ ᴅᴇꜱᴄʀɪᴘᴛɪᴏɴ.\nᴜꜱᴀɢᴇ: /setgdesc <text>",
        },
    },
    "PINS": {
        "emoji": "📌",
        "cmds": {
            "pin":      "ᴘɪɴ ᴛʜᴇ ʀᴇᴘʟɪᴇᴅ ᴍᴇꜱꜱᴀɢᴇ.\nᴜꜱᴀɢᴇ: reply /pin [loud]",
            "unpin":    "ᴜɴᴘɪɴ ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ ᴘɪɴɴᴇᴅ ᴍꜱɢ.",
            "unpinall": "ᴜɴᴘɪɴ ᴀʟʟ ᴘɪɴɴᴇᴅ ᴍᴇꜱꜱᴀɢᴇꜱ.",
            "pinned":   "ꜱʜᴏᴡ ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ ᴘɪɴɴᴇᴅ ᴍꜱɢ ʟɪɴᴋ.",
        },
    },
    "PURGE": {
        "emoji": "🗑",
        "cmds": {
            "purge": "ᴅᴇʟᴇᴛᴇ ᴍꜱɢꜱ ꜰʀᴏᴍ ʀᴇᴘʟʏ ᴛᴏ ɴᴏᴡ.\nᴜꜱᴀɢᴇ: reply /purge   ᴏʀ   /purge <n>",
            "del":   "ᴅᴇʟᴇᴛᴇ ᴛʜᴇ ʀᴇᴘʟɪᴇᴅ ᴍᴇꜱꜱᴀɢᴇ.\nᴜꜱᴀɢᴇ: reply /del",
        },
    },
    "REPORTS": {
        "emoji": "📣",
        "cmds": {
            "report":  "ʀᴇᴘᴏʀᴛ ᴀ ᴜꜱᴇʀ ᴛᴏ ᴀᴅᴍɪɴꜱ.\nᴜꜱᴀɢᴇ: reply /report  ᴏʀ  @admin",
            "reports": "ᴛᴏɢɢʟᴇ ʀᴇᴘᴏʀᴛ ɴᴏᴛɪꜰɪᴄᴀᴛɪᴏɴꜱ.\nᴜꜱᴀɢᴇ: /reports on|off",
        },
    },
    "WELCOME": {
        "emoji": "👋",
        "cmds": {
            "setwelcome":   "ꜱᴇᴛ ᴄᴜꜱᴛᴏᴍ ᴡᴇʟᴄᴏᴍᴇ ᴍꜱɢ.\nᴛᴇᴍᴘʟᴀᴛᴇꜱ: {first}, {chatname}, {count}\nʙᴜᴛᴛᴏɴꜱ: [ʟᴀʙᴇʟ](url)",
            "welcome":      "ᴛᴏɢɢʟᴇ ᴡᴇʟᴄᴏᴍᴇ ᴏɴ/ᴏꜰꜰ.\nᴜꜱᴀɢᴇ: /welcome on|off",
            "resetwelcome": "ʀᴇꜱᴛᴏʀᴇ ᴅᴇꜰᴀᴜʟᴛ ᴡᴇʟᴄᴏᴍᴇ ᴍꜱɢ.",
            "setgoodbye":   "ꜱᴇᴛ ɢᴏᴏᴅʙʏᴇ ᴍᴇꜱꜱᴀɢᴇ.\nᴜꜱᴀɢᴇ: /setgoodbye <text>",
            "cleanwelcome": "ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ᴏʟᴅ ᴡᴇʟᴄᴏᴍᴇꜱ.\nᴜꜱᴀɢᴇ: /cleanwelcome on|off",
        },
    },
    "FILTERS": {
        "emoji": "🔍",
        "cmds": {
            "filter":  "ᴀᴅᴅ ᴀɴ ᴀᴜᴛᴏ-ʀᴇᴘʟʏ ꜰɪʟᴛᴇʀ.\nᴜꜱᴀɢᴇ: /filter <keyword> <reply>\nꜱᴜᴘᴘᴏʀᴛꜱ ʙᴜᴛᴛᴏɴ ꜱʏɴᴛᴀx: [ʟᴀʙᴇʟ](url)",
            "stop":    "ʀᴇᴍᴏᴠᴇ ᴀ ꜰɪʟᴛᴇʀ.\nᴜꜱᴀɢᴇ: /stop <keyword>",
            "filters": "ʟɪꜱᴛ ᴀʟʟ ᴀᴄᴛɪᴠᴇ ꜰɪʟᴛᴇʀꜱ ɪɴ ᴛʜɪꜱ ᴄʜᴀᴛ.",
        },
    },
    "NOTES": {
        "emoji": "📝",
        "cmds": {
            "save":     "ꜱᴀᴠᴇ ᴀ ɴᴏᴛᴇ.\nᴜꜱᴀɢᴇ: /save <name> <content>",
            "get":      "ʀᴇᴛʀɪᴇᴠᴇ ᴀ ɴᴏᴛᴇ.\nᴜꜱᴀɢᴇ: /get <name>  ᴏʀ  #name",
            "clear":    "ᴅᴇʟᴇᴛᴇ ᴀ ɴᴏᴛᴇ.\nᴜꜱᴀɢᴇ: /clear <name>",
            "notes":    "ʟɪꜱᴛ ᴀʟʟ ꜱᴀᴠᴇᴅ ɴᴏᴛᴇꜱ ɪɴ ᴛʜɪꜱ ᴄʜᴀᴛ.",
            "clearall": "ᴅᴇʟᴇᴛᴇ ᴀʟʟ ɴᴏᴛᴇꜱ (ᴀᴅᴍɪɴ ᴏɴʟʏ).",
        },
    },
    "LOCKS": {
        "emoji": "🔒",
        "cmds": {
            "lock":   "ʟᴏᴄᴋ ᴀ ᴍᴇꜱꜱᴀɢᴇ ᴛʏᴘᴇ.\nᴜꜱᴀɢᴇ: /lock <type>\nᴛʏᴘᴇꜱ: text, media, sticker, gif, url, bot, forward, photo, video, voice, audio, document, poll, contact, location...",
            "unlock": "ᴜɴʟᴏᴄᴋ ᴀ ᴍᴇꜱꜱᴀɢᴇ ᴛʏᴘᴇ.\nᴜꜱᴀɢᴇ: /unlock <type>",
            "locks":  "ꜱʜᴏᴡ ᴄᴜʀʀᴇɴᴛ ʟᴏᴄᴋ ꜱᴛᴀᴛᴜꜱ ꜰᴏʀ ᴛʜɪꜱ ᴄʜᴀᴛ.",
        },
    },
    "BLOCKLIST": {
        "emoji": "🚷",
        "cmds": {
            "addblocklist":    "ᴀᴅᴅ ᴀ ᴡᴏʀᴅ ᴛᴏ ʙʟᴏᴄᴋʟɪꜱᴛ.\nᴜꜱᴀɢᴇ: /addblocklist <word>",
            "rmblocklist":     "ʀᴇᴍᴏᴠᴇ ᴀ ᴡᴏʀᴅ.\nᴜꜱᴀɢᴇ: /rmblocklist <word>",
            "blocklist":       "ᴠɪᴇᴡ ᴀʟʟ ʙʟᴏᴄᴋᴇᴅ ᴡᴏʀᴅꜱ.",
            "setblocklistmode": "ꜱᴇᴛ ᴀᴄᴛɪᴏɴ: ᴅᴇʟᴇᴛᴇ/ᴡᴀʀɴ/ᴍᴜᴛᴇ/ᴋɪᴄᴋ/ʙᴀɴ.\nᴜꜱᴀɢᴇ: /setblocklistmode <action>",
        },
    },
    "ANTIFLOOD": {
        "emoji": "🌊",
        "cmds": {
            "setflood":     "ꜱᴇᴛ ꜰʟᴏᴏᴅ ʟɪᴍɪᴛ (0 = ᴅɪꜱᴀʙʟᴇᴅ).\nᴜꜱᴀɢᴇ: /setflood <n>",
            "setfloodmode": "ꜱᴇᴛ ᴀᴄᴛɪᴏɴ: ʙᴀɴ/ᴋɪᴄᴋ/ᴍᴜᴛᴇ/ᴛʙᴀɴ/ᴛᴍᴜᴛᴇ.\nᴜꜱᴀɢᴇ: /setfloodmode <action>",
            "flood":        "ꜱʜᴏᴡ ᴄᴜʀʀᴇɴᴛ ᴀɴᴛɪ-ꜰʟᴏᴏᴅ ꜱᴇᴛᴛɪɴɢꜱ.",
        },
    },
    "RULES": {
        "emoji": "📋",
        "cmds": {
            "setrules":     "ꜱᴇᴛ ɢʀᴏᴜᴘ ʀᴜʟᴇꜱ.\nᴜꜱᴀɢᴇ: /setrules <text>",
            "rules":        "ꜱʜᴏᴡ ɢʀᴏᴜᴘ ʀᴜʟᴇꜱ.",
            "clearrules":   "ᴅᴇʟᴇᴛᴇ ᴛʜᴇ ɢʀᴏᴜᴘ ʀᴜʟᴇꜱ.",
            "privaterules": "ꜱᴇɴᴅ ʀᴜʟᴇꜱ ᴠɪᴀ ᴘᴍ ɪɴꜱᴛᴇᴀᴅ.\nᴜꜱᴀɢᴇ: /privaterules on|off",
        },
    },
    "FEDERATION": {
        "emoji": "🌐",
        "cmds": {
            "newfed":      "ᴄʀᴇᴀᴛᴇ ᴀ ɴᴇᴡ ꜰᴇᴅᴇʀᴀᴛɪᴏɴ.\nᴜꜱᴀɢᴇ: /newfed <name>",
            "joinfed":     "ᴊᴏɪɴ ᴀ ꜰᴇᴅ (ɢʀᴏᴜᴘ ᴀᴅᴍɪɴ).\nᴜꜱᴀɢᴇ: /joinfed <fed_id>",
            "leavefed":    "ʟᴇᴀᴠᴇ ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ ꜰᴇᴅ.",
            "fedban":      "ꜰᴇᴅ-ʙᴀɴ ᴀᴄʀᴏꜱꜱ ᴀʟʟ ʟɪɴᴋᴇᴅ ᴄʜᴀᴛꜱ.\nᴜꜱᴀɢᴇ: /fedban <user> [reason]",
            "unfedban":    "ʀᴇᴍᴏᴠᴇ ᴀ ꜰᴇᴅ ʙᴀɴ.\nᴜꜱᴀɢᴇ: /unfedban <user>",
            "fedinfo":     "ꜱʜᴏᴡ ꜰᴇᴅ ɪɴꜰᴏ.\nᴜꜱᴀɢᴇ: /fedinfo [fed_id]",
            "fedadmins":   "ʟɪꜱᴛ ꜰᴇᴅ ᴀᴅᴍɪɴꜱ.",
            "addfedadmin": "ᴀᴅᴅ ᴀ ꜰᴇᴅ ᴀᴅᴍɪɴ.\nᴜꜱᴀɢᴇ: /addfedadmin <user>",
            "rmfedadmin":  "ʀᴇᴍᴏᴠᴇ ᴀ ꜰᴇᴅ ᴀᴅᴍɪɴ.\nᴜꜱᴀɢᴇ: /rmfedadmin <user>",
        },
    },
    "DISABLE": {
        "emoji": "🔕",
        "cmds": {
            "disable":     "ᴅɪꜱᴀʙʟᴇ ᴀ ᴄᴏᴍᴍᴀɴᴅ ɪɴ ᴛʜɪꜱ ᴄʜᴀᴛ.\nᴜꜱᴀɢᴇ: /disable <cmd>",
            "enable":      "ʀᴇ-ᴇɴᴀʙʟᴇ ᴀ ᴅɪꜱᴀʙʟᴇᴅ ᴄᴏᴍᴍᴀɴᴅ.\nᴜꜱᴀɢᴇ: /enable <cmd>",
            "disabled":    "ʟɪꜱᴛ ᴀʟʟ ᴅɪꜱᴀʙʟᴇᴅ ᴄᴏᴍᴍᴀɴᴅꜱ.",
            "disableable": "ʟɪꜱᴛ ᴀʟʟ ᴅɪꜱᴀʙʟᴇ-ᴄᴀᴘᴀʙʟᴇ ᴄᴏᴍᴍᴀɴᴅꜱ.",
        },
    },
    "STATS": {
        "emoji": "📊",
        "cmds": {
            "stats":     "ꜱʜᴏᴡ ʙᴏᴛ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ.\nᴏᴡɴᴇʀ/ꜱᴜᴅᴏ ᴏɴʟʏ.",
            "broadcast": "ꜱᴇɴᴅ ᴀ ᴍꜱɢ ᴛᴏ ᴀʟʟ ɢʀᴏᴜᴘꜱ.\nᴏᴡɴᴇʀ ᴏɴʟʏ.\nᴜꜱᴀɢᴇ: /broadcast <message>",
        },
    },
    "MAINTENANCE": {
        "emoji": "🔧",
        "cmds": {
            "maintenance": "ᴛᴏɢɢʟᴇ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ.\nʙʀᴏᴀᴅᴄᴀꜱᴛꜱ ᴛᴏ ᴀʟʟ ᴄʜᴀᴛꜱ + ᴅᴍꜱ.\nᴏᴡɴᴇʀ ᴏɴʟʏ.\nᴜꜱᴀɢᴇ: /maintenance on|off|status",
        },
    },
}

# reverse map: command → module key
_CMD_TO_MOD = {}
for mod_key, mod_data in MODULES.items():
    for cmd in mod_data["cmds"]:
        _CMD_TO_MOD[cmd] = mod_key


# ══════════════════════════════════════════════════════════════════════════════
# LEVEL 1 — Main help menu (all modules as direct buttons, 3 columns)
# ══════════════════════════════════════════════════════════════════════════════

def main_menu_keyboard() -> InlineKeyboardMarkup:
    """All modules shown directly — no category layer."""
    btns = [
        Btn(f"{data['emoji']} {sc(key.lower())}", callback_data=f"help:{key}")
        for key, data in MODULES.items()
    ]
    rows = build_menu(btns, n_cols=3, footer=[_close()])
    return InlineKeyboardMarkup(rows)


# ══════════════════════════════════════════════════════════════════════════════
# LEVEL 2 — Module sub-menu (each command is a button)
# ══════════════════════════════════════════════════════════════════════════════

def module_help_keyboard(module_name: str) -> InlineKeyboardMarkup:
    """Show each command as a clickable sub-button."""
    mod = MODULES.get(module_name)
    if not mod:
        return InlineKeyboardMarkup([[_back("help:main")]])

    btns = [
        Btn(f"/{cmd}", callback_data=f"cmd:{module_name}:{cmd}")
        for cmd in mod["cmds"]
    ]
    rows = build_menu(btns, n_cols=3, footer=[_back("help:main"), _close()])
    return InlineKeyboardMarkup(rows)


# ══════════════════════════════════════════════════════════════════════════════
# LEVEL 3 — Command detail (text shown above, keyboard below)
# ══════════════════════════════════════════════════════════════════════════════

def command_detail_keyboard(module_name: str) -> InlineKeyboardMarkup:
    """Back to module sub-menu + close."""
    return InlineKeyboardMarkup([
        [_back(f"help:{module_name}"), _close()],
    ])


def get_command_detail(module_name: str, cmd: str) -> str | None:
    """Return the detail text for a specific command."""
    mod = MODULES.get(module_name)
    if not mod:
        return None
    return mod["cmds"].get(cmd)


def get_module_header(module_name: str) -> str:
    """Return formatted header for a module."""
    mod = MODULES.get(module_name)
    if not mod:
        return f"❓ {sc('unknown module')}"
    emoji = mod["emoji"]
    cmds = mod["cmds"]
    lines = [f"{emoji} <b>{sc(module_name.lower() + ' commands')}</b>\n"]
    for cmd, desc in cmds.items():
        first_line = desc.split("\n")[0]
        lines.append(f"• <code>/{cmd}</code> — {first_line}")
    return "\n".join(lines)


# keep old name for compatibility
def category_keyboard(category: str) -> InlineKeyboardMarkup:
    return main_menu_keyboard()
