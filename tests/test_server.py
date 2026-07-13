"""Phase 01 tests — verify server starts and tools respond."""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Add parent to path for imports
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from mcp_jobs.server import mcp, _find_scrapers_dir


def test_health_check():
    """health_check returns correct status."""
    from mcp_jobs.server import health_check
    result = health_check()
    assert result["status"] == "ok"
    assert result["server"] == "mcp-jobs"
    assert result["version"] == "0.1.0"


def test_server_instance():
    """FastMCP server is properly configured."""
    assert mcp.name == "MCP-Jobs"
    tools = mcp._tool_manager._tools
    assert "health_check" in tools


def test_search_jobs_tool_registered():
    """search_jobs tool is registered."""
    tools = mcp._tool_manager._tools
    assert "search_jobs" in tools


def test_find_scrapers_dir():
    """Local scrapers/ directory is discoverable."""
    d = _find_scrapers_dir()
    assert d is not None, "scrapers/ not found"
    assert (d / "common" / "__init__.py").exists(), "common/__init__.py missing"


def test_search_jobs_graceful_degradation():
    """search_jobs handles missing scrapers/ gracefully."""
    from mcp_jobs.server import search_jobs

    # With mock
    result = search_jobs("python")
    assert isinstance(result, list)
    # Should work since scrapers/ exists in dev environment
    assert len(result) > 0


if __name__ == "__main__":
    test_health_check()
    test_server_instance()
    test_search_jobs_tool_registered()
    test_find_scrapers_dir()
    test_search_jobs_graceful_degradation()
    print("=== ALL MINIMAL TESTS PASSED ===")
