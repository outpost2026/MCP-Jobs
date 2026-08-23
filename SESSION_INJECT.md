# SESSION INJECT — Skills Layer Kalibrace

**Datum:** 2026-08-23 | **Vlákno:** Skill Catalog F1-F3 + Kalibrace
**Účel:** Pokračování kalibrace skills vrstvy v MCP-Jobs
**Branch:** `skill_catalog` (pushnutý na GitHub)

---

## 1. SOUČASNÝ STAV

### Hotovo ✅
| Fáze | Popis | Status |
|------|-------|--------|
| F1 | Skill catalog core (skills_config.json, skills_catalog.py) | ✅ DONE |
| F2 | DB integration (skills JSONB, GIN index, backfill) | ✅ DONE |
| F3 | Dashboard UI (tags, filtr, analytika) | ✅ DONE |
| Kalibrace W | Váhy opraveny dle tržního výzkumu | ✅ DONE |
| Rešerše | IT stack trends Q2+ 2026 (globální zdroje) | ✅ DONE |
| Komprese formule | Navržena + implementována + otestována | ✅ DONE |

### Pending ⏳
| Fáze | Popis | Status |
|------|-------|--------|
| Commit + push | Nová formule na skill_catalog branch | ⏳ NEZAHÁJENO |
| Dashboard update | Aktualizace histogramu pro nové skóre | ⏳ NEZAHÁJENO |
| Final validation | End-to-end test na reálných datech | ⏳ NEZAHÁJENO |

---

## 2. KEY FILES

### Skills Layer
| Soubor | Účel |
|--------|------|
| `src/mcp_jobs/skills_config.json` | 119 skillů, 27 kategorií, váhy (opoovavené) |
| `src/mcp_jobs/skills_catalog.py` | SkillsCatalog singleton — **AKTUALIZOVÁNO kompresní formulí** |
| `src/mcp_jobs/db.py` | `_extract_skills()` + upsert integrace |
| `data/schema.sql` | `skills JSONB DEFAULT '[]'` + GIN index |
| `scripts/backfill_skills.py` | Batch backfill script — **AKTUALIZOVÁNO pro nové pole** |
| `tests/test_skills_catalog.py` | 39 unit testů |
| `dashboard/metrics.py` | `top_skills()`, `tech_score_distribution()` |
| `dashboard/tabs/ads.py` | Skills tags v detailu |
| `dashboard/tabs/analysis.py` | Skills analytika |
| `dashboard/filters.py` | IT Skills multiselect filtr |

---

## 3. KOMPRESNÍ FORMULE (HOTOVO)

### Metodologie (z KB)

| Princip | Zdroj | Aplikace |
|---------|-------|----------|
| Intelligence = komprese reality | Mikolov | Score = míra komprese popisu do skillů |
| CR > 1.5 = signal | CPM §1.3 | Minimální poměr pro relevantní ad |
| CR > 10 = silný signal | CPM §1.3 | Vysoce relevantní inzerát |
| CR < 1 = noise | CPM §1.3 | Irrelevantní inzerát |
| Minimální algoritmus | Mikolov | Minimální počet skillů pro popis reality |

### Finální formule v2 (D1+D2 fix)

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

### Diagnostika v1 formule (2026-08-23)

| Defekt | Popis | Důkaz |
|--------|-------|-------|
| D1 bimodální | 46% zero, 40% = 100, gradient = 0 | Distribuce: 2 polohy |
| D2 inverted | Single-skill avg 100.0 > multi-skill avg 90.0 | Více skillů = horší |
| D3 false positive | "Krajta Python Regius" = 100 | Stará data (bazos noise) |

D3 vyřešeno: archivace starých bazos/nyx JSON (global search ≠ category scrape).

### Výsledky v2 (100 clean ads, jobs+pracecz+jenprace+profesia+volnamista)

