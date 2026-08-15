# Edukační dokument: První kontakt s databází — kde je, jak ji otevřít (analogie Excelu)

**Datum:** 2026-08-15 | **Autor:** outpost2026 (junior dev, praxe < 5 měsíců) | **Verze:** 1.0
**Účel:** Odpovědět na otázku juniora, který poprvé využil SQL databázi a je zcela ztracen — neví, kde DB fyzicky je, jaký program spustit a jak s ní pracovat. Postaveno na analogii s Excelem, který junior ovládá tacitně.
**Kontext vlákna:** Fáze 1 pivota MCP-Jobs (PostgreSQL persistence). Po implementaci následuje pochopení: "mám DB, ale nevím, co s ní".
**Návaznost:** `docs/edukace_faze1_postgresql_2026-08-15.md` (mechanismy Fáze 1), `docs/edukace_implementace_standalone_pivot_2026-08-15.md`
**Provenance:** source-read (docker volume inspect, docker inspect, live dotazy přes psql, scripts/db.ps1) + reálná data z ETL běhů 2026-08-15

---

## 1. Proč jsi ztracen — a proč to není tvoje chyba

Tvůj problém není, že bys "neuměl SQL". Tvůj problém je **mapování**:

> V Excelu víš, že: **soubor** (`.xls`) → dvojklik → **Excel se otevře** → vidíš sešit s listy.

U databáze **žádný soubor není**. To je celý háček. Ty hledáš soubor, který neexistuje, a program, který nikdy nebyl nainstalován jako Excel.

**Základní pravda, kterou si zapamatuj:**

| Excel | PostgreSQL |
|-------|-----------|
| `.xls` soubor | **Neexistuje žádný soubor** |
| Excel aplikace | **psql** — program, který už je uvnitř kontejneru |
| Dvojklik na soubor | **Jeden příkaz** — otevře konzoli |
| Listy (`Sheet1`) | **Tabulky** (`ads`, `pipeline_runs`) |
| Vzorce (`=SUM(A1:A5)`) | **SQL dotazy** (`SELECT COUNT(*) FROM ads`) |

---

## 2. Kde databáze FYZICKY je

### 2.1 Krátká odpověď

> Databáze **není na tvém disku**. Je **uvnitř Docker kontejneru** `mcp-jobs-postgres`, který běží jako izolovaný proces.

Ověřeno příkazem (můžeš si to spustit):

```powershell
docker inspect mcp-jobs-postgres --format "{{.Config.Image}}"
# → postgres:16
```

### 2.2 Jak to vidět očima

```
Tvůj počítač (Windows)
│
├── MCP-Jobs repozitář (soubory kódu)          ← TADY pracuješ normálně
│
├── Docker Desktop (motor, běží na pozadí)
│   └── Kontejner: mcp-jobs-postgres           ← DATABÁZE ŽIJE ZDE
│       ├── PostgreSQL 16 (databázový server)
│       ├── Tabulky: ads, pipeline_runs
│       └── Volume: mcp_jobs_pgdata (data)
│           → /var/lib/docker/volumes/mcp-jobs_mcp_jobs_pgdata/_data
│
└── Port 5432 (vstupní dveře do databáze)
```

**Volume** = místo, kam se data ukládají, aby přežila restart kontejneru. Je to jediná část, která je "souborová", ale je uvnitř Docker infrastruktury — ne v tvém `C:\...`. Nebudeš ho muset nikdy otevírat ručně.

### 2.3 Klíčové číslo: port 5432

Každý program, který chce s DB mluvit, se připojí na `localhost:5432`. Jako by databáze bydlela v bytě č. 5432 v domě localhost a čekala na návštěvy.

```
Python (db.py) ──▶ localhost:5432 ──▶ PostgreSQL (v kontejneru)
psql (konzole) ──▶ localhost:5432 ──▶ PostgreSQL (v kontejneru)
```

---

## 3. Jaký program spustit — "ikona Excelu" pro databázi

V Excelu bys spustil ikonu Excelu. U databáze je to příkaz **psql** — ale psql není nainstalovaný ve Windows. Je uvnitř kontejneru (protože ho přinesl image `postgres:16`).

**Řešení:** neinstalujeme nic. Skáčeme do kontejneru a tam psql spustíme:

```powershell
docker exec -it mcp-jobs-postgres psql -U mcpjobs -d mcpjobs
```

Rozbor příkazu (toto je tvůj "dvojklik na Excel"):

