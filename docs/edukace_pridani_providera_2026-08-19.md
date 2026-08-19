# EDUKACE: Přidání nového portálu (providera) do MCP-Jobs

**Datum:** 2026-08-19 | **Typ:** metodologie / dev návod | **Rozsah:** MCP-Jobs repo
**Case study:** jenprace.cz (úspěšná integrace, 4. portál) + startupjobs.cz (negativní příklad)

---

## 1. Účel dokumentu

Kanonický návod, jak přidat nový zájmový web (portál s pracovními nabídkami) do
architektury MCP-Jobs. Vysvětluje:

1. jak celé scrapování a MCP-pipeline funguje (data flow, fáze, zodpovědnosti),
2. proč lze skrapovat pouze weby s **server-rendered HTML** a proč JS-rendered weby
   nelze zpracovat BeautifulSoupem,
3. praktické kroky integrace — od feasibility analýzy po finální validaci,
4. konkrétní vzory kódu (selectory, ošetření edge cases) doložené realnou integrací
   portálu jenprace.cz.

Cílová skupina: developer, který provádí **inkrementální modifikaci** — přidává
další portál do existující, prověřené architektury, aniž by ji rozbil.

---

## 2. Jak MCP-Jobs funguje (celkový obraz)

### 2.1 Data flow pipeline

```
config YAML (portals + queries)
        │
        ▼
SearchPipeline.run()                          ← src/mcp_jobs/pipeline.py
┌──────────────────────────────────────────────────────────────────────┐
│ 1. _scrape_all()                                                      │
│    - každý portál = vlastní vlákno (max_workers, per-portál throttle) │
│    - SEC-001: category URL validace proti url_allowlist → ValueError  │
│    - provider.scrape_all(cat.url, pages) → pool Ad inzerátů           │
│    - neznámý portál v configu (mimo REGISTRY) = warning, ne chyba     │
│ 2. _dedup(pool)                                                       │
│    - duplicita URL + fuzzy (title+company+location)                   │
│ 3. FÁZE 1: unikátní URL bez description, které prošly booleanem       │
│ 4. FÁZE 2: paralelní detail fetch (per-portál ThreadPool,             │
│            _FAILED sentinel cache — neúspěch se neopakuje)            │
│ 5. FÁZE 3: boolean match → cached description → exclude terms →       │
│            location filter → salary filter                            │
└──────────────────────────────────────────────────────────────────────┘
        │
        ├─► Storage.save_outputs → output/etl_<profile>_<ts>.{json,md,html}
        ├─► _save_correlation → data/correlation_cache.json
        └─► persist_run → PostgreSQL (tabulky ads + pipeline_runs, graceful skip)
```

### 2.2 Zodpovědnosti vrstev

| Vrstva | Soubor | Zodpovědnost |
|---|---|---|
| **Provider** | `src/mcp_jobs/providers/<portal>.py` | HTTP fetch + HTML → `Ad` objekty (parse listingu, paginace, detail) |
| **Registry** | `src/mcp_jobs/providers/__init__.py` | Mapování jméno → třída (`REGISTRY`, `ACTIVE_PORTALS`) |
| **HTTP** | `src/mcp_jobs/http.py` | Session, retry (429/5xx), throttle, encoding |
| **Model** | `src/mcp_jobs/models.py` | `Ad` dataclass → `to_dict()` (strip_emoji, missing_fields flagy) |
| **Matcher** | `src/mcp_jobs/matcher.py` | Boolean vyhledávání (AND/OR/NOT), diakritika-insensitive, word-boundary |
| **Pipeline** | `src/mcp_jobs/pipeline.py` | Orchestrace: scrape → dedup → detail → filtry |
| **Config** | `src/mcp_jobs/config.py` | YAML → `UserConfig` dataclasses, allowlist, throttle politika |
| **MCP vrstva** | `src/mcp_jobs/server.py` | FastMCP tooly, aliases, async job runner, L2 resources, persist |
| **DB** | `src/mcp_jobs/db.py` | Upsert `ads`, zápis `pipeline_runs` (graceful — DB výpadek neselže pipeline) |

