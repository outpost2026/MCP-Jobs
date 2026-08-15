# Edukační dokument: Fáze 1 — PostgreSQL persistence (standalone pivot)

**Datum:** 2026-08-15 | **Autor:** outpost2026 (junior dev, praxe < 5 měsíců) | **Verze:** 1.0
**Účel:** Retrospektivní vysvětlení všech změn, které byly v MCP-Jobs provedeny během pivota na standalone produkt — od nuly, bez předpokladu znalosti Dockeru, databází ani CI. Dokument odpovídá na otázky: co bylo změněno, proč, jak nové nástroje fungují a co se stane, když neběží.
**Kontext vlákna:** Pivot MCP-Jobs (MCP server → standalone produkt). Fáze 0 = CI + monitoring. Fáze 1 = PostgreSQL persistence.
**Návaznost:** `docs/edukace_implementace_standalone_pivot_2026-08-15.md`, `docs/edukace_port_standalone_2026-08-15.md`, KB `SKILL_GAPS_ROZBOR_Q3_2026_v2.md` (gap ❷ PostgreSQL, ❸ DevOps)
**Provenance:** source-read (všechny soubory Fáze 1: `src/mcp_jobs/db.py`, `data/schema.sql`, `docker-compose.yml`, `scripts/run_etl.py`, `tests/test_db.py`, `.github/workflows/ci.yml`, `pyproject.toml`, `.gitignore` + reálné ETL běhy 2026-08-15 s DB)

---

## 0. TL;DR — odpovědi na tři otázky, které tě trápí

| Otázka | Odpověď |
|---|---|
| **Poběží pipeline bez zapnutého Dockeru?** | **ANO.** DB je doplněk, ne nutnost. Když `DATABASE_URL` chybí nebo DB nedostupná, pipeline běží přesně jako předtím (soubory `output/*.json,.md`) a jen vypíše varování. |
| **Co je Docker a proč tam je?** | Docker = „kontejnerový box", který v izolaci spouští PostgreSQL tak, aby se neinstaloval do Windows a nekolidoval se systémem. Je to **nástroj pro provoz databáze**, ne pro samotný MCP-jobs. |
| **Co PostgreSQL dělá?** | Ukládá inzeráty jako **řádky v tabulce** místo souborů. Dává historii (kdy byl inzerát poprvé/posledně viděn), nativní dedup (stejný inzerát = 1 řádek), audit běhů a možnost dotazovat se SQL. |

**Základní jistota:** žádný ze souborů Fáze 1 nemění chování MCP serveru (STDIO nástroje z IDE) ani logiku pipeline. Přidává **novou vrstvu na konci běhu**: co se dřív končilo zápisem souborů, se teď navíc propisuje do databáze.

---

## 1. Velký obraz — kam celý pivot směřuje

### 1.1 Dnešní stav vs. před 15 minutami

```
PŘED (v0.4.0, commit 1aa327e):
  MCP-jobs = MCP server (IDE) + scripts/run_etl.py (ruční běh)
  Výstup: output/*.json, .md, .html  ← jen soubory, žádná historie

PO (commit 7f42b4b):
  MCP-jobs = MCP server + run_etl.py + [CI] + [cron] + [healthcheck] + [PostgreSQL]
  Výstup: soubory (jako dřív) + databáze (nově)
```

### 1.2 Co je to „standalone pivot" a kde jsme

Aspirace (z edukačního dokumentu): MCP-jobs má přestat být jen knihovnou pro LLM agenta a stát se **samostatným produktem** — web aplikací na systeq.cz, která běží sama, s databází, automatizací a GUI.

Pivot probíhá ve fázích. Každá fáze = jeden skill gap (dle SKILL_GAPS v2):

| Fáze | Gap | Co dělá | Stav |
|:----:|-----|---------|:----:|
| 0 | ❸ DevOps | CI + cron + healthcheck (pipeline běží sama) | ✅ DONE |
| **1** | **❷ PostgreSQL** | **Persistentní databáze (historie, dedup, audit)** | **✅ DONE (tento dokument)** |
| 2 | ❶ TS/Next.js | Web GUI na jobs.systeq.cz | ⏳ budoucí |

---

## 2. Co přesně bylo změněno — soubor po souboru

### 2.1 Přehled (9 souborů, commit `7f42b4b`)

