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

MCP server pro scraping českých pracovních portálů s boolean matchingem, exclude listy, location/salary filtry a **PostgreSQL perzistencí**. Nástupce legacy scrapers — **5.8× rychlejší**, config-driven, **148 unit testů**, hardening pro produkční nasazení.

## Features

- **8 konfigurovatelných query** — python_ai_engineer, ai_llm_engineer, mcp_agentic, data_engineering, devops_ci_cd, prumyslova_automatizace, cnc_cam_automation, reverse_engineering
- **Boolean matching** — plná AND/OR/NOT/parens logika s AST parserem + diakritika + LRU cache (8000→8 parsování)
- **Exclude listy** — word-boundary na title, substring na description (české skloňování)
- **NFKD diakritika** — automatická normalizace (programátor = programator)
- **Location & salary filter** — substring location match, regex salary extraction (thousand-separator)
- **Bazos subdomény** — automatická detekce (prace.bazos.cz, www.bazos.cz atd.)
- **Rate limiting** — 0.5s mezi requesty (ToS compliance, IP ochrana, clamp min 0.2s)
- **Pages guard** — max 50 stránek na volání (resource abuse prevence)
- **Auto-validace boolean výrazů** — fail-fast při malformed configu
- **MCP-native** — stdio transport, FastMCP SDK, ready pro AI agent integraci
- **148 unit testů** — pytest, plné pokrytí matcheru, pipeline, providerů, configu, DB perzistence
- **Structured logging** — per-card skip count, 0-ads alert, žádné silent failures
- **MCP L3 Prompts** — `search_expert` prompt pro převod přirozeného jazyka na boolean query
- **PostgreSQL persistence (Faze 1)** — schema.sql (DDL), dedup přes URL UNIQUE + ON CONFLICT, run audit (pipeline_runs), graceful degradation (DB nedostupná → pipeline běží dál, jen bez zápisu)
- **Test DB izolace (P73)** — DB testy míří na `mcpjobs_test` (odvozeno z DATABASE_URL), hard-guard odmítá TRUNCATE na non-test DB
- **`.env` self-contained** — DATABASE_URL se načítá z `data/../.env` (module root, ne CWD — funguje i z MCP transportu)

## Architektura

```
src/mcp_jobs/
├── config.py          # UserConfig → PortalConfig → CategoryConfig → QueryConfig
├── models.py          # Ad dataclass (title, url, portal, desc, company, ...)
├── http.py            # HTTP klient s retry, timeout, rate limiting (1.0s delay)
├── matcher.py         # Boolean AST evaluator + LRU cache + exclude filter + strip_diacritics
├── pipeline.py        # SearchPipeline orchestrator (scrape → filter → results → persist)
├── storage.py         # Unified output (etl_{PROFILE}_{ts}.{json,md,html}) + dedup + korelace
├── db.py              # PostgreSQL persistence (schema.sql, upsert_ads ON CONFLICT, run audit)
├── providers/         # Portal-specific scrapers
│   ├── base.py        # BaseScraper ABC
│   ├── bazos.py       # Bazos.cz s params podporou (hlokalita, humkreis)
│   ├── jobs.py        # Jobs.cz
│   └── pracecz.py     # Prace.cz
├── server.py          # FastMCP instance + tool registrace + MCP L3 prompt
└── cli.py             # CLI entry point (stdio MCP transport)
data/
├── schema.sql         # DDL pro PostgreSQL (ads, pipeline_runs, UNIQUE url)
└── query_store.json   # Persistence query výstupů
output/                # ETL výstupy etl_{PROFILE}_{ts}.{json,md,html}
scripts/
├── run_etl.py           # Základní ETL runner
├── run_etl_metrics.py   # ETL runner s per-provider timingem
├── db.ps1               # DB operace (restart, psql, logy, dedup check)
└── healthcheck.py       # Healthcheck (dry-mode bez DB)
docker-compose.yml     # PostgreSQL 16 (volume, schema.sql init, healthcheck)
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

# PostgreSQL (volitelné, pro perzistenci)
docker compose up -d
copy .env.example .env   # nastav DATABASE_URL=postgres://mcpjobs:mcpjobs@localhost:5432/mcpjobs
# nebo: scripts\db.ps1 (restart, psql, logy)

# Testy (148 testů; DB testy běží na mcpjobs_test, jinak se skipnou)
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
1. _scrape_all() → pool [Ad] (všechny portály, kategorie, stránky; 0.5s delay mezi requesty)
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
| `search_status` | Status of background search job (async pipeline) |
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
| Unit tests | 0 | **148** | — |
| Rate limiting | `sleep(1.0-2.5)` | **0.5s přesný delay** | ToS compliant |

### Hlavní vylepšení oproti v0.3.1 (Iteration 3→8)

| Feature | v0.3.1 | v0.4.0 |
|---------|--------|--------|
| AST re-parses/query | 8000 (per ad) | **8** (LRU cached) |
| Pages guard | unlimited | **max 50** |
| Request delay | 0s | **0.5s** (rate limiting) |
| Boolean validation | runtime only | **config-load time** |
| MCP error reporting | inconsistent | **unified `[{"error":...}]`** |
| Config error messages | raw TypeError | **user-friendly** |
| Test count | 97 | **148** |
| Inline import v loopu | ano | **top-level** |
| Silent errors | ano | **eliminovány loggerem** (http/storage/base) |
| Persistence | in-memory | **query_store.json + correlation_cache.json + PostgreSQL** (Faze 1) |
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
| Testy | 0 | **148 pytestů** |
| Detail fetch | sequential | **parallel** (ThreadPoolExecutor) |
| Security | none | **domain allowlist** (SSRF protection) |

## PostgreSQL persistence (Faze 1)

ETL běh ukládá data do PostgreSQL 16 (volitelné — bez DB pipeline běží dál, jen bez zápisu):

| Komponenta | Popis |
|------------|-------|
| `data/schema.sql` | DDL: `ads` (URL UNIQUE dedup), `pipeline_runs` (run audit), status, matched/raw counts |
| `docker-compose.yml` | postgres:16 + volume + schema init + healthcheck |
| `src/mcp_jobs/db.py` | `persist_run` → start_run → upsert_ads (ON CONFLICT) → finish_run; graceful degradation |
| `.env` | `DATABASE_URL` (module root resolve — funguje z MCP transportu, ne jen z CWD) |
| `scripts/db.ps1` | restart/psql/logy/dedup check |

Test izolace (P73): DB testy běží proti `mcpjobs_test` (odvozeno z `DATABASE_URL`), hard-guard odmítá TRUNCATE na non-test DB. Bez dostupného DATABASE_URL se DB testy skipnou.

**Dual-write je záměrná redundance (rozhodnutí 2026-08-19):** `storage.py` (unified `output/etl_*.{json,md,html}`) i `db.py` (PostgreSQL) běží souběžně — JSON artefakty slouží jako instantní, strojově i lidsky čitelné výstupy (LLM/CLI konzumace), PostgreSQL je strukturovaná perzistence pro standalone web (Fáze 2, Next.js čte z DB). Žádný z nich není "starý" — oba zapisují stejná data, každý pro jiného konzumenta. Čtení pro web jde výhradně z DB.

## MCP Maturity

| Level | Status |
|-------|--------|
| L1 — Tools | ✅ 6 MCP tools |
| L2 — Resources | ✅ `mcp-jobs://ads/{query_id}`, `mcp-jobs://ads/{query_id}/report`, `mcp-jobs://ads/list` |
| L3 — Prompts | ✅ `search_expert` prompt |
| L4 — Streaming | ⬜ Plánováno (progress reporting) |