### 2.3 Klíčové mechanismy, na kterých vše stojí

**Lazy detail fetch (Fáze 1+2).** Listingy se skrapují kompletně, ale popis
(`description`) se stahuje **pouze pro inzeráty, které prošly boolean filtrem**
a nemají description už z listingu (bazos ho má přímo v kartě). Detail se
stahuje 1× per URL (cache v rámci běhu), neúspěch se cacheuje sentinelem
`_FAILED` — žádný retry v rámci stejného běhu.

**Per-portál throttle.** Každá instance providera dostane vlastní `HttpClient`
s `request_delay` (default 0.5s, clamp min 0.2s). To znamená: paralelismus mezi
portály, ale slušné chování vůči každému serveru zvlášť. Retry přes urllib3
pouze na `429, 500, 502, 503, 504`.

**SEC-001 SSRF ochrana.** `BaseScraper._fetch_page` i pipeline validují každou
URL proti `url_allowlist` (`config.py` default: bazos.cz, jobs.cz, prace.cz,
jenprace.cz). URL mimo allowlist = BLOCKED (log + `ValueError` u category URL,
skip u detail fetch). **Nový portál musí být přidán do default allowlistu**,
jinak pipeline spadne i při validní konfiguraci.

**Detekce rozbité struktury (M4).** `parse_listings` loguje `ERROR` pokud
kontejner selektor vrátí 0 karet, nebo karty existují ale 0 se naparsovalo —
okamžitá signalizace změny layoutu portálu (ne tichý prázdný výsledek).

**Diakritika a word-boundary v matcheru.** Boolean výrazy fungují bez ohledu
na diakritiku (`programátor` == `programator`) a s word-boundary matchnutím
(`(?<!\w)...(?!\w)` — `cnc` NEmatchnuje `elektrocnc`, ale `c++`/`c#` matchnou).

**Encoding disciplína.** Windows konzole = cp1250. `server.py` volá
`ensure_utf8_stdout()` (P18). Všechny soubory UTF-8. Spouštění skriptů:
`python -X utf8` + `$env:PYTHONIOENCODING='utf-8'`. Emoji v titulcích
(🔥 🚚 ⛽) odstraňuje `Ad.to_dict()` přes `strip_emoji` — emoji se nikdy
nezapisují do souborů/DB.

---

## 3. Proč pouze server-rendered weby?

### 3.1 Základní princip

BeautifulSoup je **statický HTML parser** — nemá žádný JavaScript runtime.
Umí zpracovat přesně to, co přijde v HTTP odpovědi `GET` requestu.

| Typ webu | Co je v HTML odpovědi | BS zpracovatelný? |
|---|---|---|
| Server-rendered (SSR / klasický HTML) | Kompletní obsah — karty, odkazy, text | **ANO** |
| JS-rendered (SPA: Nuxt, React, Vue, Next) | Skeleton loadery, prázdné kontejnery, `__NUXT__` JSON | **NE** — data se načtou až po JS execution |

### 3.2 Jak poznat, že web je skrapovatelný (feasibility test)

1. **GET hlavní kategorii** (bez JS): `requests.get(url)` a hledej v surovém HTML
   `re.search(r'article|item|card|job', text)`. Najdeš-li inzerát jako HTML element → OK.
2. **Ověř paginaci:** `?page=N` / `/strana-2` / `?strana=N` — stačí jeden request navíc.
3. **Ověř detail stránku:** GET jeden inzerát → je popis v HTML?
4. **Anti-bot:** 403/Cloudflare/captcha → neimplementovatelné bez headless browseru.
5. **Encoding:** čeština musí být korektně dekódovaná (`apparent_encoding` fallback).

> **Anti-vzor:** DevTools → Elements ukazuje DOM **po JS execution**. Vidíš-li
> tam data, neznamená to, že jsou v surovém HTML. Vždy ověř v raw `resp.text`
> (ulož si HTML do souboru a hledej selectory v něm).

### 3.3 Negativní case study: startupjobs.cz (2026-08-19)

