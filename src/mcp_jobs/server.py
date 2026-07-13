"""
MCP-Jobs server — FastMCP instance with tool registration.

Phase 01: Iterative development. Minimal skeleton with health_check
and search_jobs that can be iterated on.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("MCP-Jobs")


# ── Helpers ───────────────────────────────────────────────────────────

def _find_scrapers_dir() -> Optional[Path]:
    """Locate the scrapers/ directory for importing common modules.
    
    Tries relative to this repo first, then common locations.
    Returns None if not found (search_jobs will degrade gracefully).
    """
    candidates = [
        Path(__file__).parent.parent.parent.parent / "scrapers",
        Path(__file__).parent.parent.parent.parent.parent / "scrapers",
    ]
    for c in candidates:
        if (c / "common" / "__init__.py").exists():
            return c
    return None


# ── Tools ─────────────────────────────────────────────────────────────

@mcp.tool(
    description="Check server health and version."
)
def health_check() -> dict:
    return {
        "status": "ok",
        "server": "mcp-jobs",
        "version": "0.1.0",
        "phase": "01-iterative",
    }


@mcp.tool(
    description=(
        "Full-text keyword search across CZ job portals. "
        "Uses unified boolean matching: AND via +, exclude via |, word boundaries."
    )
)
def search_jobs(
    query: str,
    portal: str = "vše",
) -> list[dict]:
    """
    Search CZ job portals by keyword query.

    Args:
        query: Search query. Use '+' for AND (e.g. 'python+developer'),
               pipe '|' for exclude terms.
        portal: Portal filter: 'bazos', 'jobs', 'pracecz', or 'vše' (all).
    """
    SCRAPERS_DIR = _find_scrapers_dir()
    if SCRAPERS_DIR is None:
        return [{"error": "scrapers/ directory not found. Cannot search without topic files."}]

    import sys
    sys.path.insert(0, str(SCRAPERS_DIR))

    from common import load_csv, match_keywords

    PORTAL_MAP = {
        "bazos":   (SCRAPERS_DIR / "bazos" / "topics.csv", None),
        "jobs":    (SCRAPERS_DIR / "jobs" / "topics_no_priority.csv", None),
        "pracecz": (SCRAPERS_DIR / "pracecz" / "topics_no_priority.csv", None),
        "vše":     None,  # special: iterate all
    }

    if portal not in PORTAL_MAP:
        return [{"error": f"Unknown portal '{portal}'. Choose: vše, bazos, jobs, pracecz"}]

    results = []

    def _search(topics_csv: Path) -> list[dict]:
        if not topics_csv.exists():
            return [{"error": f"Topics file not found: {topics_csv}"}]
        topics = load_csv(topics_csv)

        # Build a synthetic search: treat query as a single topic entry
        # with the query as keyword and no exclude
        synthetic_topic = {"keyword": query, "exclude": ""}
        matched = False

        # We match all topics that contain the query terms
        found = []
        for t in topics:
            raw_kw = t.get("keyword", "").strip()
            if not raw_kw:
                continue
            kw_lower = raw_kw.lower()
            reqs = [r.strip() for r in query.lower().split("+") if r.strip()]
            if not reqs:
                continue
            if all(r in kw_lower for r in reqs):
                found.append(raw_kw)

        return found

    if portal == "vše":
        for p_name in ("bazos", "jobs", "pracecz"):
            csv_path, _ = PORTAL_MAP[p_name]
            matches = _search(csv_path)
            if matches:
                for kw in matches:
                    results.append({"portal": p_name, "keyword": kw})
    else:
        csv_path, _ = PORTAL_MAP[portal]
        for kw in _search(csv_path):
            results.append({"portal": portal, "keyword": kw})

    if not results:
        return [{"message": f"No matching keywords found for '{query}' in {portal}."}]

    return results
