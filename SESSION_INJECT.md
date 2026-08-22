# Session Injekt — MCP-Jobs development (pivot na standalone produkt)

> **STATUS: v0.4.0+ Dashboard refactor + GT v17 COMPLETE — Fáze 0 CI hotová, Fáze 1 PostgreSQL NEXT.**
> 
> Vygenerováno: 2026-07-14
> Aktualizováno: 2026-08-22 — dashboard Analyza tab (9 sections), GT v17 (GT-095/096, P80/P81), kb-workflow skill cleanup, CI RUF003 fix
> Kontext: pitevni knihy MCP v B2B-Knowledge-Base/04_KNOWLEDGE_BASE/01_MCP/ + pivot artefakty v docs/

---

## STAV PO dashboard refactoru (2026-08-22) — v0.4.0+

### Dashboard Analyza tab + GT v17

| Metrika | Hodnota |
|---------|---------|
| Pipeline time | **AI_NATIVE 36.3 s** (1.61x faster vs pred C1) |
| Raw ads scraped | AI_NATIVE 28 / LEGACY 46 |
| Final matched | **182 unique** (DB: dedup by url) |
| Unit tests | **189/189 PASS** (`pytest -q`) |
| Dashboard | Analyza tab: Portal Quality, Cross-Portal Overlap, Salary, Freshness, Status Funnel, Query Efficiency, Location Analysis, Company Frequency, Portal x Query Matrix |
| GT entries | **99** (GT-001..GT-096 + GT-GCP-001..005) |
| P-rules | **P1..P81 + P-GCP-01..05** |
| Git head | `5794a81` (main, pushed) |
| CI | ✅ RUF003 fixed (× → x in comment) |

---

## PIVOT NA STANDALONE PRODUKT (2026-08-15) — AKTUÁLNÍ SMĚR

Aspirace: port MCP serveru na **standalone web app na jobs.systeq.cz** (subdoména — rozhodnuto uživatelem).

| Fáze | Náplň | Stav |
|------|-------|------|
| **Fáze 0** | CI (.github/workflows/ci.yml) + cron + healthchecks.io | ✅ Hotovo |
| **Fáze 1** | PostgreSQL: data/schema.sql (ads, pipeline_runs) + docker-compose.yml + src/mcp_jobs/db.py | ✅ Hotovo (182 ads, 22 runs) |
| **Fáze 2** | Streamlit dashboard (Analyza tab, 9 sections) + Bazos pagination fix | ✅ Hotovo |
| **Fáze 3** | TS + Next.js GUI na jobs.systeq.cz | 📅 NEXT |
| Fáze 4+ | AZ-900 (SRS), PLC (PBL) | 📅 |

**Artefakty pivota:**
- `docs/edukace_port_standalone_2026-08-15.md` — MCP vs standalone, ontologie, SWE nástroje
- `docs/edukace_implementace_standalone_pivot_2026-08-15.md` — EROI fáze + adopce skills 60/20/10/10
- KB: `SKILL_GAPS_ROZBOR_Q3_2026_v2.md`, `ADOPCNI_METODOLOGIE_2026_v1.md` (commitnuty 2026-08-15)

**EROI pořadí:** PostgreSQL (0.49/h) > DevOps (0.46/h) > TS/Next (0.30/h) → Fáze 0 a 1 před TS.

---

## STAV PO Iteration 4 (2026-07-14) — HARDENING (archiv)

### LIVE pipeline výsledky — 46.2s, 1 073 raw ads, 35 final matched

| Metrika | Hodnota |
|---------|---------|
| Pipeline time | **46.2 s** (s 1.0s rate limitingem; legacy ~210 s = **4.5× faster**) |
| Raw ads scraped | 1 073 (bazos 463, jobs 210, pracecz 400) |
| Final matched (8 query) | **35** (precision 3.3 % z raw) |
| Unit tests | **97** (legacy: 0) |
| MCP maturity | L1 (5 tools) + L3 (1 prompt) |

### Nálezy fixed v Iteration 4

