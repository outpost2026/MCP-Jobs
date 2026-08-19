import json

from mcp_jobs import __version__
from mcp_jobs.server import (
    ACTIVE_PORTALS,
    PORTAL_ALIASES,
    _query_store,
    _store_results,
    get_ads_report_resource,
    get_ads_resource,
    list_ads_resources,
    list_portals,
    mcp,
)


def test_health_check():
    from mcp_jobs.server import health_check

    result = health_check()
    assert result["status"] == "ok"
    assert result["server"] == "mcp-jobs"
    assert result["version"] == __version__
    assert result["phase"] == "05-l2-resources"


def test_server_instance():
    assert mcp.name == "MCP-Jobs"
    tools = mcp._tool_manager._tools
    assert "health_check" in tools
    assert "search_from_config" in tools
    assert "search_from_yaml" in tools
    assert "search_jobs_v2" in tools
    assert "search_status" in tools
    assert "list_portals" in tools

    resources = mcp._resource_manager._resources
    templates = mcp._resource_manager._templates
    resource_names = {r.name for r in resources.values() if r.name}
    template_names = {t.name for t in templates.values() if t.name}
    all_resources = resource_names | template_names
    assert "ads_list" in all_resources
    assert "ads_by_id" in all_resources
    assert "ads_report_by_id" in all_resources


def test_active_portals_no_nyx():
    assert "nyx" not in ACTIVE_PORTALS
    assert "bazos" in ACTIVE_PORTALS
    assert "jobs" in ACTIVE_PORTALS
    assert "pracecz" in ACTIVE_PORTALS
    assert len(ACTIVE_PORTALS) == 3


def test_portal_aliases():
    assert PORTAL_ALIASES["vše"] == "vše"
    assert PORTAL_ALIASES["vse"] == "vše"
    assert PORTAL_ALIASES["all"] == "vše"
    assert PORTAL_ALIASES["bazos"] == "bazos"
    assert PORTAL_ALIASES["jobs"] == "jobs"
    assert PORTAL_ALIASES["pracecz"] == "pracecz"
    assert PORTAL_ALIASES["prace"] == "pracecz"
    assert "nyx" not in PORTAL_ALIASES


def test_list_portals():
    portals = list_portals()
    assert len(portals) == 3
    names = [p["name"] for p in portals]
    assert "bazos" in names
    assert "jobs" in names
    assert "pracecz" in names
    for p in portals:
        assert "default_category" in p
        assert p["default_category"]


def test_search_from_config_not_found():
    from mcp_jobs.server import search_from_config

    result = search_from_config("/nonexistent/path/config.yaml")
    assert "error" in result
    assert "Config file not found" in result["error"]


def test_search_from_config_submits_job(tmp_path):
    """Valid config path submits an async job and returns job_id immediately."""
    from mcp_jobs.server import search_from_config

    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "queries:\n  test:\n    boolean: python\n    portals: [jobs]\n",
        encoding="utf-8",
    )
    result = search_from_config(str(cfg))
    assert "job_id" in result
    assert result["status"] in ("pending", "running", "done")


def test_search_status_unknown():
    from mcp_jobs.server import search_status

    result = search_status("deadbeef")
    assert "error" in result


def test_search_jobs_v2_unknown_portal():
    from mcp_jobs.server import search_jobs_v2

    result = search_jobs_v2("python", portal="nonexistent")
    assert "error" in result
    assert "nonexistent" in result["error"]


# ── Prompts ──────────────────────────────────────────────────────────


def test_search_expert_prompt_registered():
    prompts = mcp._prompt_manager._prompts
    assert "search_expert" in prompts


def test_search_expert_basic():
    from mcp_jobs.server import search_expert

    result = search_expert("python developer", "Praha", 40000)
    assert len(result) == 1
    assert result[0]["role"] == "user"
    content = result[0]["content"]
    assert "Generated Boolean Query" in content
    assert "(python) AND (developer) AND (Praha)" in content
    assert "search_jobs_v2" in content


def test_search_expert_with_exclude():
    from mcp_jobs.server import search_expert

    result = search_expert("python", exclude_terms="senior,lead")
    content = result[0]["content"]
    assert "NOT (senior)" in content
    assert "NOT (lead)" in content


def test_search_expert_multi_word_exclude_valid():
    """Multi-word exclude terms must be parenthesized AND-joined, not 'NOT a b' (parse error)."""
    from mcp_jobs.matcher import evaluate_boolean, validate_boolean
    from mcp_jobs.server import search_expert

    result = search_expert("python developer", exclude_terms="hledam praci,senior")
    content = result[0]["content"]
    assert "NOT (hledam AND praci)" in content
    assert "NOT (senior)" in content
    query = "python AND developer AND NOT (hledam AND praci) AND NOT (senior)"
    assert validate_boolean(query) is True
    assert evaluate_boolean("Python developer", query) is True
    assert evaluate_boolean("Hledam praci Python developer", query) is False
    assert evaluate_boolean("Senior Python developer", query) is False


def test_search_expert_no_location():
    from mcp_jobs.server import search_expert

    result = search_expert("python developer")
    content = result[0]["content"]
    assert "(python) AND (developer)" in content
    assert "locations:" in content


# ── L2 Resources ────────────────────────────────────────────────


def test_store_and_list_resources():
    _query_store.clear()
    qid = _store_results(
        [{"query": "test", "total_found": 1, "results": [{"title": "Test Ad"}]}]
    )
    assert len(qid) == 8

    listing = json.loads(list_ads_resources())
    assert len(listing) == 1
    assert listing[0]["query_id"] == qid


def test_get_ads_resource():
    _query_store.clear()
    data = [
        {
            "query": "test",
            "total_found": 1,
            "results": [{"title": "Python Dev", "url": "https://example.com/job"}],
        }
    ]
    qid = _store_results(data)

    raw = get_ads_resource(qid)
    parsed = json.loads(raw)
    assert len(parsed) == 1
    assert parsed[0]["results"][0]["title"] == "Python Dev"


def test_get_ads_resource_unknown():
    _query_store.clear()
    try:
        get_ads_resource("deadbeef")
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "deadbeef" in str(e)


def test_get_ads_report_resource():
    _query_store.clear()
    data = [
        {
            "query": "test",
            "total_found": 1,
            "results": [
                {
                    "title": "Python Dev",
                    "url": "https://example.com/job",
                    "portal": "jobs",
                }
            ],
        }
    ]
    qid = _store_results(data)

    report = get_ads_report_resource(qid)
    assert "Python Dev" in report
    assert "Generated" in report


def test_store_results_empty_list():
    _query_store.clear()
    _store_results([])
    listing = json.loads(list_ads_resources())
    assert len(listing) == 1
    assert listing[0]["query_count"] == 0


def test_resource_uris_in_search_output():
    """search_jobs_v2 with unknown portal should NOT have job_id."""
    from mcp_jobs.server import search_jobs_v2

    result = search_jobs_v2("python", portal="nonexistent")
    assert "job_id" not in result
    assert "error" in result
