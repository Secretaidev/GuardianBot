"""
bot/fonts.py — ɢᴜᴀʀᴅɪᴀɴʙᴏᴛ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Unicode small-caps helpers.

All user-facing text in GuardianBot is rendered in small caps so the
bot has a distinctive, premium look inside Telegram.  This module
provides:

  sc(text)       – convert a plain string to small-caps
  bold_sc(text)  – wrap the small-caps string in Markdown v2 bold
  SMALL_CAPS_MAP – raw character mapping dict (exposed for tests /
                   external callers)

Rules applied by sc():
  • a-z  → small-caps equivalent (see SMALL_CAPS_MAP)
  • A-Z  → lower-cased then converted (small caps are inherently caps)
  • 0-9, punctuation, whitespace, emoji, Markdown symbols → preserved
    as-is so formatting characters like * _ ` [ ] ( ) ~ > # + - = | { }
    . ! are never corrupted.
"""

from __future__ import annotations

# ── Small-caps character map ──────────────────────────────────────────────────
# Keys are lower-case ASCII letters; values are their Unicode small-cap glyphs.
SMALL_CAPS_MAP: dict[str, str] = {
    "a": "ᴀ",
    "b": "ʙ",
    "c": "ᴄ",
    "d": "ᴅ",
    "e": "ᴇ",
    "f": "ꜰ",
    "g": "ɢ",
    "h": "ʜ",
    "i": "ɪ",
    "j": "ᴊ",
    "k": "ᴋ",
    "l": "ʟ",
    "m": "ᴍ",
    "n": "ɴ",
    "o": "ᴏ",
    "p": "ᴘ",
    "q": "ǫ",
    "r": "ʀ",
    "s": "ꜱ",
    "t": "ᴛ",
    "u": "ᴜ",
    "v": "ᴠ",
    "w": "ᴡ",
    "x": "x",   # no dedicated Unicode small-cap x; keep as-is
    "y": "ʏ",
    "z": "ᴢ",
}

# Pre-build a translation table so sc() is O(n) with no per-char dict lookups.
# str.translate() uses a dict keyed by Unicode code-point (int).
_TRANS_TABLE: dict[int, str] = {
    ord(lc): sc_char
    for lc, sc_char in SMALL_CAPS_MAP.items()
}
# Also map upper-case letters → small-cap equivalent of their lower-case form.
_TRANS_TABLE.update(
    {ord(lc.upper()): sc_char for lc, sc_char in SMALL_CAPS_MAP.items()}
)


# ── Public helpers ────────────────────────────────────────────────────────────

def sc(text: str) -> str:
    """Convert *text* to Unicode small caps.

    All ASCII letters (upper or lower case) are converted.  Every other
    character — digits, punctuation, emoji, Markdown control characters —
    is passed through unchanged, so it is safe to call sc() on strings
    that already contain Telegram Markdown v2 markup.

    Parameters
    ----------
    text:
        The plain (or pre-formatted) string to convert.

    Returns
    -------
    str
        The small-caps version of *text*.

    Examples
    --------
    >>> sc("Hello World")
    'ʜᴇʟʟᴏ ᴡᴏʀʟᴅ'
    >>> sc("User #123 was banned!")
    'ᴜꜱᴇʀ #123 ᴡᴀꜱ ʙᴀɴɴᴇᴅ!'
    >>> sc("ok 👍")
    'ᴏᴋ 👍'
    """
    if not isinstance(text, str):
        text = str(text)
    return text.translate(_TRANS_TABLE)


def bold_sc(text: str) -> str:
    """Return *text* converted to small caps and wrapped in **Markdown bold**.

    Uses Telegram Bot API MarkdownV2 bold syntax: ``*...*``.
    The asterisks themselves are NOT passed through sc() so they remain
    plain ASCII and Telegram parses them correctly.

    Parameters
    ----------
    text:
        The plain string to convert and bold.

    Returns
    -------
    str
        A string like ``*ꜱᴍᴀʟʟ ᴄᴀᴘꜱ ᴛᴇxᴛ*``.

    Examples
    --------
    >>> bold_sc("action taken")
    '*ᴀᴄᴛɪᴏɴ ᴛᴀᴋᴇɴ*'
    """
    return f"*{sc(text)}*"


def italic_sc(text: str) -> str:
    """Return *text* converted to small caps and wrapped in *Markdown italic*.

    Uses MarkdownV2 italic syntax: ``_..._``.

    Parameters
    ----------
    text:
        The plain string to convert and italicise.

    Returns
    -------
    str
        A string like ``_ꜱᴍᴀʟʟ ᴄᴀᴘꜱ ᴛᴇxᴛ_``.
    """
    return f"_{sc(text)}_"


def code_sc(text: str) -> str:
    """Return *text* converted to small caps and wrapped in ``code`` ticks.

    Uses MarkdownV2 inline-code syntax: `` `...` ``.
    Useful for highlighting usernames or values inside log messages.
    """
    return f"`{sc(text)}`"


# ── Self-test (run: python -m bot.fonts) ─────────────────────────────────────
if __name__ == "__main__":
    _samples = [
        "Hello, World!",
        "GuardianBot v1.0",
        "User @JohnDoe was banned for 24h.",
        "Warn 3/3 — auto-ban triggered!",
        "123 spam messages deleted",
        "Already using MarkdownV2 markup",
    ]
    print("── sc() output ──")
    for s in _samples:
        print(f"  {s!r:45s} → {sc(s)!r}")
    print("\n── bold_sc() output ──")
    for s in _samples[:3]:
        print(f"  {bold_sc(s)!r}")
    print("\n── italic_sc() output ──")
    for s in _samples[:3]:
        print(f"  {italic_sc(s)!r}")
