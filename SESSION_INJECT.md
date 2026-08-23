# SESSION INJECT — MCP-Jobs Skill Catalog + Dashboard Redesign

**Datum:** 2026-08-23 | **Vlakno:** Skill Catalog F1-F3 + Kalibrace + Dashboard Redesign
**Ucel:** Skills layer kalibrace + dashboard UX redesign
**Branch:** `skill_catalog` merged into `main` (b3e27f9)

---

## 1. SOUCASNY STAV

### Hotovo
| Faze | Popis | Status |
|------|-------|--------|
| F1 | Skill catalog core (skills_config.json, skills_catalog.py) | DONE |
| F2 | DB integration (skills JSONB, GIN index, backfill) | DONE |
| F3 | Dashboard UI (tags, filtr, analytika) | DONE |
| Kalibrace W | Vahy opraveny dle trzniho vyzkumu | DONE |
| Reserse | IT stack trends Q2+ 2026 (globalni zdroje) | DONE |
| Komprese formule | Navrzena + implementovana + otestovana | DONE |
| PostgreSQL v2 backfill | 183 ads prepsano na v2 (145 updated) | DONE |
| Dashboard v2 | Layout redesign — table-first, on_select, sidebar KPI | DONE |
| Dashboard merge | skill_catalog -> main (b3e27f9) | DONE |

### Pending
| Faze | Popis | Status |
|------|-------|--------|
| EROI dimenze (L1) | Prevzato z linkedin-mcp-custom, netestovano na CZ | NEZAHAJENO |
| 84 default skill vah | Arbitrarni hodnoty, potencialni kalibrace | NEZAHAJENO |
| CZ employer tiers | Strategic/growth seznamy prazdne/male | NEZAHAJENO |
| location_score | Fixni 35.0 pro vsechny (neimplementovano) | NEZAHAJENO |

---

## 2. KEY FILES

### Skills Layer
| Soubor | Ucel |
|--------|------|
| `src/mcp_jobs/skills_config.json` | 119 skillu, 27 kategorii, kalibrovane vahy |
| `src/mcp_jobs/skills_catalog.py` | SkillsCatalog — v2 kompresni formule |
| `src/mcp_jobs/db.py` | `_extract_skills()` + upsert integrace |
| `data/schema.sql` | `skills JSONB DEFAULT '[]'` + GIN index |
| `scripts/backfill_skills.py` | Batch backfill (--force pro prepis v1->v2) |
| `tests/test_skills_catalog.py` | 39 unit testu |

### Dashboard
| Soubor | Ucel |
|--------|------|
| `dashboard/app.py` | Streamlit entry — sidebar gatekeeper + KPI |
| `dashboard/metrics.py` | `fetch_ads()`, `top_skills()`, `tech_score_distribution()`, `top_scored_ads()` |
| `dashboard/tabs/ads.py` | Table-first layout, on_select, inline detail+status |
| `dashboard/tabs/analysis.py` | Skills analytika, top ads, histogram |
| `dashboard/components/kpi.py` | KPI cards (main + sidebar compact) |
| `dashboard/components/gatekeeper.py` | Pipeline status (sidebar compact) |
| `dashboard/filters.py` | IT Skills multiselect, domain filter |
| `dashboard/theme.css` | Dark theme, metric-card styling |

---

## 3. KOMPRESNI FORMULE (HOTOVO)

### Finálni formule v2 (D1+D2 fix)

```python
import math

# Component 1: coverage (60 pts) — log-scaled to spread low values
coverage_score = min(60.0, math.log1p(mentioned_weighted * 10.0) * 12.0)

# Component 2: skill count (30 pts) — log2 scale, 8 skills = max
count_score = (math.log2(1 + skill_count) / math.log2(8)) * 30.0

# Component 3: diversity (10 pts) — unique categories ratio
diversity_score = (unique_categories / skill_count * 10.0) if skill_count > 0 else 0.0

score = min(100.0, coverage_score + count_score + diversity_score)
```

### Diagnostika v1 formule

| Defekt | Popis | Dukaz |
|--------|-------|-------|
| D1 bimodalni | 46% zero, 40% = 100, gradient = 0 | Distribuce: 2 polohy |
| D2 inverted | Single-skill avg 100.0 > multi-skill avg 90.0 | Vice skillu = horsi |
| D3 false positive | "Krajta Python Regius" = 100 | Stara data (bazos noise) |

---

## 4. KALIBRACE — VAHY (HOTOVO)

| Skill | Stara W | Nova W | Zdroj opravy |
|-------|---------|--------|--------------|
| AI | 0.50 | **0.80** | LinkedIn +287% YoY |
| GCP | 0.70 | **0.45** | Synergy 12% market |
| AWS | 0.40 | **0.50** | Synergy 31% market |
| Azure | 0.40 | **0.50** | Synergy 25% market |
| MCP | 0.70 | **0.30** | Niche, ne trzni |
| FastMCP | 0.70 | **0.30** | Niche |
| K8s | 0.50 | **0.60** | LinkedIn +78% |
| LLM | 0.50 | **0.60** | Top trend |
| CNC | 0.80 | **0.60** | Lokalni niche |
| CAM | 0.80 | **0.60** | Lokalni niche |

