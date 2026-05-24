"""
bot/config.py — ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Centralised configuration loader.

All environment variables are read here, validated, and exposed as
typed module-level constants.  Other modules import from here:

    from bot.config import BOT_TOKEN, OWNER_ID, ...

The module raises ``ValueError`` immediately on import if any *required*
variable is absent or unparseable, giving a descriptive message so the
operator knows exactly what to fix in their .env file.

Required variables
──────────────────
  BOT_TOKEN       Telegram bot token (from @BotFather)
  MONGO_URI       MongoDB connection string
  LOG_CHANNEL_ID  Telegram channel/group ID to send log messages
  OWNER_ID        Numeric Telegram user-ID of the bot owner

Optional variables (with defaults)
───────────────────────────────────
  BOT_NAME        Display name shown in help/status messages
                  Default: "ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ"
  BOT_USERNAME    @username without the @ sign (auto-resolved if empty)
  WARN_LIMIT      Number of warnings before auto-action is taken
                  Default: 3
  SUDO_USERS      Comma-separated list of numeric user-IDs that have
                  near-owner privileges.  Default: [] (empty)
  FLOOD_LIMIT     Max messages per FLOOD_TIME seconds before flood action
                  Default: 5
  FLOOD_TIME      Sliding window (seconds) for flood detection
                  Default: 5
  MAX_FEDS_PER_USER   Max federation memberships per user
                  Default: 3
  LOG_LEVEL       Python logging level string (DEBUG/INFO/WARNING/ERROR)
                  Default: INFO
  GUARDIAN_DEBUG  Set to 1/true/yes to print config summary on start
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

# ── Load .env file ────────────────────────────────────────────────────────────
# Walk up from this file's location to find a .env file so the bot works
# whether launched from the project root, a sub-directory, or via an IDE.
_here = Path(__file__).resolve().parent
_env_candidates = [
    _here / ".env",            # bot/.env
    _here.parent / ".env",     # project root .env  (most common)
]
for _env_path in _env_candidates:
    if _env_path.is_file():
        load_dotenv(dotenv_path=_env_path, override=False)
        break
else:
    # No .env file found – that is fine; variables may be set in the OS
    # environment (e.g. Docker, systemd, CI/CD).
    load_dotenv(override=False)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _require(name: str) -> str:
    """Return the value of env var *name* or raise ``ValueError``."""
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(
            f"\n\n"
            f"  ❌  Required environment variable '{name}' is not set.\n"
            f"  ──  Add it to your .env file or export it in the shell:\n\n"
            f"        {name}=<your-value>\n\n"
            f"  Refer to the README / .env.example for the full list of\n"
            f"  required variables.\n"
        )
    return value


def _require_int(name: str) -> int:
    """Return the integer value of env var *name* or raise ``ValueError``."""
    raw = _require(name)
    try:
        return int(raw)
    except ValueError:
        raise ValueError(
            f"\n\n"
            f"  ❌  Environment variable '{name}' must be an integer.\n"
            f"  ──  Got: {raw!r}\n"
        ) from None


def _optional_int(name: str, default: int) -> int:
    """Return the integer value of an optional env var, or *default*."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print(
            f"  ⚠️  {name}: cannot parse {raw!r} as integer, using default {default}",
            file=sys.stderr,
        )
        return default


def _optional_int_list(name: str) -> list[int]:
    """Parse a comma-separated list of integers from an optional env var.

    Returns an empty list if the variable is absent or blank.
    Silently skips tokens that cannot be parsed as integers and prints a
    warning to stderr so operators are informed without crashing the bot.
    """
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    result: list[int] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            result.append(int(token))
        except ValueError:
            print(
                f"  ⚠️  {name}: skipping non-integer token {token!r}",
                file=sys.stderr,
            )
    return result


# ── Required configuration ────────────────────────────────────────────────────

BOT_TOKEN: Final[str] = _require("BOT_TOKEN")
"""Telegram bot authentication token.  Keep this secret."""

MONGO_URI: Final[str] = _require("MONGO_URI")
"""MongoDB connection string, e.g. ``mongodb://localhost:27017/guardianbot``."""

