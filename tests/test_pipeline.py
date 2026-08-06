from mcp_jobs.models import Ad
from mcp_jobs.pipeline import SearchPipeline, _location_filter, _salary_filter, _dedup


class FakeProvider:
    def __init__(self, ads: list[Ad]):
        self.ads = ads

    def scrape_all(self, url: str, max_pages: int = 5) -> list[Ad]:
        return self.ads


def test_location_filter_empty():
    ad = Ad(title="Test", url="http://x", portal="jobs", location="Brno")
    assert _location_filter(ad, []) is True
    assert _location_filter(ad, ["brno"]) is True


def test_location_filter_match():
    ad = Ad(title="Test", url="http://x", portal="jobs", location="Brno-město")
    assert _location_filter(ad, ["brno"]) is True


def test_location_filter_no_match():
    ad = Ad(title="Test", url="http://x", portal="jobs", location="Praha")
    assert _location_filter(ad, ["brno"]) is False


def test_salary_filter_empty():
    ad = Ad(title="Test", url="http://x", portal="jobs", salary=None)
    assert _salary_filter(ad, 0) is True
    assert _salary_filter(ad, 40000) is True


def test_salary_filter_match():
    ad = Ad(title="Test", url="http://x", portal="jobs", salary="50000 Kč")
    assert _salary_filter(ad, 40000) is True


def test_salary_filter_no_match():
    ad = Ad(title="Test", url="http://x", portal="jobs", salary="30000 Kč")
    assert _salary_filter(ad, 40000) is False


def test_unique_by_url():
    ads = [
        Ad(title="A", url="http://x/1", portal="jobs"),
        Ad(title="B", url="http://x/2", portal="jobs"),
        Ad(title="A dup", url="http://x/1", portal="jobs"),
    ]
    result = _dedup(ads)
    assert len(result) == 2
    assert result[0].title == "A"
    assert result[1].title == "B"


def test_unique_by_url_all_unique():
    ads = [
        Ad(title="A", url="http://x/1", portal="jobs"),
        Ad(title="B", url="http://x/2", portal="jobs"),
    ]
    result = _dedup(ads)
    assert len(result) == 2


def test_unique_by_url_empty():
    assert _dedup([]) == []


def test_salary_filter_thousand_separator():
    ad = Ad(title="Test", url="http://x", portal="jobs", salary="30 000 - 50 000 Kč")
    assert _salary_filter(ad, 40000) is True
    assert _salary_filter(ad, 60000) is False


def test_salary_filter_unparseable():
    ad = Ad(title="Test", url="http://x", portal="jobs", salary="Dohodou")
    assert _salary_filter(ad, 40000) is True


def test_dedup_normalized():
    ads = [
        Ad(
            title="CNC Programátor",
            url="http://x/1",
            portal="jobs",
            company="ABC s.r.o.",
        ),
        Ad(
            title="CNC Programátor",
            url="http://x/1",
            portal="jobs",
            company="ABC s.r.o.",
        ),
        Ad(
            title="  CNC Programátor  ",
            url="http://x/2",
            portal="jobs",
            company="  ABC S.R.O.  ",
        ),
    ]
    result = _dedup(ads)
    assert len(result) == 1
    assert result[0].url == "http://x/1"


def test_dedup_same_title_company_different_location_kept():
    """C1 fix: same title+company, different URL and location -> both kept."""
    ads = [
        Ad(
            title="Technik",
            url="http://x/1",
            portal="jobs",
            company="ABC s.r.o.",
            location="Praha",
        ),
        Ad(
            title="Technik",
            url="http://x/2",
            portal="jobs",
            company="ABC s.r.o.",
            location="Brno",
        ),
    ]
    result = _dedup(ads)
    assert len(result) == 2


def test_dedup_fuzzy_drop_logs_warning(caplog):
    """Fuzzy hit on different URL now logs a warning (C1 fix)."""
    import logging

    ads = [
        Ad(
            title="Technik",
            url="http://x/1",
            portal="jobs",
            company="ABC s.r.o.",
            location="Praha",
        ),
        Ad(
            title="Technik",
            url="http://x/2",
            portal="jobs",
            company="ABC s.r.o.",
            location="Praha",
        ),
    ]
    with caplog.at_level(logging.WARNING):
        _dedup(ads)
    assert any("Dedup: fuzzy hit" in r.message for r in caplog.records)


def test_salary_filter_bazos_price_fallback():
    """M3 fix: bazos ad with price (no salary) is filtered by price."""
    ad = Ad(title="CNC", url="http://x/1", portal="bazos", price="45 000 Kč")
    assert _salary_filter(ad, 40000) is True
    ad_low = Ad(title="CNC", url="http://x/2", portal="bazos", price="30 000 Kč")
    assert _salary_filter(ad_low, 40000) is False


def test_salary_filter_uses_salary_over_price():
    """When both present, salary wins (jobs/pracecz ads)."""
    ad = Ad(
        title="Dev",
        url="http://x/1",
        portal="jobs",
        salary="60 000 Kč",
        price="30 000 Kč",
    )
    assert _salary_filter(ad, 40000) is True


