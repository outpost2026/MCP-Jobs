# MCP-Jobs

MCP server pro scraping českých pracovních portálů s boolean matchingem, exclude listy a location/salary filtry. Nástupce legacy scrapers — **11× rychlejší**, config-driven, s unit testy.

## Features

- **8 konfigurovatelných query** — python_jobs, cnc_jobs, elektrikar, spravce, udrzbar, zahradnik, truhlar, strechy
- **Boolean matching** — plná AND/OR/NOT/parens logika s AST parserem + diakritika
- **Exclude listy** — word-boundary na title, substring na description (české skloňování)
- **NFKD diakritika** — automatická normalizace (programátor = programator)
- **Location & salary filter** — substring location match, regex salary extraction
- **Bazos subdomény** — automatická detekce (prace.bazos.cz, www.bazos.cz atd.)
- **MCP-native** — stdio transport, FastMCP SDK, ready pro AI agent integraci
- **81 unit testů** — pytest, plné pokrytí matcheru, pipeline, providerů
- **Structured logging** — per-card skip count, 0-ads alert, žádné silent failures

## Architektura

```
src/mcp_jobs/
├── config.py          # UserConfig → PortalConfig → CategoryConfig → QueryConfig
├── models.py          # Ad dataclass (title, url, portal, desc, company, ...)
├── http.py            # HTTP klient s retry, headers, timeout
├── matcher.py         # Boolean AST evaluator + exclude filter + strip_diacritics
├── pipeline.py        # SearchPipeline orchestrator (scrape → filter → results)
├── storage.py         # CSV I/O + RAG index MD generování
├── providers/         # Portal-specific scrapers
│   ├── base.py        # BaseScraper ABC
│   ├── bazos.py       # Bazos.cz s params podporou (hlokalita, humkreis)
│   ├── jobs.py        # Jobs.cz
│   ├── pracecz.py     # Prace.cz
│   └── nyx.py         # Nyx.cz (deprecated — auth-gated, není job portál)
├── server.py          # FastMCP instance + tool registrace
└── cli.py             # CLI entry point (stdio MCP transport)
output/                  # ETL výstupy (timestampované JSON, reporty)
scripts/
├── run_etl.py           # Základní ETL runner
├── run_etl_metrics.py   # ETL runner s per-provider timingem a porovnáním s legacy
└── generate_final_report.py  # Generování reportu z ETL metrics
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

# Testy (81 testů)
pytest tests/ -v

# ETL pipeline + metriky
python scripts\run_etl.py
python scripts\run_etl_metrics.py   # detailní timing + srovnání s legacy
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
  python_jobs:
    boolean: "(python AND (developer OR vyvojar OR programator)) NOT senior"
    exclude: ["agentura", "nabizim", "hledam praci", ...]
    portals: ["jobs", "pracecz"]
```

## Pipeline flow

```
1. _scrape_all() → pool [Ad] (všechny portály, kategorie, stránky)
2. Pro každý query:
   ├── Portal filter (ad.portal IN query.portals?)
   ├── Boolean match (evaluate_boolean AST)
   ├── Exclude filter (has_exclude_terms)
   ├── Location filter (substring)
   └── Salary filter (number >= min_salary)
3. Vrací dict[str, list[Ad]]
```

## Výstup

Každý ETL běh generuje timestampovaný JSON v `output/etl_YYYYMMDD_HHMMSS.json`:

```json
{
  "timestamp": "2026-07-14T18:48:46",
  "elapsed_seconds": 19.0,
  "total_matched": 34,
  "config": { "portals": ["jobs","bazos","pracecz"], "queries": ["python_jobs", ...] },
  "summary": {
    "udrzbar": { "count": 11, "portals": ["bazos","jobs","pracecz"], "sample": [...] },
    ...
  },
  "provider_metrics": {
    "bazos": { "calls": 2, "elapsed": 3.0, "matched": 462, "errors": 0 },
    ...
  },
  "results": { "udrzbar": [{ "title": "...", "url": "...", ... }], ... }
}
```

`output/etl_latest.json` obsahuje vždy poslední běh.
`output/etl_metrics_latest.json` rozšiřuje o `provider_metrics` a per-query timing.

## Porovnání s legacy scrapers

### Výkonnost

| Metrika | Legacy | MCP-Jobs | Zlepšení |
|---------|--------|----------|----------|
| Pipeline time | ~210 s | **~19 s** | **11× faster** |
| Raw ads scraped | ~500 | **1 072** | 2× více dat |
| Per-provider bazos | ~80 s | **~3 s** | **27× faster** |
| Per-provider jobs | ~40 s | **~5.5 s** | **7× faster** |
| Per-provider pracecz | ~60 s | **~7 s** | **8× faster** |
| Ads per second | 0.53 | **1.66** | 3.1× efficientnější |
| Unit tests | 0 | **81** | — |

> *Měřeno na stejné HW konfiguraci (Windows 11, Python 3.11). Legacy delay: `time.sleep(1.0-2.5)` mezi stránkami. MCP-Jobs: Playwright bez umělého zpoždění.*

### Architektura a kvalita

| Aspekt | Legacy | MCP-Jobs |
|--------|--------|----------|
| Konfigurace | Hardcoded + CSV | YAML per-user |
| Matching | First-match-wins, AND-only | Boolean AST (AND/OR/NOT/parens) |
| Diakritika | Ruční mapping | NFKD normalizace |
| Exclude | Pipe v CSV (title only) | List v YAML (title+desc) |
| Location | PSČ hardcoded | YAML params (per-category) |
| Salary filter | ❌ None | ✅ regex `_SALARY_NUM_RE` |
| Error handling | `except: continue` (silent) | Structured logging + skip count |
| Dedup | URL only | URL + normalized title+company |
| JS rendering | requests + BS4 | Playwright |
| Subdomény bazos | ❌ Broken (www vs prace) | ✅ Automatická detekce |
| Output | CSV+MD per portal | Unified JSON + report |
| Protokol | Žádný | MCP (Model Context Protocol) |
| Testy | 0 | 81 pytestů |

## Tools

| Tool | Description |
|------|-------------|
| `health_check` | Server status and version |
| `search_jobs_v2` | Boolean search across CZ portals |
| `list_portals` | Available portals and categories |

## Dokumentace

- `docs/report_legacy_vs_mcp.md` — podrobný report porovnání s legacy pipeline
- `output/etl_metrics_latest.json` — poslední ETL metrics (per-provider timing, match distribuce)
- `data/COMPREHENSIVE_DOCS.md` — kompletní architektura, návod, diff vůči legacy
- `data/SEMANTIC_DIFF.md` — sémantická analýza legacy 94 topics vs MCP 8 queries
- `data/AUDIT_technologicky.md` — technický audit celého kódu

## Známé limity

- **Double scrape**: `SearchPipeline.run()` vždy rescrapuje interně, nelze injectnout existující pool
- **Description matching**: word boundaries VYPNUTY na description (záměrně — české skloňování)
- **Location filter**: substring matching (ne geokód), pro "Praha" dostačující
- **Salary filter**: heuristická extrakce čísel (různé formáty napříč portály)
