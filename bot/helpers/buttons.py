"""
Rose — Inline keyboard system.
Clean, fast, Rose-style 3-level navigation.
"""
from __future__ import annotations
from typing import Any
import math

from telegram import InlineKeyboardButton as Btn, InlineKeyboardMarkup


# ── helpers ───────────────────────────────────────────────────────────────────

def _back(cb: str) -> Btn:
    return Btn("« Back", callback_data=cb)

def _close() -> Btn:
    return Btn("Close", callback_data="help:close")

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
        nav.append(Btn("«", callback_data=f"{prefix}:{page - 1}"))
    nav.append(Btn(f"{page + 1}/{pages}", callback_data="."))
    if page < pages - 1:
        nav.append(Btn("»", callback_data=f"{prefix}:{page + 1}"))
    return nav

def confirm_keyboard(yes_cb: str, no_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [Btn("Yes", callback_data=yes_cb), Btn("No", callback_data=no_cb)]
    ])


# ══════════════════════════════════════════════════════════════════════════════
# MODULE REGISTRY — 27 modules, Rose-style
# ══════════════════════════════════════════════════════════════════════════════

MODULES = {
    "ADMIN": {
        "label": "Admin",
        "desc": "Manage admins, promotions, and group settings.",
        "cmds": {
            "promote":    "Promote a user to admin.\nUsage: /promote <user> [title]",
            "demote":     "Demote an admin.\nUsage: /demote <user>",
            "title":      "Set custom admin title (max 16 chars).\nUsage: /title <user> <title>",
            "adminlist":  "List all admins in this group.",
            "invitelink": "Get the group invite link.",
            "setgtitle":  "Change group title.\nUsage: /setgtitle <text>",
            "setgdesc":   "Change group description.\nUsage: /setgdesc <text>",
        },
    },
    "ANTIFLOOD": {
        "label": "Antiflood",
        "desc": "Prevent message flooding in your group.",
        "cmds": {
            "setflood":     "Set flood limit (0 = disabled).\nUsage: /setflood <n>",
            "setfloodmode": "Set action: ban/kick/mute/tban/tmute.\nUsage: /setfloodmode <action>",
            "flood":        "Show current anti-flood settings.",
        },
    },
    "ANTIRAID": {
        "label": "AntiRaid",
        "desc": "Protect against mass-join raids.",
        "cmds": {
            "antiraid":       "Toggle anti-raid mode.\nUsage: /antiraid on|off",
            "raidtime":       "Set raid mode duration.\nUsage: /raidtime <time>",
            "raidactionmode": "Set raid action: ban/kick/mute.\nUsage: /raidactionmode <action>",
        },
    },
    "APPROVAL": {
        "label": "Approval",
        "desc": "Approve users to bypass locks, blocklist, and antiflood.",
        "cmds": {
            "approve":   "Approve a user.\nUsage: /approve <user>",
            "unapprove": "Remove approval.\nUsage: /unapprove <user>",
            "approved":  "List all approved users.",
        },
    },
    "BANS": {
        "label": "Bans",
        "desc": "Ban and unban users from your group.",
        "cmds": {
            "ban":    "Ban a user permanently.\nUsage: /ban <user> [reason]",
            "tban":   "Temp ban for a duration.\nUsage: /tban <user> <time> [reason]",
            "unban":  "Unban a previously banned user.\nUsage: /unban <user>",
            "sban":   "Silent ban — deletes the command msg too.\nUsage: /sban <user>",
            "kick":   "Kick a user (they can rejoin).\nUsage: /kick <user> [reason]",
            "kickme": "Kick yourself from the group.",
        },
    },
    "BLOCKLISTS": {
        "label": "Blocklists",
        "desc": "Manage word blocklists to auto-moderate messages.",
        "cmds": {
            "addblocklist":    "Add a trigger to blocklist.\nUsage: /addblocklist <trigger>",
            "rmblocklist":     "Remove a trigger.\nUsage: /rmblocklist <trigger>",
            "blocklist":       "Show all blocklisted words.",
            "setblocklistmode": "Set action: ban/kick/mute/warn/delete.\nUsage: /setblocklistmode <mode>",
        },
    },
    "CAPTCHA": {
        "label": "CAPTCHA",
        "desc": "Verify new members with CAPTCHA.",
        "cmds": {
            "captcha":     "Toggle CAPTCHA for new members.\nUsage: /captcha on|off",
            "captchamode": "Set CAPTCHA type: button/math.\nUsage: /captchamode <type>",
            "captchatime": "Set time to solve before kick.\nUsage: /captchatime <time>",
        },
    },
    "CLEANCMDS": {
        "label": "Clean Cmds",
        "desc": "Auto-delete bot commands and service messages.",
        "cmds": {
            "cleancmds":    "Auto-delete command messages.\nUsage: /cleancmds on|off",
            "cleanservice": "Auto-delete service messages.\nUsage: /cleanservice on|off",
        },
    },
    "CONNECTIONS": {
        "label": "Connections",
        "desc": "Connect to a group from PM to manage settings.",
        "cmds": {
            "connect":    "Connect to a group from PM.\nUsage: /connect <chat_id>",
            "disconnect": "Disconnect from the connected group.",
            "connection": "Show your current connection.",
        },
    },
    "DISABLE": {
        "label": "Disabling",
        "desc": "Disable specific commands in your group.",
        "cmds": {
            "disable":     "Disable a command.\nUsage: /disable <cmd>",
            "enable":      "Re-enable a disabled command.\nUsage: /enable <cmd>",
            "disabled":    "List all disabled commands.",
            "disableable": "List all disable-capable commands.",
        },
    },
    "FEDERATION": {
        "label": "Federations",
        "desc": "Link groups together and share bans.",
        "cmds": {
            "newfed":      "Create a new federation.\nUsage: /newfed <name>",
            "joinfed":     "Join a federation.\nUsage: /joinfed <fed_id>",
            "leavefed":    "Leave the current federation.",
            "fedban":      "Fed-ban across all linked chats.\nUsage: /fedban <user> [reason]",
            "unfedban":    "Remove a fed ban.\nUsage: /unfedban <user>",
            "fedinfo":     "Show federation info.\nUsage: /fedinfo [fed_id]",
            "fedadmins":   "List federation admins.",
            "addfedadmin": "Add a fed admin.\nUsage: /addfedadmin <user>",
            "rmfedadmin":  "Remove a fed admin.\nUsage: /rmfedadmin <user>",
        },
    },
    "FILTERS": {
        "label": "Filters",
        "desc": "Set auto-reply triggers for keywords.",
        "cmds": {
            "filter":  "Set a filter.\nUsage: /filter <keyword> <reply>",
            "stop":    "Remove a filter.\nUsage: /stop <keyword>",
            "filters": "List all active filters.",
        },
    },
    "FORMATTING": {
        "label": "Formatting",
        "desc": "Learn how to format text in Telegram.",
        "cmds": {
            "markdownhelp": "Show markdown formatting guide.",
        },
    },
    "GREETINGS": {
        "label": "Greetings",
        "desc": "Welcome and goodbye messages for your group.",
        "cmds": {
            "setwelcome":    "Set welcome message.\nUsage: /setwelcome <text>",
            "welcome":       "Toggle welcome messages.\nUsage: /welcome on|off",
            "setgoodbye":    "Set goodbye message.\nUsage: /setgoodbye <text>",
            "goodbye":       "Toggle goodbye messages.\nUsage: /goodbye on|off",
            "cleanwelcome":  "Delete old welcome messages.\nUsage: /cleanwelcome on|off",
            "resetwelcome":  "Reset welcome to default.",
            "resetgoodbye":  "Reset goodbye to default.",
        },
    },
    "LOCKS": {
        "label": "Locks",
        "desc": "Lock specific message types in your group.",
        "cmds": {
            "lock":   "Lock a permission.\nUsage: /lock <type>\nTypes: sticker, gif, url, photo, video, voice, document, forward, game, poll",
            "unlock": "Unlock a permission.\nUsage: /unlock <type>",
            "locks":  "Show current lock status.",
        },
    },
    "LOGCHANNEL": {
        "label": "Log Channels",
        "desc": "Log admin actions to a dedicated channel.",
        "cmds": {
            "logchannel": "Get current log channel.",
            "setlog":     "Set a log channel.\nUsage: Run in the target channel",
            "unsetlog":   "Remove the log channel.",
        },
    },
    "MISC": {
        "label": "Misc",
        "desc": "Miscellaneous utility commands.",
        "cmds": {
            "id":    "Get user/chat ID.",
            "info":  "Get user information card.",
            "ping":  "Check bot latency.",
            "about": "About this bot.",
        },
    },
    "NOTES": {
        "label": "Notes",
        "desc": "Save and retrieve notes with #hashtags.",
        "cmds": {
            "save":     "Save a note.\nUsage: /save <name> <text>",
            "get":      "Get a saved note.\nUsage: /get <name> or #name",
            "clear":    "Delete a note.\nUsage: /clear <name>",
            "notes":    "List all saved notes.",
            "clearall": "Delete ALL notes in this chat.",
        },
    },
    "PIN": {
        "label": "Pin",
        "desc": "Pin and manage pinned messages.",
        "cmds": {
            "pin":      "Pin the replied message.\nUsage: reply /pin [loud]",
            "unpin":    "Unpin the current pinned message.",
            "unpinall": "Unpin all pinned messages.",
            "pinned":   "Show the current pinned message link.",
        },
    },
    "PRIVACY": {
        "label": "Privacy",
        "desc": "Manage user data and privacy settings.",
        "cmds": {
            "privacy":   "View your stored data.",
            "deletedata": "Request deletion of your data.",
        },
    },
    "PURGES": {
        "label": "Purges",
        "desc": "Bulk delete messages.",
        "cmds": {
            "purge": "Delete messages from replied to current.\nUsage: reply /purge or /purge <n>",
            "del":   "Delete the replied message.",
        },
    },
    "REPORTS": {
        "label": "Reports",
        "desc": "Allow users to report rule violations.",
        "cmds": {
            "report":  "Report a message to admins.\nUsage: reply /report",
            "reports": "Toggle reports.\nUsage: /reports on|off",
        },
    },
    "RULES": {
        "label": "Rules",
        "desc": "Set and view group rules.",
        "cmds": {
            "setrules":     "Set group rules.\nUsage: /setrules <text>",
            "rules":        "Show group rules.",
            "clearrules":   "Delete the group rules.",
            "privaterules": "Send rules via PM.\nUsage: /privaterules on|off",
        },
    },
    "TOPICS": {
        "label": "Topics",
        "desc": "Manage forum topics in supergroups.",
        "cmds": {
            "newtopic":   "Create a new topic.\nUsage: /newtopic <name>",
            "closetopic": "Close the current topic.",
            "opentopic":  "Reopen a closed topic.",
        },
    },
    "WARNINGS": {
        "label": "Warnings",
        "desc": "Issue and manage warnings.",
        "cmds": {
            "warn":       "Issue a warning.\nUsage: /warn <user> [reason]",
            "dwarn":      "Warn + delete the replied msg.\nUsage: reply /dwarn",
            "unwarn":     "Remove last warning.\nUsage: /unwarn <user>",
            "resetwarns": "Clear all warns for a user.\nUsage: /resetwarns <user>",
            "warns":      "View a user's warnings.\nUsage: /warns <user>",
            "warnlimit":  "Set warn limit (default 3).\nUsage: /warnlimit <n>",
            "warnmode":   "Set action on limit: ban/kick/mute.\nUsage: /warnmode <action>",
        },
    },
    "STATS": {
        "label": "Stats",
        "desc": "Bot statistics and broadcasting (owner only).",
        "cmds": {
            "stats":     "Show bot statistics.\nOwner/sudo only.",
            "broadcast": "Broadcast to all chats.\nOwner only.",
        },
    },
    "MAINTENANCE": {
        "label": "Maintenance",
        "desc": "Owner-only kill switch for the bot.",
        "cmds": {
            "maintenance": "Toggle maintenance mode.\nUsage: /maintenance on|off|status",
        },
    },
}

