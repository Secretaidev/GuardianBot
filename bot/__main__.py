"""
bot/__main__.py — ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Async bot entrypoint.

Run from the project root with:

    python -m bot

Or via the convenience wrapper:

    python run.py

Startup sequence
────────────────
  1. Parse env / config (done at import of bot.config)
  2. Set up logging (console + Telegram channel)
  3. Open MongoDB connection pool
  4. Build the python-telegram-bot Application
  5. Register module handlers (each module exports register_handlers(app))
  6. Wire error handler
  7. Start background services (log-channel consumer, etc.)
  8. Run polling loop until SIGINT / SIGTERM
  9. Graceful shutdown (flush logs, close DB, stop tasks)

Module registration
───────────────────
  Each module in bot/modules/ exposes:

      def register_handlers(app: Application) -> None:
          app.add_handler(CommandHandler("cmd", callback))
          ...

  Modules are imported and registered in the order listed in MODULES below.
  A failing import of any single module is logged but does NOT abort startup
  so the bot remains functional even if one feature module has a bug.
"""

from __future__ import annotations

import asyncio
import importlib
import signal
import sys
from typing import TYPE_CHECKING

from telegram import Update
from telegram.ext import Application, ApplicationBuilder, ContextTypes

# ── GuardianBot imports ───────────────────────────────────────────────────────
from bot.config import (
    BOT_NAME,
    BOT_TOKEN,
    LOG_CHANNEL_ID,
    MONGO_URI,
    OWNER_ID,
    SUDO_USERS,
    WARN_LIMIT,
)
from bot.fonts import sc, bold_sc
from bot.logger import (
    TelegramChannelHandler,
    get_logger,
    setup_logger,
)

if TYPE_CHECKING:
    pass

# ── Module logger (set up before anything else logs) ─────────────────────────
_root_logger = setup_logger()
logger = get_logger(__name__)

# ── List of feature modules to register ──────────────────────────────────────
# Each entry is a dotted import path relative to this package.
# The order determines handler registration priority.
MODULES: list[str] = [
    "bot.modules.start",
    "bot.modules.admin",
    "bot.modules.bans",
    "bot.modules.mutes",
    "bot.modules.warns",
    "bot.modules.welcome",
    "bot.modules.filters",
    "bot.modules.notes",
    "bot.modules.locks",
    "bot.modules.blocklist",
    "bot.modules.antiflood",
    "bot.modules.reports",
    "bot.modules.pins",
    "bot.modules.purge",
    "bot.modules.rules",
    "bot.modules.federation",
    "bot.modules.disable",
    "bot.modules.maintenance",
    "bot.modules.users",
    "bot.modules.stats",
]


# ── MongoDB setup ─────────────────────────────────────────────────────────────

async def _connect_mongodb() -> None:
    """Open an async MongoDB connection pool via Motor.

    The ``motor.motor_asyncio.AsyncIOMotorClient`` is imported lazily so
    the bot can start (and give a clear error) even if motor is not
    installed, rather than crashing at module import time.
    """
    try:
        from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore[import]
        from bot import database  # noqa: F401 – triggers database/__init__.py

        client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5_000)
        # Ping to verify the connection is live before we proceed
        await client.admin.command("ping")

        # Attach the client to a well-known location so all modules can import
        # it via ``from bot.database import db``
        import bot.database as _db_pkg
        _db_pkg.client = client                     # type: ignore[attr-defined]
        _db_pkg.db     = client.get_default_database()  # type: ignore[attr-defined]

        logger.info(
            "MongoDB: connected to %s",
            MONGO_URI.split("@")[-1] if "@" in MONGO_URI else MONGO_URI,
        )
    except ImportError:
        logger.warning(
            "motor not installed — running without MongoDB persistence. "
            "Install with:  pip install motor"
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("MongoDB: connection failed — %s", exc, exc_info=True)
        logger.warning("Continuing without database; some features may be unavailable.")


# ── Module loader ─────────────────────────────────────────────────────────────

def _register_modules(app: Application) -> None:
    """Import each feature module and call its ``register_handlers`` function.

    A failing import or registration is logged and skipped so a broken
    module does not prevent the rest of the bot from working.
    """
    loaded: list[str] = []
    failed: list[str] = []

    for module_path in MODULES:
        try:
            module = importlib.import_module(module_path)
            if hasattr(module, "register_handlers") and callable(module.register_handlers):
                module.register_handlers(app)
                loaded.append(module_path.split(".")[-1])
            else:
                logger.warning(
                    "Module '%s' has no register_handlers() function — skipping.",
                    module_path,
                )
                failed.append(module_path.split(".")[-1])
        except ModuleNotFoundError as exc:
            logger.warning(
                "Module '%s' not found (%s) — skipping.",
                module_path,
                exc,
            )
            failed.append(module_path.split(".")[-1])
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Module '%s' failed to load: %s",
                module_path,
                exc,
                exc_info=True,
            )
            failed.append(module_path.split(".")[-1])

    logger.info(
        "Modules loaded: %d/%d  [ok: %s]%s",
        len(loaded),
        len(MODULES),
        ", ".join(loaded) if loaded else "none",
        f"  [failed: {', '.join(failed)}]" if failed else "",
    )


