# MCP-Jobs Refresh Run Report — IT Jobs Profile

**Date:** 2026-08-06
**Config:** IT jobs profile (8 queries)
**Portals:** jobs, bazos, pracecz

**Fresh Run Update (22:54):** Parallel detail fetch (Sprint 2 — C1) reduced pipeline time from 58.5s to 36.3s (1.61x speedup). Results identical: 28 matched, same queries. No regression.

---

## 1. Per-Query Results Table

| Query | Found | Unique (est.) | Portals |
|-------|------:|:------------:|---------|
| python_ai_engineer | 1 | 1 | jobs |
| ai_llm_engineer | 2 | 2 | jobs |
| mcp_agentic | 1 | 1 | jobs |
| data_engineering | 10 | 8 | jobs, pracecz |
| devops_ci_cd | 5 | 4 | jobs, pracecz |
| prumyslova_automatizace | 7 | 7 | jobs, pracecz |
| cnc_cam_automation | 1 | 1 | pracecz |
| reverse_engineering | 1 | 1 | jobs |
| **TOTAL** | **28** | **16** | |

---

## 2. Anomalies & Errors

- **All jobs marked partial** — every job across all queries has `_flags.partial: true`, indicating missing fields (salary, price, category_name). No salary data was returned for any IT job.
- **High cross-query overlap** — the ESET "Python Software Engineer" listing appears in 5 of 8 queries (python_ai_engineer, ai_llm_engineer, mcp_agentic, data_engineering, devops_ci_cd, reverse_engineering) due to broad keyword matching.
- **bazos portal: 1 failed request** (4.2% error rate) — no specific error message logged.
- **No category_name** returned for any job on any portal — potential parser issue on jobs.cz and prace.cz.

---

## 3. Portal Performance Metrics

| Portal | OK | Failed | Error Rate | Avg Response (ms) | Total Requests |
|--------|---:|-------:|-----------:|-------------------:|---------------:|
| jobs | 25 | 0 | 0.0% | 970.3 | 25 |
| bazos | 23 | 1 | 4.2% | 826.6 | 24 |
| pracecz | 25 | 0 | 0.0% | 1,114.1 | 25 |
| **Total** | **73** | **1** | **1.3%** | **970.3 (wtd)** | **74** |

---

## 4. Pipeline Performance

| Metric | Value |
|--------|-------|
| Total requests (all portals) | 74 |
| Total unique jobs | 16 |
| Dedup ratio (raw vs unique) | 57.1% (28 raw → 16 unique) |
| Partial flag rate | 100% (all 28 jobs) |
| Failed requests | 1 (bazos) |
| Queries processed | 8 |
| Average jobs per query | 3.5 |

---

## 5. Top Jobs by Query (Top 3 per query)

### python_ai_engineer
| Title | Company | Location | Salary |
|-------|---------|----------|--------|
| Python Software Engineer (m/f/n) | ESET Research Czech Republic s.r.o. | Praha – Holešovice | — |

### ai_llm_engineer
| Title | Company | Location | Salary |
|-------|---------|----------|--------|
| Python Software Engineer (m/f/n) | ESET Research Czech Republic s.r.o. | Praha – Holešovice | — |
| Senior Data & AI Engineer | Aon Central and Eastern Europe a.s. | Praha – Nové Město | — |

### mcp_agentic
| Title | Company | Location | Salary |
|-------|---------|----------|--------|
| Python Software Engineer (m/f/n) | ESET Research Czech Republic s.r.o. | Praha – Holešovice | — |

### data_engineering
| Title | Company | Location | Salary |
|-------|---------|----------|--------|
| DevOps Engineer | Analytics Data Factory s.r.o. | Praha – Nusle | — |
| Data Engineer - Hey George | Česká spořitelna, a.s. | Praha – Michle | — |
| Senior Data Engineer | Avenga Czechia s.r.o. | Praha-Libeň | — |

### devops_ci_cd
| Title | Company | Location | Salary |
|-------|---------|----------|--------|
| DevOps Engineer | Analytics Data Factory s.r.o. | Praha – Nusle | — |
| Linux Infrastructure Engineer \| Kubernetes \| VMware \| DevOps | Future Recruitment s.r.o. | Praha | — |
| QA TESTER/ENGINEER | Analytics Data Factory s.r.o. | Praha – Nusle | — |

### prumyslova_automatizace
| Title | Company | Location | Salary |
|-------|---------|----------|--------|
| QA Automation Engineer | Daktela s.r.o. | Praha – Žižkov | — |
| Programátor PLC / Automatizační systémy / Průmysl (M/Ž) | Bohemia Controls s.r.o. | Praha-Hostivař | 40,000 – 70,000 Kč/měsíc |
| PLC programátor/ projektový inženýr - nejen pivovarnictví | SIDAT, spol. s r.o. | Praha-Košíře | — |

### cnc_cam_automation
| Title | Company | Location | Salary |
|-------|---------|----------|--------|
| Pomocný technik/seřizovač vstřikolisů /údržbář | PACKMAN'S PACK s.r.o. | Praha-Zličín | 30,000 – 35,000 Kč/měsíc |

### reverse_engineering
| Title | Company | Location | Salary |
|-------|---------|----------|--------|
| Python Software Engineer (m/f/n) | ESET Research Czech Republic s.r.o. | Praha – Holešovice | — |

---

## 6. Timeout Analysis

- **No timeouts occurred** — all 8 queries completed successfully within the pipeline.
- **Estimated total pipeline time: ~28.8s** based on weighted average response times:
  - jobs: 25 requests × 970.3ms = 24.3s
  - bazos: 24 requests × 826.6ms = 19.8s
  - pracecz: 25 requests × 1,114.1ms = 27.9s
  - *Note: Requests within each portal run concurrently; actual wall-clock time depends on parallelism. Sequential worst-case: ~72s. With 3-portal parallelism: ~28s.*

---

*Report generated from raw pipeline output. Deduplication is approximate (by URL).*