LOG_CHANNEL_ID: Final[int] = _require_int("LOG_CHANNEL_ID")
"""Numeric ID of the Telegram channel / supergroup used for audit logs.
The bot must be an *admin* with post-message rights in that channel."""

OWNER_ID: Final[int] = _require_int("OWNER_ID")
"""Numeric Telegram user-ID of the bot owner.  This user bypasses all
permission checks and can run owner-only commands."""


# ── Optional configuration ────────────────────────────────────────────────────

BOT_NAME: Final[str] = os.getenv("BOT_NAME", "ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ").strip() or "ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ"
"""Human-readable display name shown in help messages and status output."""

BOT_USERNAME: Final[str] = os.getenv("BOT_USERNAME", "").strip().lstrip("@")
"""Bot @username without the leading ``@``.
Leave blank to let the bot resolve it from the API on first start."""

WARN_LIMIT: Final[int] = _optional_int("WARN_LIMIT", 3)
"""Number of warnings a user can accumulate before automatic action
(ban/mute/kick) is triggered in a group.  Default is 3."""

SUDO_USERS: Final[list[int]] = _optional_int_list("SUDO_USERS")
"""List of numeric user-IDs that have elevated (sudo) privileges.
These users can run most admin commands even without being a group admin."""

FLOOD_LIMIT: Final[int] = _optional_int("FLOOD_LIMIT", 5)
"""Max messages a user may send within FLOOD_TIME seconds before the
anti-flood module triggers.  Default is 5."""

FLOOD_TIME: Final[int] = _optional_int("FLOOD_TIME", 5)
"""Sliding-window duration (seconds) used by the anti-flood module.
Default is 5 seconds."""

MAX_FEDS_PER_USER: Final[int] = _optional_int("MAX_FEDS_PER_USER", 3)
"""Maximum number of federations a single user may own/manage.
Default is 3."""

LOG_LEVEL: Final[str] = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"
"""Python logging level string.  Accepted values: DEBUG, INFO, WARNING, ERROR.
Default is INFO."""


# ── Derived / computed values ─────────────────────────────────────────────────

# A frozenset makes membership tests O(1) — used frequently in permission checks.
PRIVILEGED_USERS: Final[frozenset[int]] = frozenset({OWNER_ID} | set(SUDO_USERS))
"""All privileged user-IDs (owner + sudo users) as a frozenset for fast lookup."""


# ── Sanity-check summary (printed at import time in debug mode) ───────────────

def _print_config_summary() -> None:  # pragma: no cover
    """Print a non-secret configuration summary to stdout."""
    sudo_str = ", ".join(str(u) for u in SUDO_USERS) if SUDO_USERS else "none"
    print(
        f"\n"
        f"  ╔══════════════════════════════════════════╗\n"
        f"  ║       ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — ᴄᴏɴꜰɪɢ             ║\n"
        f"  ╠══════════════════════════════════════════╣\n"
        f"  ║  ʙᴏᴛ ɴᴀᴍᴇ      : {BOT_NAME:<23s}║\n"
        f"  ║  ᴏᴡɴᴇʀ ɪᴅ      : {OWNER_ID:<23d}║\n"
        f"  ║  ꜱᴜᴅᴏ ᴜꜱᴇʀꜱ    : {sudo_str:<23s}║\n"
        f"  ║  ᴡᴀʀɴ ʟɪᴍɪᴛ    : {WARN_LIMIT:<23d}║\n"
        f"  ║  ꜰʟᴏᴏᴅ ʟɪᴍɪᴛ   : {FLOOD_LIMIT:<23d}║\n"
        f"  ║  ꜰʟᴏᴏᴅ ᴛɪᴍᴇ    : {FLOOD_TIME:<23d}║\n"
        f"  ║  ʟᴏɢ ᴄʜᴀɴɴᴇʟ   : {LOG_CHANNEL_ID:<23d}║\n"
        f"  ║  ʟᴏɢ ʟᴇᴠᴇʟ     : {LOG_LEVEL:<23s}║\n"
        f"  ╚══════════════════════════════════════════╝\n"
    )


if os.getenv("GUARDIAN_DEBUG", "").lower() in ("1", "true", "yes"):
    _print_config_summary()