| ID | Nález | Effort | Dopad |
|----|-------|--------|-------|
| N1 | AST cache (8000→8 parsování) | 1h | 99.9% CPU snížení, blokující pro L4 |
| N4 | Pages guard (max 50) | 15min | Resource abuse prevence |
| N5 | Rate limiting (1.0s delay) | 1h | ToS compliance, ochrana před blokací IP |
| N6 | Auto-validate boolean při loadu | 30min | Fail-fast na malformed config |
| N7 | MCP error kontrakt sjednocen | 1h | Konzistentní LLM-friendly errors |
| N8 | Config error messages | 30min | User-friendly TypeError zprávy |
| N11 | Inline import → top-level | 5min | Lint clean |

---

## NOVÁ ARCHITEKTURA — Universal Job Engine

### Princip

MCP engine je univerzální — konfigurace je personalizace uživatele.

```
User config (YAML):
  - portals + categories
  - boolean queries per topic
  - locations, exclusions, min salary
         │
         ▼
  SearchPipeline:
    1. scrape_all(category_url, pages) per portal → raw pool
    2. boolean filter na poolu (title + desc + company)
    3. location filter + salary filter
    4. merge dedup → results per query
```

### Složení

```
MCP-Jobs/
├── src/mcp_jobs/
│   ├── server.py          # FastMCP + tool registrace
│   ├── cli.py             # CLI entry point
│   ├── pipeline.py        # NOVÝ: orchestrator (bulk → filter → merge)
│   ├── config.py          # NOVÝ: UserConfig loader (YAML → dataclass)
│   ├── models.py          # Ad, SearchResult (beze změny)
│   ├── http.py            # HttpClient wrapper (beze změny)
│   ├── matcher.py         # matches_ad() — rozšíření na full ad text
│   ├── storage.py         # CSV I/O (beze změny)
│   └── providers/
│       ├── base.py        # ABC: scrape_all(url, pages) místo search(query)
│       ├── bazos.py       # bulk scrape z prace.bazos.cz/
│       ├── jobs.py        # bulk scrape z jobs.cz/prace/informatika/
│       ├── pracecz.py     # bulk scrape z prace.cz/nabidky/?category=IT
│       └── nyx.py         # DEPRECATED — není job portál, vyžaduje auth
├── config.yaml.example    # NOVÝ: vzorová uživatelská konfigurace
└── tests/
    ├── test_matcher.py    # (beze změny)
    ├── test_providers.py  # rozšířit o scrape_all()
    ├── test_pipeline.py   # NOVÝ: unit testy pipeline
    └── test_server.py     # (beze změny)
```

### Provider interface

```python
class BaseScraper(ABC):
    """Jediná odpovědnost: stáhnout a naparsovat inzeráty z URL"""

    @abstractmethod
    def scrape_all(self, url: str, max_pages: int) -> list[Ad]:
        """Scrape ALL listings from given category URL (ne search)"""
```

**Provider neví nic o:** boolean queries, locations, salaries, user preferences.
**Provider ví jen:** jak stáhnout HTML z dané URL, jak naparsovat inzeráty z HTML.

### Matcher upgrade

```python
def matches_ad(ad: Ad, boolean_query: str) -> bool:
    """Aplikuje boolean logiku na title + description + company"""
    text = f"{ad.title} {ad.description} {ad.company}".lower()
    return evaluate_boolean(text, boolean_query)
```

### Pipeline orchestrator

```python
class SearchPipeline:
    def __init__(self, config: UserConfig):
        self.config = config

    def run(self) -> dict[str, list[Ad]]:
        """Vrátí dict {query_name: [filtered_ads]}"""

        # Fáze 1: Bulk scrap dle konfigurace
        pool = self._scrape_all()

        # Fáze 2: Filtrování dle každé query
        results = {}
        for name, qconf in self.config.queries.items():
            filtered = [
                ad for ad in pool
                if matches_ad(ad, qconf.boolean)
                and _location_filter(ad, qconf.locations)
                and _salary_filter(ad, qconf.min_salary)
            ]
            results[name] = filtered
        return results

    def _scrape_all(self) -> list[Ad]:
        pool = []
        for name, pconf in self.config.portals.items():
            if not pconf.enabled:
                continue
            provider = get_provider(name)
            for cat in pconf.categories:
                raw = provider.scrape_all(cat.url, cat.pages)
                pool.extend(raw)
        return unique_by_url(pool)
```

