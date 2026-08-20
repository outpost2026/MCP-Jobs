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
    ads = [
        _ad("https://example.com/job/3"),
        Ad(
            title="Python Backend",
            url="https://example.com/job/4",
            portal="jobs",
            company="Acme",
            location="Brno",
            salary="65000",
            description="Backend role",
            matched_keyword="python",
        ),
    ]
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


def _ad_rich(url: str, **kw) -> Ad:
    """Ad s rucne specifikovanymi poli (richness scoring)."""
    base = dict(
        title="SERVISNI TECHNIK VYTAHU",
        url=url,
        portal="pracecz",
        company="Schindler",
        location="Praha",
        salary=None,
        description=None,
        matched_keyword="q",
    )
    base.update(kw)
    return Ad(**base)


def test_fuzzy_dedup_same_semantic_ad_cross_portal(conn):
    """Stejny inzerat na jobs.cz + prace.cz (ruzne URL, stejna data) = 1 radka."""
    jobs = _ad_rich(
        "https://www.jobs.cz/rpd/2001109039/",
        portal="jobs",
        salary="60000",
        description="Vytahy Schindler",
    )
    prace = _ad_rich(
        "https://www.prace.cz/nabidka/f7fdcc20/",
        portal="pracecz",
        salary="60000",
        description="Vytahy Schindler",
    )
    n1 = upsert_ads(conn, [jobs], query_name="q", profile="p")
    n2 = upsert_ads(conn, [prace], query_name="q", profile="p")
    assert n1 == 1
    assert n2 == 0  # fuzzy hit — pracecz preskoceno (first-seen jobs vyhrava)
    rows = conn.execute("SELECT COUNT(*) FROM ads").fetchone()[0]
    assert rows == 1
    portal = conn.execute("SELECT portal FROM ads").fetchone()[0]
    assert portal == "jobs"  # portal prvni ad se zachova


def test_fuzzy_dedup_richer_data_wins(conn):
    """Nova ad s bohatsimi daty (description) nahradi chudsi existujici."""
    poor = _ad_rich(
        "https://www.jobs.cz/rpd/100/",
        portal="jobs",
        description=None,  # chudsi
    )
    rich = _ad_rich(
        "https://www.prace.cz/nabidka/100/",
        portal="pracecz",
        description="Kompletni popis role",  # bohatsi
    )
    upsert_ads(conn, [poor], query_name="q", profile="p")
    n = upsert_ads(conn, [rich], query_name="q", profile="p")
    assert n == 1  # rich nahradil poor (DELETE + insert)
    rows = conn.execute("SELECT COUNT(*) FROM ads").fetchone()[0]
    assert rows == 1
    portal, desc = conn.execute("SELECT portal, description FROM ads").fetchone()
    assert portal == "pracecz"  # portal vitezne (bohatsi) ad
    assert desc == "Kompletni popis role"


def test_fuzzy_dedup_tie_keeps_existing(conn):
    """Stejna bohatost dat — first-seen (existujici radka) vyhrava, bez churn."""
    first = _ad_rich(
        "https://www.jobs.cz/rpd/200/",
        portal="jobs",
        company="Acme",
        location="Praha",
    )
    second = _ad_rich(
        "https://www.prace.cz/nabidka/200/",
        portal="pracecz",
        company="Acme",
        location="Praha",
    )
    upsert_ads(conn, [first], query_name="q", profile="p")
    n = upsert_ads(conn, [second], query_name="q", profile="p")
    assert n == 0
    rows = conn.execute("SELECT COUNT(*) FROM ads").fetchone()[0]
    assert rows == 1
    portal = conn.execute("SELECT portal FROM ads").fetchone()[0]
    assert portal == "jobs"


def test_fuzzy_dedup_en_dash_and_diacritics(conn):
    """Normalizace: en-dash vs hyphen + diakritika = stejny fuzzy klic."""
    a = _ad_rich(
        "https://www.jobs.cz/rpd/300/",
        portal="jobs",
        location="Praha - Uhrineves",
    )
    b = _ad_rich(
        "https://www.prace.cz/nabidka/300/",
        portal="pracecz",
        location="Praha \u2013 Uhrineves",  # en-dash
    )
    upsert_ads(conn, [a], query_name="q", profile="p")
    n = upsert_ads(conn, [b], query_name="q", profile="p")
    assert n == 0  # normalizovany klic se shoduje — dedup zafungoval
    rows = conn.execute("SELECT COUNT(*) FROM ads").fetchone()[0]
    assert rows == 1


def test_fuzzy_dedup_within_batch(conn):
    """Dve ady se stejnym fuzzy klicem v JEDNOM batchi = 1 radka."""
    a = _ad_rich("https://www.jobs.cz/rpd/400/", portal="jobs")
    b = _ad_rich("https://www.prace.cz/nabidka/400/", portal="pracecz")
    n = upsert_ads(conn, [a, b], query_name="q", profile="p")
    assert n == 1  # bohatost stejna — prvni v batchi vyhrava
    rows = conn.execute("SELECT COUNT(*) FROM ads").fetchone()[0]
    assert rows == 1
    portal = conn.execute("SELECT portal FROM ads").fetchone()[0]
    assert portal == "jobs"


def test_fuzzy_dedup_skips_empty_fuzzy_key(conn):
    """Ad bez title (prazdny fuzzy klic) spolehne na URL UNIQUE."""
    a = _ad_rich("https://example.com/only-url/", title="")
    n1 = upsert_ads(conn, [a], query_name="q", profile="p")
    n2 = upsert_ads(conn, [a], query_name="q", profile="p")
    assert n1 == 1
    assert n2 == 0
    rows = conn.execute("SELECT COUNT(*) FROM ads").fetchone()[0]
    assert rows == 1
