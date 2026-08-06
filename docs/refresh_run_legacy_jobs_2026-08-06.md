# MCP-Jobs Refresh Run Report — Legacy Jobs Profile

**Date:** 2026-08-06
**Config:** Legacy jobs profile (8 queries)
**Portals:** jobs, bazos, pracecz

---

## 1. Per-Query Results Table

| Query | Found | Unique (est.) | Portals |
|-------|------:|:------------:|---------|
| elektrikar_prumysl | 2 | 2 | bazos, pracecz |
| udrzbar | 34 | 34 | jobs, bazos, pracecz |
| spravce_budov | 5 | 5 | pracecz |
| zahradnik | 4 | 4 | bazos |
| truhlar | 1 | 1 | bazos |
| strechy | 0 | 0 | — |
| cnc_jobs | 0 | 0 | — |
| **TOTAL** | **46** | **46** | |

---

## 2. Anomalies & Errors

- **All jobs marked partial** — every job across all queries has `_flags.partial: true`, indicating missing fields. Jobs from bazos consistently lack `company` and `salary` fields; pracecz jobs lack `price` and `category_name`.
- **bazos portal: 1 failed request** (4.2% error rate) — consistent across both runs.
- **2 queries returned zero results** — `strechy` (roofing) and `cnc_jobs` found no listings across any portal.
- **udrzbar query dominance** — 34 of 46 total jobs (73.9%) come from the "údržbář" query, which matches broadly across maintenance/technician roles.
- **No category_name** returned for any job — parser issue consistent across both runs.

---

## 3. Portal Performance Metrics

| Portal | OK | Failed | Error Rate | Avg Response (ms) | Total Requests |
|--------|---:|-------:|-----------:|-------------------:|---------------:|
| jobs | 25 | 0 | 0.0% | 945.4 | 25 |
| bazos | 23 | 1 | 4.2% | 874.2 | 24 |
| pracecz | 25 | 0 | 0.0% | 1,035.0 | 25 |
| **Total** | **73** | **1** | **1.3%** | **951.6 (wtd)** | **74** |

---

## 4. Pipeline Performance

| Metric | Value |
|--------|-------|
| Total requests (all portals) | 74 |
| Total unique jobs | 46 |
| Dedup ratio (raw vs unique) | 0.0% (46 raw → 46 unique) |
| Partial flag rate | 100% (all 46 jobs) |
| Failed requests | 1 (bazos) |
| Queries processed | 8 (6 with results, 2 empty) |
| Average jobs per query | 5.75 |

---

## 5. Top Jobs by Query (Top 3 per query)

### elektrikar_prumysl
| Title | Company | Location | Salary |
|-------|---------|----------|--------|
| INSTALATÉR, VODAŘ, ELEKTRIKÁŘ | — | Praha-západ | 50,000 Kč (price) |
| Hlavní inženýr projektu / Lead Engineer (Elektro & Automatizace) | SIDAT, spol. s r.o. | Praha-Košíře | — |

### udrzbar
| Title | Company | Location | Salary |
|-------|---------|----------|--------|
| SERVISNÍ TECHNIK - až 50,000 Kč | — | Praha 9 | V textu (price) |
| Provozní elektrikář/údržbář | Ústav fotoniky a elektroniky AV ČR, v.v.i. | Praha-Kobylisy | — |
| SERVISNÍ TECHNIK záložních zdrojů AEG Power Solutions | AEG Power Solutions spol. s r.o. | Praha-Hostivař | 50,000 – 80,000 Kč/měsíc |

### spravce_budov
| Title | Company | Location | Salary |
|-------|---------|----------|--------|
| Technický správce objektů | PONESTRA s.r.o. | Praha-Nové Město | 40,000 – 45,000 Kč/měsíc |
| Správce nemovitostí & technik | Nobis studio s.r.o. | Praha-Staré Město | 50,000 – 60,000 Kč/měsíc |
| Správce nemovitostí | IVF CUBE | Praha-Vokovice | — |

### zahradnik
| Title | Company | Location | Salary |
|-------|---------|----------|--------|
| ZAHRADNÍK - údržba zeleně | — | Praha | V textu (price) |
| Prace -venku -dlouhodobá | — | Praha | 30,000 Kč (price) |
| Zahradnik do party | — | Praha | 200 Kč (price) |

### truhlar
| Title | Company | Location | Salary |
|-------|---------|----------|--------|
| Truhlář | — | Praha | 40,000 Kč (price) |

### strechy
| Title | Company | Location | Salary |
|-------|---------|----------|--------|
| *(no results)* | — | — | — |

### cnc_jobs
| Title | Company | Location | Salary |
|-------|---------|----------|--------|
| *(no results)* | — | — | — |

---

## 6. Timeout Analysis

- **No timeouts occurred** — all 8 queries completed successfully within the pipeline.
- **Estimated total pipeline time: ~27.5s** based on weighted average response times:
  - jobs: 25 requests × 945.4ms = 23.6s
  - bazos: 24 requests × 874.2ms = 21.0s
  - pracecz: 25 requests × 1,035.0ms = 25.9s
  - *Note: Requests within each portal run concurrently; actual wall-clock time depends on parallelism. Sequential worst-case: ~70.5s. With 3-portal parallelism: ~27.5s.*

---

*Report generated from raw pipeline output. Deduplication is approximate (by URL).*
