"""Rebuild PostgreSQL from output snapshots (disaster recovery after TRUNCATE).

Reads the LATEST per-profile snapshot (etl_AI_NATIVE_*.json, etl_LEGACY_MANUAL_*.json)
and re-inserts all ads via the standard persistence path (persist_run), so
URL-dedup and pipeline_runs audit work exactly like a real ETL run.

Usage:
    $env:DATABASE_URL="postgresql://mcpjobs:mcpjobs@localhost:5432/mcpjobs"
    python -X utf8 scripts/rebuild_db_from_output.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mcp_jobs.db import persist_run
from mcp_jobs.models import Ad

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

SNAPSHOTS = [
    ("AI-NATIVE", "etl_AI_NATIVE_20260818_095328.json"),
    ("LEGACY-MANUAL", "etl_LEGACY_MANUAL_20260818_095409.json"),
]


def _ad_from_dict(d: dict) -> Ad:
    return Ad(
        title=d.get("title") or "",
        url=d.get("url") or "",
        portal=d.get("portal") or "",
        date=d.get("date"),
        company=d.get("company"),
        location=d.get("location"),
        salary=d.get("salary"),
        price=d.get("price"),
        description=d.get("description"),
        category_name=d.get("category_name"),
        matched_keyword=d.get("matched_keyword") or "",
    )


def main() -> int:
    for profile, fname in SNAPSHOTS:
        path = OUTPUT_DIR / fname
        if not path.exists():
            print(f"[SKIP] missing snapshot: {path}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        ads_by_query: dict[str, list[Ad]] = {}
        total = 0
        if isinstance(data, list):
            # Canonical output shape: [{query, total_found, results}]
            for entry in data:
                qname = entry.get("query", "query")
                parsed = [
                    _ad_from_dict(a) for a in entry.get("results", []) if a.get("url")
                ]
                ads_by_query[qname] = parsed
                total += len(parsed)
        else:
            # Legacy dict shape: {results: {q: [ad_dicts]}}
            for qname, ads in data.get("results", {}).items():
                parsed = [_ad_from_dict(a) for a in ads if a.get("url")]
                ads_by_query[qname] = parsed
                total += len(parsed)
        run_id = persist_run(
            ads_by_query,
            profile=profile,
            matched=total,
            raw=data.get("total_raw", 0) if not isinstance(data, list) else 0,
            elapsed_seconds=0.0,
        )
        print(f"[OK] {profile}: {total} ads -> run {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
