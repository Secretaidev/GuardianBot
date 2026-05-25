"""
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — Async entrypoint.
Crafted by 𝐒𝐄𝐂𝐑𝐄𝐓

Run:  python -m bot   or   python run.py
"""
from __future__ import annotations

import asyncio
import importlib
import logging
import signal
import sys
import time as _time

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
    try:
        from bot.database.mongo import connect_db
        await connect_db()
        logger.info("MongoDB connected via database.mongo.connect_db()")
    except Exception as exc:
        logger.error("MongoDB init failed: %s", exc, exc_info=True)
        logger.warning("Bot will start but DB features may fail.")


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
                logger.warning("Module '%s' has no register_handlers().", name)
                failed.append(name)
        except Exception as exc:
            logger.error("Module '%s' failed: %s", name, exc, exc_info=True)
            failed.append(name)

    logger.info(
        "Modules: %d/%d loaded [%s]%s",
        len(loaded), len(MODULES), ", ".join(loaded),
        f" [FAILED: {', '.join(failed)}]" if failed else "",
    )


# ── Error handler ─────────────────────────────────────────────────────────────

async def _error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    import traceback as tb

    err = context.error
    if err is None:
        return

    from telegram.error import TimedOut, NetworkError, RetryAfter
    if isinstance(err, (TimedOut, NetworkError)):
        return  # silent — these are normal on long polling
    if isinstance(err, RetryAfter):
        logger.warning("Flood wait: %s seconds", err.retry_after)
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

    try:
        short = str(err)[:200]
        await context.bot.send_message(
            LOG_CHANNEL_ID,
            f"🔴 <b>{sc('error')}</b>\n<code>{short}</code>",
            parse_mode=ParseMode.HTML,
        )
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


# ── Health check server (Railway/Render need this) ────────────────────────────

async def _start_health_server() -> None:
    """Tiny HTTP server that responds 200 OK on /health.
    Railway/Render hit this to know the bot is alive."""
    import os

    port = int(os.environ.get("PORT", 8080))

    async def _handle(reader, writer):
        try:
            data = await asyncio.wait_for(reader.read(1024), timeout=5)
        except Exception:
            data = b""
        request_line = data.decode(errors="ignore").split("\n")[0] if data else ""

        if "/health" in request_line or "/ " in request_line or request_line == "":
            body = '{"status":"ok"}'
            resp = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Connection: close\r\n\r\n"
                + body
            )
        else:
            body = "not found"
            resp = (
                "HTTP/1.1 404 Not Found\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Connection: close\r\n\r\n"
                + body
            )

        writer.write(resp.encode())
        await writer.drain()
        writer.close()

    try:
        server = await asyncio.start_server(_handle, "0.0.0.0", port)
        logger.info("Health server listening on port %d", port)
        return server
    except Exception as e:
        logger.warning("Health server failed to start on port %d: %s", port, e)
        return None


# ── Async run (NO run_polling — manual control) ──────────────────────────────

async def _run_bot() -> None:
    """Start the bot with full manual control over the polling loop.
    This function NEVER returns unless KeyboardInterrupt."""

    RESTART_DELAY = 5
    attempt = 0

    # Start health check server ONCE (survives bot restarts)
    health_server = await _start_health_server()

    while True:
        attempt += 1
        logger.info("=== Starting bot (attempt #%d) ===", attempt)
        app = None

        try:
            # Build fresh Application each attempt
            app = (
                ApplicationBuilder()
                .token(BOT_TOKEN)
                .connection_pool_size(16)
                .read_timeout(30)
                .write_timeout(30)
                .connect_timeout(30)
                .pool_timeout(15)
                .get_updates_read_timeout(30)
                .get_updates_write_timeout(30)
                .get_updates_connect_timeout(30)
                .get_updates_pool_timeout(15)
                .build()
            )

            app.add_error_handler(_error_handler)
            _register_modules(app)

            # Initialize the application
            await app.initialize()

            # Connect MongoDB
            await _connect_db()

            # Start telegram log channel
            try:
                await TelegramChannelHandler.start(app.bot, rate_limit=18.0)
            except Exception as e:
                logger.warning("Log channel start failed: %s", e)

            # Get bot info and print banner
            bot_user = await app.bot.get_me()
            username = f"@{bot_user.username}" if bot_user.username else BOT_NAME
            if attempt == 1:
                _print_banner(username, bot_user.id)

            # Send startup notification
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
            except Exception:
                pass

            logger.info("%s live as %s (ID: %d)", BOT_NAME, username, bot_user.id)

            # Start the application
            await app.start()

            # Start polling — this is the actual update fetcher
            await app.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
            )

            logger.info("Polling active — bot is running.")

            # Keep alive forever — just idle here
            # This is the KEY difference from run_polling():
            # We DON'T let the event loop stop. We wait forever.
            stop_event = asyncio.Event()

            # On SIGTERM/SIGINT, set the event instead of crashing
            def _signal_handler():
                logger.info("Signal received — will restart...")
                stop_event.set()

            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, _signal_handler)
                except NotImplementedError:
                    # Windows doesn't support add_signal_handler
                    pass

            # Wait forever (or until signal)
            await stop_event.wait()

            # Clean shutdown of this cycle
            logger.info("Stopping polling cycle...")
            await app.updater.stop()
            await app.stop()
            await app.shutdown()

            try:
                await TelegramChannelHandler.stop()
            except Exception:
                pass

            logger.info("Cycle ended — restarting in %ds...", RESTART_DELAY)
            await asyncio.sleep(RESTART_DELAY)

        except KeyboardInterrupt:
            logger.info("Shutdown via Ctrl+C. Goodbye!")
            if app:
                try:
                    await app.updater.stop()
                    await app.stop()
                    await app.shutdown()
                except Exception:
                    pass
            break

        except Exception as exc:
            logger.error(
                "Bot error: %s — restarting in %ds...",
                exc, RESTART_DELAY, exc_info=True,
            )
            if app:
                try:
                    await app.updater.stop()
                    await app.stop()
                    await app.shutdown()
                except Exception:
                    pass

            await asyncio.sleep(RESTART_DELAY)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    """Entry point — runs the immortal bot loop."""
    try:
        asyncio.run(_run_bot())
    except KeyboardInterrupt:
        logger.info("Shutdown via Ctrl+C.")


if __name__ == "__main__":
    main()
