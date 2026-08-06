# Semantic Analysis: Cross-LLM Code Review MCP-Jobs v0.4.0

**Datum:** 2026-08-06
**Reviewer:** Ondrej Soucek (semantická analýza + EROI plán)
**Zdroj:** Claude Sonnet 5 cross-LLM review (HEAD 49e79f6)
**Cíl:** Validace nálezů + EROI-prioritizovaný plán úprav (bez změn kódu/architektury)

---

## 1. Validace nálezů

### 1.1 Faktická kontrola (9/9 nálezů ověřeno)

| # | Nález | Status | Důkaz |
|---|-------|--------|-------|
| SEC-001 | SSRF přes `CategoryConfig.url` | **PLATNÝ** | `config.py:28` — `url: str` bez validace → `pipeline.py:141` → `requests.get()` |
| SEC-003 | `request_delay` bez spodního limitu | **PLATNÝ** | `config.py:60` — žádný `__post_init__` clamp |
| BUG-001 | Detail cache neúspěch se nekešuje | **PLATNÝ** | `pipeline.py:103-104` — `if detail:` → jen success |
| BUG-002 | `test_encoding_docs_exist` selhává | **PLATNÝ** | Testuje `docs/powershell_encoding.md` který nikdy neexistoval |
| BUG-003 | NyxScraper v REGISTRY | **PLATNÝ** | `providers/__init__.py:10` |
| BUG-004 | `stats.requests_ok += 1` není atomické | **PLATNÝ** (fragilní) | `base.py:65` — thread-safe jen díky per-vlákno izolaci |
| IMPR-ARCH-01 | Sekvenční detail fetch = bottleneck | **PLATNÝ** | `pipeline.py:92-111` — sekvenční přes všechny query |
| SEC-002 | Path sandboxing pro `search_from_config` | **PLATNÝ** (nízký dopad) | `config.py:56` — `Path(path)` bez sandboxu |
| SEC-004 | `.gitignore` nemá `credentials*` | **PLATNÝ** | `.gitignore` = jen `.env`, `*.local` |

### 1.2 Křížové ověření (fakta vs review)

| Tvrzení z promptu | Reálný stav | Rozpor? |
|-------------------|-------------|---------|
| 126/126 pass | 125 pass, 1 fail | **ANO** — test_encoding_docs_exist |
| LRU 8000 | maxsize=128 | **ANO** — irrelevantní (8 static queries) |
| test_server.py 17 tests | 18 tests | **ANO** — drobný |
| Python 3.12+ | >=3.11 | **ANO** — drobný |
| Providers ~600 řádků | 758 řádků | **ANO** — odhad podhodnocen |
| CI/CD neexistuje | `.github/` chybí | **NE** — přesné |
| Salary fix funguje | Test `test_salary_filter_thousand_separator` prochází | **NE** — přesné |

---

## 2. Křížové vazby (dependency map)

