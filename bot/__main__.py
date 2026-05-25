"""
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — Async entrypoint.
Crafted by 𝐒𝐄𝐂𝐑𝐄𝐓

Run:  python -m bot   or   python run.py
"""
from __future__ import annotations

import importlib
import logging
import sys

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, ApplicationBuilder, ContextTypes

from bot.config import (
    BOT_NAME, BOT_TOKEN, LOG_CHANNEL_ID,
    OWNER_ID, SUDO_USERS, WARN_LIMIT,
)
from bot.fonts import sc
from bot.logger import TelegramChannelHandler, get_logger, setup_logger

_root_logger = setup_logger()
logger = get_logger(__name__)

# ── module list ───────────────────────────────────────────────────────────────
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


# ── MongoDB ───────────────────────────────────────────────────────────────────

async def _connect_db() -> None:
    """Connect MongoDB via the proper connect_db() from database.mongo."""
    try:
        from bot.database.mongo import connect_db
        await connect_db()
        logger.info("MongoDB connected via database.mongo.connect_db()")
    except SystemExit:
        logger.critical("MongoDB connection failed — cannot start without DB.")
        raise
    except Exception as exc:
        logger.error("MongoDB init failed: %s", exc, exc_info=True)
        logger.warning("Bot will start but DB-dependent features may fail.")


# ── Module loader ─────────────────────────────────────────────────────────────

def _register_modules(app: Application) -> None:
    loaded, failed = [], []
    for path in MODULES:
        name = path.rsplit(".", 1)[-1]
        try:
            mod = importlib.import_module(path)
            if hasattr(mod, "register_handlers") and callable(mod.register_handlers):
                mod.register_handlers(app)
                loaded.append(name)
            else:
                logger.warning("Module '%s' has no register_handlers() — skipped.", name)
                failed.append(name)
        except Exception as exc:
            logger.error("Module '%s' failed: %s", name, exc, exc_info=True)
            failed.append(name)

    logger.info(
        "Modules: %d/%d loaded [%s]%s",
        len(loaded), len(MODULES), ", ".join(loaded),
        f" [FAILED: {', '.join(failed)}]" if failed else "",
    )


# ── Error handler (never lets the bot die) ────────────────────────────────────

async def _error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catch ALL unhandled exceptions. Log them, don't crash."""
    import traceback as tb

    err = context.error
    if err is None:
        return

    # Ignore harmless network blips
    from telegram.error import TimedOut, NetworkError
    if isinstance(err, (TimedOut, NetworkError)):
        logger.debug("Network blip (ignored): %s", err)
        return

    tb_str = "".join(tb.format_exception(type(err), err, err.__traceback__))
    logger.error("Unhandled exception:\n%s", tb_str)

    if isinstance(update, Update):
        info = []
        if update.effective_chat:
            c = update.effective_chat
            info.append(f"chat={c.title!r} ({c.id})")
        if update.effective_user:
            u = update.effective_user
            info.append(f"user={u.full_name!r} ({u.id})")
        if info:
            logger.error("Context: %s", " | ".join(info))

    # try to notify owner about the error
    try:
        short = str(err)[:200]
        await context.bot.send_message(
            LOG_CHANNEL_ID,
            f"🔴 <b>{sc('error')}</b>\n<code>{short}</code>",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass


# ── Post-init (runs after bot authenticates) ──────────────────────────────────

async def _post_init(app: Application) -> None:
    # connect MongoDB FIRST
    await _connect_db()

    # start telegram log channel consumer
    try:
        await TelegramChannelHandler.start(app.bot, rate_limit=18.0)
    except Exception as e:
        logger.warning("Log channel handler failed to start: %s", e)

    # server-side log rotation
    try:
        from bot.helpers.autodelete import setup_log_rotation, cleanup_old_logs
        setup_log_rotation()
        cleanup_old_logs(max_age_days=7)
    except Exception:
        pass

    # resolve bot info
    bot_user = await app.bot.get_me()
    username = f"@{bot_user.username}" if bot_user.username else BOT_NAME
    _print_banner(username, bot_user.id)

    # send startup notification to log channel
    try:
        from datetime import datetime, timezone
        now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        await app.bot.send_message(
            chat_id=LOG_CHANNEL_ID,
            text=(
                f"🟢 <b>{sc(BOT_NAME)} ᴏɴʟɪɴᴇ</b>\n"
                f"<b>{sc('username')}:</b> <code>{username}</code>\n"
                f"<b>{sc('id')}:</b> <code>{bot_user.id}</code>\n"
                f"<b>{sc('owner')}:</b> <code>{OWNER_ID}</code>\n"
                f"<b>{sc('modules')}:</b> <code>{len(MODULES)}</code>\n"
                f"<i>🕐 {now}</i>"
            ),
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        logger.warning("Startup notification failed: %s", exc)

    logger.info("%s live as %s (ID: %d)", BOT_NAME, username, bot_user.id)


async def _post_stop(app: Application) -> None:
    logger.info("Shutting down...")
    try:
        await TelegramChannelHandler.stop()
    except Exception:
        pass
    try:
        from bot.database.mongo import close_db
        await close_db()
    except Exception:
        pass


# ── Banner ────────────────────────────────────────────────────────────────────

def _print_banner(username: str, bot_id: int) -> None:
    sep = "═" * 46

    def row(label: str, value: str) -> str:
        content = f"  {sc(label)}: {value}"
        pad = 44 - len(content)
        return f"║{content}{' ' * max(pad, 0)}║"

    print(
        f"\n"
        f"  ╔{sep}╗\n"
        f"  ║{'':^44}║\n"
        f"  ║{sc('guardian bot — online'):^44}║\n"
        f"  ║{'':^44}║\n"
        f"  ╠{sep}╣\n"
        f"  {row('name', BOT_NAME)}\n"
        f"  {row('username', username)}\n"
        f"  {row('bot id', str(bot_id))}\n"
        f"  {row('owner id', str(OWNER_ID))}\n"
        f"  {row('modules', str(len(MODULES)))}\n"
        f"  {row('crafted by', '𝐒𝐄𝐂𝐑𝐄𝐓')}\n"
        f"  ╚{sep}╝\n"
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    logger.info("Building Application...")

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(_post_init)
        .post_stop(_post_stop)
        .connection_pool_size(16)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .pool_timeout(15)
        .build()
    )

    app.add_error_handler(_error_handler)
    _register_modules(app)

    logger.info("Starting polling — press Ctrl+C to stop.")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        close_loop=True,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Shutdown via Ctrl+C.")
        sys.exit(0)
