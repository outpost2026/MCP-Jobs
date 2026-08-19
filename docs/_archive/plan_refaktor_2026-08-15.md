# Plán refaktoru — Unified renderer (MD zdroj + HTML/CSS render)

**Datum:** 2026-08-15 | **Verze:** 0.1 | **Status:** NÁVRH k odsouhlasení
**Navazuje na:** `docs/analyza_output_formatu_2026-08-15.md` (sekce 6.1–6.6, 7)

---

## 0. Rozhodnutí (potvrzeno autorem)

| # | Rozhodnutí | Hodnota |
|---|---|---|
| R1 | Výstupní médium | **Markdown zdroj + HTML/CSS render** |
| R2 | Textový font | **Calibri** |
| R3 | Metadata "match" (a ostatní metadatové řádky) | **8 pt** |
| R4 | Git | **No commit do odsouhlasení** |

---

## 1. Cíle refaktoru

1. Sjednotit dva divergentní MD generátory (`storage.py:markdown_report` flat + `scripts/run_etl.py:_write_markdown_report` structured) do **jednoho** `render_report(ads, meta)`.
2. Z MD jako kanonického zdroje generovat i **HTML s CSS** (Calibri, metadata 8pt, A4 @page pro tisk/PDF).
3. Implementovat sekce 6.1–6.6 z analýzy: dedup, popis, matched_keyword, priority, precision patička.
4. Odstranit dead code (`save_incremental`, `rag_index_md`).

---

## 2. Nová struktura kódu

```
src/mcp_jobs/
├── report.py          # NOVÝ — jediný renderer (MD + HTML)
│   ├── render_report(ads: list[Ad], meta: ReportMeta) -> ReportOutput
│   │   ├── to_markdown() -> str
│   │   └── to_html() -> str          # MD -> HTML (minimal converter) + CSS
│   ├── ReportMeta (dataclass)        # ts, elapsed, total_matched, precision,
│   │                                 # profile, queries, correlation stats
│   └── dedup_key(ad) -> str          # sdílený dedup klíč (URL, normalizovaný title+company)
├── report_style.py     # NOVÝ — CSS konstanty (jediný zdroj pravdy pro styl)
└── storage.py          # ÚPRAVA — smazat markdown_report, save_incremental, rag_index_md
                        #          (dead code); zachovat save_json/save_correlation

scripts/
└── run_etl.py          # ÚPRAVA — volat report.render_report místo _write_markdown_report;
                        #          zapisovat .md i .html

src/mcp_jobs/server.py  # ÚPRAVA (volitelně) — L2 resource "markdown_report" přepnout na report.render_report
```

---

## 3. CSS typografie (report_style.py — jediný zdroj pravdy)

```css
/* A4 tisk/PDF */
@page { size: A4; margin: 18mm 16mm; }

body {
  font-family: "Calibri", "Segoe UI", sans-serif;   /* R2 */
  font-size: 10.5pt;
  line-height: 1.35;
  color: #1a1a1a;
}

/* nadpisy */
h1 { font-size: 15pt; margin: 0 0 4pt 0; }
h2 { font-size: 12pt; margin: 10pt 0 3pt 0; border-bottom: 1px solid #ccc; }

/* metadata řádky — VŠECHNY 8pt (R3) */
.meta, .match, .priority-flag, .footer {
  font-size: 8pt;              /* byla 12pt */
  color: #555;
  line-height: 1.3;
}
.match  { color: #7a5c00; font-weight: 600; }  /* zvýraznění, ale drobné */
.priority-flag { color: #b00020; }

/* tabulka přehledu */
table { width: 100%; border-collapse: collapse; font-size: 9pt; }
th, td { border: 1px solid #ddd; padding: 2pt 6pt; text-align: left; }

/* odkaz */
a { color: #1155cc; text-decoration: none; }
```

**Poznámka k R3:** "match" kategorie = `🔑 match:` tagy v ukázkovém layoutu. Aby 8pt dávalo smysl i u ostatních metadata prvků (⏱ 💰 🏢 📍), sjednocujeme celou třídu `.meta` na 8pt. Nadpisy/popis zůstávají větší.

---

## 4. Datový model & dedup

| Položka | Zdroje | Poznámka |
|---|---|---|
| `matched_keyword` | už v `Ad` modelu | renderovat jako `.match` tag |
| `description` (trunc 200) | už v `Ad` | blockquote `> popis` |
| `date` / `deadline` | už v `Ad.date` (jobs/bazos/nyx) | flagy "Končí brzy" (7 dní) / "Nové dnes" |
| precision | `correlation_cache.json` (`hit_rate`) | patička `Raw N | Matched M | Precision P%` |
| dedup napříč query | `_dedup` klíč z pipeline | agregovat "objevuje se i v query X" |

**Dedup:** použít stejný klíč jako `pipeline._dedup` (URL, případně normalizovaný title+company) — vyfiltrovat duplicity před renderem; v přehledu u každého inzerátu uvést všechny query, které ho matchly.

---

## 5. Pořadí kroků (sestupně dle EROI)

| # | Krok | Soubory | EROI | Test |
|---|---|---|---|---|
| 1 | Vytvořit `report.py` + `report_style.py` (MD render z layoutu sekce 7) | nové | HIGH | `pytest` |
| 2 | Napojit `run_etl.py` na `render_report`; zápis `.md` + `.html` | run_etl.py | HIGH | run `--config config.yaml` |
| 3 | Dedup napříč query v rendereru | report.py | HIGH | porovnat sample_output |
| 4 | Precision patička z `correlation_cache.json` | report.py | MED | run s cache |
| 5 | Smazat dead code (`markdown_report`, `save_incremental`, `rag_index_md`) | storage.py | LOW | `pytest` + grep |
| 6 | Přepnout L2 resource `markdown_report` v serveru | server.py | LOW | `tests/test_server.py` |
| 7 | Unit testy pro `render_report` (MD i HTML) | tests/ | — | `pytest` |

**Definice hotovo (DoD):** run `python scripts/run_etl.py --config config.yaml` vyprodukuje `etl_AI_NATIVE_*.md` + `.html`; HTML render → Calibri, match 8pt; dedup funkční; `pytest` zelený; `ruff` clean.

---

## 6. Rizika & otevřené otázky

1. **HTML konverze:** MD→HTML vlastním minimálním converterem (bez nové dependency) vs. přidat `markdown` knihovnu (rychlá, ale nová dep). → Doporučuji **vlastní converter** (layout je plně pod kontrolou, cca 80 řádků), protože už teď generujeme strukturovaný MD bez komplexní syntaxe.
2. **Velikost match fontu v MD:** `.md` sám o sobě font nenese — 8pt se projeví až v `.html`/PDF. V MD zůstává tag `🔑 match:` a HTML render ho styluje na 8pt.
3. **deadline:** `Ad.date` je string; parsování "končí brzy" vyžaduje normalizaci (jobs.cz ISO vs. prace.cz text). → fáze 3, MED.
4. **ASCII názvy souborů:** nové `.html` výstupy `etl_{profile}_{ts}.html` — ASCII, OK.

---

## 7. Odsouhlasení

| Otázka | Autor |
|---|---|
| OK s architekturou (report.py + report_style.py)? | ☐ |
| CSS: metadata všechny na 8pt, nebo jen `.match`? | ☐ |
| Vlastní MD→HTML converter vs. závislost `markdown`? | ☐ |

*Plán připraven: 2026-08-15. Bez commitu do odsouhlasení (R4).*