## Dokumentace

- `docs/cross_llm_code_review_prompt.md` — Cross-LLM audit prompt
- `docs/sql_ontologie_mechanismy_2026-08-15.md` — SQL ontologie (DDL/DML/DQL, dependencies) — učební dokument
- `docs/postgresql_zakladni_prikazy_2026-08-15.md` — PostgreSQL reference (psql meta, dedup vzory, ads analýzy)
- `docs/edukace_faze1_postgresql_2026-08-15.md` — retrospektiva Fáze 1 (PostgreSQL persistence)
- `docs/edukace_db_prvni_kontakt_2026-08-15.md` — první kontakt s databází (analogie Excel)
- `docs/powershell_encoding.md` — PowerShell/cp1250 encoding root causes a řešení
- `docs/l2_resources.md` — MCP L2 Resources dokumentace
- `docs/_archive/` — superseded dokumenty (audity, run reporty, plány — historie zachována)

## Známé limity

- **Rate limiting**: 1.0s delay = 36s pipeline (oproti 23s bez delay). Nutný pro ToS compliance.
- **Double scrape**: `SearchPipeline.run()` vždy rescrapuje interně, nelze injectnout existující pool
- **Description matching**: word boundaries VYPNUTY na description (záměrně — české skloňování)
- **Location filter**: substring matching (ne geokód), pro "Praha" dostačující
- **Salary filter**: heuristická extrakce čísel (různé formáty napříč portály)
- **Bazos detail fetch (P2)**: company/seller info jen z contact linku (`jmeno=`) na detail stránce — u inzerátů bez contact linku se company nevyplní. Logováno v pipeline (limit, ne chyba); plná implementace odložena.
- **Security**: threat model není dokumentován — nutno doplnit před veřejnou publikací
- **Domain allowlist**: SEC-001 SSRF protection — pouze povolené domény (bazos.cz, jobs.cz, prace.cz)
- **CI**: test DB `mcpjobs_test` se vytváří v ci.yml krokem "Create test database" (P73 izolace) — fix 2026-08-19

## Vývojový stav (2026-08-19)

| Oblast | Stav |
|--------|------|
| Verze | 0.4.0 (Faze 1 standalone pivot) |
| Testy | 148/148 PASS (lokálně; 2 encoding harness testy opraveny 2026-08-19) |
| PostgreSQL | ✅ Faze 1 done: schema, docker-compose, db.py, .env self-contained, P73 izolace |
| Output | ✅ Unified `etl_{PROFILE}_{ts}.{json,md,html}` (Storage.save_outputs, dedup na normalizovaném obsahu) |
| CI | ✅ Opraveno 2026-08-19: create test DB krok v ci.yml (P73); push k ověření |
| Backlog | Engineering-proces Phase 09 (uv, ruff+mypy, GH Actions, pre-commit, coverage 66 %), produktový Phase 09 (FTS5, Dockerfile non-root, SSRF allowlist, `__main__.py`+`--smoke`) |