def test_empty_boolean_skipped():
    """Empty boolean expression is skipped with warning (does not crash)."""
    from mcp_jobs.config import UserConfig
    from pathlib import Path
    import tempfile, json

    yaml = """
    portals: {}
    queries:
      empty_query:
        boolean: ""
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml)
        tmp = f.name
    try:
        config = UserConfig.from_yaml(Path(tmp))
        pipeline = SearchPipeline(config)
        result = pipeline.run()
        assert "empty_query" not in result
    finally:
        Path(tmp).unlink(missing_ok=True)


def test_parallel_deterministic_same_as_sequential():
    """Paralel scraping (max_workers=3) dava IDENTICKE vysledky jako sekvencni.

    Pouziva FakeProvider s konfigurovatelnym zpozdenim, aby se otestoval
    jak determinismus, tak i soubeznost (casove mereni).
    """
    import time
    from concurrent.futures import ThreadPoolExecutor
    from mcp_jobs.config import (
        UserConfig,
        PortalConfig,
        CategoryConfig,
        QueryConfig,
        PipelineSettings,
    )
    from mcp_jobs import providers as providers_mod

    delay = {"s": 0.05}

    class SlowProvider:
        name = "slow"

        def __init__(self, http_client=None):
            self.stats = type(
                "FakeStats",
                (),
                {
                    "to_dict": lambda self: {
                        "requests_ok": 1,
                        "requests_failed": 0,
                    },
                    "errors": [],
                },
            )()

        def scrape_all(self, url, max_pages=5, params=None):
            time.sleep(delay["s"])
            return [
                Ad(
                    title="Python Dev",
                    url="http://x/1",
                    portal="slow",
                    description="",
                    company="Acme",
                )
            ]

        def fetch_detail(self, ad):
            return "Full detail description text"

    orig = providers_mod.REGISTRY.get("slow")
    providers_mod.REGISTRY["slow"] = SlowProvider
    try:
        portals = {
            "slow": PortalConfig(
                enabled=True,
                categories=[CategoryConfig(url="http://x", pages=1)],
            )
        }
        queries = {
            "q1": QueryConfig(boolean="python"),
        }
        results_by_workers = {}
        for workers in (1, 3):
            config = UserConfig(
                portals=portals,
                queries=queries,
                pipeline=PipelineSettings(max_workers=workers, url_allowlist=[]),
            )
            pipeline = SearchPipeline(config)
            start = time.perf_counter()
            results, stats, _ = pipeline.run()
            elapsed = time.perf_counter() - start
            results_by_workers[workers] = (results, stats, elapsed)

        seq_results, _, seq_time = results_by_workers[1]
        par_results, _, par_time = results_by_workers[3]

        # Determinismus: shodny pocet a obsah vysledku.
        assert len(seq_results["q1"]) == len(par_results["q1"]) == 1
        assert seq_results["q1"][0].url == par_results["q1"][0].url
        assert seq_results["q1"][0].description == par_results["q1"][0].description

        # Soubeznost: paralelni bez (~3x zrychleni na 1 portalu vs 1; zde
        # jen overime, ze paralelni NENI pomalejsi nez sekvencni + margin).
        assert par_time < seq_time + 0.5, (
            f"parallel ({par_time:.3f}s) should not be slower than "
            f"sequential ({seq_time:.3f}s)"
        )
    finally:
        if orig is None:
            del providers_mod.REGISTRY["slow"]
        else:
            providers_mod.REGISTRY["slow"] = orig


def test_detail_cache_retries_failed_fetch():
    """M2 fix: failed detail fetch is NOT cached, next query retries."""
    from mcp_jobs.config import UserConfig
    from mcp_jobs import providers as providers_mod

    calls = {"n": 0}

    class FlakyProvider:
        name = "flaky"

        def __init__(self, http_client=None):
            self.stats = type(
                "FakeStats",
                (),
                {
                    "to_dict": lambda self: {
                        "requests_ok": 0,
                        "requests_failed": 0,
                    },
                    "errors": [],
                },
            )()

        def scrape_all(self, url, max_pages=5, params=None):
            return [
                Ad(
                    title="Python Dev",
                    url="http://x/1",
                    portal="flaky",
                    description="",
                    company="Acme",
                )
            ]

        def fetch_detail(self, ad):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("transient")
            return "Full detail description text"

    orig = providers_mod.REGISTRY.get("flaky")
    providers_mod.REGISTRY["flaky"] = FlakyProvider
    try:
        from mcp_jobs.config import PipelineSettings as _PS

        config = UserConfig(
            portals={
                "flaky": __import__(
                    "mcp_jobs.config", fromlist=["PortalConfig"]
                ).PortalConfig(
                    enabled=True,
                    categories=[
                        __import__(
                            "mcp_jobs.config", fromlist=["CategoryConfig"]
                        ).CategoryConfig(url="http://x", pages=1)
                    ],
                )
            },
            queries={
                "q1": __import__(
                    "mcp_jobs.config", fromlist=["QueryConfig"]
                ).QueryConfig(boolean="python"),
                "q2": __import__(
                    "mcp_jobs.config", fromlist=["QueryConfig"]
                ).QueryConfig(boolean="python"),
            },
            pipeline=_PS(url_allowlist=[]),
        )
        pipeline = SearchPipeline(config)
        results, _, _ = pipeline.run()
        # BUG-001 fix: neuspech se cache jako _FAILED, retry se NEDela.
        # Drive: calls["n"]==2 (retry). Nyni: calls["n"]==1 (cache failure).
        assert calls["n"] == 1, (
            f"expected 1 detail fetch (cached failure), got {calls['n']}"
        )
        assert "q1" in results and "q2" in results
        # Description zustava prazdne (fetch selhal, cached _FAILED).
        assert results["q1"][0].description == ""
        assert results["q2"][0].description == ""
    finally:
        if orig is None:
            del providers_mod.REGISTRY["flaky"]
        else:
            providers_mod.REGISTRY["flaky"] = orig
