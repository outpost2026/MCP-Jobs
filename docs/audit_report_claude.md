# MCP-Jobs — Senior Data Engineer / Staff Architect Audit

**Cross-LLM audit: architektura, filtrovací logika, modularita a produkční připravenost**

| | |
|---|---|
| **Fáze** | 03-category-bulk |
| **Verze** | 0.3.0 |
| **Datum** | 14. 7. 2026 |
| **Doména** | MCP (Model Context Protocol) server pro trh práce ČR |
| **Auditor** | Claude (Anthropic) — na vyžádání autora |

---

## 1. Executive Summary

Celkově je MCP-Jobs solidní projekt fáze 03: boolean matcher je nejlépe otestovaný modul (23 testů), pipeline je čitelná a modulární, a providery jsou přehledně oddělené přes REGISTRY pattern. Architektura je připravená na růst — ale ne bez úprav. Klíčová zjištění:

- **Kritický nález v salary filtru:** `_salary_filter()` u částek s mezerou jako tisícovým oddělovačem ("30 000 - 50 000 Kč") párá čísla na [30, 0, 50, 0] a tiše zahazuje validní inzeráty, které by měly projít filtrem `min_salary`. Ověřeno empiricky — jde o opačný bug, než audit brief předpokládal (false-reject, ne false-accept).

- **Boolean parser je permisivní tam, kde by měl selhat:** nevyvážené závorky a chybějící operátory se tiše přijmou místo vyhození chyby, takže uživatel s překlepem v YAML configu nedostane žádnou zpětnou vazbu.

- **Silent failure je systémový vzorec napříč projektem:** scrapery polykají všechny výjimky (`except Exception: continue`) bez logování, pipeline error handling zahazuje traceback, a `strip_emoji()` existuje a je otestovaný, ale nikdy se nevolá. Tento vzorec je potřeba řešit systematicky, ne bod po bodu.

- **MCP-compliance je zatím na úrovni "tool-calling wrapper", ne "agentic pipeline infrastructure":** server nevyužívá Resources, Prompts ani streaming/sampling — což je v pořádku pro fázi 03, ale je to jasný další krok pro autorovu deklarovanou ambici stát se MCP expertem.

- **Prioritní akce:** (1) opravit salary parsing, (2) zpřísnit boolean parser na explicitní chybu u malformed inputu, (3) zavést konzistentní logování na místo tichého polykání výjimek ve scraperech.

---

## 2. Findings Table

Řazeno dle závažnosti (Critical → Major → Minor → Info). Detailní kód-diffy pro top nálezy jsou v sekci 4.

### Critical

| Oblast | Popis | Umístění |
|--------|-------|----------|
| **4.3 Filter chain** | Salary filter mis-parses thousand-separator formatted salaries. `'30 000 - 50 000 Kč'.split()` yields `['30','000','-','50','000','Kč']` → `int()` on each token produces `[30, 0, 50, 0]`. A `min_salary` of 40000 then rejects this ad even though its real range (30 000–50 000 Kč) satisfies the filter. Verified empirically. This is the opposite failure mode from what the audit brief hypothesized (false-accept from `int('000')=0`) — it is actually a false-reject, silently dropping qualifying ads. | `pipeline.py`, `_salary_filter()` |

### Major

