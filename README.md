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

MCP server pro scraping českých pracovních portálů s boolean matchingem, exclude listy a location/salary filtry. Nástupce legacy scrapers — **4.5× rychlejší**, config-driven, 131 unit testů, hardening pro produkční nasazení.

## Features

- **8 konfigurovatelných query** — python_ai_engineer, ai_llm_engineer, mcp_agentic, data_engineering, devops_ci_cd, prumyslova_automatizace, cnc_cam_automation, reverse_engineering
- **Boolean matching** — plná AND/OR/NOT/parens logika s AST parserem + diakritika + LRU cache (8000→8 parsování)
- **Exclude listy** — word-boundary na title, substring na description (české skloňování)
- **NFKD diakritika** — automatická normalizace (programátor = programator)
- **Location & salary filter** — substring location match, regex salary extraction (thousand-separator)
- **Bazos subdomény** — automatická detekce (prace.bazos.cz, www.bazos.cz atd.)
- **Rate limiting** — 1.0s mezi requesty (ToS compliance, IP ochrana)
- **Pages guard** — max 50 stránek na volání (resource abuse prevence)
- **Auto-validace boolean výrazů** — fail-fast při malformed configu
- **MCP-native** — stdio transport, FastMCP SDK, ready pro AI agent integraci
- **131 unit testů** — pytest, plné pokrytí matcheru, pipeline, providerů, configu
- **Structured logging** — per-card skip count, 0-ads alert, žádné silent failures
- **MCP L3 Prompts** — `search_expert` prompt pro převod přirozeného jazyka na boolean query

## Architektura

```
src/mcp_jobs/
├── config.py          # UserConfig → PortalConfig → CategoryConfig → QueryConfig
├── models.py          # Ad dataclass (title, url, portal, desc, company, ...)
├── http.py            # HTTP klient s retry, timeout, rate limiting (1.0s delay)
├── matcher.py         # Boolean AST evaluator + LRU cache + exclude filter + strip_diacritics
├── pipeline.py        # SearchPipeline orchestrator (scrape → filter → results)
├── storage.py         # CSV I/O + RAG index MD generování
├── providers/         # Portal-specific scrapers
│   ├── base.py        # BaseScraper ABC
│   ├── bazos.py       # Bazos.cz s params podporou (hlokalita, humkreis)
│   ├── jobs.py        # Jobs.cz
│   ├── pracecz.py     # Prace.cz
│   └── nyx.py         # Nyx.cz (deprecated — auth-gated, není job portál)
├── server.py          # FastMCP instance + tool registrace + MCP L3 prompt
└── cli.py             # CLI entry point (stdio MCP transport)
output/                  # ETL výstupy (JSON, reporty)
scripts/
├── run_etl.py           # Základní ETL runner
└── run_etl_metrics.py   # ETL runner s per-provider timingem
```

## Quick start

```powershell
# Instalace
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"

# Konfigurace
copy config.yaml.example config.yaml
# Uprav PSČ, radius, query, exclude dle potřeby

# Testy (131 testů)
pytest tests/ -v

# ETL pipeline
python scripts\run_etl.py
```

## Konfigurace

Všechna personalizace je v `config.yaml` — žádná osobní data v kódu:

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

> **Poznámka:** Od Iteration 3 je boolean parser **strict-only** — nepodporuje implicitní AND.
> `"python developer"` je nutné psát jako `"python AND developer"`. Viz `validate_boolean()` pro kontrolu syntaxe.

## Pipeline flow

```
1. _scrape_all() → pool [Ad] (všechny portály, kategorie, stránky; 1.0s delay mezi requesty)
2. Pro každý query:
   ├── Portal filter (ad.portal IN query.portals?)
   ├── Boolean match (evaluate_boolean AST — LRU cached, 1× parse per unique query)
   ├── Exclude filter (has_exclude_terms)
   ├── Location filter (substring)
   └── Salary filter (number >= min_salary)
3. Vrací dict[str, list[Ad]]
```

## Tools

| Tool | Description |
|------|-------------|
| `health_check` | Server status and version |
| `search_jobs_v2` | Boolean search across CZ portals (pages guard: max 50) |
| `search_from_config` | Full pipeline from YAML file path |
| `search_from_yaml` | Full pipeline from inline YAML content |
| `list_portals` | Available portals and categories |

## Prompts

| Prompt | Description |
|--------|-------------|
| `search_expert` | Convert natural language → boolean query + YAML snippet |

## Výstup

Každý ETL běh generuje JSON s per-provider timingem:

```json
{
  "pipeline_elapsed_s": 36.3,
  "total_raw_scraped": 1073,
  "total_final_matched": 28,
  "precision_pct": 2.6,
  "provider_detail": {
    "bazos": { "elapsed_s": 12.0, "raw_ads": 463, "errors": 0 },
    "jobs": { "elapsed_s": 8.0, "raw_ads": 210, "errors": 0 },
    "pracecz": { "elapsed_s": 16.0, "raw_ads": 400, "errors": 0 }
  }
}
```

## Porovnání s legacy scrapers