### Config example

```yaml
user: "default"
portals:
  jobs:
    enabled: true
    categories:
      - url: "https://www.jobs.cz/prace/informatika/"
        pages: 5
  bazos:
    enabled: true
    categories:
      - url: "https://prace.bazos.cz/"
        pages: 10
  pracecz:
    enabled: true
    categories:
      - url: "https://www.prace.cz/nabidky/?category=IT"
        pages: 5

queries:
  python_jobs:
    boolean: "python AND (developer OR vývojář OR programátor) NOT senior"
    min_salary: 0
    locations: []
    portals: ["jobs", "pracecz"]
  cnc_jobs:
    boolean: "(cnc OR frézař) AND (programování OR seřizování)"
    locations: ["brno", "praha", "ostrava"]
    portals: ["bazos", "pracecz"]
```

---

## Bus factor eliminace

| Riziko | Řešení |
|--------|--------|
| Autorovy kategorie/URL | Uživatel definuje v `config.yaml` |
| Autorovy boolean query | Uživatel píše vlastní per téma |
| Autorovy lokality | Location filtr dle konfigurace |
| Pevný seznam portálů | Registry providerů, user si vybírá `enabled` |
| Znalost HTML struktury | Provider per portal — OOP zapouzdření |

---

## ZÁKAZY (platné pro všechny fáze)

