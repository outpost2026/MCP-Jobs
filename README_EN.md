<div align="left">
  <a href="https://github.com/outpost2026/MCP-Jobs/blob/main/README.md">
    <img src="https://flagcdn.com/24x18/cz.png" alt="CZ" height="18"> Česky
  </a>
  &nbsp;|&nbsp;
  <a href="https://github.com/outpost2026/MCP-Jobs/blob/main/README_EN.md">
    <img src="https://flagcdn.com/24x18/gb.png" alt="EN" height="18"> English
  </a>
</div>

# MCP-Jobs

MCP server for scraping Czech job portals with boolean matching, exclude lists, and location/salary filters. Successor to legacy scrapers — **4.5× faster**, config-driven, 97 unit tests, production hardening.

## Features

- **8 configurable queries** — python_jobs, cnc_jobs, elektrikar, spravce, udrzbar, zahradnik, truhlar, strechy
- **Boolean matching** — full AND/OR/NOT/parens AST parser + diacritics + LRU cache (8000→8 parses)
- **Exclude lists** — word-boundary on title, substring on description (Czech inflection support)
- **NFKD diacritics** — automatic normalization (programátor = programator)
- **Location & salary filter** — substring location match, regex salary extraction (thousand-separator)
- **Bazos subdomains** — automatic detection (prace.bazos.cz, www.bazos.cz, etc.)
- **Rate limiting** — 1.0s between requests (ToS compliance, IP protection)
- **Pages guard** — max 50 pages per call (resource abuse prevention)
- **Auto-validation** — boolean expressions validated at config load time (fail-fast)
- **MCP-native** — stdio transport, FastMCP SDK, ready for AI agent integration
- **97 unit tests** — pytest, full coverage of matcher, pipeline, providers, config
- **Structured logging** — per-card skip count, 0-ads alert, no silent failures
- **MCP L3 Prompts** — `search_expert` prompt for natural language to boolean query conversion

## Architecture

```
src/mcp_jobs/
├── config.py          # UserConfig → PortalConfig → CategoryConfig → QueryConfig
├── models.py          # Ad dataclass (title, url, portal, desc, company, ...)
├── http.py            # HTTP client with retry, timeout, rate limiting (1.0s delay)
├── matcher.py         # Boolean AST evaluator + LRU cache + exclude filter + strip_diacritics
├── pipeline.py        # SearchPipeline orchestrator (scrape → filter → results)
├── storage.py         # CSV I/O + RAG index MD generation
├── providers/         # Portal-specific scrapers
│   ├── base.py        # BaseScraper ABC
│   ├── bazos.py       # Bazos.cz with params support (hlokalita, humkreis)
│   ├── jobs.py        # Jobs.cz
│   ├── pracecz.py     # Prace.cz
│   └── nyx.py         # Nyx.cz (deprecated — auth-gated, not a job portal)
├── server.py          # FastMCP instance + tool registration + MCP L3 prompt
└── cli.py             # CLI entry point (stdio MCP transport)
output/                  # ETL outputs (JSON, reports)
scripts/
├── run_etl.py           # Basic ETL runner
└── run_etl_metrics.py   # ETL runner with per-provider timing
```

## Quick start

```powershell
# Install
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"

# Configure
copy config.yaml.example config.yaml
# Edit postal code, radius, queries, excludes as needed

# Tests (97 tests)
pytest tests/ -v

# ETL pipeline
python scripts\run_etl.py
```

## Configuration

All personalization is in `config.yaml` — no personal data in code:

```yaml
user: "default"

portals:
  jobs:
    categories:
      - url: "https://www.jobs.cz/prace/praha/"
        pages: 5

  bazos:
    categories:
      - url: "https://prace.bazos.cz/"
        pages: 15
        params: {hlokalita: "18000", humkreis: "25"}

queries:
  python_jobs:
    boolean: "(python AND (developer OR vyvojar OR programator)) AND NOT senior"
    exclude: ["agentura", "nabizim", "hledam praci", ...]
    portals: ["jobs", "pracecz"]
```

> **Note:** Since Iteration 3, the boolean parser is **strict-only** — implicit AND is not supported.
> `"python developer"` must be written as `"python AND developer"`. Use `validate_boolean()` for syntax checking.

## Pipeline flow

```
1. _scrape_all() → pool [Ad] (all portals, categories, pages; 1.0s delay between requests)
2. For each query:
   ├── Portal filter (ad.portal IN query.portals?)
   ├── Boolean match (evaluate_boolean AST — LRU cached, 1× parse per unique query)
   ├── Exclude filter (has_exclude_terms)
   ├── Location filter (substring)
   └── Salary filter (number >= min_salary)
3. Returns dict[str, list[Ad]]
```

## Tools