| Oblast | Popis | Umístění |
|--------|-------|----------|
| **4.1 Boolean engine** | Parser silently accepts unbalanced/malformed expressions instead of rejecting them. A trailing stray `)` (e.g. `'python)'`) is left unconsumed by `parse()` and never triggers an error — `evaluate_boolean()` returns a result as if the query were valid. | `matcher.py`, `_Parser.parse()` / `_parse_expr()` |
| **4.1 Boolean engine** | No explicit AND is required between two words — `'python java'` silently parses as an implicit AND (WORD triggers the `_parse_term` loop). Two consecutive AND/OR operators (`'python AND AND java'`) also parse without error, silently dropping the second operator. Users get no feedback that their query syntax is malformed. | `matcher.py`, `_parse_term()` |
| **4.3 Filter chain** | `has_exclude_terms()` uses word-boundary matching on title but plain substring matching on description. This is asymmetric: a description containing 'nábor' as part of a longer compound word (e.g. Czech agglutination) will false-positive-exclude, while the same fragment in the title would not. | `matcher.py`, `has_exclude_terms()` |
| **4.2 Scrapers** | `parse_listings()` in every provider wraps the per-card loop in a bare `except Exception: continue`, silently swallowing all parsing errors including programming bugs (AttributeError, TypeError). No logging of what failed or how many cards were skipped. | `providers/jobs.py`, `pracecz.py`, `bazos.py` |
| **4.2 Scrapers** | CSS selectors are tightly coupled to current site markup, including auto-generated utility class names (Tailwind-style) on prace.cz. No selector-health check or alerting when a scrape returns 0 ads. | `providers/jobs.py`, `pracecz.py` |
| **4.5 Production** | `_run_pipeline()` catches the entire pipeline run in one broad `except Exception` and returns a single opaque error string, discarding the original traceback. Combined with near-absent logging, production failure is hard to diagnose. | `server.py`, `_run_pipeline()` |
| **4.5 Production** | No per-page timeout distinct from the client-level HttpClient timeout (30s default) + retries (3x with backoff). A single slow page can block the whole pipeline for well over a minute. | `http.py`, `HttpClient.__init__()` |

### Minor

| Oblast | Popis | Umístění |
|--------|-------|----------|
| **4.1 Boolean engine** | AND-before-OR precedence is implemented correctly but undocumented outside test suite. | `matcher.py` |
| **4.3 Filter chain** | `_location_filter()` uses unscoped substring match allowing false positives. | `pipeline.py` |
| **4.2 Scrapers** | Early-stop pagination heuristic does not distinguish repeated content from genuine end-of-list. | `providers/*.py` |
| **4.4 Modularity** | `server.py` recomputes `ACTIVE_PORTALS` instead of importing from `providers/__init__.py`. | `server.py` L.11 |
| **4.4 Modularity** | `CategoryConfig(**c)` / `QueryConfig(**qdata)` raises raw TypeError on unexpected YAML keys. | `config.py` |
| **4.5 Production** | No readiness/liveness endpoints for containerized deployment. | `server.py` |
| **4.7 Data quality** | `strip_emoji()` is fully implemented and tested but never called in the pipeline. | `utils.py` |
| **4.8 Configuration** | `min_salary` is misleading for bazos queries (price, not salary) and invites misuse. | `pipeline.py`, `config.yaml` |

### Info

| Oblast | Popis | Umístění |
|--------|-------|----------|
| **4.1 Boolean engine** | Deep nesting (100+ levels) relies on Python recursion limit; `RecursionError` not caught. | `matcher.py` |
| **4.3 Filter chain** | Boolean match evaluated before exclude (minor perf win possible by reordering). | `pipeline.py` |
| **4.5 Production** | Thread-safe today (stateless per-call), but invariant is undocumented. | `server.py`, `pipeline.py` |
| **4.7 Data quality** | URL-only dedup won't catch near-identical ads across different URLs. | `pipeline.py` |
| **4.8 Configuration** | Empty `boolean: ''` silently skipped without warning to user. | `pipeline.py`, `config.py` |

---

## 3. Code Quality Score

Škála 1–5 (5 = nejlepší). MCP-compliance se hodnotí jen pro `server.py`.

| Modul | Čitelnost | Testovatelnost | Robustnost | MCP-compliance |
|-------|-----------|----------------|------------|----------------|
| `server.py` | 4 | 3 | 3 | 3 |
| `config.py` | 4 | 4 | 3 | — |
| `pipeline.py` | 4 | 4 | 3 | — |
| `matcher.py` | 4 | **5** | 3 | — |
| `providers/*` | 3 | 3 | **2** | — |
| `http.py` | 4 | 2 | 4 | — |
| `storage.py` | 4 | 2 | 3 | — |