| Část | Význam |
|------|--------|
| `docker exec -it` | "Vejdi do běžícího kontejneru interaktivně" |
| `mcp-jobs-postgres` | "Kterého" — název kontejneru |
| `psql` | "Spusť databázovou konzoli" |
| `-U mcpjobs` | "Přihlas se jako uživatel mcpjobs" (heslo: mcpjobs) |
| `-d mcpjobs` | "Otevři databázi mcpjobs" |

**Proč si to nemusíš pamatovat:** vytvořil jsem skript `scripts/db.ps1`, který je tvoje "ikona". Všechny příkazy níže jsou přes něj.

---

## 4. Tvůj první kontakt — 4 kroky (přes scripts/db.ps1)

### Krok 1: Ověř, že databáze běží (ekvivalent: "je Excel otevřený?")

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\db.ps1 status
```

Výstup: `mcp-jobs-postgres   Up ... (healthy)` = databáze je živá.

Pokud kontejner neběží, spusť ho: `docker compose up -d` (z kořene repozitáře).

### Krok 2: Podívej se, co databáze obsahuje (ekvivalent: "otevřel jsem sešit, vidím listy")

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\db.ps1 tables
```

Výstup:

```
 List of relations
 public | ads           | table | mcpjobs
 public | pipeline_runs | table | mcpjobs
```

**Překlad:** máš 2 "listy" (tabulky). `ads` = inzeráty, `pipeline_runs` = historie běhů.

### Krok 3: Otevři interaktivní konzoli (ekvivalent: "dvojklik na Excel, sedneš do sešitu")

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\db.ps1
```

Uvidíš:

```
mcpjobs=> _
```

To je **kurzor uvnitř databáze**. Můžeš psát SQL. Ukončení: `\q` + Enter.

### Krok 4: První dotaz (ekvivalent: "napsal jsi první vzorec")

Buď v konzoli napiš:

```sql
SELECT * FROM ads LIMIT 5;
```

Nebo přes skript (bez vstupu do konzole):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\db.ps1 query "SELECT * FROM ads LIMIT 5;"
```

**Pozor na středník `;`** — SQL příkazy končí středníkem, jako věty v češtině. Když ho zapomeneš, konzole čeká na pokračování.

---

## 5. Co vidíš — rozbor prvního dotazu

```sql
SELECT  *  FROM  ads  LIMIT  5;
│       │       │      │     │
│       │       │      │     └─ "max 5 řádků" (jako LIMIT 5 v Excelu = prvních 5 řádků)
│       │       │      └─ omezit počet výsledků
│       │       └─ "která tabulka" (jako vybrat list)
│       └─ "všechny sloupce" (jako celý řádek v Excelu)
└─ "vyber" (jako vložit vzorec = požádat o data)
```

**Výstup = tabulka.** Řádky = inzeráty. Sloupce = pole (title, company, location, salary...). Přesně jako list v Excelu, jen se naplnil daty z pipeline.

---

## 6. Od Excelu k SQL — překladová tabulka tvých tacitních znalostí

| Co umíš v Excelu | Jak to uděláš v SQL | Příkaz |
|---|---|---|
| Otevřít soubor | Otevřít konzoli | `scripts\db.ps1` |
| Vybrat list | `FROM` | `FROM ads` |
| Vybrat sloupce | `SELECT` | `SELECT title, company` |
| Vybrat celý list | `SELECT *` | `SELECT * FROM ads` |
| Filtr (auto filter) | `WHERE` | `WHERE company = 'Firma'` |
| Hledání (Ctrl+F) | `WHERE ... ILIKE` | `WHERE title ILIKE '%python%'` |
| Řazení (sort) | `ORDER BY` | `ORDER BY company` |
| COUNT (počet) | `COUNT(*)` | `SELECT COUNT(*) FROM ads` |
| Kontingenční tabulka | `GROUP BY` | `SELECT status, COUNT(*) FROM ads GROUP BY status` |
| Vzorec v buňce | SQL výraz | `SELECT salary` |
| Uložit změny (Ctrl+S) | Nic — DB ukládá automaticky | — |
| Nový list | Nová tabulka | `CREATE TABLE ...` |

**Základní pocit, který si odnes:** `SELECT ... FROM ... WHERE ...` = "dej mi data z listu, kde platí podmínka". Vše ostatní je variace.

---

## 7. Konkrétní dotazy, které dávají smysl pro TEBE (job-hunt)

Máš v DB 26 inzerátů z reálného běhu. Toto jsou otázky, na které odpovíš:

