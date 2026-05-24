"""
bot/logger.py — ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Advanced dual-sink logging system.

This module wires up two log sinks:
  1. Console (StreamHandler)  — always active, coloured with level prefixes
  2. Telegram channel         — TelegramChannelHandler sends formatted
                                records to LOG_CHANNEL_ID using an async
                                queue so the event-loop is never blocked.

Public surface
──────────────
  setup_logger(name, level)  – call once after the Application is built;
                               returns the root "guardianbot" logger.
  get_logger(name)           – thin wrapper around logging.getLogger(name)
                               scoped under the "guardianbot" namespace.
  log_action(...)            – send a structured moderation-action card to
                               the log channel.

Design notes
────────────
• TelegramChannelHandler buffers outgoing messages in an asyncio.Queue.
  A background coroutine drains the queue at up to 18 messages/second
  (Telegram's global bot flood limit is ~20; we use 18 to stay safe).

• On first import the handler registers itself but does NOT start its
  consumer task — that requires a running event-loop.  Call
  ``TelegramChannelHandler.start(bot)`` after the Application has started.

• If the Telegram send fails (network error, channel unreachable, etc.)
  the handler prints a fallback line to stderr and discards the record
  so logging itself never crashes the bot.
"""

from __future__ import annotations

import asyncio
import html
import logging
import sys
import traceback
from datetime import datetime, timezone
from typing import Optional

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from bot.config import LOG_CHANNEL_ID, LOG_LEVEL
from bot.fonts import sc

# ── Level decorators ──────────────────────────────────────────────────────────
_LEVEL_EMOJI: dict[int, str] = {
    logging.DEBUG:    "🔵",
    logging.INFO:     "🟢",
    logging.WARNING:  "🟡",
    logging.ERROR:    "🔴",
    logging.CRITICAL: "🆘",
}

_LEVEL_LABEL: dict[int, str] = {
    logging.DEBUG:    sc("debug"),
    logging.INFO:     sc("info"),
    logging.WARNING:  sc("warning"),
    logging.ERROR:    sc("error"),
    logging.CRITICAL: sc("critical"),
}


# ── Telegram Channel Handler ──────────────────────────────────────────────────

