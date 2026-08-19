"""CLI entry point for MCP-Jobs server."""

import logging
import sys
from pathlib import Path

from .utils import ensure_utf8_stdout


def _setup_logging() -> None:
    """P25 (GT-010): log to FileHandler ONLY — never StreamHandler(stderr).

    Bez konfigurace pouziva root logger logging.lastResort (interni
    StreamHandler(stderr)). V MCP STDIO serveru je stderr sdilena pipe
    s klientem: dedup/scrape warningy (stovky zaznamu pri full runu)
    zaplni pipe buffer (4-64 KB) -> writer blokuje -> event loop freeze
    -> MCP timeout -32001 na vsech tool requests (vce. search_status).
    """
    log_dir = Path(__file__).resolve().parent.parent.parent / "data"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_dir / "mcp-jobs.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        encoding="utf-8",
        force=True,
    )


def main():
    # P18: Console encoding safety — Windows cp1250 nepodporuje Unicode > U+00FF
    ensure_utf8_stdout()
    _setup_logging()

    from .server import mcp

    if "--help" in sys.argv or "-h" in sys.argv:
        print("MCP-Jobs server — CZ job portal search via MCP")
        print()
        print("Usage:")
        print("  mcp-jobs                    Start MCP server (stdio)")
        print("  mcp-jobs --list-tools       List available tools")
        print("  mcp-jobs --version          Show version")
        return

    if "--version" in sys.argv or "-V" in sys.argv:
        from . import __version__

        print(f"MCP-Jobs {__version__}")
        return

    if "--list-tools" in sys.argv:
        print("Available tools:")
        for name, tool in mcp._tool_manager._tools.items():
            desc = tool.description.split("\n")[0] if tool.description else ""
            print(f"  {name:30s} {desc}")
        return

    mcp.run()


if __name__ == "__main__":
    main()