| Pattern | Důvod |
|---------|-------|
| Hardcoded `C:\...` cesty | Použít `Path(__file__)`. Viz ZÁZNAM 076. |
| Substring matching | VŽDY `\b` word boundary. `cnc` nesmí matchovat `elektrocnc`. |
| Portal `?q=` search jako primární zdroj | Black box bez boolean logiky = low SNR. Místo: category bulk scrape. |
| Provider-specific business logic | Provider ví jen jak scrapovat URL. Filtrování = pipeline layer. |
| `except Exception: continue` | Silent data loss — vždy logovat skip count (#022). |
| Hardcoded BASE_URL pro bazos | Subdoména závisí na kategorii — extrahovat z page URL. |

---

## FALZIFIKAČNÍ TESTY

```python
# Test 1: AND logic
assert matches_ad(Ad(title="Python Developer"), "python AND developer") == True
assert matches_ad(Ad(title="Java Developer"), "python AND developer") == False

# Test 2: Word boundary
assert matches_ad(Ad(title="CNC fréza"), "cnc") == True
assert matches_ad(Ad(title="elektrocnc"), "cnc") == False

# Test 3: Exclude
assert matches_ad(Ad(title="Senior Test Engineer"), "test NOT senior") == False

# Test 4: Description fallback
assert matches_ad(Ad(title="Název pozice", description="Hledáme autoelektrikáře"), "autoelektrikář") == True

# Test 5: Location filter
assert _location_filter(Ad(location="Brno"), ["praha"]) == False
assert _location_filter(Ad(location="Brno"), ["brno"]) == True

# Test 6: Query isolation
assert matches_ad(Ad(title="cnc operátor"), "python") == False
```

---

## SNR dosažené (Phase 03 realita)

| Portál | Raw ads | Final matched | Precision | Poznámka |
|--------|---------|---------------|-----------|----------|
| **Bazos** | 462 | 17 (sample) | ~3.7 % | Generalista — nízká hustota IT/řemeslo. Přesnost daná booleanem |
| **Jobs** | 210 | 3 (sample) | ~1.4 % | Nízký match, protože kategorie jsou široké, location filtr ořezává |
| **Pracecz** | 400 | 6 (sample) | ~1.5 % | Podobné jako Jobs — široké kategorie |

> *Precision je záměrně nízká — raději 34 jistých matchů než 112 s ~30% noise jako legacy.*

---

## Phase roadmap (aktuální k 2026-08-22)

| Phase | Náplň | Stav | EROI |
|-------|-------|------|------|
| 01 | FastMCP skeleton + search_jobs | ✅ Hotovo | 90/100 |
| 02 | Live scraping (requests+BS4, 4 portály) | ✅ Architektonický defect → Phase 03 | 60/100 |
| 03 | Category bulk + boolean pipeline + config layer | ✅ **v0.3.0** | 90/100 |
| 04 | **Hardening: AST cache, pages guard, rate limiting, auto-validate, MCP error kontrakt** | ✅ **v0.3.1 (Iter4)** | **95/100** |
| 05 | **Refaktor outputu: unified MD+HTML renderer, dedup napříč query** | ✅ **v0.4.0** | **95/100** |
| 06 | **PIVOT: Fáze 0 CI/cron → Fáze 1 PostgreSQL → Fáze 2 Streamlit dashboard** | ✅ **2026-08-22** | **90/100** |
| 07 | **Dashboard Analyza tab (9 sections) + GT v17 + CI fix** | ✅ **2026-08-22** | **90/100** |
| 08 | TS + Next.js GUI na jobs.systeq.cz | 📅 NEXT | 70/100 |
| 09 | LinkedIn integrace, hostovaný demo | 📅 | 70/100 |

---

## EROI scoring — template pro port (z linkedin-mcp-custom)

| Dimenze | Váha | CZ adaptace |
|---------|------|-------------|
| Domain | 35% | Stejný engine — industrial automation keywords jsou language-agnostic |
| Tech | 25% | Skill matrix beze změny, přidat CZ-specific (TIA Portal, Siemens PLC) |
| Role | 20% | "Engineer" vs "Service Tech" — universální pattern |
| Growth | 10% | Replace LinkedIn employers → CZ: Siemens, ABB, Škoda Auto, Thermo Fisher, Bosch, Foxconn |
| Formal | 5% | CZ vzdělání: VŠ/Ing preferred, VOŠ/SŠ accepted |
| Location | 5% | CZ města: Praha, Brno, Ostrava, Plzeň + remote score |

Thresholds: ≥65 SLEDOVAT, 50-64 MEDIUM, 40-49 HRANICNI, <40 NESLEDOVAT

---

## REFERENCE

| Odkaz | Účel |
|-------|------|
| `_github/scrapers/` | Původní Python skripty — reference fungující architektury |
| `_github/scrapers/common/matcher.py` | Unified keyword matching engine |
| `_github/scrapers/common/http.py` | make_session, get_soup, is_url_alive |
| `_github/scrapers/bazos/fast_v3.py` | Reference — nejčistší save strategie |
| `_github/scrapers/jobs/jobsfastv2.py` | Reference — AND matching + selectory |
| `_github/scrapers/pracecz/pracefastv1.py` | Reference — nejčistší matching |
| `_github/scrapers/verify_selectors.py` | Selector health test suite |
| `_github/linkedin-mcp-custom/` | Referenční architektura MCP serveru (EROI, KB, CLI) |
| `_github/linkedin-mcp-custom/src/linkedin_mcp_custom/analysis/` | EROI scoring engine template |
| `_github/B2B-Knowledge-Base/04_KNOWLEDGE_BASE/01_MCP/linkedin_mcp_pitevni_kniha_v1.md` | LinkedIn MCP post-mortem |
| `_github/B2B-Knowledge-Base/04_KNOWLEDGE_BASE/01_MCP/sdilena_pitevni_kniha_mcp.md` | Cross-repo MCP pravidla (P1-P16) |
| `_github/CONTEXT_REPOS.md` | Hlavní index všech repozitářů |
| `docs/edukace_port_standalone_2026-08-15.md` | Pivot: MCP vs standalone, ontologie, SWE nástroje |
| `docs/edukace_implementace_standalone_pivot_2026-08-15.md` | EROI fáze pivota + adopce skills 60/20/10/10 |
| `_github/B2B-Knowledge-Base/01_METODIKY/04_skill_acquisition/SKILL_GAPS_ROZBOR_Q3_2026_v2.md` | 6 skill gapů + trajektorie |
| `_github/B2B-Knowledge-Base/01_METODIKY/04_skill_acquisition/ADOPCNI_METODOLOGIE_2026_v1.md` | 60/20/10/10 adopční metodika |
| `data/` | Live scraped raw HTML + results JSON (Phase 02 artifacts) |