| Tool | Description |
|------|-------------|
| `health_check` | Server status and version |
| `search_jobs_v2` | Boolean search across CZ portals (page guard: max 50) |
| `search_from_config` | Full pipeline from YAML file path |
| `search_from_yaml` | Full pipeline from inline YAML content |
| `list_portals` | Available portals and categories |

## Prompts

| Prompt | Description |
|--------|-------------|
| `search_expert` | Convert natural language → boolean query + YAML snippet |

## Output

Each ETL run generates JSON with per-provider timing:

```json
{
  "pipeline_elapsed_s": 46.2,
  "total_raw_scraped": 1073,
  "total_final_matched": 35,
  "precision_pct": 3.3,
  "provider_detail": {
    "bazos": { "elapsed_s": 24.2, "raw_ads": 463, "errors": 0 },
    "jobs": { "elapsed_s": 7.5, "raw_ads": 210, "errors": 0 },
    "pracecz": { "elapsed_s": 11.0, "raw_ads": 400, "errors": 0 }
  }
}
```

## Performance vs Legacy

| Metric | Legacy | MCP-Jobs | Improvement |
|--------|--------|----------|-------------|
| Pipeline time | ~210 s | **~46 s** | **4.5× faster** |
| Raw ads scraped | ~500 | **1 073** | 2× more data |
| Per-provider bazos | ~80 s | **~24 s** | **3.3× faster** |
| Per-provider jobs | ~40 s | **~7.5 s** | **5.3× faster** |
| Per-provider pracecz | ~60 s | **~11 s** | **5.4× faster** |
| Unit tests | 0 | **97** | — |
| Rate limiting | `sleep(1.0-2.5)` random | **1.0s precise delay** | ToS compliant |

### Key Improvements v0.3.0 → v0.3.1 (Iteration 3→4)

| Feature | v0.3.0 | v0.3.1 (Iter4) |
|---------|--------|----------------|
| AST re-parses/query | 8000 (per ad) | **8** (LRU cached) |
| Pages guard | unlimited | **max 50** |
| Request delay | 0s | **1.0s** (rate limiting) |
| Boolean validation | runtime only | **config-load time** |
| MCP error reporting | inconsistent | **unified `[{"error":...}]`** |
| Config error messages | raw TypeError | **user-friendly** |
| Test count | 92 | **97** |
| Inline import in loop | yes | **top-level** |

### Architecture & Quality

| Aspect | Legacy | MCP-Jobs |
|--------|--------|----------|
| Configuration | Hardcoded + CSV | YAML per-user |
| Matching | First-match-wins, AND-only | Boolean AST (AND/OR/NOT/parens) + LRU cache |
| Diacritics | Manual mapping | NFKD normalization |
| Exclude | Pipe in CSV (title only) | List in YAML (title+desc) |
| Location | Postal code hardcoded | YAML params (per-category) |
| Salary filter | ❌ None | ✅ regex `_SALARY_NUM_RE` |
| Rate limiting | `sleep(1.0-2.5)` random | ✅ 1.0s precise delay |
| Error handling | `except: continue` (silent) | Structured logging + skip count + MCP error contract |
| Dedup | URL only | URL + normalized title+company |
| Bazos subdomains | ❌ Broken (www vs prace) | ✅ Automatic detection |
| Output | CSV+MD per portal | Unified JSON |
| Protocol | None | MCP (Model Context Protocol) |
| Prompts | N/A | `search_expert` (MCP L3) |
| Tests | 0 | **97 pytest** |

## MCP Maturity

| Level | Status |
|-------|--------|
| L1 — Tools | ✅ 5 MCP tools |
| L2 — Resources | ⬜ Planned (mcp-jobs://ads/{query_id}) |
| L3 — Prompts | ✅ `search_expert` prompt |
| L4 — Streaming | ⬜ Planned (progress reporting) |

## Documentation

- `docs/report_legacy_vs_mcp.md` — detailed legacy vs MCP-Jobs comparison
- `docs/report_full_comparison_iter4.md` — Iteration 4 hardening report
- `docs/audit_report_claude.md` — v0.3.0 audit
- `docs/audit_MCP-Jobs_v0.3.1.md` — Cross-LLM meta-audit (Sonnet 5.0 peer review)
- `docs/audit_prompt_v1.1.docx` — Current audit prompt for frontier LLMs
- `output/etl_metrics_iter4.json` — Latest ETL metrics

## Known Limitations

- **Rate limiting**: 1.0s delay = 46s pipeline (vs 23s without). Required for ToS compliance.
- **Double scrape**: `SearchPipeline.run()` always rescrapes internally — no existing pool injection
- **Description matching**: word boundaries DISABLED on description (intentional — Czech inflection)
- **Location filter**: substring matching (no geocoding), sufficient for "Praha"
- **Salary filter**: heuristic number extraction (varying formats across portals)
- **Security**: threat model not documented — must be added before public release
