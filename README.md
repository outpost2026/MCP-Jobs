# MCP-Jobs

MCP server for CZ job portal search and EROI analysis.

## Phase 01 — Iterative Development

Minimal skeleton with:
- health_check
- search_jobs (keyword matching against topics CSVs)

## Quick start

```bash
pip install -e .
mcp-jobs --list-tools
mcp-jobs                   # starts MCP server on stdio
```

## Tools

| Tool | Description |
|------|-------------|
| health_check | Server status |
| search_jobs | Keyword search across CZ portals |