| Soubor | Nový/změněný | Co dělá |
|--------|:---:|---------|
| `data/schema.sql` | 🆕 | Definice tabulek („návrh domu" databáze) |
| `docker-compose.yml` | 🆕 | Spouští PostgreSQL v kontejneru jedním příkazem |
| `src/mcp_jobs/db.py` | 🆕 | Python kód, který čte/zapisuje do databáze |
| `scripts/run_etl.py` | ✏️ | Na konci běhu volá `db.py` (s graceful fallbackem) |
| `tests/test_db.py` | 🆕 | 5 testů databázové vrstvy |
| `.github/workflows/ci.yml` | ✏️ | Přidán PostgreSQL service → DB testy běží i v CI |
| `pyproject.toml`, `requirements.txt` | ✏️ | Přidána závislost `psycopg[binary]>=3.1` |
| `.gitignore` | ✏️ | Výjimka, aby se `schema.sql` commitoval, ale scrap data ne |

### 2.2 Proč zrovna tato čtveřice souborů?

Databáze v praxi = **4 věci**, které musíš mít:

```
1. Schema (definice)      → data/schema.sql
2. Provozní prostředí     → docker-compose.yml  („kde DB běží")
3. Klient (kód)           → src/mcp_jobs/db.py  („jak Python mluví s DB")
4. Napojení do pipeline   → scripts/run_etl.py  („kdy se DB zapisuje")
```

Nic z toho neexistovalo. Muselo vzniknout vše čtyři — chybí-li jedno, celek nefunguje.

---

## 3. Nový nástroj č. 1: Docker — co to je, proč tam je

### 3.1 Co je Docker (od základu)

Docker je nástroj, který spouští aplikace v **izolovaných kontejnerech**.

**Analogie:** přepravní kontejner na lodi. V něm je zabalený celý svět aplikace (program + nastavení + data). Kontejner se odváží kamkoliv a funguje stejně — na tvém notebooku, na serveru, u zákazníka. Nic se neinstaluje do systému; kontejner má vlastní „mini-OS".

**Proč to děláme:**
- **Čistota Windows:** PostgreSQL se nemusí instalovat jako služba do Windows (nechceš cizí databázi v systémových službách).
- **Reprodukovatelnost:** kontejner postgres:16 je všude identický — lokálně, v CI (GitHub Actions), později na serveru.
- **Snadné smazání:** `docker compose down` → DB zmizí beze stopy (vč. dat).

### 3.2 Klíčové pojmy

| Pojem | Význam | V MCP-Jobs |
|-------|--------|-----------|
| **Image** | „Forma / šablona" — hotový zabalený program | `postgres:16` (oficiální image databáze) |
| **Container** | Běžící instance image | `mcp-jobs-postgres` |
| **Daemon** | Docker pozadí („motor"), musí běžet | Docker Desktop |
| **Port** | Adresa, na které služba poslouchá | DB poslouchá na **5432** |
| **Volume** | Trvalé úložiště dat (přežije restart) | `mcp_jobs_pgdata` |
| **Compose** | Definice více služeb v YAML | `docker-compose.yml` |

### 3.3 Konkrétně v MCP-Jobs — `docker-compose.yml`

```yaml
services:
  postgres:
    image: postgres:16                    # použij oficiální PostgreSQL verze 16
    ports: ["5432:5432"]                  # host:kontejner — Python mluví na localhost:5432
    environment:                          # přihlašovací údaje (vytvořeny při startu)
      POSTGRES_USER: mcpjobs
      POSTGRES_PASSWORD: mcpjobs
      POSTGRES_DB: mcpjobs
    volumes:
      - mcp_jobs_pgdata:/var/lib/postgresql/data   # data přežijí restart kontejneru
      - ./data/schema.sql:/docker-entrypoint-initdb.d/01-schema.sql:ro  # schema se spustí při prvním startu
    healthcheck:                          # „je DB už připravená?" — čeká se na pg_isready
      test: ["CMD-SHELL", "pg_isready -U mcpjobs -d mcpjobs"]
```

**Co se děje při `docker compose up -d`:**
1. Docker stáhne image `postgres:16` (poprvé; pak je lokálně uložený)
2. Vytvoří kontejner + volume pro data
3. **Při prvním startu** automaticky spustí `data/schema.sql` (protože je v `initdb.d`) → tabulky vzniknou
4. Kontejner běží na portu 5432 a čeká na připojení

**Důležité:** data se ukládají do volume `mcp_jobs_pgdata`. Když kontejner zastavíš a znovu spustíš, data zůstanou. Když spustíš `docker compose down` bez `-v`, data zůstanou taky. (`down -v` = smazat i data.)

### 3.4 Ovládání (cheat sheet)

```powershell
docker compose up -d              # start DB (detached)
docker compose ps                 # stav: healthy = připraveno
docker compose down               # stop kontejneru (data zůstávají)
docker compose down -v            # stop + smazat data (úplný reset)
docker compose logs postgres      # logy DB
```

---

## 4. Nový nástroj č. 2: PostgreSQL — co to dělá a proč nestačí soubory

### 4.1 Soubory nejsou databáze

Dosud MCP-jobs ukládal výsledky jako `output/etl_*.json`. Tři problémy:

| Problém souborů | Řešení databáze |
|---|---|
| **Žádná historie** — nevíš, který inzerát tu byl včera a je tu zase | Řádky s `first_seen` / `last_seen` |
| **Žádný dedup napříč běhy** — stejný inzerát se objeví každý den znovu | `UNIQUE` index na URL → 1 řádek = 1 inzerát |
| **Žádné dotazování** — jen čteš celý soubor | SQL: `SELECT ... WHERE company = 'X'` |

**Analogie:** soubory jsou jako papír s výpisem. Databáze je jako **evidence s kartotékou** — každý inzerát má svoji kartu, na kartě je kdy přišel, kdy naposledy, jakou má status. Můžeš se ptát: „dej mi všechny inzeráty s Pythonem, co přišly tento týden".

### 4.2 Co je SQL

SQL = jazyk, kterým se s databází mluví. Příklady z MCP-Jobs:

```sql
CREATE TABLE ads (...);                  -- vytvoř evidenci inzerátů
INSERT INTO ads (url, ...) VALUES (...); -- přidej inzerát
ON CONFLICT (url) DO UPDATE ...;         -- pokud URL už existuje, aktualizuj
SELECT * FROM ads WHERE status='new';    -- dotaz: nové inzeráty
```

### 4.3 Ontologie PostgreSQL (nové pojmy, které Fáze 1 zavedla)

```
PostgreSQL
├── Tabulka (table)        = evidence (sloupce = typy, řádky = záznamy)
├── Řádek (row)            = jeden inzerát / jeden běh
├── Sloupec (column)       = jedno pole (title, url, status ...)
├── PRIMARY KEY / SERIAL   = auto ID, jednoznačný identifikátor
├── UNIQUE index           = hodnota se nesmí opakovat (dedup!)
├── JSONB                  = JSON sloupec (metadata běhu, flexibilní)
├── Index                  = „obsahový rejstřík" pro rychlé dotazy
├── Query / SELECT         = dotaz
└── Migration              = evoluce schématu (idempotentní — IF NOT EXISTS)
```

---

## 5. Jádro kódu — jak Python mluví s databází (`src/mcp_jobs/db.py`)

### 5.1 Vrstvy komunikace

```
scripts/run_etl.py  (pipeline, znáš ho)
        │  volá
        ▼
src/mcp_jobs/db.py  (NOVÝ — obsluha databáze)
        │  používá
        ▼
psycopg             (ovladač PostgreSQL pro Python, nová závislost)
        │  TCP na portu 5432
        ▼
PostgreSQL          (kontejner v Dockeru, tabulky ads + pipeline_runs)
```

### 5.2 Funkce v db.py a jejich role

| Funkce | Role | Klíčová myšlenka |
|--------|------|------------------|
| `get_database_url()` | Přečte `DATABASE_URL` z prostředí | Prázdné = DB vypnutá |
| `connect()` | Otevře připojení k DB | Provider-agnostic: Docker/Neon/Supabase = jen jiná URL |
| `init_db()` | Spustí `schema.sql` | **Idempotentní** — `IF NOT EXISTS`, dá se spustit opakovaně |
| `start_run()` | Vloží řádek do `pipeline_runs` (status=running), vrátí ID | Začátek auditu běhu |
| `finish_run()` | Označí běh completed/failed + počty | Konec auditu běhu |
| `upsert_ads()` | Vloží/aktualizuje inzeráty | **Srdce dedup** — viz níže |
| `persist_run()` | Orchestruje celý zápis | Try/except → graceful skip |

### 5.3 Nejzajímavější kus: dedup bez duplicit (`upsert_ads`)

```sql
INSERT INTO ads (url, ...)
VALUES (...)
ON CONFLICT (url) DO UPDATE SET ...   -- URL už existuje → místo insertu UPDATE
RETURNING (xmax = 0) AS inserted
```

**Jak to funguje (fyzická realita, ne teorie):**
1. PostgreSQL má `UNIQUE` index na sloupci `url` (z `schema.sql`).
2. Při běhu se snaží vložit inzerát.
3. `ON CONFLICT (url)`: pokud inzerát s touto URL **už existuje**, místo duplicitního řádku se stávající **aktualizuje** (`last_seen` na dnešek, nový title, nová salary...).
4. `RETURNING (xmax = 0)`: trik — v PostgreSQL vrací `true` jen pro **nově vložené** řádky. Díky tomu víme, kolik inzerátů je opravdu nových (`new_count`).

**Důsledek:** stejný inzerát ve dvou bězích = **1 řádek**. A status se nepřepisuje — takže když inzerát označíš jako `applied`, nezmizí ti to dalším během (update nemění `status`).

### 5.4 Graceful degradation (proč pipeline běží bez Dockeru)

`persist_run()` je celý zabalený v try/except a vrátí `None`, když se cokoliv nepovede:

```python
try:
    if _db is None:
        _db = connect()          # selže, když DATABASE_URL chybí → RuntimeError
    ...
except (RuntimeError, ImportError) as e:
    logger.warning("DB write skipped: %s", e)
    return None
```

A `run_etl.py` to obaluje znovu:

```python
try:
    run_id = persist_run(...)
except Exception as e:
    print(f"Warning: DB persistence skipped: {e}", file=sys.stderr)
```

**Následek (ověřeno):** když spustíš ETL bez Dockeru, uvidíš:

```
Saved: output\etl_AI_NATIVE_....json
Report: output\etl_AI_NATIVE_....md
Warning: DB persistence skipped: DATABASE_URL not set - DB write skipped
```

A soubory se vygenerují **stejně jako předtím**. DB je volitelné zlepšení, ne podmínka běhu.

---

## 6. Změny chování MCP-jobs — co je jinak

### 6.1 Co se NEzměnilo (klíčová jistota)

| Vrstva | Beze změny |
|--------|-----------|
| MCP server (`src/mcp_jobs/server.py`) | ✅ — nástroje, STDIO, config |
| Pipeline (scrape → boolean match) | ✅ |
| Matcher / report / storage souborů | ✅ |
| Konfigurace (config.yaml) | ✅ |
| Spouštění z IDE | ✅ |

### 6.2 Co se změnilo (přidáno na konci běhu)

| Změna | Projev |
|-------|--------|
| Nová závislost `psycopg` | Vyžaduje `pip install` (již v requirements) |
| Po běhu ETL se píše do DB | `DB: run N persisted` v konzoli |
| Pokud DB neběží | `Warning: DB persistence skipped: ...` — běh pokračuje |
| CI má PostgreSQL service | DB testy běží v GitHub Actions |
| Cron (Fáze 0) teď umí zapisovat do DB | Stačí `DATABASE_URL` v `.env` |

### 6.3 Rozdíl proti předchozí verzi (souhrn 1aa327e → 7f42b4b)

```
+ data/schema.sql          (2 tabulky: ads, pipeline_runs + indexy)
+ docker-compose.yml       (postgres:16)
+ src/mcp_jobs/db.py       (151 řádků: connect/init/start/finish/upsert/persist)
+ tests/test_db.py         (5 integration testů)
~ scripts/run_etl.py       (+20 řádků: DB persistence s fallbackem)
~ pyproject.toml, requirements.txt  (+psycopg[binary]>=3.1)
~ .github/workflows/ci.yml (+postgres service, DATABASE_URL)
~ .gitignore               (+data/*, !data/schema.sql, src/data/)
```

---

## 7. Životní cyklus jednoho běhu — celý příběh

Co se stane, když spustíš `python -X utf8 scripts/run_etl.py --config config.yaml` (s běžícím Dockerem):

```
1. Pipeline scrapne 4 portály, boolean match proti 8 query     (~50 s)
2. Uloží soubory: output/etl_*.json, .md, .html               (jako dřív)
3. Uloží correlation_cache.json                                (jako dřív)
4. db.persist_run():
   a. connect() → připojí se na localhost:5432
   b. init_db() → spustí schema.sql (idempotentně, bezpečně)
   c. start_run() → INSERT do pipeline_runs (status=running)  → run_id
   d. upsert_ads() → každý inzerát INSERT ... ON CONFLICT (url)
   e. finish_run() → status=completed, matched/raw/metadata
5. Konzole: "DB: run N persisted"
```

**Ověřený výsledek (reálné běhy 2026-08-15):**

| Běh | Co se stalo | V DB |
|-----|-------------|------|
| run 2 | 27 matched, 2112 raw | 24 inzerátů nově vloženo |
| run 3 | 27 matched, 2112 raw | **0 nových** (dedup!) → celkem 26 řádků (2 z testů) |

`SELECT * FROM ads WHERE status='new'` → vrací 26 inzerátů. Dedup **funkčně ověřen**: run 3 přidal 0 řádků, jen aktualizoval `last_seen`.

---

## 8. Testy — jak se Fáze 1 ověřuje

`tests/test_db.py` = 5 integration testů. **Auto-skip:** bez `DATABASE_URL` se přeskočí (aby běžná `pytest` nezela na lidech bez DB).

| Test | Co dokazuje |
|------|-------------|
| `test_upsert_dedup_single_row` | 2× upsert stejné URL = **1 řádek** (dedup) |
| `test_upsert_updates_last_seen_on_conflict` | Update zachovává `status`, mění `query_name` |
| `test_run_lifecycle` | `pipeline_runs`: running → completed s počty |
| `test_persist_run_graceful_without_db` | Bez DATABASE_URL → vrátí `None` (nespadne) |
| `test_persist_run_creates_run_and_ads` | Kompletní persist → 1 run + 2 ads |

Lokální spuštění (Docker běží):

```powershell
docker compose up -d
$env:DATABASE_URL = "postgres://mcpjobs:mcpjobs@localhost:5432/mcpjobs"
python -X utf8 -m pytest tests/test_db.py -v
```

Celá suite: **142/142 PASS** (137 původních + 5 nových).

---

## 9. Proč CI teď startuje PostgreSQL (`ci.yml`)

GitHub Actions umí spustit **service container** — na CI runneru se na chvíli nastartuje PostgreSQL, testy běží proti němu, pak se zničí:

```yaml
services:
  postgres:
    image: postgres:16
    env: { POSTGRES_USER: mcpjobs, POSTGRES_PASSWORD: mcpjobs, POSTGRES_DB: mcpjobs }
    ports: ["5432:5432"]
env:
  DATABASE_URL: postgres://mcpjobs:mcpjobs@localhost:5432/mcpjobs
```

Důvod: DB testy mají smysl jen když se skutečně vykonají. Bez service by v CI byly vždy přeskočené a nikdo by nevěděl, jestli `db.py` funguje. S service běží vždy → regrese se chytí hned.

---

## 10. Slovník pojmů (rychlá reference)

| Pojem | Význam |
|-------|--------|
| **PostgreSQL** | Relační open-source databáze |
| **Tabulka** | Evidence — sloupce (typy) + řádky (záznamy) |
| **SQL** | Jazyk pro práci s databází (SELECT, INSERT, UPDATE) |
| **UNIQUE index** | Sloupec, kde se hodnota nesmí opakovat → dedup |
| **Dedup** | Zajištění, že stejný inzerát je v DB jen jednou |
| **Upsert** | INSERT + UPDATE v jednom (INSERT ... ON CONFLICT DO UPDATE) |
| **SERIAL** | Auto-increment ID |
| **JSONB** | JSON sloupec (metadata běhu) |
| **pipeline_runs** | Auditní tabulka — kdy/kdo/jak dopadl každý běh |
| **Docker** | Kontejnerizace — izolované spouštění aplikací |
| **Image / Container** | Šablona / běžící instance |
| **docker compose** | Definice služeb v YAML, `up -d` = start |
| **Volume** | Trvalé úložiště dat kontejneru |
| **Port 5432** | Standardní port PostgreSQL |
| **psycopg** | Python ovladač pro PostgreSQL |
| **DATABASE_URL** | Env proměnná s připojovacím řetězcem |
| **Provider-agnostic** | Funguje s jakýmkoli hostem (Docker/Neon/Supabase) |
| **Idempotentní** | Dá se spustit opakovaně bez chyby (IF NOT EXISTS) |
| **Graceful degradation** | Při selhání doplňku systém dál funguje |
| **Service container** | Dočasný kontejner v CI pro testy |

---

## 11. Rizika a jak se s nimi zachovat

| Riziko | Pravděpodobnost | Řešení |
|--------|:---:|--------|
| Zapomenutý Docker → DB se nepíše | Vysoká | **Není kritické** — pipeline běží, log řekne `DB persistence skipped`. Pro DB: `docker compose up -d`. |
| Docker daemon nesvítí | Časté po restartu PC | `docker info` → pokud error, spustit Docker Desktop a počkat na daemon |
| Port 5432 obsazený jinou DB | Nízká | Změnit v compose (`"5433:5432"`) + `DATABASE_URL` |
| **Únik dat / credentials** | Nízká | `DATABASE_URL` je v `.env` (gitignored). Nikdy necommitovat. |
| Volume naroste | Nízká (job-hunt) | `docker compose down -v` = čistý reset |

---

## 12. Co přijde dál (Fáze 2) a co dělat teď

**Fáze 2** (rozhodnuto): nový samostatný repo → Next.js web na jobs.systeq.cz čtoucí tuto databázi. GUI = dashboard inzerátů, filtry, PDF report (Calibri/A4 — renderer už existuje).

**Tobě teď doporučuji ověřit si, že rozumíš:**

```powershell
# 1. Start DB a ověř tabulky
docker compose up -d
$env:DATABASE_URL = "postgres://mcpjobs:mcpjobs@localhost:5432/mcpjobs"

# 2. Podívej se vlastníma očima, co DB drží
python -X utf8 -c "import psycopg, os; c=psycopg.connect(os.environ['DATABASE_URL']); print(c.execute('SELECT COUNT(*) FROM ads').fetchone()[0]); print(c.execute('SELECT id, status, matched FROM pipeline_runs ORDER BY id DESC LIMIT 3').fetchall())"

# 3. Spusť ETL a sleduj řádek "DB: run N persisted"
python -X utf8 scripts/run_etl.py --config config.yaml

# 4. Ověř graceful fallback: bez Dockeru
docker compose down
python -X utf8 scripts/run_etl.py --config config.yaml   # → Warning, ale běží dál
```

**Anti-blackbox princip:** než projdeš krok 1–4 a sám uvidíš data v DB, nepovažuj Fázi 1 za naučenou. Každý pojem z tabulky v sekci 10 umíš vysvětlit vlastními slovy? Pak je pivot pod kontrolou.

---

## 13. Shrnutí (jedna stránka)

1. **Pivot standalone** = MCP-jobs se stává samostatným produktem (web + DB + automatizace). Fáze 0 a 1 jsou hotové.
2. **Fáze 1 přidala databázi:** schema, Docker, db.py, napojení do pipeline, testy, CI service.
3. **PostgreSQL řeší** historii, dedup a dotazování, které soubory neumí.
4. **Docker** provozuje DB izolovaně (neinstaluje se do Windows), data žijí ve volume.
5. **Dedup** = `UNIQUE` na URL + `INSERT ... ON CONFLICT DO UPDATE`. Ověřeno: run 3 přidal 0 duplicit.
6. **Pipeline běží bez Dockeru** — DB je doplněk s graceful degradation, ne podmínka.
7. **Testy:** 142/142, z toho 5 DB integration testů (auto-skip bez DATABASE_URL).
8. **Co NEmění:** MCP server, matcher, report, config — jen přibyla vrstva na konci běhu.

---

*Dokument vytvořen: 2026-08-15 | Autor: outpost2026*
*Provenance: source-read (všechny soubory Fáze 1 + reálné ETL běhy s DB) + retrospektiva session 2026-08-15*
*Návaznost: edukace_implementace_standalone_pivot_2026-08-15.md, edukace_port_standalone_2026-08-15.md, SKILL_GAPS_ROZBOR_Q3_2026_v2.md*