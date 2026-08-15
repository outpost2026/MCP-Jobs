"""Unified report renderer — single source producing Markdown + HTML.

Replaces the two divergent generators:
  - storage.py::markdown_report  (flat, no dedup)
  - scripts/run_etl.py::_write_markdown_report  (structured, no dedup)

Design decisions (2026-08-15):
- Markdown is the canonical source (readable, diffable).
- HTML is rendered by an OWN minimal MD->HTML converter (no external dep),
  with embedded CSS from report_style.py (Calibri, metadata 8 pt, A4).
- Dedup is shared across queries using the same key as pipeline._dedup.
- Metadata rows (.meta/.match/.priority-flag/.footer) are styled 8 pt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from .models import Ad
from .report_style import CSS

DESC_LIMIT = 200
PRIORITY_LIMIT = 8
FOOTER_JSON_LINK = True


@dataclass
class ReportMeta:
    """Context used to render the report header/footer."""

    timestamp: str = ""
    elapsed_seconds: float = 0.0
    total_matched: int = 0
    total_raw: int = 0
    precision: float = 0.0
    profile: str = "default"
    config_file: str = ""
    json_link: str = ""
    portals: list[str] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)


@dataclass
class ReportOutput:
    markdown: str
    html: str


# ── Dedup (shared key with pipeline._dedup) ─────────────────────────


def dedup_key(ad: Ad) -> tuple[str, str, str, str]:
    return (
        ad.url,
        ad.title.lower().strip(),
        (ad.company or "").lower().strip(),
        (ad.location or "").lower().strip(),
    )


def _unique_ads(
    ads_by_query: dict[str, list[Ad]],
) -> tuple[list[Ad], dict[str, set[str]]]:
    """Global dedup across queries.

    Returns (unique_ads, ad_queries) where ad_queries maps a dedup key to the
    set of query names that matched the ad (for the 🔑 match tag).
    """
    order: list[tuple[str, Ad]] = []
    seen: set[tuple[str, str, str, str]] = set()
    ad_queries: dict[tuple[str, str, str, str], set[str]] = {}

    for qname, ads in ads_by_query.items():
        for ad in ads:
            key = dedup_key(ad)
            if key not in seen:
                seen.add(key)
                order.append((qname, ad))
            ad_queries.setdefault(key, set()).add(qname)

    unique = [ad for _, ad in order]
    return unique, ad_queries


# ── Date parsing for priority flags ──────────────────────────────────


def _parse_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    s = raw.strip()
    # ISO (jobs.cz style: 2026-08-14) and CZ (14.08.2026)
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d. %m. %Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    return None


def _priority_flag(ad: Ad, today: date) -> str:
    d = _parse_date(ad.date)
    if d is None:
        return ""
    if d == today:
        return "Nové dnes"
    if (d - today).days >= 1 and (d - today).days <= 7:
        return "Končí brzy"
    return ""


# ── MD helpers ───────────────────────────────────────────────────────


def _desc(ad: Ad) -> str:
    if not ad.description:
        return ""
    return ad.description[:DESC_LIMIT].replace("\n", " ").replace("\r", " ").strip()


def _meta_line(ad: Ad, flag: str = "") -> str:
    parts = []
    if ad.date:
        parts.append(f"⏱ {ad.date}")
    if ad.salary:
        parts.append(f"💰 {ad.salary}")
    elif ad.price:
        parts.append(f"💰 {ad.price}")
    if ad.company:
        parts.append(f"🏢 {ad.company}")
    if ad.location:
        parts.append(f"📍 {ad.location}")
    if ad.portal:
        parts.append(f"({ad.portal})")
    if flag:
        parts.append(f"⚠️ {flag}")
    return " | ".join(parts) if parts else ""


def _match_tag(ad_queries: dict[tuple[str, str, str, str], set[str]], ad: Ad) -> str:
    qs = ad_queries.get(dedup_key(ad), set())
    if not qs:
        return ""
    return "🔑 match: " + ", ".join(sorted(qs))


# ── Report ───────────────────────────────────────────────────────────


def render_report(ads_by_query: dict[str, list[Ad]], meta: ReportMeta) -> ReportOutput:
    """Render the unified report from a per-query ad mapping.

    Returns both Markdown (canonical) and HTML (styled, own converter).
    """
    unique, ad_queries = _unique_ads(ads_by_query)

    md = _render_markdown(ads_by_query, unique, ad_queries, meta)
    html = _render_html(md, meta)
    return ReportOutput(markdown=md, html=html)


def _render_markdown(
    ads_by_query: dict[str, list[Ad]],
    unique: list[Ad],
    ad_queries: dict[tuple[str, str, str, str], set[str]],
    meta: ReportMeta,
) -> str:
    today = date.today()
    lines: list[str] = []
    _a = lines.append

    # Header
    _a(f"# Job Hunt Report — {meta.timestamp[:10] if meta.timestamp else ''}")
    _a("")
    _a(
        f"🧭 Spuštěno {meta.timestamp} | ⏱ {meta.elapsed_seconds}s "
        f"| ✅ Matched {meta.total_matched} | 🔻 Precision {meta.precision}%"
    )
    if meta.profile:
        _a(
            f"📁 Profil: `{meta.profile}` | Queries: {len(meta.queries)} | Portály: {', '.join(meta.portals)}"
        )
    _a("")
    _a("---")
    _a("")

    # Priority
    flagged = [ad for ad in unique if _priority_flag(ad, today)]
    _a("## 🔴 Priority (nové / končí brzy)")
    _a("")
    if not flagged:
        _a("Žádné inzeráty s priority flagem (nové dnes / končí brzy).")
        _a("")
    else:
        for i, ad in enumerate(flagged[:PRIORITY_LIMIT], 1):
            _a(f"{i}. **[{ad.title}]({ad.url})**")
            mline = _meta_line(ad, _priority_flag(ad, today))
            if mline:
                _a(f"   {mline}")
            d = _desc(ad)
            if d:
                _a(f"   > {d}")
            mt = _match_tag(ad_queries, ad)
            if mt:
                _a(f"   {mt}")
            _a("")

    # Overview table
    _a("## 📊 Přehled (per query)")
    _a("")
    _a("| Query | N | Portály |")
    _a("|---|---|---|")
    for qname, ads in ads_by_query.items():
        portals = ", ".join(sorted({a.portal for a in ads if a.portal}))
        _a(f"| {qname} | {len(ads)} | {portals} |")
    _a("")
    _a(
        f"> Po dedup: {len(ads_by_query.items() and unique)} unikátních inzerátů napříč query."
    )
    _a("")

    # Per-query sections
    for qname, ads in ads_by_query.items():
        _a(f"## 📂 {qname} — {len(ads)}")
        _a("")
        if not ads:
            _a("0 matchingů.")
            _a("")
            continue
        for i, ad in enumerate(ads, 1):
            _a(f"{i}. **[{ad.title}]({ad.url})**")
            mline = _meta_line(ad)
            if mline:
                _a(f"   {mline}")
            d = _desc(ad)
            if d:
                _a(f"   > {d}")
            mt = _match_tag(ad_queries, ad)
            if mt:
                _a(f"   {mt}")
            _a("")
        if FOOTER_JSON_LINK and meta.json_link:
            _a(f"> + plný JSON → [{meta.json_link}]({meta.json_link})")
            _a("")

    # Footer with precision
    _a("---")
    _a("")
    _a(
        f"> 📊 Raw: {meta.total_raw} | Matched: {meta.total_matched} "
        f"| Precision: {meta.precision}% | Generated: {meta.timestamp}"
    )
    _a("")

    return "\n".join(lines)


# ── Own MD -> HTML converter ─────────────────────────────────────────


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_INLINE_RE = [
    (re.compile(r"\*\*([^*]+)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"\*([^*]+)\*"), r"<em>\1</em>"),
    (re.compile(r"`([^`]+)`"), r"<code>\1</code>"),
    (re.compile(r"\[([^\]]+)\]\(([^)]+)\)"), r'<a href="\2">\1</a>'),
]


def _inline(text: str) -> str:
    out = _escape(text)
    for rx, repl in _INLINE_RE:
        out = rx.sub(repl, out)
    return out


def _md_to_html(md: str) -> str:
    """Own minimal MD->HTML converter (no external dependency).

    Supports: #/## headings, --- hr, tables (|...|), blockquotes (>),
    ordered lists, paragraphs, **bold**/*em*/`code`/links.
    Metadata/priority/footer rows are classified into CSS classes
    (.meta, .match, .priority-flag) so they render at 8 pt.
    """
    out: list[str] = []
    lines = md.splitlines()
    i = 0
    n = len(lines)

    def is_table_row(ln: str) -> bool:
        return ln.strip().startswith("|") and ln.strip().endswith("|")

    while i < n:
        ln = lines[i].rstrip()
        s = ln.strip()

        if not s:
            i += 1
            continue

        if s == "---":
            out.append("<hr>")
            i += 1
            continue

        if s.startswith("### "):
            out.append(f"<h3>{_inline(s[4:])}</h3>")
            i += 1
            continue
        if s.startswith("## "):
            out.append(f"<h2>{_inline(s[3:])}</h2>")
            i += 1
            continue
        if s.startswith("# "):
            out.append(f"<h1>{_inline(s[2:])}</h1>")
            i += 1
            continue

        # Table: collect consecutive rows
        if is_table_row(ln):
            rows = []
            while i < n and is_table_row(lines[i].rstrip()):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(cells)
                i += 1
            if len(rows) >= 2:  # header + separator + data
                tbl = ["<table>"]
                for ri, row in enumerate(rows):
                    if ri == 1 and all(re.match(r"^:?-{3,}:?$", c) for c in row if c):
                        continue  # separator
                    tag = "th" if ri == 0 else "td"
                    tbl.append(
                        "<tr>"
                        + "".join(f"<{tag}>{_inline(c)}</{tag}>" for c in row)
                        + "</tr>"
                    )
                tbl.append("</table>")
                out.append("".join(tbl))
            continue

        # Blockquote: collect consecutive lines
        if s.startswith(">"):
            quotes = []
            while i < n and lines[i].strip().startswith(">"):
                content = lines[i].strip()[1:].strip()
                if content.startswith("📊 ") or content.startswith("+ plný"):
                    quotes.append(f'<p class="footer">{_inline(content)}</p>')
                else:
                    quotes.append(f"<p>{_inline(content)}</p>")
                i += 1
            out.append("<blockquote>" + "".join(quotes) + "</blockquote>")
            continue

        # Priority flags row (🔴 section item meta with ⚠️)
        if s.startswith("⚠️") or s.startswith("⏱"):
            out.append(f'<p class="meta">{_inline(s)}</p>')
            i += 1
            continue

        # Match tag
        if s.startswith("🔑 match:"):
            out.append(f'<p class="match">{_inline(s)}</p>')
            i += 1
            continue

        # Header meta line
        if s.startswith("🧭") or s.startswith("📁"):
            out.append(f'<p class="meta">{_inline(s)}</p>')
            i += 1
            continue

        # Ordered list item
        m = re.match(r"^(\d+)\.\s+(.+)$", s)
        if m:
            out.append(f'<ol start="{m.group(1)}"><li>{_inline(m.group(2))}</li></ol>')
            i += 1
            continue

        # Paragraph
        out.append(f"<p>{_inline(s)}</p>")
        i += 1

    return "\n".join(out)


def _render_html(md: str, meta: ReportMeta) -> str:
    title = f"Job Hunt Report — {meta.timestamp[:10] if meta.timestamp else ''}"
    body = _md_to_html(md)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="cs">\n<head>\n'
        '<meta charset="utf-8">\n'
        f"<title>{_escape(title)}</title>\n"
        f"<style>\n{CSS}</style>\n"
        "</head>\n<body>\n"
        f"{body}\n"
        "</body>\n</html>\n"
    )
