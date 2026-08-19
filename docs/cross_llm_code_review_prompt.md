# Cross-LLM Code Review Prompt: MCP-Jobs v0.4.0

**Datum:** 2026-08-06
**Účel:** Prompt pro cross-LLM audit repozitáře MCP-Jobs přes git fetch
**Repo:** https://github.com/outpost2026/MCP-Jobs.git
**Branch:** main (HEAD: e309cc3)
**Autor review:** Alternativní LLM (Claude/GPT/Gemini/Codex)

---

## 1. REPOZITÁŘ — AKTUÁLNÍ STAV

### 1.1 Přehled
- **Název:** MCP-Jobs v0.4.0
- **Jazyk:** Python 3.12+ (FastMCP, requests, BeautifulSoup, PyYAML)
- **Účel:** MCP server pro scraping českých pracovních portálů (Bazos, Jobs.cz, Prace.cz)
- **Stack:** FastMCP stdio transport, synchronní `requests` + throttle 0.5s/portal
- **Testy:** 126/126 pass (pytest)
- **CI/CD:** NEEXISTUJE (.github/ chybí)
- **Deployment:** manuální přes .bat launcher

### 1.2 Klíčové soubory (přesné cesty)

| Modul | Cesta | Řádků | Role |
|-------|-------|------:|------|
| Pipeline | `src/mcp_jobs/pipeline.py` | 208 | Orchestrace: paralelní scraping (ThreadPoolExecutor) + query matching |
| Server | `src/mcp_jobs/server.py` | 440 | FastMCP: 5 tools, 3 resources, 1 prompt |
| Matcher | `src/mcp_jobs/matcher.py` | 268 | Boolean AST parser + LRU cache + NFKD diakritika |
| Config | `src/mcp_jobs/config.py` | 158 | UserConfig, PipelineSettings (max_workers, request_delay) |
| HTTP | `src/mcp_jobs/http.py` | 86 | Synchronní HTTP klient (requests.Session + retry + throttle) |
| Storage | `src/mcp_jobs/storage.py` | 233 | CSV I/O + query_store.json persistence |
| Models | `src/mcp_jobs/models.py` | 81 | Ad dataclass |
| Providers | `src/mcp_jobs/providers/*.py` | ~600 | BazosScraper, JobsScraper, PraceczScraper, NyxScraper (deprecated) |
| Tests | `tests/test_*.py` | ~2000 | 126 unit testů |

### 1.3 Architektura

```
User/MCP Client
  └─> server.py (FastMCP stdio)
       ├─ search_jobs_v2: ad-hoc query
       ├─ search_from_config: YAML config pipeline
       ├─ search_from_yaml: inline YAML
       ├─ list_portals: portál metadata
       ├─ health_check: status
       └─ resources: mcp-jobs://ads/{query_id}
            └─> pipeline.py (SearchPipeline)
                 ├─ _scrape_all() [PARALLEL — ThreadPoolExecutor]
                 │   ├─ bazos.py   → requests + BeautifulSoup
                 │   ├─ jobs.py    → requests + BeautifulSoup
                 │   └─ pracecz.py → requests + BeautifulSoup
                 ├─ _dedup() [fuzzy + URL dedup]
                 └─ query matching (matcher.py)
                      └─ fetch_detail() [sequential, lazy]
```

### 1.4 Pipeline config (config.yaml)

```yaml
pipeline:
  max_workers: 3        # paralelism portálů
  request_delay: 0.5    # sekundy mezi requesty per portal

portals:
  jobs:     { enabled: true, categories: [{url, pages: 20+5}] }
  bazos:    { enabled: true, categories: [{url, pages: 15+15}] }
  pracecz:  { enabled: true, categories: [{url, pages: 25}] }

queries: 8 dotazů (python_ai_engineer, ai_llm_engineer, mcp_agentic,
           data_engineering, devops_ci_cd, prumyslova_automatizace,
           cnc_cam_automation, reverse_engineering)
```

### 1.5 Test coverage (126 testů)