**Top 10:**
| # | Titulek | Score | Matches | Coverage |
|---|---------|-------|---------|----------|
| 1 | AI Python Developer - CV & ML | 64.8 | 3 | 0.0422 |
| 2 | Senior Backend Developer - Python, AWS, K8s | 63.8 | 3 | 0.0386 |
| 3 | Senior Python Engineer for Agentic AI | 62.0 | 3 | 0.0441 |
| 4 | Integration Engineer - Python / API / K8s | 61.0 | 3 | 0.0404 |
| 5 | Machine Learning Engineer - Python | 59.1 | 2 | 0.0275 |
| 6 | Java Developer - AI-Driven Engineer | 58.3 | 2 | 0.0220 |
| 7 | Senior Python Engineer for Agentic AI | 57.2 | 2 | 0.0441 |
| 8 | Integration Engineer - Python / API / K8s | 56.2 | 2 | 0.0404 |
| 9 | Python & Product Engineer | 44.9 | 1 | 0.0184 |
| 10 | Python Developer | 44.9 | 1 | 0.0184 |

**Distribuce:**
```
  0- 9:  46 ads (46%) — zero matches (non-IT / parse failure)
 30-39:   4 ads (4%)
 40-49:  36 ads (36%) — single-skill IT jobs
 50-59:   6 ads (6%) — dual-skill IT jobs
 60-69:   8 ads (8%) — multi-skill IT jobs (BEST)
```

---

## 4. KALIBRACE — VÁHY (HOTOVO)

### Opravené váhy (před/po)

| Skill | Stará W | Nová W | Zdroj opravy |
|-------|---------|--------|--------------|
| AI | 0.50 | **0.80** | LinkedIn +287% YoY |
| GCP | 0.70 | **0.45** | Synergy 12% market |
| AWS | 0.40 | **0.50** | Synergy 31% market |
| Azure | 0.40 | **0.50** | Synergy 25% market |
| MCP | 0.70 | **0.30** | Niche, ne tržní |
| FastMCP | 0.70 | **0.30** | Niche |
| K8s | 0.50 | **0.60** | LinkedIn +78% |
| LLM | 0.50 | **0.60** | Top trend |
| CNC | 0.80 | **0.60** | Lokální niche |
| CAM | 0.80 | **0.60** | Lokální niche |

---

## 5. DB STATISTIKY (po kompresní kalibraci)

```
Coverage: 145/183 (79%)
Unikátních skills: 98
Kategorií: 25
Celkem matchů: 291

Score distribuce:
  0-10:  93 (64%)
 30-40:  17 (12%)
 80-90:  10 (7%)
   90+:   2 (1%)
```

---

## 6. NEXT STEPS

1. **Commit + push** — v2 formule + archivace starých dat + skills_config kalibrace
2. **Dashboard update** — aktualizovat histogram pro v2 skóre (0-100 rozsah)
3. **EROI dimenze (L1)** — převzato z linkedin-mcp-custom, netestováno na CZ trh
4. **84 default skill vah (L2)** — arbitrární hodnoty, potenciální kalibrace
5. **CZ employer tiers** — strategic/growth seznamy prázdné/malé

---

## 7. GUARDRAILS

- `PYTHONIOENCODING=utf-8` + `-X utf8`
- ruff: E4/E7/E9/F/W/I/UP/RUF/PIE/FURB/DTZ
- Žádné emoji v kódu
- ASCII-NOM názvy souborů
- Testy: `pytest tests/test_skills_catalog.py tests/test_dashboard_contract.py`
- Commit: `[SKILL_CATALOG] ...`

---

## 8. KNOWN ISSUES

- `test_report.py` — 1 pre-existing fail (date-dependent, ignorovat)
- 84 skillů s default vahou (0.30-0.50) — potenciální budoucí kalibrace
- employer_tier: všechny ads = "unknown" (strategic/growth seznam prázdný)
- location_score: fixní 35.0 pro všechny (neimplementováno)
- EROI dimenze (L1): převzato z linkedin-mcp-custom, netestováno na CZ trh
- location_score: fixní 35.0 pro všechny (neimplementováno)

---

## 9. ZDROJE PRO DALŠÍ KALIBRACI

- LinkedIn Jobs on the Rise 2026
- Stack Overflow Developer Survey 2025
- Synergy Research Q1 2026
- Robert Half 2026
- DataCamp/MirrorCV
- Linux Foundation 2025
- TIOBE 2026
- `linkedin-mcp-custom/analysis/tech.py` (reference scoring formula)