class TelegramChannelHandler(logging.Handler):
    """A non-blocking ``logging.Handler`` that ships log records to a
    Telegram channel via an internal async queue.

    The handler is safe to attach before the event-loop starts; records
    queued before ``start()`` is called are held in memory and delivered
    once the consumer coroutine is running.

    Parameters
    ----------
    channel_id:
        Numeric Telegram chat-ID of the destination channel/group.
    min_level:
        Only records at this level or above are forwarded to Telegram.
        Records below this threshold are silently dropped (they are still
        handled by other attached handlers such as the console handler).
    max_queue_size:
        Hard cap on buffered records.  Oldest records are discarded when
        the queue is full to avoid unbounded memory growth.
    rate_limit:
        Maximum messages per second sent to Telegram.  Telegram's global
        per-bot flood limit is ~20 msg/s; the default is 18 to stay safe.
    """

    # Class-level queue and consumer task so all instances share one pipeline.
    _queue: asyncio.Queue = asyncio.Queue(maxsize=500)
    _consumer_task: Optional[asyncio.Task] = None
    _bot: Optional[Bot] = None
    _rate_limit: float = 18.0

    def __init__(
        self,
        channel_id: int = LOG_CHANNEL_ID,
        min_level: int = logging.INFO,
        max_queue_size: int = 500,
        rate_limit: float = 18.0,
    ) -> None:
        super().__init__(level=min_level)
        self.channel_id = channel_id
        TelegramChannelHandler._rate_limit = rate_limit
        if TelegramChannelHandler._queue.maxsize != max_queue_size:
            TelegramChannelHandler._queue = asyncio.Queue(maxsize=max_queue_size)

    # ── Formatting ────────────────────────────────────────────────────────────

    @staticmethod
    def _format_record(record: logging.LogRecord) -> str:
        """Build the HTML-formatted Telegram message for *record*."""
        emoji = _LEVEL_EMOJI.get(record.levelno, "⚪")
        label = _LEVEL_LABEL.get(record.levelno, sc(record.levelname.lower()))
        now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Escape the message body so it is safe in HTML parse mode
        msg_body = html.escape(record.getMessage())

        lines = [
            f"{emoji} <b>[{label.upper()}]</b>  <code>{now}</code>",
            f"<b>ᴍᴏᴅᴜʟᴇ:</b> <code>{html.escape(record.name)}</code>",
            f"<b>ᴍᴇꜱꜱᴀɢᴇ:</b> {msg_body}",
        ]

        # Append formatted exception traceback if present
        if record.exc_info:
            tb_text = "".join(traceback.format_exception(*record.exc_info))
            # Telegram has a 4096 char limit; truncate the traceback if needed
            max_tb = 1800
            if len(tb_text) > max_tb:
                tb_text = tb_text[:max_tb] + "\n... (truncated)"
            lines.append(f"\n<pre>{html.escape(tb_text)}</pre>")

        return "\n".join(lines)

    # ── Queue interface ───────────────────────────────────────────────────────

    def emit(self, record: logging.LogRecord) -> None:
        """Enqueue *record* for delivery to the Telegram channel.

        If the queue is full the oldest item is discarded to make room,
        preventing this handler from blocking the calling thread.
        """
        try:
            msg = self._format_record(record)
        except Exception:  # noqa: BLE001 — never let logging crash the bot
            self.handleError(record)
            return

        try:
            TelegramChannelHandler._queue.put_nowait(msg)
        except asyncio.QueueFull:
            # Discard the oldest item and try again
            try:
                TelegramChannelHandler._queue.get_nowait()
                TelegramChannelHandler._queue.put_nowait(msg)
            except Exception:  # noqa: BLE001
                pass  # Give up silently rather than crashing

    # ── Consumer coroutine ────────────────────────────────────────────────────

    @classmethod
    async def start(cls, bot: Bot, rate_limit: float = 18.0) -> None:
        """Attach *bot* to this handler class and start the consumer task.

        Must be called from within a running asyncio event-loop, e.g.
        inside an ``Application.post_init`` callback or after
        ``application.initialize()`` has been awaited.

        Parameters
        ----------
        bot:
            The authenticated ``telegram.Bot`` instance (obtained from
            ``application.bot``).
        rate_limit:
            Maximum messages per second.  Default: 18.
        """
        cls._bot = bot
        cls._rate_limit = rate_limit
        if cls._consumer_task is None or cls._consumer_task.done():
            cls._consumer_task = asyncio.create_task(
                cls._consume_with_rate(rate_limit),
                name="tg-log-consumer",
            )

    @classmethod
    async def _consume_with_rate(cls, rate_limit: float) -> None:
        """Rate-limited consumer loop (called by :meth:`start`)."""
        interval = 1.0 / rate_limit
        while True:
            msg = await cls._queue.get()
            if msg is None:
                # Sentinel value — stop the consumer gracefully
                cls._queue.task_done()
                break
            if cls._bot is not None:
                try:
                    await cls._bot.send_message(
                        chat_id=LOG_CHANNEL_ID,
                        text=msg,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True,
                    )
                except TelegramError as exc:
                    print(
                        f"[TelegramChannelHandler] Telegram error: {exc}",
                        file=sys.stderr,
                    )
                except Exception as exc:  # noqa: BLE001
                    print(
                        f"[TelegramChannelHandler] unexpected error: {exc}",
                        file=sys.stderr,
                    )
            cls._queue.task_done()
            await asyncio.sleep(interval)

    @classmethod
    async def stop(cls) -> None:
        """Gracefully stop the consumer task.

        Sends a sentinel ``None`` into the queue and waits up to 10 s for
        the consumer to drain remaining messages before cancelling.
        """
        if cls._consumer_task and not cls._consumer_task.done():
            await cls._queue.put(None)
            try:
                await asyncio.wait_for(cls._consumer_task, timeout=10.0)
            except asyncio.TimeoutError:
                cls._consumer_task.cancel()


# ── Console formatter ─────────────────────────────────────────────────────────

