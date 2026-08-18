"""Integration tests for PostgreSQL persistence (Faze 1).

Skipped automatically when DATABASE_URL is not set (local dev without DB,
or CI without the postgres service). Run locally:

    docker compose up -d
    $env:DATABASE_URL = "postgres://mcpjobs:mcpjobs@localhost:5432/mcpjobs"
    python -X utf8 -m pytest tests/test_db.py -v
"""

from __future__ import annotations

import pytest

from mcp_jobs.db import (
    connect,
    finish_run,
    get_database_url,
    init_db,
    persist_run,
    start_run,
    upsert_ads,
)
from mcp_jobs.models import Ad

pytestmark = pytest.mark.skipif(
    not get_database_url(),
    reason="DATABASE_URL not resolvable — DB integration tests skipped",
)


@pytest.fixture()
def conn():
    c = connect()
    init_db(c)
    c.execute("TRUNCATE ads, pipeline_runs RESTART IDENTITY CASCADE")
    yield c
    c.close()


def _ad(url: str, title: str = "Test job") -> Ad:
    return Ad(
        title=title,
        url=url,
        portal="jobs",
        company="Acme",
        location="Praha",
        salary="60000",
        description="Python developer role",
        matched_keyword="python",
    )


def test_upsert_dedup_single_row(conn):
    ad = _ad("https://example.com/job/1")
    n1 = upsert_ads(conn, [ad], query_name="python_ai", profile="ai_native")
    n2 = upsert_ads(conn, [ad], query_name="python_ai", profile="ai_native")
    assert n1 == 1
    assert n2 == 0
    count = conn.execute("SELECT COUNT(*) FROM ads").fetchone()[0]
    assert count == 1


def test_upsert_updates_last_seen_on_conflict(conn):
    ad = _ad("https://example.com/job/2")
    upsert_ads(conn, [ad], query_name="q1", profile="p")
    upsert_ads(conn, [ad], query_name="q1", profile="p")
    rows = conn.execute(
        "SELECT status, query_name FROM ads WHERE url=%s", (ad.url,)
    ).fetchall()
    assert rows[0][0] == "new"
    assert rows[0][1] == "q1"


def test_run_lifecycle(conn):
    run_id = start_run(conn, "ai_native")
    finish_run(conn, run_id, "completed", matched=5, raw=100)
    rows = conn.execute(
        "SELECT status, matched, raw FROM pipeline_runs WHERE id=%s", (run_id,)
    ).fetchall()
    assert rows[0] == ("completed", 5, 100)


def test_persist_run_graceful_without_db(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    result = persist_run({"q": [_ad("https://x.example/1")]}, "p", 1, 10, 1.0)
    assert result is None


def test_persist_run_creates_run_and_ads(conn):
    ads = [_ad("https://example.com/job/3"), _ad("https://example.com/job/4")]
    run_id = persist_run(
        {"q1": ads}, "ai_native", matched=2, raw=50, elapsed_seconds=3.5
    )
    assert run_id is not None
    status = conn.execute(
        "SELECT status FROM pipeline_runs WHERE id=%s", (run_id,)
    ).fetchone()[0]
    assert status == "completed"
    count = conn.execute("SELECT COUNT(*) FROM ads").fetchone()[0]
    assert count == 2
