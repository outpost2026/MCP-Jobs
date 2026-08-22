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
from .utils import _fuzzy_norm, fuzzy_key

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]

SCHEMA_PATH = _REPO_ROOT / "data" / "schema.sql"

_db = None  # module-level cached connection (reuse across calls in one run)

_ENV_PATH = _REPO_ROOT / ".env"


def _load_env(path: Path = _ENV_PATH) -> None:
    """Load .env into os.environ (setdefault, idempotent). Mirrors healthcheck.py."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def get_database_url() -> str:
    """Return DATABASE_URL or '' (empty = DB disabled). Loads .env if needed."""
    if not os.environ.get("DATABASE_URL"):
        _load_env()
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


def _richness_score(ad: Ad) -> int:
    """Skore bohatosti dat: description > salary > company > location."""
    score = 0
    if ad.description:
        score += 8
    if ad.salary:
        score += 4
    if ad.company:
        score += 2
    if ad.location:
        score += 1
    return score


def upsert_ads(conn: Any, ads: list[Ad], query_name: str, profile: str) -> int:
    """Insert/update ads with URL + fuzzy (cross-portal) dedup.

    Dedup priorita ("bohatsi data vyhravaji", tie-break = first-seen):
      1. URL UNIQUE — native dedup stejneho inzeratu napric behy.
      2. Fuzzy klic (title, company, location, normalizovany) — stejny
         inzerat cross-publikovany na vice portalech (jobs.cz + prace.cz
         = LMC network). Vyhraje ad s nejbohatsimi daty; portal vitezne
         ad = zdroj, jehoz URL+portal se zachova. Na stejne skore si
         podrzi existujici radek (first-seen, bez churn).

    DB round-tripy: 1 batched SELECT pro vsechny fuzzy klice + 1 insert
    per ad (ON CONFLICT url). Scrape (network-bound) zustava dominantni.
    """
    if not ads:
        return 0

    # 1) Seskup ady podle fuzzy klice (within-batch dedup pred DB).
    fk_groups: dict[tuple, list[Ad]] = {}
    for ad in ads:
        if not ad.url:
            continue
        fk = fuzzy_key(ad)
        if any(fk):
            fk_groups.setdefault(fk, []).append(ad)

    # 2) Jeden batched SELECT: existujici fuzzy klice najednou.
    existing: dict[tuple, list] = {}
    query_keys = list(fk_groups)
    if query_keys:
        titles = [k[0] for k in query_keys]
        companies = [k[1] for k in query_keys]
        rows = conn.execute(
            "SELECT id, title, company, location, salary, description, url, "
            "fuzzy_title, fuzzy_company "
            "FROM ads WHERE (fuzzy_title, fuzzy_company) IN "
            "(SELECT * FROM unnest(%s::text[], %s::text[]))",
            (titles, companies),
        ).fetchall()
        for r in rows:
            fk = (r[7] or "", r[8] or "")
            existing.setdefault(fk, []).append(r)

    # 3) Rozhodnuti per fuzzy klic: kdo vyhraje, co se smaze/preskoci.
    skip_urls: set[str] = set()
    for fk, group in fk_groups.items():
        winner = max(group, key=_richness_score)  # tie-break = first in list
        for a in group:
            if a is not winner:
                skip_urls.add(a.url)  # within-batch loser — neinsertovat
        dups = existing.get(fk, [])
        if not dups:
            continue
        best_existing = max(dups, key=lambda r: _richness_score(_row_to_ad(r)))
        if _richness_score(winner) <= _richness_score(_row_to_ad(best_existing)):
            skip_urls.add(winner.url)  # first-seen vyhrava — bez churn
        else:
            for r in dups:
                conn.execute("DELETE FROM ads WHERE id=%s", (r[0],))

    # 4) Insert zbylych ad (ON CONFLICT url = native URL dedup).
    new_count = 0
    for ad in ads:
        if not ad.url or ad.url in skip_urls:
            continue
        fk = fuzzy_key(ad)
        ft, fc = fk if any(fk) else (None, None)
        fl = _fuzzy_norm(ad.location or "") or None
        cur = conn.execute(
            "INSERT INTO ads (url, title, company, location, salary, description, "
            "matched_keyword, portal, query_name, profile, "
            "fuzzy_title, fuzzy_company, fuzzy_location) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (url) DO UPDATE SET "
            "last_seen=CURRENT_DATE, title=EXCLUDED.title, company=EXCLUDED.company, "
            "location=EXCLUDED.location, salary=EXCLUDED.salary, "
            "description=EXCLUDED.description, matched_keyword=EXCLUDED.matched_keyword, "
            "portal=EXCLUDED.portal, query_name=EXCLUDED.query_name, "
            "fuzzy_title=EXCLUDED.fuzzy_title, fuzzy_company=EXCLUDED.fuzzy_company, "
            "fuzzy_location=EXCLUDED.fuzzy_location "
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
                ft,
                fc,
                fl,
            ),
        )
        row = cur.fetchone()
        if row and row[0]:
            new_count += 1
    return new_count


def _row_to_ad(r) -> Ad:
    """Reconstruct minimal Ad from DB row.

    Row layout (step 2 SELECT): id, title, company, location, salary,
    description, url, fuzzy_title, fuzzy_company, fuzzy_location.
    """
    return Ad(
        title=r[1] or "",
        url=r[6] or "",
        portal="",
        company=r[2],
        location=r[3],
        salary=r[4],
        description=r[5],
    )


def persist_run(
    ads_by_query: dict[str, list[Ad]],
    profile: str,
    matched: int,
    raw: int,
    elapsed_seconds: float,
    database_url: str | None = None,
) -> int | None:
    """Full persistence entry point. Returns run_id or None if DB disabled/failed.

    `database_url` overrides the env/.env DATABASE_URL (used by integration
    tests to target the isolated *_test database — never the live one).
    """
    global _db
    try:
        if _db is None:
            _db = connect(database_url)
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