- **Nuxt 3 SSR**: stránka vrací HTML, ale seznam inzerátů je vykreslován
  client-side — v HTML jen skeleton loadery (`<div class="skeleton">`).
- Pokus o API: `POST /api/search-offers` a `GET /api/offers` → **404**.
- Závěr: **nelze bez headless browseru** (Playwright) — to by znamenalo novou
  runtime závislost a kompletně jinou architekturu providera. Odmítnuto, zůstává
  otevřená otázka.

---

## 4. FÁZE 0: Feasibility analýza nového portálu

Před psaním kódu odpověz na otázky (case study: jenprace.cz):

| Otázka | jenprace.cz odpověď |
|---|---|
| Je obsah v surovém HTML? | ANO — `article.item` karty, 100 karet/stránku |
| Paginace? | `?page=N` (page 1 bez parametru) |
| Detail stránka server-rendered? | ANO — `div.offer-content` (popis) + `div.row.items-box-cont` (sumární grid) |
| Anti-bot? | Ne, funguje plain requests |
| Jaké pole má karta? | title, url, company, location, salary, date |
| Chybí v kartě něco? | company/location jsou duplikované pro mobile (`.d-none.d-sm-inline`) s `.separator` `\|` — nutné čištění |
| Extras? | `data-cy` atributy = stabilní selektory (devs je používají pro testy) |

**Výstup fáze 0:** rozhodnutí implementovat / neimplementovat + dokumentovaná
struktura selektorů (ulož si stažené HTML jako referenci, např. do tempu).

---

## 5. FÁZE 1: Implementace providera

Soubor: `src/mcp_jobs/providers/<portal>.py`

### 5.1 Kontrakt třídy (`BaseScraper`)

```python
class XxxScraper(BaseScraper):
    @property
    def name(self) -> str: ...                  # jméno = klíč v REGISTRY + configu

    def parse_listings(self, html_text: str, query: str = "") -> list[Ad]:
        """HTML stránky → list Ad (jedna stránka)."""

    def scrape_all(self, url, max_pages=5, params=None) -> list[Ad]:
        """Paginovaný scrape celé kategorie → list Ad (všechny stránky)."""

    def fetch_detail(self, ad: Ad) -> str | None:
        """Popis + doplnění chybějících polí z detailu (volitelné, lazy)."""
```

Co dostáváš zdarma z `BaseScraper`:
- `self._fetch_page(url)` — allowlist check + throttle + stats (requests_ok/failed, response times)
- `self.stats` — `ScraperRunStats` → `to_dict()` (field_failures, errors)
- `self._fetch_detail_text(url, selectors)` — GET + první matchnutý selektor

### 5.2 Vzor implementace (jenprace.py, reálný kód)

```python
cards = soup.select("article.item")
for card in cards:
    title_el = card.select_one("span.offer-link")          # titulek
    link = card.select_one('a.container-link[data-cy="offer-link-label"]')
    url = link.get("href", "")
    if url and not url.startswith("http"):                 # absolutizace relativní URL
        url = f"{self.BASE_URL}{url}"

    company_el = card.select_one("span.company .d-none.d-sm-inline")
    if company_el:
        sep = company_el.select_one(".separator")          # mobilní duplikace '|'
        if sep:
            sep.decompose()                                # odstranit, jinak 'Firma |'
        company = company_el.get_text(strip=True)
```

**Pravidla pro selectory:**
1. Preferuj **stabilní atributy** (`data-cy`, `data-testid`) před řetězenými CSS třídami s hashy (jako `JobCard-module-scss__ki5xOq__` — ty se mění s buildem).
2. Ošetři **duplikace/separátory** v textu (decompose).
3. **Absolutizuj URL** (relativní → BASE_URL + path).
4. Chybějící pole → `None`, nikdy prázdný string do DB.
5. `parse_listings` musí logovat chyby dle M4 (0 karet / karty ale 0 parsed).

### 5.3 Detail fetch — vzor "doplnění chybějících polí"

jenprace: company/location se v listingu objeví jen někdy (mobilní/desktop
duplikace). Detail stránka má sumární grid s `data-cy`:

```python
if not ad.company:                                        # jen pokud chybí!
    el = soup.select_one('[data-cy="company-value"] a')
    if el:
        ad.company = el.get_text(strip=True) or None
if not ad.location:
    el = soup.select_one('[data-cy="locality-detail-value"] a[href^="/nabidky/"]')
    if el:
        ad.location = el.get_text(strip=True) or None

for sel in self._DETAIL_BODY_SELECTORS:                   # popis
    el = soup.select_one(sel)
    if el:
        body = el.get_text(strip=True)
        if body:
            return body
return None
```

Doplněná pole se propsají do DB (upsert_ads: company, location sloupce) — stejný
vzor jako bazos. **Pozor:** extra pole (relation, education, driving_license,
contact) z jenprace gridu **nemají DB sloupec** — mapují se jen existující pole.
Rozšíření schema = samostatný task (ALTER TABLE + upsert), ne součást přidání
portálu.

---

## 6. FÁZE 2: Registrace (4 registrační body)

| # | Soubor | Změna |
|---|---|---|
| 1 | `providers/<portal>.py` | Třída `XxxScraper` |
| 2 | `providers/__init__.py` | import + `REGISTRY["jenprace"] = JenpraceScraper` + `__all__` |
| 3 | `config.py` | `PipelineSettings.url_allowlist` default + `"jenprace.cz"` (SEC-001!) |
| 4 | `server.py` | `PORTAL_ALIASES["jenprace"]`, `_default_category()`, `_portal_description()` |

Bez bodu 2 portál pipeline nespustí (warning "not in REGISTRY — skipping").
Bez bodu 3 padne SEC-001 validace. Bez bodu 4 MCP tooly (list_portals,
search_jobs_v2) portál nevidí.

> **Restart MCP serveru je povinný.** Provider registrace se importuje při startu
> procesu. Editable install sám o sobě nestačí — server musí být restartován,
> pak `list_portals` ukáže nový portál.

---

## 7. FÁZE 3: Konfigurace (config YAML)

### 7.1 Sekce portálu (přidat do `config.yaml` i `config_legacy_manual.yaml`)

```yaml
portals:
  jenprace:
    enabled: true
    categories:
      - url: "https://www.jenprace.cz/nabidky/praha/"
        pages: 10
      - url: "https://www.jenprace.cz/brigady/praha/"
        pages: 5
```

### 7.2 Zařazení do query (`portals:` pole)

Query vidí jen portály v `portals:` — portál bez zařazení se skrapuje, ale
nic se nespáruje. Rozhodnutí, do kterých query portál patří, dělá uživatel dle
typu inzerce (jenprace = manuální/brigádní trh → legacy profil, nikoliv AI-native).

---

## 8. FÁZE 4: Testy

| Soubor | Co přidat |
|---|---|
| `tests/test_providers.py` | fixture `XXX_HTML` (reálná struktura!), testy: parse_listings (všechna pole), relativní URL, chybějící pole (salary=None), prázdný HTML, broken selector → ERROR log (M4), fetch_detail doplnění polí (mock HTTP klient), registry: `len(ACTIVE_PORTALS) == 4` |
| `tests/test_server.py` | `test_active_portals_no_nyx` (count 3→4), `test_portal_aliases` (+"jenprace"), `test_list_portals` (len + default_category) |
| `tests/test_ssrf.py` | allowlist obsahuje novou doménu (pokud se testuje default) |

Fixtures stav **z reálného HTML** (uložené stránky portálu), ne z hlavy —
testy pak chytají skutečnou strukturu.

---

## 9. FÁZE 5: Validace (postupně, v tomto pořadí)

```powershell
$env:PYTHONIOENCODING='utf-8'

# 1. Statická kontrola
.venv\Scripts\ruff check .

# 2. Testy
python -X utf8 -m pytest tests/ -q            # baseline 148 → 155 testů

# 3. Live smoke test providera (1 stránka + 1 detail na reálné URL)
python -X utf8 -c "from mcp_jobs.providers.jenprace import JenpraceScraper; ..."

# 4. Dry run pipeline (bez zápisu do souborů/DB) — filtr config.portals na 1 portál
#    + výpis pool_sizes, stats, matched ads + description přítomnost

# 5. Test via MCP (PO restartu serveru!)
#    list_portals → search_jobs_v2(query, portal="vše") → search_status(job_id)

# 6. Plný ETL run obou configů + kontrola DB (runs, matched counts)
```