### Výkonnost

| Metrika | Legacy | MCP-Jobs | Zlepšení |
|---------|--------|----------|----------|
| Pipeline time | ~210 s | **~36 s** | **5.8× faster** |
| Raw ads scraped | ~500 | **1 073** | 2× více dat |
| Per-provider bazos | ~80 s | **~12 s** | **6.7× faster** |
| Per-provider jobs | ~40 s | **~8 s** | **5.0× faster** |
| Per-provider pracecz | ~60 s | **~16 s** | **3.8× faster** |
| Unit tests | 0 | **131** | — |
| Rate limiting | `sleep(1.0-2.5)` | **1.0s přesný delay** | ToS compliant |

### Hlavní vylepšení oproti v0.3.1 (Iteration 3→8)

| Feature | v0.3.1 | v0.4.0 |
|---------|--------|--------|
| AST re-parses/query | 8000 (per ad) | **8** (LRU cached) |
| Pages guard | unlimited | **max 50** |
| Request delay | 0s | **1.0s** (rate limiting) |
| Boolean validation | runtime only | **config-load time** |
| MCP error reporting | inconsistent | **unified `[{"error":...}]`** |
| Config error messages | raw TypeError | **user-friendly** |
| Test count | 97 | **131** |
| Inline import v loopu | ano | **top-level** |
| Silent errors | ano | **eliminovány loggerem** (http/storage/base) |
| Persistence | in-memory | **query_store.json + correlation_cache.json** |
| Detail fetch | sequential | **parallel** (ThreadPoolExecutor, max_workers=3) |
| Domain allowlist | none | **SEC-001 SSRF protection** |
| Request delay clamp | none | **min 0.2s** (config safety) |

### Architektura a kvalita

| Aspekt | Legacy | MCP-Jobs |
|--------|--------|----------|
| Konfigurace | Hardcoded + CSV | YAML per-user |
| Matching | First-match-wins, AND-only | Boolean AST (AND/OR/NOT/parens) + LRU cache |
| Diakritika | Ruční mapping | NFKD normalizace |
| Exclude | Pipe v CSV (title only) | List v YAML (title+desc) |
| Location | PSČ hardcoded | YAML params (per-category) |
| Salary filter | ❌ None | ✅ regex `_SALARY_NUM_RE` |
| Rate limiting | `sleep(1.0-2.5)` random | ✅ 1.0s přesný delay |
| Error handling | `except: continue` (silent) | Structured logging + skip count + MCP error kontrakt |
| Dedup | URL only | URL + normalized title+company |
| Subdomény bazos | ❌ Broken (www vs prace) | ✅ Automatická detekce |
| Output | CSV+MD per portal | Unified JSON |
| Protokol | Žádný | MCP (Model Context Protocol) |
| Prompty | N/A | `search_expert` (MCP L3) |
| Testy | 0 | **131 pytestů** |
| Detail fetch | sequential | **parallel** (ThreadPoolExecutor) |
| Security | none | **domain allowlist** (SSRF protection) |

## MCP Maturity

| Level | Status |
|-------|--------|
| L1 — Tools | ✅ 5 MCP tools |
| L2 — Resources | ✅ `mcp-jobs://ads/{query_id}`, `mcp-jobs://ads/{query_id}/report`, `mcp-jobs://ads/list` |
| L3 — Prompts | ✅ `search_expert` prompt |
| L4 — Streaming | ⬜ Plánováno (progress reporting) |

## Dokumentace

- `docs/report_legacy_vs_mcp.md` — podrobný report porovnání s legacy pipeline
- `docs/report_full_comparison_iter4.md` — Iteration 4 hardening report
- `docs/audit_report_claude.md` — v0.3.0 audit
- `docs/audit_MCP-Jobs_v0.3.1.md` — Cross-LLM meta-audit (peer review Sonnet 5.0)
- `docs/audit_prompt_v1.1.docx` — Aktuální audit prompt pro frontier LLM
- `docs/cross_llm_code_review_prompt.md` — Cross-LLM audit prompt
- `docs/semantic_analysis_cross_review_2026-08-06.md` — EROI analysis + action plan
- `docs/refresh_run_it_jobs_2026-08-06.md` — Fresh run report (AI_NATIVE)
- `docs/refresh_run_legacy_jobs_2026-08-06.md` — Fresh run report (LEGACY_MANUAL)

## Známé limity

- **Rate limiting**: 1.0s delay = 36s pipeline (oproti 23s bez delay). Nutný pro ToS compliance.
- **Double scrape**: `SearchPipeline.run()` vždy rescrapuje interně, nelze injectnout existující pool
- **Description matching**: word boundaries VYPNUTY na description (záměrně — české skloňování)
- **Location filter**: substring matching (ne geokód), pro "Praha" dostačující
- **Salary filter**: heuristická extrakce čísel (různé formáty napříč portály)
- **Security**: threat model není dokumentován — nutno doplnit před veřejnou publikací
- **Domain allowlist**: SEC-001 SSRF protection — pouze povolené domény (bazos.cz, jobs.cz, prace.cz)
