# Sémantická analýza audit reportu + aktualizovaný iterační plán

---

## 1. Sémantická analýza — komentář k jednotlivým vrstvám zjištění

### 1.1 Patternová analýza: co report říká o projektu jako celku

Audit není jen seznam bugů — je to **diagnostika vývojové zralosti**. Zřetelně vystupují tři vrstvy:

**Vrstva A — KOREKTNOST (Critical + Major nálezy 1–7)**
Projekt dělá věci, které dělá špatně. Salary filtr vrací opačný výsledek, než má. Boolean parser akceptuje syntaktický garbage. Exclude matching je asymetrické. Toto jsou **přímé chyby v logice** — ne styl, ne architektura, ale prostě bugy. Jsou opravitelné a měly by být opraveny jako první.

**Vrstva B — ROBUSTNOST (Major nálezy 4, 6, 7)**
Projekt se při chybě chová špatně. Scrapery polykají výjimky — `except Exception: continue` je programátorský antipattern první kategorie, který **aktivně skrývá důkazy o tom, že se něco rozbilo**. Pipeline error handling dělá totéž na vyšší úrovni. Chybí per-request timeout. Toto není o logice — je to o **selhání detekce selhání**.

**Vrstva C — ZRALOST (Minor + Info + MCP guidance)**
Projekt má věci, které *zatím* nejsou problém, ale *stanou se* problémem při škálování. Duplicitní ACTIVE_PORTALS, raw TypeError z dataclass(**dict), chybějící health endpoint. A nad tím vším: MCP server, který nevyužívá MCP jako protokol — jen jako RPC wrapper.

**Klíčová sémantická linie:** report opakovaně ukazuje, že projekt je *funkcionálně úplný* (scrape, filtruj, output) ale *operačně nezralý* (když selže, selže tiše; když dostane špatný vstup, mlčí; když se změní web, nevíš to).

### 1.2 Kritická distance — kde Claude (auditor)可能 má pravdu a kde可能 ne

**Kde má pravdu:**
- Salary parsing bug je empiricky ověřitelný, reproducer existuje. Toto není názor — je to fakt.
- `except Exception: continue` bez logování je objektivně špatně.
- Boolean parser bez validace je měkké břicho pro konfigurační chyby.

**Kde je třeba názor relativizovat:**
- **Implicitní AND:** Claude navrhuje zakázat. To je *design decision*, ne bug. Google vyhledávání, Amazon, všechny fulltexty používají implicitní AND. Je to otázka: chceme být "striktní SQL" nebo "uživatelsky přívětivý vyhledávač"? Report to správně označuje jako otevřenou otázku (poznámka pod čarou u diffu 4.2).
- **MCP maturity ladder:** Claude hodnotí L1 jako aktuální stav. To je správné, ale 5 nástrojů + YAML konfigurace + pipeline orchestrace je víc než "tool wrapper" — je to *domain-specific ETL server* s MCP rozhraním. L2/L3 jsou cíle, ne dluh.
- **Skóre robustnosti 2 pro providery:** Je to férové skóre, ale je potřeba říct, že scrapeování cizích webů je ze své podstaty křehké — žádné selectorové inženýrství to nezmění. Bod zlepšení je v detekci breakage, ne v eliminaci.

**Co report neříká (slepá místa):**
- **Testování:** Report chválí matcher.py za 23 testů, ale neptá se, jestli těch 23 testů pokrývá hraniční případy (malformed, empty, unicode, whitespace). Počet testů ≠ kvalita testů.
- **Produkční monitoring:** Report navrhuje logger.exception() — to je nutná, nikoli postačující podmínka. V produkci potřebuješ strukturované logování (JSON), metriky (počet scraped ad, error rate, latency), ideálně APM. Log do konzole nestačí.
- **Bezpečnost:** Report vůbec neřeší, co se stane, když uživatel pošle boolean query s injekcí (rekurzivní struktura, billion laughs, encoding attack). FastMCP to možná řeší, ale mělo by to být zmíněno.
- **Náklady na scraping:** Každý HTTP request na jobs.cz/prace.cz/bazos.cz je legálně šedá zóna. Report nezmíňuje rate limiting, politiku robot.txt, ani etiku scrapování.

