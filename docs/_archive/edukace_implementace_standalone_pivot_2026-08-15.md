# Edukační & implementační artefakt: pivot MCP-jobs na standalone produkt + adopce SWE skills

**Datum:** 2026-08-15 | **Autor:** outpost2026
**Účel:** Propojení aspiračního pivota MCP-jobs na standalone software s adopční metodikou SWE skills (60/20/10/10) — edukační výklad + konkrétní implementační plán přímo na reálné soubory repozitáře.
**Typ:** edukační + implementační | **Doména:** skill acquisition, produktový pivot, DevOps, full-stack
**Návaznost:** `docs/edukace_port_standalone_2026-08-15.md`, `docs/plan_refaktor_2026-08-15.md`, `docs/analyza_output_formatu_2026-08-15.md`, KB `01_METODIKY/04_skill_acquisition/ADOPCNI_METODOLOGIE_2026_v1.md`, KB `01_METODIKY/04_skill_acquisition/SKILL_GAPS_ROZBOR_Q3_2026_v2.md`, KB `02_ANALYZY/07_CV_automatizace/CV_YOLO11_ADOPTION_ASSESSMENT_v1.md`
**Provenance:** source-read (pyproject.toml, scripts/run_etl.py, config.yaml, src/mcp_jobs/*) + Summary (navazuje na předchozí artefakty z vlákna)

---

## 1. Východisko — kde MCP-jobs dnes je (ground truth)

### 1.1 Reálný stav repozitáře (2026-08-15, source-read)

```
MCP-Jobs/
├── pyproject.toml            # v0.4.0, FastMCP>=3.0.0, requests, bs4, pyyaml
├── config.yaml               # PRIMÁRNÍ matice: 8 query, 4 portály, exclude pool
├── config_legacy_manual.yaml # fallback (6 manuálních query)
├── src/mcp_jobs/
│   ├── server.py             # MCP server (STDIO) — 5 nástrojů
│   ├── pipeline.py           # SearchPipeline (scrape → boolean match)
│   ├── matcher.py            # boolean matcher, word-boundary, diakritika
│   ├── report.py             # unified MD+HTML renderer (vlastní konvertor)
│   ├── report_style.py       # CSS: Calibri, 8pt meta, A4 @page
│   ├── storage.py            # correlation cache, timestamped save
│   ├── config.py             # UserConfig (YAML → objekty)
│   ├── models.py             # Ad model
│   └── providers/            # base + 4 portály (jobs, bazos, pracecz, nyx)
├── scripts/run_etl.py        # CLI: plný ETL běh → output/*.{json,md,html}
├── tests/                    # 11 test modulů (pytest), ruff clean
└── output/                   # etl_*.{json,md,html} + etl_latest_* per profil
```

**Klíčové číselné metadaty (z E2E běhů 2026-08-15, ověřeno):**

| Běh | Doba | Matched | Raw | Precision |
|-----|:----:|:-------:|:---:|:---------:|
| AI-NATIVE (`etl_AI_NATIVE_20260815_124639`) | 54 s | 28 | 2113 | 1.3 % |
| LEGACY-MANUAL (`etl_LEGACY_MANUAL_20260815_125235`) | 45.9 s | 40 | ~2100 | 1.9 % |

**Závěr ground truth:** pipeline je **funkční a otestovaná** (129 testů PASS), má **unified report renderer** (MD+HTML), per-profile `latest` výstupy, correlation cache. Chybí jí celá **produkční vrstva**: DB persistence, automatizace, monitoring, web UI.

### 1.2 Co je aktuálním deliverable

Dnes je deliverable = **MCP server běžící přes STDIO z IDE (opencode)** + CLI `scripts/run_etl.py` + výstupní soubory `output/*.{json,md,html}`.

**Aspirace (pivot):** deliverable = **standalone produkt** — samostatná web app s GUI, DB, cronem a monitoringem, hostovaná na `systeq.cz`.

> **Deliverable = forma, ve které produkt běží.** Nejde jen o to, *co* pipeline dělá (scrape+match), ale *jak a kde* běží (ručně z IDE vs. samostatně s UI).

---

## 2. Edukační část — co musím pochopit pro pivot

> Tato sekce vysvětluje nové pojmy od základu (junior, praxe < 5 měsíců). Každý pojem je vztažen na konkrétní soubor MCP-Jobs.

### 2.1 MCP server vs. standalone produkt

| Vrstva | MCP-jobs dnes | Standalone cíl |
|--------|---------------|----------------|
| Spouštění | Na vyžádání z klienta (opencode) | Samostatně (server/daemon) |
| UI | Žádné (LLM konzumuje výstup) | Web GUI na systeq.cz |
| Perzistence | `output/*.json,.md` soubory | PostgreSQL |
| Automatizace | Ruční `python scripts/run_etl.py` | Cron (denně 5:00) |
| Monitoring | Manuální kontrola | healthchecks.io |
| Distribuce | MCP konfigurace | Vercel / Docker / VPS |

**Insight:** `scripts/run_etl.py` je **už dnes CLI pipeline** — oddělená od MCP serveru. To je základní pattern, na kterém standalone staví (viz outprep: `fide-pipeline` CLI oddělené od webu).

### 2.2 Adopční metodika 60/20/10/10 (z KB ADOPCNI_METODOLOGIE)

Pivot není jen úkol — je to **PBL (Project-Based Learning) projekt**, na kterém se adoptují nové SWE skills. Rozdělení času:

| Podíl | Metoda | V pivotu konkrétně |
|:-----:|--------|--------------------|
| **60 %** | PBL (praxe) | Implementace fází 0–4 (níže) na reálném MCP-jobs |
| **20 %** | Feynman → Glossary | Nové termíny (SQL, Docker, cron, Next.js...) zapsat do KB SWE_GLOSSARY |
| **10 %** | SRS (opakování) | Flashcards z nových termínů (FSRS engine) |
| **10 %** | Concept Mapping | Mapa: ETL → DB → API → UI → cron |

**Guardrail:** Glossary nikdy nepřesáhne 20 % času. Termíny se zapisují jen z **reálného kontextu**, ne akademicky.

### 2.3 Transfer learning — co už umím a přenese se

| Autorův skill (doloženo kódem) | Aplikace v pivotu | Transfer |
|--------------------------------|-------------------|:--------:|
| Python ETL (`scripts/run_etl.py`) | Backend logika, scrape → DB | Přímý |
| pytest (129 testů) | CI: test na push | Přímý |
| report.py + report_style.py (MD+HTML) | Export do PDF/web | Přímý |
| correlation_cache | → nahradit UNIQUE index v DB | Near |
| config.yaml (YAML) | Konfigurace zůstává YAML | Přímý |
| Docker → Cloud Run (z jiných rep) | docker-compose (postgres) | Near |
| Streamlit dashboard | → Next.js UI | Novel (30-50 %) |
| Soubory jako persistence | → PostgreSQL | Novel |

### 2.4 Nové skill gapy, které pivot vytahuje (z SKILL_GAPS v2)

| Gap | EROI | Čas | Role v pivotu |
|-----|:----:|:---:|---------------|
| **TypeScript + Next.js + monorepo** | 9/10 | 25–35 h | GUI na systeq.cz, API routes |
| **PostgreSQL + schema + migrace** | 8.5/10 | 15–20 h | Produkční perzistence, dedup, historie |
| **DevOps: Docker, cron, monitoring** | 8/10 | 15–20 h | Automatizace ELT, healthchecks, CI |

**Priorita (dle EROI/hod):** PostgreSQL (0.49) > DevOps (0.46) > TS+Next (0.30). Proto implementační plán začíná DevOps a DB, TS+Next až ve fázi 2.

---

## 3. Implementační část — fáze pivota na reálných souborech

> Každá fáze je **reverzibilní** (dle CI_CD_INTEGRACE_PROTOKOL: mazání = návrat). Každá fáze končí **měřitelným milníkem**.

### FÁZE 0 — CI + automatizace stávající pipeline (týden 1, ~8 h) — Gap ❸ DevOps

**Cíl:** Pipeline běží sama + víš o selhání. Bez nového jazyka.

| Krok | Soubor k vytvoření | Co dělá |
|------|--------------------|---------|
| 1. CI | `.github/workflows/ci.yml` | Na každý push: `pip install -r requirements.txt`, `pytest`, `ruff check src/` |
| 2. Cron | Windows Task Scheduler (nebo `scripts/schedule.ps1`) | Deně 5:00 → `python scripts/run_etl.py --config config.yaml` |
| 3. Monitoring | `scripts/healthcheck.py` | Na konci běhu → `requests.get(HEALTHCHECKS_URL)` (ping) |

**Milník:** `git push` → CI zelený do 60 s. Cron běží bez IDE. healthchecks.io pípne email při selhání.

**Transfer:** pytest → CI test step (přesně dle CI_CD_INTEGRACE_PROTOKOL, který už existuje v KB).

### FÁZE 1 — PostgreSQL persistence (týden 2–3, 15–20 h) — Gap ❷ DB

**Cíl:** Soubory → databáze. Nativní dedup + historie + audit.

| Krok | Soubor k vytvoření | Co dělá |
|------|--------------------|---------|
| 1. Schema | `data/schema.sql` | Tabulky `ads` (URL UNIQUE = dedup) + `pipeline_runs` (audit) |
| 2. Infra | `docker-compose.yml` | `postgres:16`, port 5432, mount schema |
| 3. Klient | `src/mcp_jobs/db.py` (nový modul) | Provider-agnostic připojení (`DATABASE_URL` env), upsert ads |
| 4. Integrace | upravit `scripts/run_etl.py` | Po běhu: INSERT/UPDATE ads + `pipeline_runs` record (running→completed/failed) |

**Schema (vzor):**
```sql
CREATE TABLE IF NOT EXISTS ads (
  id SERIAL PRIMARY KEY,
  url TEXT NOT NULL UNIQUE,          -- nativní dedup (nahrazuje correlation_cache)
  title TEXT, company TEXT, location TEXT, salary TEXT,
  description TEXT,
  matched_keyword TEXT,
  portal TEXT,
  query_name TEXT,
  first_seen DATE DEFAULT CURRENT_DATE,
  last_seen DATE DEFAULT CURRENT_DATE,
  status TEXT DEFAULT 'new'          -- new / seen / applied / rejected
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
  id SERIAL PRIMARY KEY,
  profile TEXT NOT NULL,
  status TEXT DEFAULT 'running',     -- running / completed / failed
  matched INT, raw INT,
  started_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  metadata JSONB DEFAULT '{}'
);
```

**Milník:** 1 reálný run → data v DB, dotaz `SELECT * FROM ads WHERE status='new'` vrací inzeráty. Dedup: stejný inzerát ve 2 bězích = 1 řádek.

### FÁZE 2 — TS + Next.js GUI (týden 4–6, 25–35 h) — Gap ❶ TS/Next

**Cíl:** První standalone web čtoucí **Postgres z fáze 1** (ne soubory!).

| Krok | Soubor k vytvoření | Co dělá |
|------|--------------------|---------|
| 1. TS základy | `packages/core/` (nový) | Přepis 1 python modulu (např. matcher.py) do TS |
| 2. Next.js app | `app/` (nový monorepo adresář) | Dashboard: seznam inzerátů, filter, priority |
| 3. API routes | `app/api/jobs/route.ts`, `app/api/report/route.ts` | GET z Postgres, export reportu (PDF — HTML+CSS renderer existuje!) |

**Proč monorepo:** MCP-jobs je **multi-repo** (každý MCP zvlášť). Standalone chce **monorepo** — jedno repo, oddělené balíčky (ETL / core / UI). Vzor: outprep `packages/*`.

**Milník:** `systeq.cz` zobrazuje dnešní inzeráty z DB. Export reportu (Calibri/A4) funguje jako PDF.

### FÁZE 3+ — pokračování (mimo MCP-jobs repo)

AZ-900 (SRS, paměťová doména), PLC (PBL, doménový přesah). Detaily viz KB SKILL_GAPS v2 trajektorie.

---

## 4. Mapování stávajících modulů na novou architekturu

| Dnešní modul (MCP-Jobs) | Standalone role | Přesun / port |
|-------------------------|-----------------|---------------|
| `scripts/run_etl.py` | `packages/etl` (CLI) | Zůstává, přidá se DB write |
| `src/mcp_jobs/matcher.py` | `packages/core` | Port do TS (učení) NEBO zůstává Python volaný API |
| `src/mcp_jobs/report.py` + `report_style.py` | Web export / PDF | Reuse v Next.js (HTML render) |
| `src/mcp_jobs/storage.py` | → `db.py` (Postgres) | **Nahrazeno** — soubory → DB |
| `src/mcp_jobs/pipeline.py` | `packages/etl` | Zůstává Python |
| `config.yaml` | Konfigurace (YAML) | Zůstává |
| `src/mcp_jobs/server.py` (MCP) | MCP vrstva pro IDE | Zůstává vedle webu (nebo odpadá) |

**Klíčové rozhodnutí:** **MCP server NEMUSÍ zaniknout.** Standalone je *doplněk* — stejná pipeline, nový deliverable. MCP zůstává pro agentní použití, web pro lidské. Oba čtou stejnou DB.

---

## 5. Edukační slovníček — nové pojmy pivota (Feynman → glossary)

> Každý pojem vysvětlen tak, jak by byl zapsán do SWE_GLOSSARY.

| Pojem | Definice (vlastními slovy) | Analogie z mé praxe |
|-------|---------------------------|---------------------|
| **Standalone** | Aplikace běžící sama, nezávisle na klientovi | MCP server → web app |
| **Deliverable** | Forma, ve které produkt běží a je doručen | MD soubor → web na doméně |
| **Monorepo** | Jedno repo, více balíčků | `_github` má každý MCP zvlášť |
| **npm workspaces** | Monorepo mechanismus v JS | — (nové) |
| **PostgreSQL** | Relační databáze (tabulky, SQL) | `output/*.json` ale s dotazováním |
| **Schema** | Definice tabulek a sloupců | struktura JSON, ale vynucená |
| **Migrace** | Evoluce schématu, idempotentní | versioning kódu, ale pro DB |
| **JSONB** | JSON sloupec v Postgres | uložení `summary` z run_etl.py |
| **UNIQUE index** | Dedup — hodnota se neopakuje | nahrazuje correlation_cache |
| **Cron** | Plánovač úloh | Windows Task Scheduler |
| **healthchecks.io** | Dead-man's-switch monitoring | ping = "žiju" |
| **CI/CD** | Auto build+test+deploy na push | pytest po každém pushi |
| **Port** | Číslo, na kterém služba poslouchá | 5432 = Postgres, 3000 = Next.js |
| **Provider-agnostic** | Funguje s jakýmkoli hostem | `DATABASE_URL` → Neon/Supabase/Docker |
| **Next.js** | React framework (API routes + UI) | Streamlit ale produkční |
| **API route** | HTTP endpoint v Next.js | MCP tool ale přes HTTP |

---

## 6. Milníky a metriky úspěchu (měřitelné)

| Milník | Čas | Důkaz |
|--------|:---:|-------|
| CI zelený na push | T1 | GitHub Actions badge / zelený run |
| Cron běží 7 dní bez výpadku | T1–2 | healthchecks.io heartbeat |
| Reálný run → DB, dedup funguje | T2–3 | `SELECT COUNT(*)` vs. `output/*.json` počet unikátů |
| `pipeline_runs` audit 5+ běhů | T3 | `SELECT status, count(*) GROUP BY status` |
| Web na systeq.cz zobrazuje data | T6 | Prohlížeč → doména → seznam inzerátů |
| PDF export (Calibri/A4) | T6 | Report z webu jako soubor |

---

## 7. Rizika a mitigace

| Riziko | Pravděpodobnost | Mitigace |
|--------|:---------------:|----------|
| **TS/Next = největší časová investice (0.30/h)** | Jistota | Dělat až po Fázích 0–1 (které mají vyšší EROI/hod) |
| **Scope creep** (vše najednou) | Vysoká | Striktní fáze, každá reverzibilní (vzor CI_CD protokol) |
| **Python → TS port matcheru** | Střední | Portovat až v Fázi 2; matcher může zůstat Python volaný API |
| **Přepisování LLM kódu bez pochopení** | Střední | Anti-blackbox: každý výstup vysvětlit vlastními slovy (Feynman) |
| **DB únik dat (scraped data)** | Nízká | `DATABASE_URL` v `.env` (gitignored), žádné credentials v gitu |
| **SRS opuštěno** | Vysoká | 10 min/den fixní, LLM generuje karty |

---

## 8. Co tento pivot adoptuje (skills → portfolio)

| Skill | Úroveň po pivotu | Důkaz v portfoliu |
|-------|:----------------:|-------------------|
| PostgreSQL / SQL | Základy–produkční | `data/schema.sql`, `src/mcp_jobs/db.py` |
| Docker Compose | Produkční | `docker-compose.yml` |
| Cron + monitoring | Produkční | healthchecks.io heartbeat |
| CI/CD (GitHub Actions) | Produkční | `.github/workflows/ci.yml` |
| TypeScript / Next.js | Základy–PoC | `packages/core`, `app/` |
| API routes | Základy | `app/api/jobs/route.ts` |
| Monorepo organizace | Základy | struktura `packages/*` |

**B2B signál:** po pivotu umí autor **produkovat standalone software** — ne jen MCP servery. To je skok z "knihovny pro LLM" na "produkt pro lidi".

---

## 9. Souhrn — logika celého artefaktu

```
MCP-jobs dnes (MCP server, soubory, ruční běh)
        │
        ▼  FÁZE 0: CI + cron + monitoring (DevOps, ~8 h)     → běží sama, víš o selhání
        ▼  FÁZE 1: PostgreSQL (DB, 15–20 h)                  → dedup, historie, audit
        ▼  FÁZE 2: TS + Next.js GUI (25–35 h)                → standalone web na systeq.cz
        ▼
Standalone produkt (deliverable: web app) + MCP server (zůstává pro IDE)
        │
        └── každá fáze = PBL = adopce skillu (60/20/10/10), termíny → glossary
```

**7 pravidel adopce (z ADOPCNI_METODOLOGIE), aplikovaná na pivot:**
1. **Praxe > dokumentace** — každá fáze = reálný artefakt, ne čtení.
2. **Vysvětli vlastními slovy** — každý nový pojem zapsat do glossary.
3. **Opakuj, nebo zapomeň** — SRS karty z nových termínů.
4. **Mapuj vztahy** — ETL → DB → API → UI → cron.
5. **Anti-blackbox** — každý LLM výstup projít.
6. **Kvalita > kvantita** — 30 kontextovaných termínů > 300 definic.
7. **Živý systém** — plán, glossary, koncept mapy průběžně aktualizovat.

---

*Dokument vytvořen: 2026-08-15 | Autor: outpost2026*
*Provenance: source-read (pyproject.toml, scripts/run_etl.py, config.yaml, src/mcp_jobs/*) + Summary (předchozí artefakty vlákna)*
*Návaznost: docs/edukace_port_standalone_2026-08-15.md, KB ADOPCNI_METODOLOGIE_2026_v1, KB SKILL_GAPS_ROZBOR_Q3_2026_v2, KB CV_YOLO11_ADOPTION_ASSESSMENT_v1*