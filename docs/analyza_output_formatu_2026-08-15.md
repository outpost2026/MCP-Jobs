# Analýza výstupních formátů MCP-Jobs pipeline

**Datum:** 2026-08-15
**Rozsah:** Kompletní inventář a sémantická analýza všech výstupů MCP-Jobs (MD, JSON, CSV, HTML, L2 resources)
**Cíl:** Identifikovat gaps, redundance a navrhnout vylepšení výstupních formátů/layoutu s ohledem na hSNR a doménu job-hunt.

---

## 1. Inventář výstupních formátů

### 1.1 Markdown (MD)

| # | Soubor | Generátor | Formát | Použití |
|---|--------|-----------|--------|---------|
| MD-1 | `output/etl_{ts}.md`, `output/etl_latest.md` | `storage.py:markdown_report()` (flat) | Plochý seznam `## [title](url)` | MCP tools (`save_timestamped`) |
| MD-2 | `output/etl_{profile}_{ts}.md`, `output/etl_latest_{profile}.md` | `scripts/run_etl.py:_write_markdown_report()` (structured) | Pipeline report: přehledová tabulka + per-query sekce | CLI ETL runner |
| MD-3 | `mcp-jobs://ads/{query_id}/report` (L2 resource) | `server.py:351` → `Storage.markdown_report()` (flat) | Stejný flat formát jako MD-1 | MCP resource read |

**Klíčový nález:** MD-1 a MD-2 jsou **dva divergentní generátory** pro stejný typ dat, s odlišnou strukturou. Oba píší do `output/` — konfuze názvů (`etl_latest.md` vs `etl_latest_AI_NATIVE.md`).

### 1.2 JSON

| # | Soubor | Generátor | Struktura |
|---|--------|-----------|-----------|
| JSON-1 | `output/etl_{ts}.json`, `etl_latest.json` | `storage.py:save_timestamped()` | `[{query, total_found, results[], _stats, query_id, resource_uri}]` |
| JSON-2 | `output/etl_{profile}_{ts}.json`, `etl_latest_{profile}.json` | `scripts/run_etl.py` | `{timestamp, elapsed, total_matched, profile, config, summary, results}` |
| JSON-3 | `output/etl_metrics_{ts}.json`, `etl_metrics_latest.json` | `scripts/run_etl_metrics.py` | `{timestamp, provider_metrics, query_summary, sample, results}` |
| JSON-4 | `data/query_store.json` | `server.py:_save_query_store()` | `{query_id: {data, timestamp, type}}` (max 50, LRU) |
| JSON-5 | `data/correlation_cache.json` | `storage.py:save_correlation()` | `[{query, portal, total_found, total_scraped, hit_rate, errors, timestamp}]` (304+ záznamů) |
| JSON-6 | `data/pipeline_report_{ts}.json`, `pipeline_latest.json` | `scripts/analyze_pipeline.py` | Diagnostický report s anomalies |
| JSON-7 | `data/comparison_report.json` | `scripts/compare_legacy_vs_mcp.py` | Gap analýza vs legacy |

### 1.3 CSV

| # | Soubor | Generátor | Stav |
|---|--------|-----------|------|
| CSV-1 | — | `storage.py:save_incremental()` | ⚠️ **Dead code** — metoda nikde není volána (grep potvrzeno) |

### 1.4 HTML (raw dumps)

| # | Soubor | Generátor | Stav |
|---|--------|-----------|------|
| HTML-1 | `data/{portal}/raw_{portal}_{ts}.html` | Live testy (Playwright) | Debug artefakty ze 2026-07-14 |

---

## 2. Sémantická analýza MD formátů

### 2.1 Flat formát (MD-1 / MD-3) — `storage.py:184-202`

```markdown
> Generated: {ts} | Queries: N | Total ads: N

# Search Results (N ads)

## [Title](url)
 portal=pracecz | company=X | location=Praha
> {description[:200]}
```

**hSNR hodnocení:**
- ✅ Per-inzerát řádek má portál/firmu/lokaci/plat/cenu
- ✅ Popis (trunc 200) = triage kontext
- ❌ **Žádná deduplikace** — stejný inzerát se opakuje pod více query (evidence: `etl_20260815_091515.md` — `Full stack Developer - Python v AI` 3×, CRA cluster 4×)
- ❌ **Žádná agregace/priorita** — plochý seznam bez seskupení, bez zvýraznění nových/končících
- ❌ Chybí `matched_keyword` (JSON ho má, MD ne)
- ❌ Chybí časová značka per inzerát (date pole existuje v Ad, ale MD ho nezobrazuje)