| Modul | Počet | Pokrytí |
|-------|------:|---------|
| test_matcher.py | 40 | Boolean parser, diakritika, edge cases |
| test_pipeline.py | 19 | Dedup, filtry, paralelismus, detail cache |
| test_providers.py | 21 | Parse, empty HTML, stop-on-empty |
| test_server.py | 17 | Tools, resources, prompts |
| test_config.py | 10 | YAML parsing, validation, fail-fast |
| test_utils.py | 6 | strip_emoji |
| test_synthetic_guardrails.py | 9 | Encoding, cp1250 |
| test_http.py | 3 | Exception handling |
| live_scrapers.py | 1 | Live integration test |

### 1.6 Reální výsledky (2026-08-06)

| Metrika | Hodnota |
|---------|---------|
| Sekvenční beh (max_workers=1) | 106.4s |
| Paralelní beh (max_workers=3) | 58.5s |
| Zrychlení | 1.82x |
| Requestů na beh | 74 |
| Unique jobs (IT run) | 16 / 28 raw |
| Avg response time | 826-1114 ms |

---

## 2. CODE REVIEW FOKUSOVÉ OBLASTI

### 2.1 Bezpečnost (Security)
- [ ] **注入 (Injection):** Je `boolean` výraz z uživatelského vstupu bezpečně parsován? (matcher.py: parse_boolean)
- [ ] **Rate limiting bypass:** Je throttle (0.5s) dostatečný proti 429/ban?
- [ ] **Credential leak:** Jsou .env soubory, API klíče, cookies v .gitignore?
- [ ] **URL manipulation:** Může uživatel přes `search_from_yaml` zadat libovolnou URL?
- [ ] **Path traversal:** Je `config` cesta v `search_from_config` bezpečná?
- [ ] **Dependency vulnerabilities:** Jsou závislosti aktuální? (fastmcp, requests, bs4)

### 2.2 Bugy a Edge Cases
- [ ] **Threading race conditions:** `ThreadPoolExecutor` + `detail_cache` (dict) v `run()` — je thread-safe?
- [ ] **Threading + `requests.Session`:** Je Session objekt thread-safe mezi vlákny?
- [ ] **Dedup fuzzy:** `seen_fuzzy` set — může hashovací kolize zahodit validní ads?
- [ ] **Boolean parser edge cases:** Co s `NOT NOT x`, `AND AND`, prázdné závorky `()`?
- [ ] **Empty pool:** Co když `_scrape_all()` vrátí prázdný pool? (pipeline.py:194)
- [ ] **Provider failure:** Co když jeden portál spadne celý? (pipeline.py:191)
- [ ] **Detail cache miss:** `fetch_detail()` selže — je ad stále v resultech bez description?
- [ ] **N+1 detail fetch:** V `run()` se fetch_detail volá sekvenčně pro každou unikátní URL. Při 100+ inzerátech = 100 sekvenčních requestů.
- [ ] **Memory:** 74+ requestů + BeautifulSoup objekty — může to narůst?
- [ ] **Config validation:** Co když `max_workers: 0` + žádné portály? (pipeline.py:165)

### 2.3 Architektura
- [ ] **Sekvenční detail fetch:** `run()` fáze dělá `fetch_detail()` sekvenčně přes všechny unikátní URL. To je bottleneck. Navrhněte paralelizaci.
- [ ] **Storage.py:** CSV I/O + JSON persistence — je to robustní? Co s koncurentním přístupem?
- [ ] **Nyx provider:** Deprecated, ale stále v REGISTRY. Odstranit?
- [ ] **Error handling:** `provider.stats.errors.append(str(e))` — mělo by se logovat stack trace.
- [ ] **Test mockování:** Testy používají `FakeProvider` s hand-rolled stats. Mělo by se to zjednodušit přes mock/fixture.
- [ ] **Maturity gap:** L1 (5 tools), L2 (resources), L3 (1 prompt) — je to complete? Chybí L4 (agent)?

### 2.4 Výkon (Performance)
- [ ] **Throttle 0.5s:** Naměřeno 58.5s paralelně. S throttle 1.0s bylo 58.5s také. Snížení throttle NEMÁ měřitelný vliv — bottleneck je síťová latence (~900ms).
- [ ] **LRU cache:** `matcher.py` má LRU 8000 pro boolean parsing. Stačí to?
- [ ] **Soup parsing:** BeautifulSoup parser — je `html.parser` nebo `lxml` rychlejší?
- [ ] **Pagination:** `max_pages: 20-25` — koľko reálně stránek se scrapne?