**Poznámky ke skóre:**

- **server.py:** Clear tool definitions, but broad `except Exception` swallowing and duplicated `ACTIVE_PORTALS` logic.
- **config.py:** Good error messages for top-level type errors; raw `dataclass(**dict)` construction is a soft spot.
- **pipeline.py:** Clean filter chain, but the salary-parsing bug is a real correctness issue and logging is thin.
- **matcher.py:** Best-tested module (23 tests) but the parser accepts malformed input rather than rejecting it.
- **providers/***: Selector-heavy and site-coupled by nature; silent per-card exception swallowing hides real breakage.
- **http.py:** Solid retry/backoff config; no dedicated unit tests found; no per-request timeout override.
- **storage.py:** Straightforward CSV/markdown generation; per-portal field maps won't scale past a handful of portals.

---

## 4. Top 3 Fixes — Code Diffs

### 4.1 Salary filter — oprava parsování tisícových oddělovačů (Critical)

**Soubor:** `pipeline.py`, `_salary_filter()`

**Před:**
```python
def _salary_filter(ad: Ad, min_salary: int) -> bool:
    if min_salary <= 0 or not ad.salary:
        return True
    numbers = [int(s) for s in ad.salary.split()
               if s.replace(".", "", 1).lstrip("-").isdigit()]
    return any(n >= min_salary for n in numbers)
```

**Po:**
```python
import re

_SALARY_NUM_RE = re.compile(r"\d{1,3}(?:[ \u00a0]\d{3})+|\d+")

def _salary_filter(ad: Ad, min_salary: int) -> bool:
    if min_salary <= 0 or not ad.salary:
        return True
    # Match full numbers including space/nbsp thousand separators
    # before splitting, so "30 000" is read as 30000, not [30, 0].
    raw_numbers = _SALARY_NUM_RE.findall(ad.salary)
    numbers = [int(n.replace(" ", "").replace("\u00a0", ""))
               for n in raw_numbers]
    if not numbers:
        return True  # unparseable salary (e.g. "Dohodou") still passes
    return any(n >= min_salary for n in numbers)
```

**Test doplnit do `test_pipeline.py`:**
```python
def test_salary_filter_thousand_separator():
    ad = Ad(title="Test", url="http://x", portal="jobs",
            salary="30 000 - 50 000 Kč")
    assert _salary_filter(ad, 40000) is True   # upper bound qualifies
    assert _salary_filter(ad, 60000) is False
```

---

### 4.2 Boolean parser — explicitní chyba na malformed input (Major)

**Soubor:** `matcher.py`, `_Parser` a `parse_boolean()`

**Před:**
```python
def parse(self) -> _Node:
    return self._parse_expr()

def _parse_term(self) -> _Node:
    left = self._parse_factor()
    while self.peek()[0] in ("AND", "NOT", "WORD", "LPAREN"):
        if self.peek()[0] == "AND":
            self.consume()
            right = self._parse_factor()
            left = _And(left, right)
        else:
            right = self._parse_factor()   # implicit AND, no error
            left = _And(left, right)
    return left
```

**Po:**
```python
def parse(self) -> _Node:
    node = self._parse_expr()
    if self.peek()[0] != "EOF":
        raise ValueError(
            f"Unexpected trailing token: {self.peek()}")
    return node

def _parse_term(self) -> _Node:
    left = self._parse_factor()
    while self.peek()[0] == "AND":
        self.consume()
        right = self._parse_factor()
        left = _And(left, right)
    # NOT/WORD/LPAREN directly after a factor is now a syntax error
    # instead of an implicit AND — require an explicit operator.
    return left
```

> Toto je záměrně přísnější chování — pokud chcete implicitní AND zachovat jako feature (např. Google-style vyhledávání), zdokumentujte to v `config.yaml.example` místo tichého parsování a v README uveďte příklad.

---

### 4.3 Scrapery — logování místo tichého polykání výjimek (Major)

**Soubor:** `providers/jobs.py`, `pracecz.py`, `bazos.py` — `parse_listings()`

**Před:**
```python
for card in soup.select("article.SearchResultCard"):
    try:
        ...
        ads.append(ad)
    except Exception:
        continue
```

**Po:**
```python
import logging
logger = logging.getLogger(__name__)

cards = soup.select("article.SearchResultCard")
skipped = 0
for card in cards:
    try:
        ...
        ads.append(ad)
    except Exception as e:
        skipped += 1
        logger.warning(f"{self.name}: failed to parse card: {e}")

if cards and not ads:
    logger.error(
        f"{self.name}: found {len(cards)} cards but parsed 0 ads "
        "— selector likely broken after a site redesign.")
elif skipped:
    logger.info(f"{self.name}: skipped {skipped}/{len(cards)} cards")

return ads
```

---

## 5. Top 3 Recommendations — Časová osa

### Ihned (tento týden)

- **Oprava salary parsing bugu** (4.1) — aktivně zahazuje validní poptávky, přímo poškozuje business hodnotu nástroje.
- **Přidat `logger.exception()`** do `_run_pipeline()` error handleru v `server.py`, aby produkční chyby nezmizely beze stopy.
- **Zavolat `strip_emoji()`** na title/description v `Ad.to_dict()` nebo v každém provideru — je hotovo a otestováno, jen se nepoužívá.

### Příštích 30 dní

- **Zpřísnit boolean parser** (4.2) tak, aby malformed query vracel chybu, ne tichý (a případně nesprávný) výsledek.
- **Sjednotit exclude-term matching** na word-boundary v title i description, případně zdokumentovat substring chování jako explicitní kompromis.
- **Přidat selector-health check** do každého provideru (0 karet při 200 OK odpovědi = pravděpodobně rozbitý selector).
- **Rozšířit `test_pipeline.py`** o testy s reálnými formáty platů (mezery, rozsahy, 'Kč', 'Dohodou').

### Příští kvartál

- **Zvážit MCP Resources** pro scraped ad pool (`mcp-jobs://ads/{query_id}`), aby klient mohl stránkovat výsledky bez opakovaného scrapování.
- **Přidat `@mcp.prompt()`** šablonu pro sestavení boolean query z přirozeného jazyka — přímo využívá autorovu doménovou znalost a je to nízko-riziková cesta k MCP expertize.
- **Universal Ad schema / storage refaktor**, pokud se REGISTRY rozroste nad ~6-8 portálů.

---

## 6. MCP Evolution Guidance

Autor chce v MCP ekosystému vybudovat ranou expertízu (cíl Q3+ 2026). MCP-Jobs je v tuto chvíli čistě tool-calling server: 5 nástrojů, žádné Resources, žádné Prompts, žádný sampling. To je zcela v pořádku pro fázi 03 — ale je to zároveň přesná mapa toho, co se autor má naučit dál.

### MCP maturity ladder pro server tohoto typu

| Úroveň | Popis | Stav |
|--------|-------|------|
| **L0 — Skript** | Jednorázový scraper bez MCP obalu. | Překonáno |
| **L1 — Tool wrapper** | Stateless nástroje (`@mcp.tool`), žádný stav mezi voláními. | **Aktuální stav MCP-Jobs** |
| **L2 — Resources** | Stavová data (ad pool, poslední běh) exponovaná přes URI (`mcp-jobs://...`). | Další krok |
| **L3 — Prompts** | `@mcp.prompt()` šablony pro časté úlohy (formulace boolean query). | Další krok |
| **L4 — Streaming/Sampling** | Progress reporting pro dlouho běžící pipeline, partial results. | Střednědobě |
| **L5 — Multi-transport** | SSE/HTTP vedle stdio pro multi-client nasazení. | Dlouhodobě, dle potřeby |
| **L6 — Orchestrace více MCP serverů** | MCP-Jobs jako jeden z více composable ETL serverů v agentní pipeline. | Vize |

### Konkrétní specifikace a koncepty ke studiu

- **MCP Resources (URI templates):** nejpřirozenější další krok — expozice scraped ad pool jako `mcp-jobs://ads/{query_id}` umožní LLM agentovi číst výsledky opakovaně bez re-scrapování a otevírá cestu k cachování.

- **`@mcp.prompt()`:** šablona typu `search_expert`, která pomůže uživateli formulovat boolean query z přirozeného popisu ("hledám CNC práci v Praze nad 35k") — přímo demonstruje MCP prompt-engineering pattern a je nízkonákladová.

- **Transporty: stdio vs. SSE/HTTP:** stdio je správná volba pro single-client desktop use (Claude Desktop, Claude Code). SSE/HTTP streaming dává smysl až při multi-client nasazení (např. sdílený tým, webová aplikace).

- **Capability negotiation & spec verze:** ověřit, kterou verzi MCP specifikace aktuální FastMCP implementuje, a sledovat changelog — protokol se v roce 2026 stále rychle vyvíjí (community-driven po Anthropic-led fázi).

- **Long-running operace / sampling:** pipeline běh 30s+ je hraniční pro synchronní tool-call UX. Stojí za prostudování, jak MCP řeší progress reporting / streaming částečných výsledků pro dlouho běžící nástroje.

---

## 7. Scope Creep Analysis — Univerzální marketplace scraper?

**Otázka:** Je současná architektura vhodná pro zobecnění na univerzální marketplace scraper (nejen práce, ale např. i Bazoš zboží, nemovitosti, Sbazar), nebo je lepší oddělený MCP server?

### Argumenty pro rozšíření v rámci MCP-Jobs

- **BaseScraper ABC a REGISTRY pattern** jsou doménově agnostické — `scrape_all`/`parse_listings` rozhraní by fungovalo i pro jiné typy inzerátů.
- **Boolean matcher** (`matcher.py`) je zcela nezávislý na doméně 'práce' — funguje na libovolném textu (title+description+company).
- **Sdílená HTTP infrastruktura** (retry, headers, encoding handling) by se zbytečně duplikovala v novém projektu.

### Argumenty proti — oddělený server je lepší volba

- **Ad schéma je už teď mírně napjaté:** salary vs. price rozlišení (viz nález 4.8) ukazuje, že 'universal Ad dataclass' pro dvě domény (práce vs. inzerce/zboží) už teď vyžaduje kompromisy. Přidání nemovitostí nebo zboží přinese další doménově specifická pole (m², stav, kategorie zboží) a `Ad` se rozroste do nesourodého grab-bagu.
- **Storage.PORTAL_FIELDS mapping** už teď nese technický dluh: ruční CSV field-mapy per-portál se s každou novou doménou znásobí kombinatoricky (portál × doména).
- **MCP tool sémantika:** `search_jobs_v2` jako název nástroje je doménově explicitní — pokud by stejný server najednou vracel i nábytek z Bazoše, název i description nástrojů by matly LLM agenta.

### Doporučení

**Zachovat MCP-Jobs jako doménově zaměřený server na trh práce.** Pokud vznikne potřeba univerzálního marketplace scraperu, extrahovat sdílené vrstvy (`HttpClient`, `BaseScraper ABC`, `boolean matcher engine`) do samostatného interního balíčku (např. `mcp_scrape_core`), který si MCP-Jobs i budoucí MCP-Marketplace importují jako závislost — místo aby jeden monolitický server nesl obě domény. Toto řeší DRY bez obětování sémantické čistoty jednotlivých MCP serverů.