**Akceptační kritéria:**
- 0 chyb ruff, 100% testy PASS
- Live smoke: kompletní pole (title/company/location/salary/date), detail vrací popis
- Dry run: `requests_failed == 0`, `field_failures == {}`, dedup aktivní
- MCP: `list_portals` zobrazuje portál, `search_jobs_v2` vrací ads + per-portal stats
- chování konzistentní s historickými portály (stejné fáze pipeline, stejné Ad → to_dict)

---

## 10. Case study souhrn: jenprace.cz (výsledky 2026-08-19)

| Metrika | Hodnota |
|---|---|
| Pool (po dedupu, 15 stránek) | 1156 ads |
| Requests | 13 OK / 0 failed |
| avg response | 838ms (pomalejší než jobs/pracecz ~300-500ms — 100 karet/stránku) |
| Matched (dry run, cnc_cam_automation) | 7 ads, **7/7 s description** (lazy detail) |
| MCP test (vše, pages=1) | 4 portály scrape, 3 matched (2× jenprace, 1× jobs), 0 chyb |
| Dedup | 16 fuzzy/URL dropů v dry runu |

---

## 11. Checklist (tahák pro další portál)

```
[ ] F0  Feasibility: raw HTML obsahuje karty? paginace? detail? anti-bot? encoding?
[ ] F1  providers/<portal>.py — parse_listings, scrape_all, fetch_detail
[ ] F2  providers/__init__.py — REGISTRY + __all__
[ ] F2  config.py — url_allowlist default
[ ] F2  server.py — PORTAL_ALIASES + _default_category + _portal_description
[ ] F3  config.yaml + config_legacy_manual.yaml — sekce + portals v query
[ ] F4  tests: fixtures z reálného HTML, registry counts, fetch_detail mock
[ ] F5  ruff + pytest
[ ] F5  live smoke (scrape_all + fetch_detail na reálné URL)
[ ] F5  dry run pipeline (stats: 0 failed, dedup, description přítomen)
[ ] F5  RESTART MCP serveru + test via MCP (list_portals / search_jobs_v2)
[ ] F5  plný ETL run + konsolidace + commit (jen na vyžádání)
[ ] GO/NO-GO: 100% testy, 0 field_failures, konzistence s historickými portály
```

---

## 12. Reference (klíčové soubory)

| Soubor | Co v něm hledat |
|---|---|
| `src/mcp_jobs/providers/base.py` | `BaseScraper`, `_fetch_page`, `_fetch_detail_text`, `is_url_allowed` (SEC-001) |
| `src/mcp_jobs/providers/jenprace.py` | Referenční implementace (case study) |
| `src/mcp_jobs/pipeline.py` | Fáze 1-2-3, dedup, `_FAILED` sentinel, per-portal threading |
| `src/mcp_jobs/http.py` | `HttpClient` — retry politika, throttle, encoding |
| `src/mcp_jobs/matcher.py` | Boolean engine, diakritika, word-boundary |
| `src/mcp_jobs/models.py` | `Ad` + `to_dict()` (strip_emoji, missing_fields) |
| `src/mcp_jobs/config.py` | `UserConfig`, `PipelineSettings.url_allowlist` |
| `src/mcp_jobs/server.py` | MCP tooly, async job runner, aliases, L2 resources |
| `config.yaml` / `config_legacy_manual.yaml` | Profily, portály, query |
| `tests/test_providers.py` / `tests/test_server.py` | Testy providerů a registrace |

---

*Tento dokument vznikl na základě reálné integrace jenprace.cz (2026-08-19) —
od feasibility po validaci via MCP. Datové hodnoty v sekci 10 jsou ověřeny
z deterministických výstupů (dry run, MCP search_status).*