---

## 3. ASPIRATIONAL FEATURES — SKILL GAPS ANALÝZA

### 3.1 Kontext

Dokument `SKILL_GAPS_ROZBOR_Q3_2026_v1.md` (B2B-Knowledge-Base) identifikuje 4 mezery v autorově stacku, které blokují 35-45% analyzovaných rolí. Tyto gapy přímo souvisejí s MCP-Jobs a mají implikace pro code review:

### 3.2 Gap ❶: TypeScript + Playwright (ERROI: 8/10)

**Co je aspirační:**
- Playwright E2E testy pro MCP-Jobs (nejsou implementovány)
- TypeScript MCP client/test suite (neexistuje)
- Web scraping přes Playwright místo requests+BS4 (pro JS-renderované stránky)

**Posouzení implikace pro MCP-Jobs:**
- **Současný scraping:** requests + BeautifulSoup (synchronní, rychlý pro server-rendered HTML)
- **Playwright alternativa:** Potřeba pro stránky s client-side rendering (React/Vue). Bazos a Jobs.cz jsou server-rendered → Playwright NENÍ potřeba.
- **E2E testy:** Playwright testy pro MCP tools neexistují. Chybí smoke testy: "spusť MCP server → zavolej search_jobs_v2 → ověř výsledek."
- **Doporučení:** Playwright E2E testy = prioritní gap pro test automation. Ne pro scraping (requests stačí).

### 3.3 Gap ❷: AZ-900 Azure Fundamentals (ERROI: 7.5/10)

**Co je aspirační:**
- Deploy MCP-Jobs na Azure App Service / Container Instances
- Azure DevOps CI/CD pipeline
- Azure Monitor logging

**Posouzení implikace pro MCP-Jobs:**
- **Současný deployment:** manuální (.bat launcher, stdio)
- **Azure cesta:** MCP-Jobs jako kontejner → Azure Container Instances → CI/CD přes Azure DevOps
- **Priorita:** NÍZKÁ. MCP-Jobs je lokální tool, ne SaaS. Azure deployment = aspirational, ne nutný.
- **Doporučení:** Azure = gateway k enterprise rolím, ale pro MCP-Jobs samotný není potřeba.

### 3.4 Gap ❸: PLC Basics & Industrial Protocols (ERROI: 5.5/10)

**Co je aspirační:**
- PLC data scraper (Modbus/OPC UA) → MCP-Jobs jako průmyslový ETL
- Průmyslové portály (Siemens Job Portal, Rockwell Careers)
- Integrace s SCADA/MES daty

**Posouzení implikace pro MCP-Jobs:**
- **Současný scope:** jen pracovní portály (Bazos, Jobs, Prace)
- **PLC integrace:** mimo scope MCP-Jobs. Autorův CNC_2_LLM projekt = separátní.
- **Průmyslové portály:** Mohly by se přidat jako nové providery (Siemens, Rockwell career stránky). Ale to je nový modul, ne refaktor.
- **Doporučení:** PLC = dlouhodobý skill gap, ne urgentní pro MCP-Jobs. Implementace nových providerů = možná budoucí větev.

### 3.5 Gap ❹: Kubernetes (ERROI: 4/10)

**Co je aspirační:**
- MCP-Jobs jako K8s Deployment
- Auto-scaling scraperů
- Portabilita (AWS/GCP/Azure)

**Posouzení implikace pro MCP-Jobs:**
- **Současný deployment:** lokální stdio, žádný kontejner
- **K8s nasazení:** MCP servery jako K8s Deployment + Service. Technicky možné, ale MCP stdio transport = nevhodný pro síťový přístup.
- **Priorita:** NÍZKÁ. MCP stdio = lokální. K8s = pro síťové servery.
- **Doporučení:** K8s = aspirational. Pro MCP-Jobs aktuálně nedává smysl. Pro jiné MCP servery (linkedin-analyzer) = ano.

---

## 4. OTÁZKY PRO CODE REVIEW