### 2.2 Structured format (MD-2) — `run_etl.py:45-123`

```markdown
# MCP-Jobs Pipeline Report
**Spuštěno:** ... | **Trvání:** ... | **Matched:** N
**Profil (config):** `AI-NATIVE`

## Přehled
| # | Query | Počet | Portály |
|---|-------|-------|---------|

## 1. data_engineering — 5 matchingů
1. **[Title](url)**
   — {salary} | {company} | {location} | (portal)
> +N dalších inzerátů (celkem N)
```

**hSNR hodnocení:**
- ✅ Přehledová tabulka nahoře = dashboard (okamžitý přehled počtů per query)
- ✅ Per-query seskupení = přirozený dedup kontext
- ✅ Sample cap 5 + "+N dalších" = kompaktní
- ❌ **Chybí popis** (na rozdíl od flat MD-1)
- ❌ Chybí datum/deadline per inzerát
- ❌ Sample cap skrývá plný seznam bez odkazu na JSON
- ❌ Nepoužívá dedup (pipeline dedupuje jen v `_dedup` na pool úrovni, ne per report)

---

## 3. Redundance a divergence

### 3.1 Dva divergentní MD generátory

| Aspekt | Flat (MD-1) | Structured (MD-2) |
|--------|-------------|-------------------|
| Voláno z | MCP tools (`save_timestamped`) | CLI (`run_etl.py`) |
| Má popis | ✅ | ❌ |
| Má overview tabulku | ❌ | ✅ |
| Má per-query grouping | ❌ | ✅ |
| Sampuje | ❌ (vše) | ✅ (5+) |
| Název souboru | `etl_{ts}.md` | `etl_{profile}_{ts}.md` |

**Problém:** Dvě implementace stejného konceptu ("výstupní report") s odlišnou strukturou = nekonzistence, dvojí údržba, matoucí `output/` adresář.

### 3.2 Dead code

- `storage.py:save_incremental()` (CSV) — **nevoláno**
- `storage.py:rag_index_md()` — **nevoláno** (grep: pouze definice, žádné volání)

### 3.3 Redundantní data

- `data/correlation_cache.json` — 304 záznamů, akumulace bez LRU capu (na rozdíl od query_store s cap 50). Růst bez limitu.
- `output/` — mnoho `etl_latest*.md/json` per profil; absence dedup v reportech vede k duplicitním blokům.

---

## 4. Gaps (evidence-based)

| # | Gap | Evidence | Dopad na hSNR |
|---|-----|----------|---------------|
| G-1 | **Žádná deduplikace napříč query** v reportech | `etl_20260815_091515.md`: ESET AI Security 3×, CRA cluster 4×, Full stack 3× | Vysoký — hledač čte stejný inzerát vícekrát |
| G-2 | **Dva divergentní MD generátory** | `storage.py:184` vs `run_etl.py:45` | Střední — nekonzistence, dvojí údržba |
| G-3 | **Structured (MD-2) nemá popis** | `run_etl.py:97-107` (jen salary/company/location/portal) | Střední — chybí triage kontext |
| G-4 | **Flat (MD-1) nemá agregaci/prioritu** | `storage.py:184-202` — čistý plochý seznam | Vysoký na velkých listech |
| G-5 | **`matched_keyword` a `date` nejsou v MD** | JSON má `matched_keyword`/`date`, MD ne | Nízký-střední — chybí proč-shoda a čerstvost |
| G-6 | **Dead code** (`save_incremental`, `rag_index_md`) | grep potvrzeno | Nízký — údržbová zátěž |
| G-7 | **Sample cap bez odkazu na plná data** | `run_etl.py:112-113` — "+N dalších" bez linku na JSON | Střední — neprokliknutelnost |
| G-8 | **correlation_cache bez capu** | 304 záznamů akumulace | Nízký — dlouhodobý růst |
| G-9 | **Žádná časová priorita** (nové dnes / končí zítra) | Žádný generátor flaguje deadline | Střední — pro job-hunt klíčové |

