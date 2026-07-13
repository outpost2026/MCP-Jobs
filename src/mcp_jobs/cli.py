"""CLI entry point for MCP-Jobs server."""

import sys


def main():
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
