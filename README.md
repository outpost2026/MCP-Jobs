# MCP-Jobs

MCP server for CZ job portal search with live scraping, boolean keyword matching, and EROI analysis.

## Features

- **Live scraping** — real-time search across 4 CZ portals (Bazos, Jobs, Pracecz, Nyx)
- **Boolean matching** — AND via `+`, exclude via `|`, word-boundary matching
- **MCP-native** — stdio transport, FastMCP SDK, ready for AI agent integration
- **Layered OOP architecture** — clean separation: models → infrastructure → providers → server
- **Standalone** — zero external runtime dependencies beyond the Python stack

## Quick start

```bash
pip install mcp-jobs
mcp-jobs                          # Start MCP server (stdio)
mcp-jobs --list-tools              # List available tools
mcp-jobs --version                 # Show version
```

## Tools

| Tool | Description |
|------|-------------|
| `health_check` | Server status and version |
| `search_jobs` | Live keyword search across CZ portals |
| `list_portals` | Available portals and their search URLs |

## Architecture

```
src/mcp_jobs/
├── models.py          # Domain dataclasses (Ad, SearchResult)
├── http.py            # HTTP client with retry, headers, timeout
├── matcher.py         # Boolean keyword matching (\b word boundaries)
├── storage.py         # CSV I/O with incremental dedup
├── providers/         # Portal-specific scrapers
│   ├── base.py        # Abstract base scraper (template method)
│   ├── bazos.py       # Bazos.cz scraper
│   ├── jobs.py        # Jobs.cz scraper
│   ├── pracecz.py     # Prace.cz scraper
│   └── nyx.py         # Nyx.cz scraper
├── server.py          # FastMCP instance + tool registration
└── cli.py             # CLI entry point (stdio MCP transport)
```

## Development

```bash
pip install -e .
pytest tests/ -v
```
