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

MCP server for scraping Czech job portals with boolean matching, exclude lists, location/salary filters and **PostgreSQL persistence**. Successor to legacy scrapers — **5.8× faster**, config-driven, **144 unit tests**, production hardening.

## Features

- **8 configurable queries** — python_ai_engineer, ai_llm_engineer, mcp_agentic, data_engineering, devops_ci_cd, prumyslova_automatizace, cnc_cam_automation, reverse_engineering
- **Boolean matching** — full AND/OR/NOT/parens AST parser + diacritics + LRU cache (8000→8 parses)
- **Exclude lists** — word-boundary on title, substring on description (Czech inflection support)
- **NFKD diacritics** — automatic normalization (programátor = programator)
- **Location & salary filter** — substring location match, regex salary extraction (thousand-separator)
- **Bazos subdomains** — automatic detection (prace.bazos.cz, www.bazos.cz, etc.)
- **Rate limiting** — 1.0s between requests (ToS compliance, IP protection)
- **Pages guard** — max 50 pages per call (resource abuse prevention)
- **Auto-validation** — boolean expressions validated at config load time (fail-fast)
- **MCP-native** — stdio transport, FastMCP SDK, ready for AI agent integration
- **144 unit tests** — pytest, full coverage of matcher, pipeline, providers, config, DB persistence
- **Structured logging** — per-card skip count, 0-ads alert, no silent failures
- **MCP L3 Prompts** — `search_expert` prompt for natural language to boolean query conversion
- **PostgreSQL persistence (Phase 1)** — schema.sql (DDL), URL UNIQUE + ON CONFLICT dedup, run audit (pipeline_runs), graceful degradation (DB down → pipeline keeps running, just no writes)
- **Test DB isolation (P73)** — DB tests target `mcpjobs_test` (derived from DATABASE_URL), hard guard refuses TRUNCATE on non-test DB
- **`.env` self-contained** — DATABASE_URL loaded from module root (not CWD — works from MCP transport)

## Architecture

```
src/mcp_jobs/
├── config.py          # UserConfig → PortalConfig → CategoryConfig → QueryConfig
├── models.py          # Ad dataclass (title, url, portal, desc, company, ...)
├── http.py            # HTTP client with retry, timeout, rate limiting (1.0s delay)
├── matcher.py         # Boolean AST evaluator + LRU cache + exclude filter + strip_diacritics
├── pipeline.py        # SearchPipeline orchestrator (scrape → filter → results → persist)
├── storage.py         # Unified output (etl_{PROFILE}_{ts}.{json,md,html}) + dedup + correlation
├── db.py              # PostgreSQL persistence (schema.sql, upsert_ads ON CONFLICT, run audit)
├── providers/         # Portal-specific scrapers
│   ├── base.py        # BaseScraper ABC
│   ├── bazos.py       # Bazos.cz with params support (hlokalita, humkreis)
│   ├── jobs.py        # Jobs.cz
│   ├── pracecz.py     # Prace.cz
│   └── nyx.py         # Nyx.cz (deprecated — auth-gated, not a job portal)
├── server.py          # FastMCP instance + tool registration + MCP L3 prompt
└── cli.py             # CLI entry point (stdio MCP transport)
data/
├── schema.sql         # DDL for PostgreSQL (ads, pipeline_runs, UNIQUE url)
└── query_store.json   # Query output persistence
output/                # ETL outputs etl_{PROFILE}_{ts}.{json,md,html}
scripts/
├── run_etl.py           # Basic ETL runner
├── run_etl_metrics.py   # ETL runner with per-provider timing
├── db.ps1               # DB operations (restart, psql, logs, dedup check)
└── healthcheck.py       # Healthcheck (dry-mode without DB)
docker-compose.yml     # PostgreSQL 16 (volume, schema.sql init, healthcheck)
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

# PostgreSQL (optional, for persistence)
docker compose up -d
copy .env.example .env   # set DATABASE_URL=postgres://mcpjobs:mcpjobs@localhost:5432/mcpjobs
# or: scripts\db.ps1 (restart, psql, logs)

# Tests (144 tests; DB tests run against mcpjobs_test, skipped otherwise)
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
  python_ai_engineer:
    boolean: "(python AND (ai OR ml OR data OR vyvojar OR programator OR inzenyr OR engineer OR developer)) NOT (lektor OR kurz OR skoleni)"
    exclude: ["agentura", "nabizim", "hledam praci"]
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
| `search_status` | Status of background search job (async pipeline) |
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
| Pipeline time | ~210 s | **~36 s** | **5.8× faster** |
| Raw ads scraped | ~500 | **1 073** | 2× more data |
| Per-provider bazos | ~80 s | **~12 s** | **6.7× faster** |
| Per-provider jobs | ~40 s | **~8 s** | **5.0× faster** |
| Per-provider pracecz | ~60 s | **~16 s** | **3.8× faster** |
| Unit tests | 0 | **144** | — |
| Rate limiting | `sleep(1.0-2.5)` random | **1.0s precise delay** | ToS compliant |

### Key Improvements v0.3.1 → v0.4.0 (Iteration 3→8)

| Feature | v0.3.1 | v0.4.0 |
|---------|--------|--------|
| AST re-parses/query | 8000 (per ad) | **8** (LRU cached) |
| Pages guard | unlimited | **max 50** |
| Request delay | 0s | **1.0s** (rate limiting) |
| Boolean validation | runtime only | **config-load time** |
| MCP error reporting | inconsistent | **unified `[{"error":...}]`** |
| Config error messages | raw TypeError | **user-friendly** |
| Test count | 97 | **144** |
| Inline import in loop | yes | **top-level** |
| Silent errors | yes | **eliminated via logger** (http/storage/base) |
| Persistence | in-memory | **query_store.json + correlation_cache.json + PostgreSQL** (Phase 1) |
| Detail fetch | sequential | **parallel** (ThreadPoolExecutor, max_workers=3) |
| Domain allowlist | none | **SEC-001 SSRF protection** |
| Request delay clamp | none | **min 0.2s** (config safety) |

### Architecture & Quality

| Aspect | Legacy | MCP-Jobs |
|--------|--------|----------|
| Configuration | Hardcoded + CSV | YAML per-user |
| Matching | First-match-wins, AND-only | Boolean AST (AND/OR/NOT/parens) + LRU cache |
| Diacritics | Manual mapping | NFKD normalization |
| Exclude | Pipe in CSV (title only) | List in YAML (title+desc) |
| Location | Hardcoded PSČ | YAML params (per-category) |
| Salary filter | ❌ None | ✅ regex `_SALARY_NUM_RE` |
| Rate limiting | `sleep(1.0-2.5)` random | ✅ 1.0s precise delay |
| Error handling | `except: continue` (silent) | Structured logging + skip count + MCP error contract |
| Dedup | URL only | URL + normalized title+company |
| Bazos subdomains | ❌ Broken (www vs prace) | ✅ Automatic detection |
| Output | CSV+MD per portal | Unified JSON |
| Protocol | None | MCP (Model Context Protocol) |
| Prompts | N/A | `search_expert` (MCP L3) |
| Tests | 0 | **144 pytest** |
| Detail fetch | sequential | **parallel** (ThreadPoolExecutor) |
| Security | none | **domain allowlist** (SSRF protection) |

## PostgreSQL persistence (Phase 1)

ETL runs persist to PostgreSQL 16 (optional — without DB the pipeline keeps running, just without writes):

| Component | Description |
|-----------|-------------|
| `data/schema.sql` | DDL: `ads` (URL UNIQUE dedup), `pipeline_runs` (run audit), status, matched/raw counts |
| `docker-compose.yml` | postgres:16 + volume + schema init + healthcheck |
| `src/mcp_jobs/db.py` | `persist_run` → start_run → upsert_ads (ON CONFLICT) → finish_run; graceful degradation |
| `.env` | `DATABASE_URL` (module root resolve — works from MCP transport, not only CWD) |
| `scripts/db.ps1` | restart/psql/logs/dedup check |

Test isolation (P73): DB tests run against `mcpjobs_test` (derived from `DATABASE_URL`), hard guard refuses TRUNCATE on non-test DB. Without a resolvable DATABASE_URL the DB tests are skipped.

## MCP Maturity

| Level | Status |
|-------|--------|
| L1 — Tools | ✅ 5 MCP tools |
| L2 — Resources | ✅ `mcp-jobs://ads/list`, `mcp-jobs://ads/{query_id}`, `mcp-jobs://ads/{query_id}/report` |
| L3 — Prompts | ✅ `search_expert` prompt |
| L4 — Streaming | ⬜ Planned (progress reporting) |

