# MCP-Jobs

MCP server pro scraping českých pracovních portálů s boolean matchingem, exclude listy a location/salary filtry. Nástupce legacy scrapers — config-driven, bez hardcoded osobních dat.

## Features

- **8 query** — python_jobs, cnc_jobs, elektrikar, spravce, udrzbar, zahradnik, truhlar, strechy
- **Boolean matching** — plná AND/OR/NOT/parens logika s AST parserem
- **Exclude listy** — word-boundary na title, substring na description (české skloňování)
- **NFKD diakritika** — automatická normalizace (programátor = programator)
- **Location & salary filter** — substring location match, číselný salary comparison
- **Bazos params** — per-category PSČ+radius (pouze Bazos, YAML konfigurovatelné)
- **MCP-native** — stdio transport, FastMCP SDK, ready pro AI agent integraci
- **76 unit testů** — pytest, plné pokrytí matcheru, pipeline, providerů

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

# Testy
pytest tests/ -v

# Pipeline
python scripts\run_pipeline_test.py
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

## Porovnání s legacy scrapers

| Aspekt | Legacy | MCP-Jobs |
|--------|--------|----------|
| Konfigurace | Hardcoded + CSV | YAML per-user |
| Matching | First-match-wins, AND-only | Boolean AST (AND/OR/NOT) |
| Diakritika | Ruční mapping | NFKD normalizace |
| Exclude | Pipe v CSV (title only) | List v YAML (title+desc) |
| Location | PSČ hardcoded | YAML params (per-category) |
| Protokol | Žádný | MCP (Model Context Protocol) |
| Testy | Minimální | 76 pytestů |

## Tools

| Tool | Description |
|------|-------------|
| `health_check` | Server status and version |
| `search_jobs_v2` | Boolean search across CZ portals |
| `list_portals` | Available portals and categories |

## Dokumentace

- `data/COMPREHENSIVE_DOCS.md` — kompletní architektura, návod, diff vůči legacy
- `data/SEMANTIC_DIFF.md` — sémantická analýza legacy 94 topics vs MCP 8 queries
- `data/AUDIT_technologicky.md` — technický audit celého kódu

## Známé limity

- **Double scrape**: `SearchPipeline.run()` vždy rescrapuje interně, nelze injectnout existující pool
- **Description matching**: word boundaries VYPNUTY na description (záměrně — české skloňování)
- **Location filter**: substring matching (ne geokód), pro "Praha" dostačující
- **Salary filter**: heuristická extrakce čísel (různé formáty napříč portály)