| Otázka | SQL dotaz |
|---|---|
| Kolik mám celkem inzerátů? | `SELECT COUNT(*) FROM ads;` |
| Které firmy nabízejí nejvíc? | `SELECT company, COUNT(*) FROM ads GROUP BY company ORDER BY COUNT(*) DESC;` |
| Které inzeráty jsou v Praze? | `SELECT title, company FROM ads WHERE location ILIKE '%praha%';` |
| Které inzeráty obsahují "Python"? | `SELECT title FROM ads WHERE title ILIKE '%python%';` |
| Které jsem už neviděl/označil? | `SELECT status, COUNT(*) FROM ads GROUP BY status;` |
| Kdy běžela pipeline a kolik našla? | `SELECT status, matched, raw FROM pipeline_runs;` |
| Jak dlouho trval každý běh? | `SELECT id, metadata->>'elapsed_seconds' AS secs FROM pipeline_runs;` |

---

## 8. Mapování tvého světa — kde co je (shrnutí)

| Tvoje otázka | Odpověď |
|---|---|
| "Kde je soubor .xls?" | **Žádný soubor není.** Data v kontejneru `mcp-jobs-postgres`, volume `mcp_jobs_pgdata`. |
| "Který program mám spustit?" | **Žádný neinstaluješ.** Konzole psql je uvnitř kontejneru. Otevřeš ji přes `scripts\db.ps1`. |
| "Jak se přihlásím?" | Automaticky: uživatel `mcpjobs`, heslo `mcpjobs`, databáze `mcpjobs` (z docker-compose.yml). |
| "Kde mám psát dotazy?" | V konzoli psql (`scripts\db.ps1`) nebo přes `scripts\db.ps1 query "SQL"`. |
| "Co když DB neběží?" | `docker compose up -d` → počkat na `healthy`. |
| "Když smažu kontejner, smažu data?" | `docker compose down` = NE. `docker compose down -v` = ANO (i volume). |

---

## 9. Tvoje cvičení (30 minut, anti-blackbox)

Neber mě za slovo — ověř si to vlastníma očima:

1. `powershell ... scripts\db.ps1 status` → vidíš `healthy`
2. `powershell ... scripts\db.ps1 tables` → vidíš 2 tabulky
3. `powershell ... scripts\db.ps1 query "SELECT company, COUNT(*) FROM ads GROUP BY company ORDER BY COUNT(*) DESC;"` → vidíš firmy s počtem
4. `powershell ... scripts\db.ps1` → otevři konzoli, napiš `SELECT * FROM ads LIMIT 3;`, pak `\q`
5. Změň něco: `UPDATE ads SET status='seen' WHERE id=1;` → pak `SELECT status, COUNT(*) FROM ads GROUP BY status;` → vidíš, že se to změnilo

**Až tohle zvládneš, umíš:**
- Najít data (kde je DB)
- Otevřít nástroj (psql přes skript)
- Dotazovat se (SELECT/FROM/WHERE)
- Upravovat stav (UPDATE)
- Pochopit, že to je "tabulkový procesor na data, která přežijí mezi běhy"

**Další úroveň (až budeš v pohodě):** GUI klient (např. pgAdmin nebo DBeaver) — to je "Excel s klikacím rozhraním" na stejnou DB. Ale začni terminálem, abys rozuměl, co se děje pod kapotou.

---

## 10. Slovníček pro tuto kapitolu

| Pojem | Význam |
|-------|--------|
| **Kontejner** | Izolovaný běžící program (zde databázový server) |
| **psql** | Konzolový program pro práci s PostgreSQL (připojený ke konzoli) |
| **Volume** | Trvalé úložiště dat uvnitř Dockeru |
| **Port 5432** | Adresa, kde databáze poslouchá |
| **Tabulka** | "List" — data v sloupcích a řádcích |
| **SELECT / FROM / WHERE** | "Vyber / z čeho / kde platí" — základ SQL |
| **LIMIT** | Omez počet výsledků |
| **ILIKE '%...%'** | Hledání obsahující text (case-insensitive) |
| **GROUP BY** | Seskupení (jako kontingenční tabulka) |
| **\q** | Ukončení psql konzole |

---

*Dokument vytvořen: 2026-08-15 | Autor: outpost2026*
*Provenance: source-read (docker volume inspect, docker inspect, live psql dotazy, scripts/db.ps1) + reálná data z ETL běhů*
*Návaznost: edukace_faze1_postgresql_2026-08-15.md (mechanismy Fáze 1), edukace_implementace_standalone_pivot_2026-08-15.md*