### 1.3 Syntéza: co si z reportu odnést

| Co audit říká | Moje interpretace |
|---|---|
| Salary filtr je Critical bug | Okamžitá oprava — zahazuje reálné výsledky |
| Silent failure je systémový vzorec | Nejnebezpečnější zjištění — podkopává důvěryhodnost celého nástroje |
| Boolean parser je moc permisivní | Design choice, ne bug — ale musí být zdokumentováno |
| MCP-expertiza je na L1 | Přirozený stav pro fázi 03, strategický cíl pro fázi 04/05 |
| Scope creep → separátní server | Souhlas — doménová čistota je cennější než DRY za každou cenu |

---

## 2. Aktualizovaný iterační plán (no code, no refactor — pouze plán)

### 2.1 Fáze 03b — Stabilizace (1–2 týdny)

Cíl: projekt je korektní a při selhání detekuje selhání.

**Iterace 03b‑1: Core bugs**

| ID | Úkol | Zdroj | Očekávaný dopad |
|---|---|---|---|
| S1 | Opravit `_salary_filter()` na tisícové oddělovače | Critical #4.3 | Přestanou mizet validní inzeráty |
| S2 | Přidat testy reálných formátů platů | Major implikace | Důkaz, že S1 funguje + regression |
| S3 | Zavolat `strip_emoji()` v pipeline | Minor #4.7 | Hotová funkce začne být použitá |
| S4 | `parse()` kontroluje EOF token | Major #4.1 | Malformed query → chyba, ne tichý výsledek |

**Iterace 03b‑2: Error handling**

| ID | Úkol | Zdroj | Očekávaný dopad |
|---|---|---|---|
| S5 | `logger.exception()` v `_run_pipeline()` error handleru | Major #4.5 | Traceback přestane mizet |
| S6 | Logování + skip count v každém scraperu | Major #4.2 | Site redesign → detekovatelný, ne tichý |
| S7 | Sanity check: 0 ads + 200 OK → warning | Major #4.2 | Rozbitý selector = hlasitá chyba |
| S8 | Sjednotit exclude matching (word-boundary všude nebo dokumentovaný kompromis) | Major #4.3 | Predikovatelné chování |

**Iterace 03b‑3: Konfigurace a dotazování**

| ID | Úkol | Zdroj | Očekávaný dopad |
|---|---|---|---|
| S9 | Wrap `CategoryConfig(**c)` v try/except TypeError | Minor #4.4 | Config chyba = čitelná hláška, ne Python traceback |
| S10 | Dokumentovat AND-before-OR precedenci | Minor #4.1 | Uživatel ví, jak psát dotazy |
| S11 | Warning na prázdný `boolean:` v configu | Info #4.8 | Config chyba neprojde tiše |
| S12 | Rozhodnout: implicitní AND = feature nebo zakázat? Dokumentovat. | Major #4.1, otevřená otázka | Explicitní design decision |

### 2.2 Fáze 04 — MCP Resources + Prompt template (3–4 týdny)

Cíl: posunout server z L1 (tool wrapper) na L2/L3 (Resources + Prompts), získat reálnou MCP expertizu.

**Iterace 04‑1: Resources (ad pool)**

| ID | Úkol |
|---|---|
| R1 | Implementovat `mcp-jobs://ads/{query_id}` URI template |
| R2 | Uložit výsledky pipeline do per-call cache (v paměti, TTL) |
| R3 | Resource reader vrací ad pool jako JSON (stránkovaně) |
| R4 | Upravit `search_jobs_v2` tool: po dokončení vrátí `query_id` (URI), ne celý dataset |
| R5 | Testy: resource read, cache eviction, concurrent access |

**Iterace 04‑2: Prompt šablona**

