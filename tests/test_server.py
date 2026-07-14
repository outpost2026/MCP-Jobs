from mcp_jobs import __version__
from mcp_jobs.server import mcp, list_portals, PORTAL_ALIASES, ACTIVE_PORTALS


def test_health_check():
    from mcp_jobs.server import health_check
    result = health_check()
    assert result["status"] == "ok"
    assert result["server"] == "mcp-jobs"
    assert result["version"] == __version__
    assert result["phase"] == "03-category-bulk"


def test_server_instance():
    assert mcp.name == "MCP-Jobs"
    tools = mcp._tool_manager._tools
    assert "health_check" in tools
    assert "search_from_config" in tools
    assert "search_from_yaml" in tools
    assert "search_jobs_v2" in tools
    assert "list_portals" in tools


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
    assert isinstance(result, list)
    assert len(result) == 1
    assert "error" in result[0]


def test_search_jobs_v2_unknown_portal():
    from mcp_jobs.server import search_jobs_v2
    result = search_jobs_v2("python", portal="nonexistent")
    assert isinstance(result, list)
    assert len(result) == 1
    assert "error" in result[0]
    assert "nonexistent" in result[0]["error"]
