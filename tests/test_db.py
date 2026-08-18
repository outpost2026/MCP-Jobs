"""Integration tests for PostgreSQL persistence (Faze 1).

ISOLATION (P73): these tests NEVER touch the live database. They connect to
a dedicated test database derived from DATABASE_URL by appending `_test`
(e.g. `mcpjobs` -> `mcpjobs_test`) and refuse (hard fail) to TRUNCATE any
database whose name does not end with `_test`.

Create the test DB once (docker):
    docker exec mcp-jobs-postgres createdb -U mcpjobs mcpjobs_test

Run locally:
    python -X utf8 -m pytest tests/test_db.py -v

If DATABASE_URL is not resolvable the tests are skipped (CI without DB).
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

_TEST_DB_SUFFIX = "_test"


def _derive_test_db_url() -> str:
    """Derive the isolated test DB URL from DATABASE_URL (mcpjobs -> mcpjobs_test)."""
    url = get_database_url().rstrip("/")
    if not url:
        return ""
    base, _, dbname = url.rpartition("/")
    if not dbname:
        return url
    if dbname.endswith(_TEST_DB_SUFFIX):
        return url
    return f"{base}/{dbname}{_TEST_DB_SUFFIX}"


TEST_DATABASE_URL = _derive_test_db_url()

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="DATABASE_URL not resolvable — DB integration tests skipped",
)


@pytest.fixture()
def conn():
    c = connect(TEST_DATABASE_URL)
    init_db(c)
    dbname = c.execute("SELECT current_database()").fetchone()[0]
    if not dbname.endswith(_TEST_DB_SUFFIX):
        c.close()
        pytest.fail(
            f"Refusing to run TRUNCATE against non-test DB: {dbname} "
            f"(isolation P73 violated)"
        )
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
        {"q1": ads},
        "ai_native",
        matched=2,
        raw=50,
        elapsed_seconds=3.5,
        database_url=TEST_DATABASE_URL,
    )
    assert run_id is not None
    status = conn.execute(
        "SELECT status FROM pipeline_runs WHERE id=%s", (run_id,)
    ).fetchone()[0]
    assert status == "completed"
    count = conn.execute("SELECT COUNT(*) FROM ads").fetchone()[0]
    assert count == 2