| ID | Úkol |
|---|---|
| P1 | Navrhnout `@mcp.prompt("search_expert")` — z přirozeného jazyka sestaví boolean query |
| P2 | Prompt template obsahuje: seznam portálů, syntaxi boolean dotazů, příklady |
| P3 | Otestovat s Claude Desktop: "najdi mi CNC práci v Praze nad 40k" → vygeneruje YAML/volání |
| P4 | Iterovat prompt dle reálného chování LLM agenta |

### 2.3 Fáze 05 — Produkční provoz (2–3 týdny)

Cíl: server je deployovatelný, monitorovatelný, supportovatelný.

| ID | Úkol |
|---|---|
| D1 | Strukturované JSON logování (structlog / python-json-logger) |
| D2 | Per-portál timeout (10s/page) s možností override v configu |
| D3 | /healthz HTTP endpoint (pro orchestrátor) |
| D4 | Dockerfile + docker-compose (stdio i SSE režim) |
| D5 | Dokumentace: README s příklady, config.yaml.example s komentáři, deployment guide |

### 2.4 Fáze 06 — Rozšíření a optimalizace (průběžně, dle priority)

| ID | Úkol |
|---|---|
| E1 | Fuzzy dedup (normalized title + company) — pokud URL dedup nestačí |
| E2 | Per-query filter reorder (exclude před boolean) — pokud profiling ukáže bottleneck |
| E3 | Zvážit SSE transport pro multi-client nasazení |
| E4 | Extrahovat `mcp_scrape_core` balíček — až (a pokud) vznikne druhý MCP server |

### 2.5 Rizika a závislosti

| Riziko | Pravděpodobnost | Dopad | Mitigace |
|---|---|---|---|
| Změna markupu jobs.cz/prace.cz | Vysoká (průběžně) | Vysoký (0 výsledků) | Sanity check S7, monitoring D1 |
| MCP specifikace se změní (2026) | Střední | Střední | Sledovat changelog, FastMCP release notes |
| LinkedIn zablokuje session | Střední | Střední | LinkedIn je sekundární portal (přes analyzer MCP) |
| Rate limiting ze strany portálů | Nízká-střední | Střední | Konfigurovatelný delay mezi requesty (není v plánu, přidat pokud nastane) |

---

## 3. Testovací otázky pro dev — ověření porozumění reportu

Instrukce: dev odpoví **stručně (1–3 věty)** na každou otázku. LLM vyhodnotí, zda odpověď prokazuje porozumění klíčovému sdělení.

### 3.1 Critical porozumění

| # | Otázka | Co testuje |
|---|---|---|
| Q1 | Salary filtr má bug. Jaký je jeho mechanismus a proč je klasifikovaný jako Critical, ne Major? | Pochopení, že bug aktivně zahazuje validní data (false reject), ne že by jen občas selhal. "Proč Critical" testuje schopnost odlišit závažnost dopadu od složitosti opravy. |
| Q2 | Report říká, že bug je "opačný, než audit brief předpokládal". Co to znamená o procesu auditu? | Testuje metaporozumění: audit není lineární kontrola seznamu, ale iterativní objevování. Předpoklad byl false-accept, realita je false-reject. |
| Q3 | Po opravě salary filtru: jaký test napíšeš, aby ses ujistil, že se bug nevrátí? | Testuje schopnost navrhnout regression test z popisu chyby. |

### 3.2 Pattern recognition

| # | Otázka | Co testuje |
|---|---|---|
| Q4 | Report identifikuje "systémový vzorec" napříč projektem. Jaký? Uveď tři různá místa v kódu, kde se projevuje. | Testuje, zda dev viděl pattern, ne jen izolované nálezy. Tři místa = prokazatelné přečtení více sekcí. |
| Q5 | Proč je `except Exception: continue` horší než `except (AttributeError, TypeError): continue`? | Testuje pochopení: první polyká všechno (včetně KeyError, MemoryError), druhý je explicitní. Nejde o syntaxi — jde o záměr. |
| Q6 | Report navrhuje tři prioritní akce. Která z nich má nejvyšší business dopad a proč? | Testuje schopnost prioritizace dle dopadu na uživatele, ne dle severity labelu. |