---

## 5. Best practice pro job-hunt output listy

Na základě domény (jobs hunt) a principů high-SNR reporting:

| Princip | Popis |
|---------|-------|
| **Dedup** | Každý inzerát max jednou (URL + normalizovaný title) |
| **Action-first** | Klikatelný titulek + přímý odkaz; deadline/čerstvost flag |
| **Decision block** | `⏱ datum | 💰 salary | 🏢 company | 📍 location | 🔑 matched keyword` + `> popis` |
| **Hierarchie** | Dashboard (přehled) → grouped results → per-item detail |
| **Prokliknutelnost** | Report odkazuje na plný JSON / raw data |
| **Konsistence** | Jeden kanonický renderer pro všechny cesty (tool, resource, CLI) |
| **Metriky** | Patička: raw scraped vs matched vs precision (z correlation_cache) |

---

## 6. Návrhy na vylepšení (prioritizováno dle EROI)

### 6.1 Unified renderer (odstraňuje G-2, G-3, G-4, G-5, G-9) — HIGH EROI

Sjednotit `markdown_report` (storage) a `_write_markdown_report` (run_etl) do **jednoho** `render_report(ads, meta)`. Structured (MD-2) jako základ + přidat:
- popis (trunc 200) per inzerát
- `matched_keyword` a `date`
- dedup napříč query
- sekce "🔴 Priority" (nové dnes / končí brzy) podle `date`

### 6.2 Dedup v reportech (odstraňuje G-1) — HIGH EROI

Pipeline už deduplikuje pool (`_dedup` — URL + normalized title+company dle README). Report musí **sdílet stejný dedup klíč** napříč query — vyfiltrovat duplicitní URL před vykreslením, nebo agregovat "objevuje se i v query X".

### 6.3 Patička s precision metrikou (odstraňuje G-8 částečně) — MED EROI

```
> Zdroj: etl_....json | Raw: N | Matched: M | Precision: P% | Generated: ...
```
Založeno na `correlation_cache.json` (hit_rate už existuje v datovém modelu).

### 6.4 Prokliknutí na plná data (odstraňuje G-7) — MED EROI

V structured reportu: `> +{K} dalších → [plný JSON](etl_....json)` místo jen čísla.

### 6.5 Odstranit dead code (odstraňuje G-6) — LOW EROI / quick win

- Smazat `save_incremental()` (CSV) a `rag_index_md()` z `storage.py`, pokud se neplánuje legacy CSV output.

### 6.6 Konzistentní názvy output souborů (odstraňuje matoucí `output/`) — LOW EROI

`etl_{profile}_{ts}.md` jako kanonický název; flat `etl_latest.md` buď odstranit, nebo přejmenovat.

---

## 7. Cílový layout (návrh)

```markdown
# Job Hunt Report — {date}
🧭 Spuštěno {ts} | ⏱ {elapsed}s | ✅ Matched {N} | 🔻 Precision {P}%

## 🔴 Priority (nové / končí brzy)
1. **[Title](url)** — ⏱ {date} | 💰 {salary} | 🏢 {company} | 📍 {location} | ⚠️ Končí {deadline}
   > {popis 200 zn}

## 📊 Přehled (per query)
| Query | N | Portály |
...

## 📂 {query} — {N}
1. **[...](url)** — ...
   > {popis}
> +{K} dalších → [plný JSON](etl_....json)
```

---

## 8. Shrnutí

| Aspekt | Flat (MD-1) | Structured (MD-2) | Legacy Master |
|--------|-------------|-------------------|---------------|
| Popis | ✅ | ❌ | ❌ |
| Dashboard | ❌ | ✅ | ❌ |
| Dedup | ❌ | ❌ | ❌ |
| Priorita | ❌ | ❌ | 🟡 datum |
| Proklik na data | ❌ | ❌ | ❌ |

**Doporučení:** Structured (MD-2) je nejsilnější základ — rozšířit o popis, dedup, matched_keyword, datum a patičku s precision metrikou; sjednotit s flat generátorem do jednoho rendereru.

---

*Analýza provedena: 2026-08-15*
*Metoda: Kompletní inventář formátů + grep-verifikace generátorů + sémantická hSNR analýza + best practice pro job-hunt doménu*
