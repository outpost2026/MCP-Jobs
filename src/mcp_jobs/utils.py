"""Encoding-safe utilities for Windows cp1250 console."""

from __future__ import annotations

import re
import sys
import unicodedata
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

if TYPE_CHECKING:
    from .models import Ad

# Emoji a supplementary Unicode znaky (U+1F000+) zpusobuji
# UnicodeEncodeError na Windows cp1250. Tento pattern je
# odstranuje, ale necha Central European diakritiku (cs, pl...).
_EMOJI_RE = re.compile(
    "["
    "\U0001f600-\U0001f64f"  # Emoticons (U+1F600..1F64F)
    "\U0001f300-\U0001f5ff"  # Misc symbols & pictographs
    "\U0001f680-\U0001f6ff"  # Transport & map
    "\U0001f1e0-\U0001f1ff"  # Flags
    "\U00002600-\U000027bf"  # Misc symbols
    "\U0000fe00-\U0000fe0f"  # Variation selectors
    "\U000e0100-\U000e01ef"  # Variation selectors supplement
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


# Tracking/session parametry, ktere se meni mezi behy scrape (searchId, rps)
# a zpusobuji duplicity v DB (UNIQUE na raw URL je nechyti). UTM parametry
# nemaji vliv na dedup, ale nesou jen marketingove info - osekneme je take.
_TRACKING_PARAMS = {
    "searchid",
    "search_id",
    "rps",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
}


def normalize_url(url: str) -> str:
    """Kanonizuj URL: odstran tracking/session parametry.

    Dedup logika (pipeline _dedup i DB UNIQUE constraint) spolehla na to,
    ze stejna ad ma stejny URL. Jobs.cz vklada do linku searchId, prace.cz
    rps - oba se meni kazdy beh, takze stejny inzerat se ulozil vicekrat.
    Odstranenim techto parametru dostaneme stabilni kanonicky URL.

    Neporovnatelne URL (prazdne, malformed) vraci beze zmeny.
    """
    if not url:
        return url
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    qs = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS
    ]
    query = urlencode(qs) if qs else ""
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


# En-dash/em-dash — vizualne zaměnitelné s pomlckou, ale ruzne unicode znaky.
_DASHES_RE = re.compile("[\u2013\u2014\u2012]")


_PRAHA_RE = re.compile(r"^(hlavni\s+mesto\s+praha|praha\s*-\s*|praha\s+)|,\s*praha$")


def _fuzzy_norm(text: str) -> str:
    """Normalizuj text pro fuzzy dedup: lowercase, bez diakritiky, dash->'-'.

    - lowercase
    - NFKD + strip diakritiky
    - pomlcky (en/em) -> '-'
    - kolaps whitespace a sezevani kolem pomlcek
    - Praha normalizace: 'Hlavní město Praha' -> 'praha',
      'Praha-Vysočany' -> 'vysocany', 'Praha - Nusle' -> 'nusle'
    """
    if not text:
        return ""
    t = text.lower().strip()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = _DASHES_RE.sub("-", t)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s*-\s*", "-", t)
    t = _PRAHA_RE.sub("", t)
    return t


def fuzzy_key(ad: Ad) -> tuple[str, str]:
    """Kanonicky fuzzy dedup klic (title, company).

    Location je vyloucena — portaly ji formatuji nesourodce
    ('Vysočany, Praha' vs 'Praha-Vysočany'), coz zpusobuje miss dedupu.
    Sdilen mezi pipeline _dedup a DB-level dedup.
    """
    if not hasattr(ad, "title"):
        return ("", "")
    return (
        _fuzzy_norm(ad.title),
        _fuzzy_norm(ad.company or ""),
    )