## Documentation

- `docs/report_legacy_vs_mcp.md` — detailed legacy vs MCP-Jobs comparison
- `docs/report_full_comparison_iter4.md` — Iteration 4 hardening report
- `docs/audit_report_claude.md` — v0.3.0 audit
- `docs/audit_MCP-Jobs_v0.3.1.md` — Cross-LLM meta-audit (Sonnet 5.0 peer review)
- `docs/audit_prompt_v1.1.docx` — Current audit prompt for frontier LLMs
- `docs/cross_llm_code_review_prompt.md` — Cross-LLM audit prompt
- `docs/semantic_analysis_cross_review_2026-08-06.md` — EROI analysis + action plan
- `docs/refresh_run_it_jobs_2026-08-06.md` — Fresh run report (AI_NATIVE)
- `docs/refresh_run_legacy_jobs_2026-08-06.md` — Fresh run report (LEGACY_MANUAL)

## Known Limitations

- **Rate limiting**: 1.0s delay = 36s pipeline (vs 23s without). Required for ToS compliance.
- **Double scrape**: `SearchPipeline.run()` always rescrapes internally — no existing pool injection
- **Description matching**: word boundaries DISABLED on description (intentional — Czech inflection)
- **Location filter**: substring matching (no geocoding), sufficient for "Praha"
- **Salary filter**: heuristic number extraction (varying formats across portals)
- **Bazos detail fetch (P2)**: company/seller info only from contact link (`jmeno=`) on the detail page — ads without a contact link get no company. Logged in pipeline (limit, not error); full implementation deferred.
- **Security**: threat model not documented — must be added before public release
- **Domain allowlist**: SEC-001 SSRF protection — only allowed domains (bazos.cz, jobs.cz, prace.cz)
- **CI**: test DB `mcpjobs_test` created by the "Create test database" step in ci.yml (P73 isolation) — fixed 2026-08-19

## Development status (2026-08-19)

| Area | Status |
|------|--------|
| Version | 0.4.0 (Phase 1 standalone pivot) |
| Tests | 144/144 PASS (locally; 2 encoding harness tests fixed 2026-08-19) |
| PostgreSQL | ✅ Phase 1 done: schema, docker-compose, db.py, .env self-contained, P73 isolation |
| Output | ✅ Unified `etl_{PROFILE}_{ts}.{json,md,html}` (Storage.save_outputs, dedup on normalized content) |
| CI | ✅ Fixed 2026-08-19: create test DB step in ci.yml (P73); push for verification |
| Backlog | Engineering-process Phase 09 (uv, ruff+mypy, GH Actions, pre-commit, coverage 66 %), product Phase 09 (FTS5, Dockerfile non-root, SSRF allowlist, `__main__.py`+`--smoke`) |
