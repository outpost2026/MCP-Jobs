"""Encoding-safe utilities for Windows cp1250 console."""

from __future__ import annotations

import re
import sys

# Emoji a supplementary Unicode znaky (U+1F000+) zpusobuji
# UnicodeEncodeError na Windows cp1250. Tento pattern je
# odstranuje, ale necha Central European diakritiku (cs, pl...).
_EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # Emoticons (U+1F600..1F64F)
    "\U0001F300-\U0001F5FF"  # Misc symbols & pictographs
    "\U0001F680-\U0001F6FF"  # Transport & map
    "\U0001F1E0-\U0001F1FF"  # Flags
    "\U00002600-\U000027BF"  # Misc symbols
    "\U0000FE00-\U0000FE0F"  # Variation selectors
    "\U000E0100-\U000E01EF"  # Variation selectors supplement
    "]",
    re.UNICODE,
)


def strip_emoji(text: str) -> str:
    """Odstrani emoji, ponecha ASCII + Central European."""
    return _EMOJI_RE.sub("", text)


def ensure_utf8_stdout() -> None:
    """Nastavi stdout na UTF-8 (fallback z cp1250)."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