---

## 5. DB STATISTIKY (po v2 backfill)

```
Total ads: 183
With skills: 145 (79%)
Zero-score: 93 (non-IT queries: udrzbar, zahradnik, strechy)

Score distribuce (v2):
  0 (no skills):   93 ads
  1-39:             2 ads
  40-59:           19 ads
  60-79:           16 ads
  80+:             53 ads

Portal avg score (v2):
  jobs:      47.9 (28/61 with skills)
  profesia:  25.4 (1/3)
  jenprace:  21.2 (15/38)
  pracecz:   10.4 (8/62)
  bazos:      0.0 (0/14)
  volnamista: 0.0 (0/5)

Backup: ads_v1_backup table (183 rows, v1 scores)
```

---

## 6. DASHBOARD LAYOUT (v2 — 2026-08-23)

### Zmeny UX
| Pred | Po |
|------|-----|
| Gatekeeper + 8 KPI cards nahore | Gatekeeper = 1 radek v sidebar, KPI = compact sidebar |
| Tabulka pod foldem | Tabulka = prvni vec co user vidi |
| Manualni ID input pro detail | Klik na radek -> auto-detail (on_select) |
| Status change dole, rucne ID | Status change inline pod vybranym radkem |
| H3 plain text | H3 jako hyperlink na portal URL |
| IT tags pod popisem | IT tags hned pod nadpisem (rychla orientace) |
| Prvni videni | Datum |
| Tech score nesourozny | Tech score homogenni (metadata = metrics) |

### Novy UX flow
```
[Table] -> klik na radek -> [Inline status change] + [Detail + Tags]
         vyber 2+ radku -> [Bulk status change]
```

### Detail layout
```
<h3><a href="url">Senior Data Engineer</a></h3>    <- clickable
Python | PostgreSQL | AWS | Spark | Airflow          <- tags
----------------------------------------------------
Firma: ...  |  Mzda: ...     |  Datum: ...
Lokace: ... |  Query: ...    |  Score: 64.8
Portal: ... |  Status: ...   |  Keyword: ...
----------------------------------------------------
Popis: [textarea]
----------------------------------------------------
[64.8] [Coverage 4.1%] [Domain 25] [Tier unknown]
```

---

## 7. DATA ARCHITECTURE

```
PostgreSQL (mcp-jobs-postgres) = PRIMARNI
  - 183 ads, v2 scoring
  - Pipeline pise pres persist_run() -> upsert_ads() -> _extract_skills()
  - Backup: ads_v1_backup table

JSON files = OUTPUT ARTIFAKTY (ne data store)
  - etl_*.json, etl_*.md, etl_*.html — reporty
  - pipeline_latest.json, pipeline_debug.json — debug data
```

---

## 8. COMMITS (skill_catalog -> main)

```
b3e27f9 Merge branch 'skill_catalog' into main
a7ff3b2 dashboard: h3 hyperlink, metric cards -50%, fix tech_score inconsistency
ff894db dashboard: move IT stack tags after header, before description
f56fd9a dashboard: layout redesign - table-first, on_select, inline detail+status
81e5e2a dashboard: resize skill tags +50% in ad detail view
cab027f dashboard: update for v2 scoring (tech_score column, high-tech KPI)
1835e8f backfill: add --force flag for v2 re-scoring existing ads
ccf9613 [SKILL_CATALOG] calibrate: L2 per-skill weights for CZ market
f3c4bc5 [SKILL_CATALOG] fix: v2 scoring formula (D1+D2) + weight calibration
```

---

## 9. GUARDRAILS

- `PYTHONIOENCODING=utf-8` + `-X utf8`
- ruff: E4/E7/E9/F/W/I/UP/RUF/PIE/FURB/DTZ
- zadne emoji v kodu
- ASCII-NOM nazvy souboru
- Testy: `pytest tests/test_skills_catalog.py tests/test_dashboard_contract.py`

---

## 10. KNOWN ISSUES

- `test_report.py` — 1 pre-existing fail (date-dependent, ignorovat)
- 84 skillu s default vahou (0.30-0.50) — potencialni budouci kalibrace
- employer_tier: vsechny ads = "unknown" (strategic/growth seznam prazdny)
- location_score: fixni 35.0 pro vsechny (neimplementovano)
- EROI dimenze (L1): prevzato z linkedin-mcp-custom, netestovano na CZ trh

---

## 11. ZDROJE PRO DALSI KALIBRACI

- LinkedIn Jobs on the Rise 2026
- Stack Overflow Developer Survey 2025
- Synergy Research Q1 2026
- Robert Half 2026
- DataCamp/MirrorCV
- Linux Foundation 2025
- TIOBE 2026
- ManpowerGroup Q2 2026
- ABSL Report 2026
- Mordor Intelligence CZ ICT 2026-2031