### 3.3 Náročná rozhodnutí

| # | Otázka | Co testuje |
|---|---|---|
| Q7 | Report navrhuje zakázat implicitní AND v boolean parseru. Je to správně? Uveď argumenty pro i proti. | Testuje, zda dev viděl poznámku o otevřené otázce. Neexistuje správná odpověď — existuje správná úvaha. |
| Q8 | Claude skóruje providery robustností 2/5. Je to fér? Co bys musel změnit, aby byly 4/5? | Testuje kritické myšlení o auditu: je skóre objektivní? Co by zlepšení obnášelo a stojí to za to? |
| Q9 | Report doporučuje extrahovat sdílené vrstvy do `mcp_scrape_core` — ale až když vznikne druhý MCP server. Proč ne hned? | Testuje pochopení YAGNI vs. DRY trade-off. |

### 3.4 MCP a architektura

| # | Otázka | Co testuje |
|---|---|---|
| Q10 | Aktuální server je na L1 MCP maturity. Co konkrétně chybí k L2? Uveď příklad URI a co by klientovi umožnilo. | Testuje, zda dev rozumí MCP Resources konceptu, nejen že "máme udělat Resources". |
| Q11 | Report neřeší bezpečnost. Jaký bezpečnostní problém vidíš u boolean parseru, který akceptuje libovolný string? | Testuje schopnost najít slepé místo v auditu. |
| Q12 | Proč report nepovažuje rozšíření na univerzální marketplace scraper za dobrou cestu? Souhlasíš? | Testuje, zda dev rozumí argumentům o doménové čistotě a sémantice tool naming. |

### 3.5 Syntéza

| # | Otázka | Co testuje |
|---|---|---|
| Q13 | Kdybys měl report shrnout do jedné věty pro CEO (netechnického), co bys řekl? | Testuje schopnost abstrakce — vytáhnout podstatu bez technického detailu. |
| Q14 | Kdybys měl report shrnout do jedné věty pro senior engineer (technického), co bys řekl? | Testuje schopnost cílit sdělení na publikum. |
| Q15 | Který nález z reportu bys **neopravil** a proč? | Testuje nezávislé myšlení: dev musí zdůvodnit conscious decision, ne jen následovat audit. |

### Vyhodnocení

| Počet správných odpovědí | Hodnocení |
|---|---|
| 15/15 | Dev nejen četl, ale kriticky zpracoval |
| 12–14 | Dev četl pozorně, pár nuancí uniklo |
| 8–11 | Dev četl, ale spíš projížděl — doporučit opakované čtení |
| <8 | Dev nečetl nebo neporozuměl — report je třeba presentovat osobně |

---

## 4. Metodologická poznámka (k userově racionále)

User správně identifikuje riziko: **LLM může nahradit kognitivní mezikrok abstrakce a disekce problému**. Tento plán je strukturovaný tak, aby k tomu nedocházelo:

1. **Sémantická analýza (sekce 1)** není přepis reportu — je to *druhé čtení*, které se ptá na patterny, slepá místa, a relativizuje autoritu auditora (Clauda). To je mentální operace, kterou LLM za usera neudělá — ale může ji *modelovat* a user se s ní může konfrontovat.

2. **Plán (sekce 2)** není seznam úkolů — je to *argumentovaná prioritizace* s explicitními trade-offy. Každá iterace má zdůvodnění "proč teď" a očekávaný dopad.

3. **Testovací otázky (sekce 3)** jsou nástroj, ne výstup. Jejich účelem je *vynutit si*, aby dev (nebo user sám) provedl syntézu — nejen přečetl. Otázky Q7, Q8, Q11, Q15 jsou záměrně otevřené a vyžadují stanovisko, ne reprodukci.

**Doporučení:** Před implementací jakéhokoli bodu z plánu si user (nebo dev) písemně odpoví na otázky Q4, Q7, Q13, Q14 — tím se vytvoří *mentální model* problému dřív, než se sáhne na klávesnici. LLM pak slouží jako nástroj realizace, ne jako náhrada myšlení.