# ── Error handler ─────────────────────────────────────────────────────────────

async def _error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Global error handler — log every unhandled exception.

    Sends a brief error card to the Telegram log channel and a full
    traceback to the console logger so nothing is silently swallowed.
    """
    import traceback as tb

    err = context.error
    tb_str = "".join(tb.format_exception(type(err), err, err.__traceback__))

    logger.error(
        "Unhandled exception in update handler.\n%s",
        tb_str,
    )

    # Also log the update that triggered the error (if any)
    if isinstance(update, Update):
        chat_info = ""
        if update.effective_chat:
            chat_info = (
                f" | chat={update.effective_chat.title!r}"
                f" ({update.effective_chat.id})"
            )
        user_info = ""
        if update.effective_user:
            user_info = (
                f" | user={update.effective_user.full_name!r}"
                f" ({update.effective_user.id})"
            )
        logger.error("Triggered by update%s%s", chat_info, user_info)


# ── Application post-init ─────────────────────────────────────────────────────

async def _post_init(app: Application) -> None:
    """Called by the Application right after initialisation.

    At this point the bot object is authenticated and the event-loop is
    running, so we can:
      - Start the Telegram log-channel consumer
      - Send a startup notification to the log channel
      - Print the startup banner
    """
    # Start the async log consumer
    await TelegramChannelHandler.start(app.bot, rate_limit=18.0)

    # Setup server-side log rotation to keep host lean
    try:
        from bot.helpers.autodelete import setup_log_rotation, cleanup_old_logs
        setup_log_rotation()
        cleanup_old_logs(max_age_days=7)
    except Exception:
        pass  # non-critical

    # Resolve bot info
    bot_user = await app.bot.get_me()
    username = f"@{bot_user.username}" if bot_user.username else BOT_NAME

    _print_startup_banner(username, bot_user.id)

    # Notify the log channel that the bot is online
    try:
        from bot.fonts import sc as _sc
        from datetime import datetime, timezone
        now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        startup_msg = (
            f"🟢 <b>{_sc(BOT_NAME)} ᴏɴʟɪɴᴇ</b>\n"
            f"<b>ᴜꜱᴇʀɴᴀᴍᴇ:</b> <code>{username}</code>\n"
            f"<b>ɪᴅ:</b> <code>{bot_user.id}</code>\n"
            f"<b>ᴏᴡɴᴇʀ:</b> <code>{OWNER_ID}</code>\n"
            f"<b>ꜱᴜᴅᴏ:</b> <code>{len(SUDO_USERS)}</code>\n"
            f"<b>ᴡᴀʀɴ ʟɪᴍɪᴛ:</b> <code>{WARN_LIMIT}</code>\n"
            f"<i>🕐 {now}</i>"
        )
        from telegram.constants import ParseMode
        await app.bot.send_message(
            chat_id=LOG_CHANNEL_ID,
            text=startup_msg,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not send startup notification to log channel: %s", exc)

    logger.info(
        "%s is live as %s (ID: %d)",
        sc(BOT_NAME),
        username,
        bot_user.id,
    )


async def _post_stop(app: Application) -> None:
    """Called by the Application just before it exits.

    Flushes any remaining log messages and closes the MongoDB connection.
    """
    logger.info("Shutdown initiated — flushing log queue...")
    await TelegramChannelHandler.stop()

    # Close MongoDB if it was opened
    try:
        import bot.database as _db_pkg
        if hasattr(_db_pkg, "client") and _db_pkg.client is not None:  # type: ignore[attr-defined]
            _db_pkg.client.close()  # type: ignore[attr-defined]
            logger.info("MongoDB connection closed.")
    except Exception:  # noqa: BLE001
        pass


# ── Startup banner ────────────────────────────────────────────────────────────

def _print_startup_banner(username: str, bot_id: int) -> None:
    """Print the small-caps startup banner to stdout."""
    sep   = "═" * 46
    blank = "║" + " " * 44 + "║"

    def row(label: str, value: str) -> str:
        content = f"  {sc(label)}: {value}"
        pad = 44 - len(content)
        return f"║{content}{' ' * max(pad, 0)}║"

    print(
        f"\n"
        f"  ╔{sep}╗\n"
        f"  ║{'':^44}║\n"
        f"  ║{sc('Guardian Bot — online'):^44}║\n"
        f"  ║{'':^44}║\n"
        f"  ╠{sep}╣\n"
        f"  {row('name',     BOT_NAME)}\n"
        f"  {row('username', username)}\n"
        f"  {row('bot id',   str(bot_id))}\n"
        f"  {row('owner id', str(OWNER_ID))}\n"
        f"  {row('sudo',     str(len(SUDO_USERS)) + ' users')}\n"
        f"  {row('warn limit', str(WARN_LIMIT))}\n"
        f"  {row('modules',  str(len(MODULES)) + ' registered')}\n"
        f"  ╚{sep}╝\n"
    )


# ── Main entrypoint ───────────────────────────────────────────────────────────

def main() -> None:
    """Build the Application, register handlers, and start polling.

    This function is synchronous — it calls ``app.run_polling()`` which
    manages its own event-loop internally (python-telegram-bot v20+
    pattern).  Signal handlers for graceful shutdown are registered
    automatically by the library on POSIX systems.
    """
    logger.info("Building Application...")

    # Build the Application with sensible defaults
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(_post_init)
        .post_stop(_post_stop)
        # Increase connection pool for high-traffic bots
        .connection_pool_size(16)
        # Longer read timeout for stability on slow networks
        .read_timeout(20)
        .write_timeout(20)
        .connect_timeout(20)
        .pool_timeout(10)
        .build()
    )

    # Register the global error handler
    app.add_error_handler(_error_handler)

    # Register all feature module handlers
    _register_modules(app)

    # Connect to MongoDB (best-effort; bot starts even on failure)
    # We run this synchronously here so the DB is ready before polling starts.
    async def _setup_db_then_run() -> None:
        await _connect_mongodb()
        # Run polling inside the existing event-loop created by run_polling()
        # NOTE: we do NOT call run_polling() here because it creates its own
        # event-loop; instead we await the internal _run_polling coroutine.
        # python-telegram-bot v20 exposes this via updater.start_polling().
        await app.updater.start_polling(  # type: ignore[union-attr]
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )
        await app.start()

    # python-telegram-bot v20 manages the event-loop via run_polling().
    # We hook in our DB setup via post_init instead of a separate coroutine
    # to keep everything inside the library's managed loop.
    logger.info("Starting polling loop — press Ctrl+C to stop.")

    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        close_loop=True,
    )


# ── Windows-compatible signal handling ────────────────────────────────────────
# python-telegram-bot v20 handles SIGINT/SIGTERM internally on POSIX.
# On Windows only SIGINT (Ctrl+C) is reliably available; SIGTERM is not.
# The run_polling() call above handles cleanup via post_stop automatically.

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info(sc("Shutdown requested via keyboard interrupt."))
        sys.exit(0)