class _ConsoleFormatter(logging.Formatter):
    """Colourised console formatter for development and server stdout."""

    _COLOURS: dict[int, str] = {
        logging.DEBUG:    "\033[94m",   # bright blue
        logging.INFO:     "\033[92m",   # bright green
        logging.WARNING:  "\033[93m",   # bright yellow
        logging.ERROR:    "\033[91m",   # bright red
        logging.CRITICAL: "\033[95m",   # bright magenta
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        colour = self._COLOURS.get(record.levelno, "")
        emoji  = _LEVEL_EMOJI.get(record.levelno, "⚪")
        now    = datetime.now(tz=timezone.utc).strftime("%H:%M:%S")
        label  = record.levelname.ljust(8)
        base   = (
            f"{colour}{emoji} {now} [{label}] "
            f"{record.name}: {record.getMessage()}{self._RESET}"
        )
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


# ── Module-level singleton handler ────────────────────────────────────────────
# Created once so callers can call TelegramChannelHandler.start(bot) directly.
_tg_handler = TelegramChannelHandler(min_level=logging.INFO)


# ── Public setup function ─────────────────────────────────────────────────────

def setup_logger(
    name: str = "guardianbot",
    level: str = LOG_LEVEL,
) -> logging.Logger:
    """Configure and return the root GuardianBot logger.

    Call this **once** during bot startup before any module logs anything.
    The logger has two handlers attached:

      * Console handler  — always active; colourised by level.
      * Telegram handler — active once ``TelegramChannelHandler.start(bot)``
                           has been awaited.

    Parameters
    ----------
    name:
        Logger namespace.  All child loggers (e.g.
        ``guardianbot.modules.bans``) inherit this logger's handlers.
    level:
        Minimum log-level string (DEBUG / INFO / WARNING / ERROR).
        Defaults to the ``LOG_LEVEL`` config variable.

    Returns
    -------
    logging.Logger
        The configured root logger for GuardianBot.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    logger = logging.getLogger(name)
    if logger.handlers:
        # Already configured — return as-is to avoid duplicate handlers.
        return logger

    logger.setLevel(numeric_level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(_ConsoleFormatter())
    logger.addHandler(console_handler)

    # Telegram channel handler (INFO and above only)
    _tg_handler.setLevel(logging.INFO)
    logger.addHandler(_tg_handler)

    # Prevent double-printing through the root Python logger
    logger.propagate = False

    return logger


def get_logger(module_name: str) -> logging.Logger:
    """Return a child logger scoped under the ``guardianbot`` namespace.

    Usage in any module::

        from bot.logger import get_logger
        logger = get_logger(__name__)

    Parameters
    ----------
    module_name:
        Typically ``__name__`` from the calling module.

    Returns
    -------
    logging.Logger
        Child logger that inherits handlers from the root GuardianBot logger.
    """
    # Strip leading "bot." prefix for cleaner log output
    clean = (
        module_name.removeprefix("bot.")
        if module_name.startswith("bot.")
        else module_name
    )
    return logging.getLogger(f"guardianbot.{clean}")


# ── log_action helper ─────────────────────────────────────────────────────────

async def log_action(
    bot: Bot,
    action: str,
    chat_id: int,
    chat_title: str,
    target_user_id: int,
    target_username: str,
    performed_by_id: int,
    performed_by_username: str,
    reason: str = "",
    duration: str = "",
    extra: Optional[dict[str, str]] = None,
) -> None:
    """Send a structured moderation-action card to the log channel.

    Builds a rich HTML message and dispatches it directly (bypassing the
    queue) so moderation cards are always delivered immediately.

    Parameters
    ----------
    bot:
        Authenticated ``telegram.Bot`` instance.
    action:
        Human-readable action name, e.g. ``"ban"``, ``"warn"``, ``"mute"``.
    chat_id:
        Numeric ID of the group where the action occurred.
    chat_title:
        Display title of the group.
    target_user_id:
        Numeric ID of the affected user.
    target_username:
        @username or first-name of the affected user (no @ prefix needed).
    performed_by_id:
        Numeric ID of the admin who triggered the action.
    performed_by_username:
        @username or first-name of the performing admin.
    reason:
        Optional free-text reason for the action.
    duration:
        Optional duration string (e.g. ``"1h"``, ``"30m"``, ``"permanent"``).
    extra:
        Optional dict of additional label→value rows appended to the card.
    """
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    action_label = sc(action.upper())

    _action_emoji: dict[str, str] = {
        "ban":      "🔨",
        "unban":    "🔓",
        "kick":     "👢",
        "mute":     "🔇",
        "unmute":   "🔊",
        "warn":     "⚠️",
        "unwarn":   "✅",
        "pin":      "📌",
        "unpin":    "📌",
        "lock":     "🔒",
        "unlock":   "🔓",
        "purge":    "🗑️",
        "filter":   "🚫",
        "fedban":   "🌐🔨",
        "unfedban": "🌐🔓",
        "report":   "📢",
    }
    emoji = _action_emoji.get(action.lower(), "⚙️")

    target_link = (
        f'<a href="tg://user?id={target_user_id}">'
        f"{html.escape(target_username)}</a>"
    )
    admin_link = (
        f'<a href="tg://user?id={performed_by_id}">'
        f"{html.escape(performed_by_username)}</a>"
    )

    lines: list[str] = [
        f"{emoji} <b>{action_label}</b>",
        f"<b>ɢʀᴏᴜᴘ:</b> {html.escape(chat_title)} (<code>{chat_id}</code>)",
        f"<b>ᴛᴀʀɢᴇᴛ:</b> {target_link} (<code>{target_user_id}</code>)",
        f"<b>ʙʏ:</b> {admin_link} (<code>{performed_by_id}</code>)",
    ]
    if duration:
        lines.append(f"<b>ᴅᴜʀᴀᴛɪᴏɴ:</b> {html.escape(duration)}")
    if reason:
        lines.append(f"<b>ʀᴇᴀꜱᴏɴ:</b> {html.escape(reason)}")
    if extra:
        for k, v in extra.items():
            lines.append(f"<b>{html.escape(sc(k))}:</b> {html.escape(str(v))}")
    lines.append(f"<i>🕐 {now}</i>")

    text = "\n".join(lines)

    try:
        await bot.send_message(
            chat_id=LOG_CHANNEL_ID,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except TelegramError as exc:
        _internal = get_logger(__name__)
        _internal.error(
            "log_action: failed to deliver moderation card [%s] for user %d: %s",
            action,
            target_user_id,
            exc,
        )
