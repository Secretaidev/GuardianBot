"""
bot/helpers/time_parser.py
ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ — Time string parsing and formatting utilities.

Supports:
  s  → seconds
  m  → minutes
  h  → hours
  d  → days
  w  → weeks

Examples:
  parse_time("3d")   → timedelta(days=3)
  parse_time("2h30m") → timedelta(hours=2, minutes=30)  (compound supported)
  format_duration(timedelta(days=1, hours=2)) → "1 day 2 hours"
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

# Regex that matches one or more <number><unit> components.
# Compound strings like "1d12h" are fully supported.
_TIME_RE = re.compile(
    r"(?:(\d+)\s*w)?"   # weeks
    r"(?:(\d+)\s*d)?"   # days
    r"(?:(\d+)\s*h)?"   # hours
    r"(?:(\d+)\s*m)?"   # minutes
    r"(?:(\d+)\s*s)?",  # seconds
    re.IGNORECASE,
)

# Individual token pattern for the greedy multi-token approach
_TOKEN_RE = re.compile(r"(\d+)\s*([wdhms])", re.IGNORECASE)


# ─────────────────────────────────────────────────────────────────────────────
# Public functions
# ─────────────────────────────────────────────────────────────────────────────

def parse_time(time_str: str) -> Optional[timedelta]:
    """
    Convert a human-readable time string to a :class:`datetime.timedelta`.

    The string may contain any combination of week (w), day (d), hour (h),
    minute (m) and second (s) components in any order.

    Returns *None* if the string cannot be parsed or the total duration is
    zero.

    Examples::

        parse_time("30m")      → timedelta(minutes=30)
        parse_time("1w2d")     → timedelta(weeks=1, days=2)
        parse_time("10s")      → timedelta(seconds=10)
        parse_time("2h30m10s") → timedelta(hours=2, minutes=30, seconds=10)
        parse_time("abc")      → None
    """
    if not time_str or not isinstance(time_str, str):
        return None

    time_str = time_str.strip()
    tokens = _TOKEN_RE.findall(time_str)

    if not tokens:
        return None

    weeks = days = hours = minutes = seconds = 0

    unit_map = {
        "w": "weeks",
        "d": "days",
        "h": "hours",
        "m": "minutes",
        "s": "seconds",
    }

    for value_str, unit in tokens:
        value = int(value_str)
        key = unit.lower()
        if key == "w":
            weeks += value
        elif key == "d":
            days += value
        elif key == "h":
            hours += value
        elif key == "m":
            minutes += value
        elif key == "s":
            seconds += value

    delta = timedelta(
        weeks=weeks,
        days=days,
        hours=hours,
        minutes=minutes,
        seconds=seconds,
    )

    # Return None for zero-length durations to catch mistakes like parse_time("")
    if delta.total_seconds() == 0:
        return None

    return delta


def format_duration(delta: timedelta) -> str:
    """
    Convert a :class:`datetime.timedelta` to a human-readable English string.

    Examples::

        format_duration(timedelta(days=1, hours=2))   → "1 day 2 hours"
        format_duration(timedelta(minutes=30))        → "30 minutes"
        format_duration(timedelta(seconds=90))        → "1 minute 30 seconds"
        format_duration(timedelta(0))                 → "0 seconds"
    """
    total_seconds = int(delta.total_seconds())

    if total_seconds < 0:
        total_seconds = abs(total_seconds)

    weeks, remainder = divmod(total_seconds, 604_800)    # 7*24*3600
    days,  remainder = divmod(remainder, 86_400)          # 24*3600
    hours, remainder = divmod(remainder, 3_600)
    minutes, seconds = divmod(remainder, 60)

    parts: list[str] = []

    def _plural(n: int, unit: str) -> str:
        return f"{n} {unit}{'s' if n != 1 else ''}"

    if weeks:
        parts.append(_plural(weeks, "week"))
    if days:
        parts.append(_plural(days, "day"))
    if hours:
        parts.append(_plural(hours, "hour"))
    if minutes:
        parts.append(_plural(minutes, "minute"))
    if seconds or not parts:
        parts.append(_plural(seconds, "second"))

    return " ".join(parts)


def get_future_time(time_str: str) -> Optional[datetime]:
    """
    Parse *time_str* and return the UTC :class:`datetime` that is that far
    into the future from *now*.

    Returns *None* if *time_str* cannot be parsed.

    Example::

        get_future_time("1h") → datetime(2024, 1, 1, 13, 0, tzinfo=timezone.utc)
    """
    delta = parse_time(time_str)
    if delta is None:
        return None
    return datetime.now(tz=timezone.utc) + delta


def parse_time_to_seconds(time_str: str) -> Optional[int]:
    """
    Convenience wrapper — returns the number of whole seconds in *time_str*.

    Returns *None* on parse failure.
    """
    delta = parse_time(time_str)
    if delta is None:
        return None
    return int(delta.total_seconds())