### 4.1 Bezpečnost (5 otázek)
1. `matcher.py: parse_boolean()` — je parser odolný proti injection? (např. `__import__('os').system('rm -rf /')`)
2. `server.py: search_from_yaml()` — může uživatel předat YAML s nebezpečnými příkazy?
3. `.gitignore` — obsahuje `.env`, `*.local`, `credentials*`?
4. `http.py` — je retry backoff dostatečný proti brute-force rate limitu?
5. `storage.py` — je `query_store.json` chráněný proti přetečení (overflow)?

### 4.2 Bugy (5 otázek)
1. `pipeline.py:165` — `workers = max(1, min(workers, len(tasks)))` — co když `tasks` je prázdný?
2. `pipeline.py:184` — `as_completed(futures)` — může se `pool.extend(got)` provést současně ve dvou vláknech? (thread-safe?)
3. `matcher.py` — LRU cache má maxsize=8000. Při 8 queries + variabilní text = stačí?
4. `providers/base.py:61` — `self.stats.requests_ok += 1` — thread-safe?
5. `pipeline.py:111` — `detail_cache.get(ad.url)` — může vrátit None i když fetch_detail proběhl?

### 4.3 Architektura (5 otázek)
1. Detail fetch v `run()` je sekvenční. Je to bottleneck? Navrhněte řešení.
2. `NyxScraper` je deprecated. Odstranit z REGISTRY?
3. `storage.py` — CSV I/O + JSON persistence — je to robustní pro concurrency?
4. MCP L3 (prompt) = `search_expert`. Je to complete? Chybí L4 (agent)?
5. `config.yaml` vs `config.yaml.example` — proč jsou rozdílné? (config.yaml má 8 queries, example má 8 legacy queries)

### 4.4 Výkon (5 otázek)
1. Paralelism portálů: 1.82x zrychlení. Jak paralelizovat detail fetch (sekvenční bottleneck)?
2. BeautifulSoup parser: `html.parser` vs `lxml` — jaký je rozdíl v rychlosti?
3. Throttle 0.5s vs 1.0s: naměřeno 58.5s v obou případech. Proč nemá vliv?
4. `max_pages: 20-25` — kolik reálně stránek se scrapne? Je to efektivní?
5. `LRU cache: 8000` — jaká je cache hit rate?

---

## 5. HODNOTICÍ KRITÉRIA

### 5.1 Code Quality (0-10)
- Čistota kódu, čitelnost, komentáře
- DRY princip, opakování kódu
- Typování (Type hints)
- Error handling
- Logging kvalita

### 5.2 Test Coverage (0-10)
- Unit test pokrytí
- Edge case pokrytí
- Mock kvalita
- Integration testy
- E2E testy (chybí)

### 5.3 Architecture (0-10)
- Separation of concerns
- Extensibility (nové portály, nové query)
- Coupling (závislosti mezi moduly)
- Configurability
- Deployment readiness

### 5.4 Security (0-10)
- Input validation
- Rate limiting
- Credential handling
- Dependency vulnerabilities
- OWASP Top 10

### 5.5 Performance (0-10)
- Paralelismus
- Throttling
- Memory usage
- Cache effectiveness
- Bottleneck identification

---

## 6. VÝSTUP FORMÁT

Požadovaný výstup pro každou oblast:

```
## [Oblast]: [Hodnocení X/10]

### Silné stránky
1. [konkrétní nalezený pattern]
2. [další silná stránka]

### Bugs / Rizika
1. [BUG-001] Soubor:řádek — Popis — Dopad — Doporučení
2. [BUG-002] ...

### Návrhy na vylepšení
1. [IMPR-001] Popis — Priorita (H/M/L) — Odhad času
2. [IMPR-002] ...

### Aspirational Features posouzení
1. [gap z SKILL_GAPS] — Implementovat / Neimplementovat — Důvod
```

---

## 7. SOUHRNNÁ TABULKA

| Oblast | Hodnocení | Klíčový nález |
|--------|:---------:|---------------|
| Bezpečnost | ?/10 | |
| Bugy | ?/10 | |
| Architektura | ?/10 | |
| Výkon | ?/10 | |
| Testy | ?/10 | |
| Aspirational | ?/10 | |
| **CELOKEM** | **?/10** | |

---

*Prompt vytvořen: 2026-08-06*
*Pro cross-LLM audit: git clone https://github.com/outpost2026/MCP-Jobs.git && git checkout main*
*HEAD: e309cc3*