```
┌─────────────────────────────────────────────────────────────────┐
│                    DEPENDENCY MAP                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  BUG-001 (cache failure) ─────┐                                 │
│                               ├──→ IMPR-ARCH-01 (parallel      │
│  IMPR-PERF-01 (parallel) ────┘     detail fetch)               │
│                               │   Řeší OBOJÍ současně           │
│                               │                                 │
│  SEC-001 (SSRF) ─────────────┼──→ Bezpečnostní hardening       │
│  SEC-003 (delay clamp) ──────┘   (nezávislé opravy)            │
│                                                                 │
│  BUG-002 (red test) ────────────→ IMPR-TEST-01 (fix/delete)    │
│                                                                 │
│  BUG-003 (nyx) ─────────────────→ Cleanup (nezávislé)          │
│                                                                 │
│  IMPR-TEST-02 (boolean tests) ──→ Regresní pojistka             │
│                                                                 │
│  IMPR-ARCH-02 (atomic write) ──→ Storage hardening             │
│  IMPR-TEST-03 (E2E) ───────────→ Playwright gap (aspirational) │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Klíčový insight:** IMPR-ARCH-01 + BUG-001 + IMPR-PERF-01 = JEDNA oprava řeší 3 nálezy současně. To je nejvyšší EROI v celém review.

---

## 3. EROI-prioritizovaný plán úprav

### 3.1 EROI definice

```
EROI = (dopad × priorita) / (čas implementace × riziko regrese)
```

Hodnoty: dopad (1-5), priorita (1-3), čas (0.25h-4h), riziko (1-3)

### 3.2 TIER 1: Quick wins (EROI 10/10) — celkem ~30 min

| # | Oprava | Soubor | Čas | Dopad | Přínos |
|---|--------|--------|-----|-------|--------|
| **Q1** | Smazat `test_encoding_docs_exist` | `tests/test_synthetic_guardrails.py` | 2 min | OK | 125→125 pass (zelený suite) |
| **Q2** | Clamp `request_delay` na `max(0.2, ...)` | `src/mcp_jobs/config.py` | 5 min | M | Zamezí `request_delay: 0` bypass |
| **Q3** | Přidat `credentials*` do `.gitignore` | `.gitignore` | 2 min | L | Defense-in-depth |
| **Q4** | Odstranit NyxScraper z REGISTRY | `src/mcp_jobs/providers/__init__.py` | 5 min | L | Snížení maint. plochy |
| **Q5** | Komentář k thread-safe invariantu v `base.py` | `src/mcp_jobs/providers/base.py` | 5 min | L | Dokumentace fragilního invariantu |

**Výsledek:** 5 minutové až 5 minutové opravy, 0 rizika regrese, okamžitý efekt.

### 3.3 TIER 2: Core fixes (EROI 8/10) — celkem ~3-4h

| # | Oprava | Soubory | Čas | Dopad | Přínos |
|---|--------|---------|-----|-------|--------|
| **C1** | Paralelizovat detail fetch + cache failure fix | `pipeline.py` | 2-3h | H | Řeší BUG-001 + IMPR-ARCH-01 + IMPR-PERF-01 (3 v 1) |
| **C2** | Boolean edge case testy (`NOT NOT`, `AND AND`, `()`) | `tests/test_matcher.py` | 20 min | M | Regresní pojistka pro fail-safe parser |

**Podrobný plán C1 (dvoufázový detail fetch):**

```
FAZE 1: Collect union URLs (CPU, rychlé)
  └─ Projet všechny query → sesbírat unikátní URL z pool
  └─ Výsledek: set_urls = {url1, url2, ..., urlN}

FAZE 2: Parallel detail fetch (I/O, pomalé)
  └─ ThreadPoolExecutor(max_workers=workers)
  └─ Každé vlákno: provider.fetch_detail(ad)
  └─ Zapsat DO cache I neúspěch: detail_cache[url] = result or _FAILED
  └─ Zachovat per-portál throttle přes sdílený HttpClient

FAZE 3: Filter queries (CPU, rychlé)
  └─ Projet každou query nad již naplněnou cache
  └─ detail_cache.get(url) → ad.description = ...
```

**Klíčový detail:** Zápis neúspěchu do cache (`_FAILED sentinel`) řeší BUG-001 automaticky — opakované query na stejnou padlou URL už nebudou dělat retry.

### 3.4 TIER 3: Security hardening (EROI 6/10) — celkem ~1-2h

| # | Oprava | Soubor | Čas | Dopad | Přínos |
|---|--------|--------|-----|-------|--------|
| **S1** | Domain allowlist pro category URL | `config.py` + `pipeline.py` | 1-2h | H | Uzavře SSRF vektor (SEC-001) |

**Podrobný plán S1:**

```python
# config.py — nová konstanta
ALLOWED_DOMAINS = {
    "bazos.cz", "prace.bazos.cz", "reality.bazos.cz", ...,
    "jobs.cz", "*.jobs.cz",
    "prace.cz", "*.prace.cz",
}

