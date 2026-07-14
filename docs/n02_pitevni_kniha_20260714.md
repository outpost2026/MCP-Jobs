# Pitevní kniha — Session 2026-07-14

**MCP-Jobs v0.3.0 → feature/v2 — od auditu po produkční stabilizaci**

---

## 1. Executive Summary sessione

### Co se stalo

Jednodenní session (14. 7. 2026) pokrývající celý cyklus: **audit → sémantická analýza → plán → implementace → ETL → debug → fix → verifikace**. Výstup: 5 commitů na `feature/v2`, 12 změněných souborů, 79 testů zelených.

### Klíčová čísla

| Metrika | Hodnota |
|---|---|
| Délka session | ~3-4 hodiny |
| Commitů | 5 |
| Změněných souborů | 12 |
| Testů před | 76 |
| Testů po | 79 (+3 nové, žádný broken) |
| ETL čas | 19.5–23.2s |
| Matched ads baseline | 28 |
| Matched ads po fixech | 34 (+21%) |
| Odhalených bugů | 5 |
| Z toho opraveno | 4 |

### Co bylo odhaleno

| Nález | Kde | Detection method |
|---|---|---|
| Salary filter false-reject | pipeline.py | Claude audit |
| Silent failure pattern | providers/*, server.py | Claude audit |
| Bazos selectors broken | bazos.py | ETL output analysis |
| Exclude čeština false positive | config.yaml | Debug script + user review |
| YAML parse bug (dříve) | config.py | search_from_yaml test |

---

## 2. Sémantická analýza procesu

### 2.1 Cyklus: audit → akce → realita

**Audit (Claude) předpověděl:**
- Salary bug: falsi accept ("000" → 0 → false pass)
- Boolean parser: nejvyšší priorita
- Silent failure: tři oddělené body

**Realita po ETL:**
- Salary bug: **false reject** — opačný mechanismus, než audit předpověděl. Claude měl špatnou hypotézu, ale správný závěr (je to bug).
- Boolean parser: **nízká priorita** — v praxi se malformed query nevyskytly. Config píše autor, ne externí uživatel.
- Silent failure: **systematický** — nejde o tři body, ale o kulturní pattern. A projevil se i způsobem, který audit nečekal: bazos selectory byly roky rozbité, ale nikdo to nevěděl, protože `except Exception: continue` vše polykalo.

**Klíčová lekce:** Audit měl pravdu v závěrech, ale částečně se mýlil v mechanismech a prioritách. Teprve konfrontace s reálnými daty (ETL běh) ukázala správnou prioritu.

### 2.2 Pattern: tichá degradace

Nejnebezpečnější pattern, který se v session opakovaně projevil:

1. **Bazos selectory se rozbily** (HTML struktura se změnila)
2. **`except Exception: continue` to polklo** — žádná chyba, žádný warning
3. **Pipeline vrátila 0 výsledků** pro bazos
4. **Uživatel/LLM neví, proč** — vypadá to jako "není poptávka"
5. **Časem se na to přestane ptát** — akceptuje 0 jako normální

Tento pattern je nebezpečnější než kterýkoli jednotlivý bug. **Nezabíjí funkcionalitu — zabíjí důvěru v data.**

### 2.3 Meta-lekce: LLM-assisted vývoj

Tři z pěti odhalených bugů nebyly v kódu, který LLM psal — byly v kódu, který LLM **neviděl** (staré selectory, config exclude listy). LLM je výborný v:
- Generování nového kódu (salary fix, logging)
- Analýze existujícího kódu (audit)
- Syntéze znalostí (plán, otázky)

LLM je slabý v:
- Detekci tiché degradace (broken selectory)
- Doménové sémantice (čeština na bazosu)
- Ověření, že starý kód stále funguje (regression detection)

**Závěr:** LLM-assisted vývoj vyžaduje **pravidelný ETL feedback loop**. Bez reálných dat LLM neví, že se selectory rozbily.

---

## 3. Rozhodovací strom — proč jsme dělali, co jsme dělali

### Rozhodnutí 1: Priorita salary fix > boolean parser

| Váha | Argument |
|---|---|
| +3 | Salary bug aktivně zahazuje validní data |
| +2 | Empiricky ověřitelný (Claude test) |
| -1 | Boolean parser je "tichý" — user neví, že query je špatná |
| -1 | V praxi config píše autor, ne externí uživatel |
| → | **Salary fix first** |

### Rozhodnutí 2: Bazos selectory > cnc_jobs debug

| Váha | Argument |
|---|---|
| +3 | Selectory = systematický problém (všechna bazos data postižená) |
| +2 | ETL data jasně ukázala prázdná pole |
| -1 | cnc_jobs bez bazos je "přirozený" stav (žádné CNC inzeráty) |
| → | **Bazos fix first** |

### Rozhodnutí 3: Exclude čeština fix > portal-specific exclude architektura

| Váha | Argument |
|---|---|
| +3 | Okamžitý dopad: zahradnik 0→4 |
| +2 | Nízké riziko: ostatní exclude termy stále fungují |
| -1 | Portal-specific exclude by byl čistší, ale trvá déle |
| → | **Rychlý fix teď, architektura potom** |

---

## 4. Co jsme se naučili

### O projektu

1. **ETL čas je stabilní (~20s)** — dost rychlý pro iterativní vývoj, moc pomalý pro real-time
2. **Bazos yield je nízký** — 462 surových → 11–15 relevantních (2.4–3.2%). Ostatní portály mají vyšší hustotu
3. **Bazos data jsou řídká** — location/price/date často chybí i po fixu (generalistický marketplace)
4. **Čeština je sémantický problém** — stejné slovo = opačný význam podle kontextu (poptávám, sháním, hledám)

### O procesu

1. **Audit → ETL feedback loop je kritický** — bez reálných dat je audit jen teorie
2. **`except Exception: continue` je time bomb** — odhalení trvalo, až když jsme se podívali na výstup
3. **LLM dobře generuje, špatně detekuje degradaci** — vyžaduje lidský dohled nebo ETL monitoring
4. **Prioritizace podle ETL dat** je přesnější než podle severity labelu v auditu

---

## 5. Stav projektu po session

### Hotovo

| Oblast | Stav |
|---|---|
| Salary filter | ✅ Opraven — regex na tisícové oddělovače |
| Dedup | ✅ URL + normalizovaný title+company |
| Error logging | ✅ Všichni 4 providers + server.py |
| strip_emoji | ✅ Volá se v Ad.to_dict() |
| Bazos selectory | ✅ Opraveny na aktuální HTML strukturu |
| Exclude čeština | ✅ Opraveno pro bazos-only query |
| ETL runner | ✅ scripts/run_etl.py s timestamp |
| Testy | ✅ 79/79, 3 nové testy |

### Nehotovo (odloženo)

| Oblast | Důvod |
|---|---|
| Boolean parser zpřísnění | Nízká priorita — config píše autor |
| Portal-specific exclude | Vyžaduje změnu schématu config.yaml |
| MCP Resources (L2) | Produkční stabilita až po Iteraci 3 |
| MCP Prompts (L3) | Závisí na L2 |
| Per-request timeout | Nízká priorita — 20s ETL je akceptovatelné |
| Docker/health endpoint | Nízká priorita — stdio režim stačí |

---

## 6. Doporučení pro další session

### Immediate (příště)

1. **Opravit boolean parser** — přidat EOF check v `parse()` (máme diff ready, 15 minut práce)
2. **Zvážit portal-specific exclude** v config.yaml schématu (architektonické rozhodnutí, 1-2 hodiny)
3. **Spustit ETL na začátku session** jako health check — pokud se selectory rozbily, víme to hned

### Krátkodobě (do 7 dní)

4. **Přidat do ETL runneru diff** — porovnání s předchozím během, alert na >20% pokles
5. **Zvážit MCP Resources** (L2) — ad pool jako `mcp-jobs://ads/{query_id}`

### Střednědobě (30 dní)

6. **MCP Prompts** — `@mcp.prompt("search_expert")`
7. **Dockerfile + health endpoint** pro orchestrátor
8. **Strukturované JSON logování** pro produkční monitoring

---

## 7. Exekutivní shrnutí (pro CEO)

MCP-Jobs prošel auditem, implementoval 4 kritické opravy a zvýšil výtěžnost o 21 %. Projekt je stabilní a funkční, ale provozně nezralý — chybí mu monitoring, alerting a MCP Resources. Další vývoj by se měl zaměřit na:

1. **Dokončit boolean parser zpřísnění** (malá práce, velký dopad na konzistenci)
2. **Posunout MCP compliance z L1 na L2** (Resources — zásadní pro LLM agenty)
3. **Zavést ETL monitoring** (detekce tiché degradace)

Aktuální kód je na větvi `feature/v2`, 79 testů, 34 matched ads z ~1100 surových při 20s běhu.
