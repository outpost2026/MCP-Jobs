"""PostgreSQL persistence for the ETL pipeline (Faze 1 standalone pivot).

Provider-agnostic: connects via DATABASE_URL (Docker, Neon, Supabase, ...).
Graceful degradation: if DB is unreachable, callers log a warning and
continue without DB write - the file-based pipeline keeps working.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from .models import Ad

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path("data") / "schema.sql"

_db = None  # module-level cached connection (reuse across calls in one run)


def get_database_url() -> str:
    """Return DATABASE_URL or '' (empty = DB disabled)."""
    return os.environ.get("DATABASE_URL", "").strip()


def connect(database_url: str | None = None) -> Any:
    """Open a psycopg connection. Raises RuntimeError if psycopg missing."""
    url = database_url or get_database_url()
    if not url:
        raise RuntimeError("DATABASE_URL not set - DB write skipped")
    try:
        import psycopg
        from psycopg.types.json import Jsonb
    except ImportError as e:
        raise RuntimeError(
            "psycopg not installed - pip install 'psycopg[binary]'"
        ) from e
    conn = psycopg.connect(url, autocommit=True)
    conn.jsonb = Jsonb
    return conn


def init_db(conn: Any) -> None:
    """Apply schema.sql (idempotent)."""
    if not SCHEMA_PATH.exists():
        raise RuntimeError(f"schema not found: {SCHEMA_PATH}")
    conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))


def start_run(conn: Any, profile: str) -> int:
    """Insert pipeline_runs row (status=running), return run id."""
    cur = conn.execute(
        "INSERT INTO pipeline_runs (profile, status) VALUES (%s, 'running') RETURNING id",
        (profile,),
    )
    return cur.fetchone()[0]


def finish_run(
    conn: Any,
    run_id: int,
    status: str,
    matched: int,
    raw: int,
    metadata: dict | None = None,
) -> None:
    """Mark run completed/failed with counts."""
    conn.execute(
        "UPDATE pipeline_runs SET status=%s, matched=%s, raw=%s, "
        "completed_at=NOW(), metadata=%s WHERE id=%s",
        (status, matched, raw, conn.jsonb(metadata or {}), run_id),
    )


def upsert_ads(conn: Any, ads: list[Ad], query_name: str, profile: str) -> int:
    """Insert/update ads (URL UNIQUE dedup). Returns number of new rows."""
    if not ads:
        return 0
    new_count = 0
    for ad in ads:
        if not ad.url:
            continue
        cur = conn.execute(
            "INSERT INTO ads (url, title, company, location, salary, description, "
            "matched_keyword, portal, query_name, profile) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (url) DO UPDATE SET "
            "last_seen=CURRENT_DATE, title=EXCLUDED.title, company=EXCLUDED.company, "
            "location=EXCLUDED.location, salary=EXCLUDED.salary, "
            "description=EXCLUDED.description, matched_keyword=EXCLUDED.matched_keyword, "
            "portal=EXCLUDED.portal, query_name=EXCLUDED.query_name "
            "RETURNING (xmax = 0) AS inserted",
            (
                ad.url,
                ad.title,
                ad.company,
                ad.location,
                ad.salary,
                ad.description,
                ad.matched_keyword,
                ad.portal,
                query_name,
                profile,
            ),
        )
        row = cur.fetchone()
        if row and row[0]:
            new_count += 1
    return new_count


def persist_run(
    ads_by_query: dict[str, list[Ad]],
    profile: str,
    matched: int,
    raw: int,
    elapsed_seconds: float,
) -> int | None:
    """Full persistence entry point. Returns run_id or None if DB disabled/failed."""
    global _db
    try:
        if _db is None:
            _db = connect()
        init_db(_db)
        run_id = start_run(_db, profile)
        total_new = 0
        for qname, ads in ads_by_query.items():
            total_new += upsert_ads(_db, ads, qname, profile)
        finish_run(
            _db,
            run_id,
            "completed",
            matched,
            raw,
            {"elapsed_seconds": round(elapsed_seconds, 1), "new_ads": total_new},
        )
        logger.info(
            "DB: run %s completed, %d new ads (dedup against existing)",
            run_id,
            total_new,
        )
        return run_id
    except (RuntimeError, ImportError) as e:
        logger.warning("DB write skipped: %s", e)
        return None
    except Exception as e:
        logger.warning("DB write failed: %s", e)
        return None