# pipeline.py — validace před scrapingem
def _validate_url(url: str, allowed: set[str]) -> bool:
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    return any(host == d or host.endswith("." + d) for d in allowed)
```

**Riziko:** Nízké — allowlist je expanzivní (přidávání nových domén = 1 řádek).

### 3.5 TIER 4: Nice-to-have (EROI 4/10) — celkem ~3-5h

| # | Oprava | Soubor | Čas | Dopad | Přínos |
|---|--------|---------|-----|-------|--------|
| **N1** | Atomický zápis pro `query_store.json`/CSV | `storage.py` | 1h | M | Ochrana proti crash při zápisu |
| **N2** | E2E smoke test (Playwright/httpx) | `tests/` | 2-4h | M | Splnění Gap ❶ (TypeScript/Playwright) |
| **N3** | `pytest --cov` lokální skript | `scripts/` | 1h | L | Coverage visibility |
| **N4** | README sekce: `config.yaml` vs `.example` | `README.md` | 15 min | L | Dokumentace |

---

## 4. Aspirational features — posouzení

### 4.1 Přepis do EROI matice

| Gap | Autorův názor | Claude souhlas | EROI | Doporučení |
|-----|---------------|----------------|------|------------|
| TypeScript + Playwright | E2E testy: ano, scraping: ne | **Souhlas** | 8/10 | Implementovat E2E (N2) |
| AZ-900 Azure | Aspirational, ne urgentní | **Souhlas** | 3/10 | Neimplementovat pro MCP-Jobs |
| PLC/Industrial | Mimo scope, jiný projekt | **Souhlas** | 2/10 | Neimplementovat |
| Kubernetes | Stdio = lokální, K8s = síťový | **Souhlas** | 2/10 | Neimplementovat |

### 4.2 Klíčový insight

Claude správně identifikoval, že **jediná akční položka** ze všech 4 gapů je **Playwright E2E test** (N2). Ostatní gapy = mimo scope MCP-Jobs. Toto je důležité protože:
- E2E test = regresní pojistka pro MCP tools
- Playwright = standard pro test automation (tržní signál)
- Nízká implementační složitost (existující testy = unit, chybí E2E)

---

## 5. Souhrnná tabulka

| Oblast | Claude | Moje validace | Změna |
|--------|--------|---------------|-------|
| Bezpečnost | 6/10 | **6/10** | Souhlas — SSRF + delay clamp = reálné mezery |
| Bugy | 7/10 | **7/10** | Souhlas — BUG-001 = reálný, BUG-002 = mrtvý test |
| Architektura | 8/10 | **8/10** | Souhlas — detail fetch = bottleneck |
| Výkon | 7/10 | **7/10** | Souhlas — 1.82x portál, detail = zbývající |
| Testy | 7/10 | **7/10** | Souhlas — 1 red test, chybí E2E |
| Aspirational | 8/10 | **8/10** | Souhlas — jen Playwright E2E = akční |
| **CELKEM** | **7.2/10** | **7.2/10** | **Souhlas** |

---

## 6. Implementační pořadí (EROI sestupně)

```
SPRINT 1 (30 min): Quick wins
  Q1: Smazat mrtvý test
  Q2: Clamp request_delay
  Q3: .gitignore credentials
  Q4: Odstranit Nyx z REGISTRY
  Q5: Komentář k thread-safe invariantu

SPRINT 2 (3-4h): Core fixes
  C1: Paralelní detail fetch + cache failure fix (3 v 1)
  C2: Boolean edge case testy

SPRINT 3 (1-2h): Security
  S1: Domain allowlist

SPRINT 4 (3-5h): Nice-to-have
  N1: Atomic writes
  N2: E2E smoke test
  N3: Coverage skript
  N4: README dokumentace
```

**Celkový odhad:** 7-11h práce na 2-3 sprints
**Výsledek:** 7.2/10 → odhad 8.5-9/10 po implementaci

---

*Analýza provedena: 2026-08-06*
*Zdroj: Claude Sonnet 5 cross-LLM review (HEAD 49e79f6)*
*Metoda: Faktická validace + křížové vazby + EROI priorita*