# reverse lookup: cmd → module key
_CMD_TO_MOD: dict[str, str] = {}
for _k, _v in MODULES.items():
    for _c in _v["cmds"]:
        _CMD_TO_MOD[_c] = _k


# ══════════════════════════════════════════════════════════════════════════════
# LEVEL 1 — Main help menu (27 modules, 3 columns, clean text)
# ══════════════════════════════════════════════════════════════════════════════

def main_menu_keyboard() -> InlineKeyboardMarkup:
    btns = [
        Btn(data["label"], callback_data=f"help:{key}")
        for key, data in MODULES.items()
    ]
    rows = build_menu(btns, n_cols=3, footer=[_back("start:main"), _close()])
    return InlineKeyboardMarkup(rows)


# ══════════════════════════════════════════════════════════════════════════════
# LEVEL 2 — Module sub-menu (commands as buttons)
# ══════════════════════════════════════════════════════════════════════════════

def module_help_keyboard(module_name: str) -> InlineKeyboardMarkup:
    mod = MODULES.get(module_name)
    if not mod:
        return InlineKeyboardMarkup([[_back("help:main")]])

    btns = [
        Btn(cmd, callback_data=f"cmd:{module_name}:{cmd}")
        for cmd in mod["cmds"]
    ]
    rows = build_menu(btns, n_cols=3, footer=[_back("help:main"), _close()])
    return InlineKeyboardMarkup(rows)


# ══════════════════════════════════════════════════════════════════════════════
# LEVEL 3 — Command detail
# ══════════════════════════════════════════════════════════════════════════════

def command_detail_keyboard(module_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_back(f"help:{module_name}"),
         Btn("Menu", callback_data="help:main"),
         _close()],
    ])


def get_command_detail(module_name: str, cmd: str) -> str | None:
    mod = MODULES.get(module_name)
    if not mod:
        return None
    return mod["cmds"].get(cmd)


def get_module_header(module_name: str) -> str:
    mod = MODULES.get(module_name)
    if not mod:
        return "Unknown module."
    label = mod["label"]
    desc = mod["desc"]
    cmds = mod["cmds"]
    lines = [f"<b>{label}</b>\n{desc}\n"]
    for cmd, detail in cmds.items():
        first_line = detail.split("\n")[0]
        lines.append(f" • <code>/{cmd}</code> — {first_line}")
    lines.append(f"\n<i>Tap any command below for details.</i>")
    return "\n".join(lines)
