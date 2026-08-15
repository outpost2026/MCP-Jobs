# SQL ontologie: mechanismy, dependencies a praktické využití — učební dokument

**Datum:** 2026-08-15 | **Autor:** outpost2026 | **Verze:** 1.0
**Účel:** První ontologie SQL jazyka, mechanismů tvorby databáze a závislostí — učební dokument stavěný na autorových vlastních datech z pracovních portálů (MCP-Jobs ETL pipeline)
**Typ:** edu / ontologie | **Doména:** SQL, PostgreSQL, databázová architektura | **EROI:** 9/10
**Návaznost:** `docs/edukace_db_prvni_kontakt_2026-08-15.md` (první kontakt), `docs/postgresql_zakladni_prikazy_2026-08-15.md` (příkazová reference), `src/mcp_jobs/db.py`, `data/schema.sql`, `src/mcp_jobs/models.py`
**Provenance:** source-read (schema.sql, db.py, models.py, live psql dotazy na reálných datech ETL běhů 2026-08-15) + autoreflexe autora

---

## 0. Proč tento dokument vznikl — přechod z blackboxu k vhledu

Toto je **první artefakt**, ve kterém autor nepřepisuje neznámé neznámé (SQL = blackbox), ale **částečně rozumí**, co SQL a celá rodina nástrojů je a jak pracuje.

**Stav porozumění (autoreflexe autora):**

| Před tímto dokumentem | Nyní |
|---|---|
| "Databáze = soubor s daty" | DB = server se strukturou (návrh) + daty (plnění) |
| "Sloupce = výsledek vstupních dat" | Sloupce = **design rozhodnutí**; data je plní |
| "SQL = kouzlo, které parsuje data" | SQL = deklarativní programovací jazyk |
| "Nevím, kde cokoli je" | Znám celý řetězec: parser → model → schema → db.py → dotaz |

**Důležité:** autor předpokládá, že část domněnek je chybná. LLM korekce jsou **výrazně označeny v textu** (⚠ KOREKCE) a potvrzení (✓ POTVRZENO).

---

## 1. Autorovy teze — korekce a potvrzení

### Teze 1: "PostgreSQL vytváří své kategorie/sloupce dle logiky, kterou připravil Python skript (ETL)"

**⚠ KOREKCE — zásadní.**

PostgreSQL **nevytváří sloupce podle Python skriptu.** Sloupce definuje **`schema.sql` (DDL)** — samostatný soubor, který je **design rozhodnutí autora**, ne výstup parseru.

```
SPRÁVNÝ řetězec:
parser (scrape) → Ad model (Python) → schema.sql definuje sloupce → db.py vkládá data
                     ↑                    ↑
              "jak vypadá data"   "jak vypadá struktura"  ← DVĚ NEZÁVISLÉ VĚCI
```

Python (ETL) **plní** data do struktury, kterou autor navrhl v SQL. Ne naopak. MySQL vs PostgreSQL vs SQLite — všechny mají **stejné principy**, liší se syntaxí detailů.

### Teze 2: "Autor může přidat kategorie nezávisle na ETL skriptu"

**✓ POTVRZENO — s nuancemi.**

Autor MŮŽE přidat sloupec (např. `response_date`) přímo přes `ALTER TABLE`, zcela nezávisle na Pythonu. **Ale:**
- Nový sloupec bez výchozí hodnoty = `NULL` u všech existujících řádků
- Data do něj nedoplní ETL automaticky — buď ručně (UPDATE), nebo úpravou db.py
- Přidání sloupce je **struktura** (DDL); jeho plnění je **data** (DML)

### Teze 3: "Lze těžit metadata jako first_seen, last_seen a další"

**✓ POTVRZENO.**

To je přesně to, co `schema.sql` dělá:
```sql
first_seen DATE DEFAULT CURRENT_DATE,   -- design: kdy přišel
last_seen  DATE DEFAULT CURRENT_DATE,   -- design: kdy naposledy viděn
status     TEXT DEFAULT 'new'           -- design: workflow stav
```
`CURRENT_DATE` = **funkce databáze**, ne hodnota z parseru. DB si to vypočítá sama.

### Teze 4: "SQL je programovací jazyk — specifický, triviální, ale programovací. Jako Markdown."

**✓ POTVRZENO — s upřesněním analogie.**

SQL **JE programovací jazyk** — deklarativní, doménově specifický (DSL). Není triviální ani jednoduchý: je kompaktní, ale jeho výpočetní model (relační algebra, set-based myšlení) je pro lidský mozek **nepřirozený**. Řeší se v něm celá škála problémů — od jednoduchých SELECT po analytické dotazy.

**⚠ Upřesnění analogie s Markdown:** Markdown NENÍ programovací jazyk — je **značkovací** (markup, popisuje vzhled dokumentu). SQL je **dotazovací/programovací** (popisuje, JAKÁ data chceš, ne jak vypadají). Přesnější analogie:

| Jazyk | Typ | Říká |
|-------|-----|------|
| Python | imperativní | **JAK** to udělat krok za krokem |
| SQL | deklarativní | **CO** chceš získat |
| Markdown | značkovací | **JAK** to má vypadat |

Autorova intuice "SQL = programovací jazyk" je **správná**. Analogie s Markdown je **slabá** (jiná kategorie jazyků).

---

## 2. Ontologie SQL — mapa celé domény

```
                    ┌─────────────────────────────┐
                    │   SQL = DEKLARATIVNÍ JAZYK  │
                    └──────────────┬──────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
    ┌─────────▼─────────┐ ┌───────▼────────┐ ┌─────────▼─────────┐
    │  DDL (Design)     │ │  DML (Data)    │ │  DQL (Dotaz)     │
    │  Definuje TVAR    │ │  PLNÍ data     │ │  ČTE data        │
    ├───────────────────┤ ├────────────────┤ ├──────────────────┤
    │ CREATE TABLE      │ │ INSERT         │ │ SELECT           │
    │ ALTER TABLE       │ │ UPDATE         │ │ FROM, WHERE      │
    │ DROP TABLE        │ │ DELETE         │ │ GROUP BY, HAVING │
    │ CREATE INDEX      │ │ ON CONFLICT    │ │ ORDER BY, LIMIT  │
    └───────────────────┘ └────────────────┘ └──────────────────┘
```

**Klíčový princip:** tři kategorie dělají **tři různé věci**:
- **DDL** = navrhuje strukturu (architekt navrhuje dům)
- **DML** = plní data (stěhovák nosí nábytek)
- **DQL** = čte data (návštěvník si prohlíží)

---

## 3. Hlavní mechanismus: forma vs odlitek (a dependency)

### 3.1 Proces vzniku databáze — pořadí

```
KROK 1: Navrhneš strukturu (DDL)          → data/schema.sql
KROK 2: Aplikuješ strukturu                → python -c ... init_db()  /  psql -f schema.sql
KROK 3: ETL běh plní data (DML)            → db.py upsert_ads()
KROK 4: Dotazuješ se (DQL)                 → psql SELECT ...
```

**Závislost (dependency):** KROK 3 NEMŮŽE proběhnout před KROKEM 2 — tabulka musí existovat, než do ní vložíš data. To je **směr závislosti**: DDL → DML → DQL. Vždy v tomto pořadí.

### 3.2 Dependency graf — kdo na kom závisí

```
parser (scrape portály)
   │  vytváří
   ▼
Ad model (models.py) ──────────────┐
   │  mapuje pole                  │  stejná pole
   ▼                              ▼
db.py (DML) ──vyplňuje──▶ schema.sql (DDL: CREATE TABLE ads)
                                 │
                                 ▼
                            PostgreSQL server
                                 │
                                 ▼
                            psql / dotazy (DQL)
```

**Autorova pozice v grafu:** autor je návrhář struktury (schema.sql) A autor plnění (db.py) A uživatel dotazování (psql). Tři role, jeden člověk.

---

## 4. Mapování Ad model → sloupce ads (důkaz nezávislosti)

| Ad model (models.py) | Sloupec (schema.sql) | Zdroj |
|---|---|---|
| `title` | `title TEXT` | Parser (scraped) |
| `url` | `url TEXT NOT NULL UNIQUE` | Parser + design (UNIQUE) |
| `portal` | `portal TEXT` | Parser |
| `company` | `company TEXT` | Parser |
| `location` | `location TEXT` | Parser |
| `salary` | `salary TEXT` | Parser |
| `description` | `description TEXT` | Parser |
| `matched_keyword` | `matched_keyword TEXT` | Pipeline (booleovský filtr) |
| `query_name` | `query_name TEXT` | Pipeline (parametr) |
| `scraped_at` | `first_seen DATE` | **Redesign:** parser dává ISO timestamp, DB ukládá jen datum, default CURRENT_DATE |
| `price`, `category_name` | **— (nejsou v ads)** | Autor NENAVRHOVAL tyto sloupce — data zůstávají jen v output/*.json |
| — (není v modelu) | `last_seen DATE` | **Čistý design:** sleduje opětovný výskyt |
| — (není v modelu) | `status TEXT` | **Čistý design:** workflow new/seen/applied/rejected |

**Důkaz dvou věcí:**
1. **Ne vše z modelu jde do DB** — `price`, `category_name` autor vynechal (nemá pro ně využití)
2. **Něco v DB není z modelu** — `last_seen`, `status`, `id` jsou čistý design

To je přímá empirická demonstrace, že **sloupce = design rozhodnutí, ne vstupní data.**

---

## 5. SQL jako programovací jazyk — mechanismus myšlení

### 5.1 Proč je SQL "programovací"

SQL splňuje definici programovacího jazyka:
- **Syntaxe a gramatika** (SELECT/FROM/WHERE jsou klíčová slova)
- **Proměnné a typy** (TEXT, INT, DATE, JSONB)
- **Logika** (AND/OR/NOT, podmínky)
- **Funkce** (COUNT, MIN, MAX, NOW, CURRENT_DATE)
- **Kontrola toku** (CASE WHEN, JOIN)
- **Data types system** (NULL vs NOT NULL, typy sloupců)

### 5.2 Rozdíl: imperativní (Python) vs deklarativní (SQL)

| Python (imperativní) | SQL (deklarativní) |
|---|---|
| "Udělej A, pak B, pak C" | "Chci výsledek X" |
| Řídíš každý krok | Databáze optimalizuje JAK |
| Cykly, proměnné, funkce | Set-based operace nad celými tabulkami |
| `for ad in ads: ...` | `SELECT ... FROM ads WHERE ...` |

**Klíčový mentální přepínač:** v Pythonu myslíš "jeden řádek za druhým" (iterace). V SQL myslíš "celá množina najednou" (set-based). **To je hlavní kognitivní bariéra — ne syntaxe.**

### 5.3 Příklad — stejná otázka ve dvou jazycích

**Otázka:** "Kolik inzerátů má každá firma, seřazeno sestupně?"

```python
# Python (imperativní — říkáš JAK)
from collections import Counter
counts = Counter(ad.company for ad in ads)
for company, n in sorted(counts.items(), key=lambda x: -x[1]):
    print(company, n)
```

```sql
-- SQL (deklarativní — říkáš CO)
SELECT company, COUNT(*) AS pocet FROM ads GROUP BY company ORDER BY pocet DESC;
```

**Stejný výsledek. Jiný mechanismus.** Python prochází data sám; SQL přikáže databázi, aby to udělala (a ta zvolí optimální cestu přes indexy).

### 5.4 Jádro kognitivní investice: buňka → množina (Feynman)

**Proč je tohle ta netriviální část — vysvětleno od základu.**

#### 5.4.1 Excel: jedno místo, jeden výpočet

Excel ti **nikdy nenechá pracovat s celou tabulkou naráz**. Vždy manipuluješ buňky, sloupce, výběry — a každý výpočet se týká **konkrétních buněk**, které jsi označil.

```
Excel (myšlení po buňkách / imperativní):
┌────────┬────────┬────────┐
│ firma  │ pocet  │        │
├────────┼────────┼────────┤
│ A      │ =COUNT(...)  ← konkrétní buňka, konkrétní rozsah
│ B      │ ...
└────────┴────────┴────────┘
Ty jsi řekl JAK: "spočítej tyhle konkrétní buňky"
```

Důsledek: Excel modeluje **lokální operace**. Když máš 10 000 řádků, Excel to umí, ale ty pořád myslíš "která buňka, který rozsah".

#### 5.4.2 SQL: celá množina najednou

SQL **nemá pojmy "buňka" ani "rozsah"**. Pracuje s **množinami řádků** — a každý dotaz vrací celou novou množinu.

```
SQL (myšlení po množinách / deklarativní):
┌─────────────────────────────────────────┐
│ SELECT ... FROM ads WHERE status='new'  │
│                                         │
│  vstup: celá tabulka ads (26 řádků)     │
│  filtr: ponech jen status='new'         │
│  výstup: NOVÁ množina řádků             │
└─────────────────────────────────────────┘
Ty jsi řekl CO: "chci řádky, kde platí podmínka"
```

**Klíčový posun:** nepopisuješ cestu k buňce. Popisuješ **vlastnost množiny**, kterou chceš. Databáze sama zvolí, jak ji najít (přes index nebo postupným procházením).

#### 5.4.3 Analogie, která to usadí: šanon vs sešívačka

**Excel = sešívačka.** Máš papíry, sešiješ vybrané, podíváš se na konkrétní stránku. Fyzicky držíš v ruce ten konkrétní papír.

**SQL = šanon s kartami + dotazník.** Máš šanon plný karet (inzerátů). Neprohlížíš je jednu po druhé — **vyplníš dotazník** ("dej mi všechny karty, kde je Praha") a šanon (databáze) sám projde tisíce karet a vrátí jen ty, které splňují podmínku. Ty nikdy nedržíš kartu v ruce — vidíš jen **výsledek dotazu** (novou hromádku).

#### 5.4.4 Co je JOIN a proč v Excelu neexistuje

Excel má **jeden list** (max propojení přes VLOOKUP = ruční dohledání). Relační databáze mají **více tabulek, které jsou provázané** — a JOIN je mechanismus, který je **spojuje na základě shody**:

```
Tabulka ads:                    Tabulka pipeline_runs:
┌────┬──────────┬─────────┐    ┌────┬─────────┬───────┐
│ id │ company  │ query   │    │ id │ profile │ matched│
├────┼──────────┼─────────┤    ├────┼─────────┼───────┤
│ 1  │ T-Mobile │ devops  │    │ 2  │AI-NATIVE│  27   │
│ 2  │ VALEO    │ cnc     │    │ 3  │AI-NATIVE│  27   │
└────┴──────────┴─────────┘    └────┴─────────┴───────┘
          │                          │
          └─────── JOIN ─────────────┘
                  (spojení na shodě)
```

**Myšlenka:** dvě samostatné hromádky karet chceš **sloučit do jedné** na základě společného klíče (např. `id` běhu). V Excelu bys musel ručně dohledávat a kopírovat (VLOOKUP) — a při 10 000 řádcích je to neudržitelné. SQL to udělá jedním příkazem:

```sql
SELECT r.id, r.matched, a.company
FROM pipeline_runs r
JOIN ads a ON a.query_name = 'devops_ci_cd'
WHERE r.id = 2;
```

**Kognitivní investice:** JOIN vyžaduje myslet **ve dvou tabulkách najednou** a pochopit, že data o jednom faktu (inzerátu) mohou být **rozdělena do více tabulek** a znovu spojena klíčem. Excel tě k tomu nikdy nevede — tam je vždy jen jeden prostor.

#### 5.4.5 Proč je to "investice", ne triviální krok

| Excel reflex | SQL reflex (nový) |
|---|---|
| "Které buňky vyberu?" | "Jakou vlastnost má požadovaná množina?" |
| Procházím řádek po řádku | Popisuji podmínku; databáze prochází |
| Jedna tabulka, jeden prostor | Více tabulek, propojení klíči |
| Lokální vzorec = konkrétní buňka | Dotaz = celá množina → nová množina |
| "Jak" (postup) | "Co" (výsledek) |

**Závěr (potvrzuje autorovu tezi z předchozí iterace):** tvrzení "kdo zvládá Excel, zvládá SQL" je pravdivé **jen pro syntaxi základních příkazů** (SELECT/FROM/WHERE — to je přenositelné). Ale **kognitivní model SQL je jiný**: myslet v množinách, ne v buňkách; myslet ve více tabulkách, ne v jednom listu. To je přechod, který se **neučí čtením, ale řešením reálných dotazů** — a proto patří do PBL (adopční metodika 60/20/10/10).

---

## 6. Reálné těžení — autorova vlastní data (2026-08-15)

### 6.1 Data v DB (reálný stav)

```
ads: 26 inzerátů, 12 firem, 2 portály (jobs, pracecz)
pipeline_runs: 3 běhy
```

### 6.2 Dotazy, které autor reálně použil (rozbor mechanismu)

**Dotaz 1 — kontingenční tabulka firem:**
```sql
SELECT company, COUNT(*) AS pocet FROM ads GROUP BY company ORDER BY pocet DESC;
```
**Výsledek:**
```
České Radiokomunikace a.s.   8
ATS LSS                      3
Acme                        2 | ADASTRA | T-Mobile | Česká spořitelna | AI Excellence  (2×)
```
**Mechanismus:** `GROUP BY` rozdělí řádky podle firmy → `COUNT(*)` spočítá řádky v každé skupině → `ORDER BY pocet DESC` seřadí. Tři operace, jeden řádek kódu. V Pythonu by to byl cyklus + slovník + sort.

**Dotaz 2 — inzeráty podle query (mapa portfolia):**
```sql
SELECT query_name, COUNT(*) AS pocet FROM ads GROUP BY query_name ORDER BY pocet DESC;
```
**Výsledek:**
```
devops_ci_cd            10
prumyslova_automatizace  5
cnc_cam_automation       3
data_engineering         2
ai_llm_engineer          2
python_ai_engineer       2
```
**Mechanismus:** ukazuje, která hledání generují nejvíc matchů — **reporting** z dat, které autor sám těží.

**Dotaz 3 — kontextové hledání:**
```sql
SELECT title FROM ads WHERE title ILIKE '%python%' OR title ILIKE '%ai%';
```
**Mechanismus:** `ILIKE` + `%` = obsahuje text (case-insensitive). Ekvivalent Ctrl+F, ale přes celou tabulku.

**Dotaz 4 — audit běhů (JSONB metadata):**
```sql
SELECT id, metadata->>'new_ads' AS novych, metadata->>'elapsed_seconds' AS sekundy
FROM pipeline_runs;
```
**Výsledek:**
```
id | novych | sekundy
1  | 2      | 3.5
2  | 15     | 40.2
3  | 9      | 38.2
```
**Mechanismus:** `metadata` je JSONB — **autor sám navrhl tento sloupec** pro proměnlivá data běhu. `->>` extrahuje hodnotu z JSON. To je příklad Teze 3: autor přidal vlastní metadatovou kategorii.

### 6.3 Co tato data dokazují o SQL

| Pozorování | Závěr |
|---|---|
| Stejná data, 4 různé dotazy, 4 různé odpovědi | SQL = dotazovací jazyk nad jednou strukturou |
| `first_seen`/`last_seen`/`status` nejsou v parseru | Design rozhodnutí, ne vstupní data |
| `metadata` JSONB drží strukturu, kterou navrhl autor | Autor řídí schéma, ne data |
| Dotazy běží v milisekundách | Indexy + databázový engine |

---

## 7. Dependencies v praxi — kdo potřebuje koho

### 7.1 Závislost kódu na schématu

```
db.py: upsert_ads() INSERT INTO ads (url, title, ...)
   ↑                                                   
   │  selže, pokud schema.sql neobsahuje tyto sloupce
   │
schema.sql: CREATE TABLE ads (...)
```

Pokud autor smaže sloupec ze schema.sql a nespustí `init_db` — db.py posílá INSERT s neexistujícím sloupcem → chyba. **Kód a schéma musí být v synchronizaci.**

### 7.2 Závislost dat na schématu (constraints)

| Constraint v schema.sql | Co vynucuje | Co se stane při porušení |
|---|---|---|
| `NOT NULL` | Sloupec nesmí být prázdný | Chyba INSERT |
| `UNIQUE` | Hodnota nesmí být duplicitní | Chyba / ON CONFLICT |
| `PRIMARY KEY` | id = jednoznačný identifikátor | Automaticky unique + not null |
| `DEFAULT` | Výchozí hodnota, když není zadána | Databáze doplní sama |

**`UNIQUE` + `ON CONFLICT` je tvůj dedup mechanismus** — a je to čistá funkce SQL, kterou bys v souborech musel programovat ručně (hashset, složitost O(n) vs O(log n) indexu).

### 7.3 Závislost rychlosti na indexech

```sql
CREATE INDEX idx_ads_status ON ads (status);
```

Bez indexu by `WHERE status = 'new'` procházelo všech 26 řádků (a u milionů by to bylo pomalé). S indexem databáze ví, kde statusy jsou. **Index je design rozhodnutí** — zrychlení za cenu úložiště.

---

## 8. Autorova nová mentální mapa (po přečtení)

```
┌───────────────────────────────────────────────────────────────┐
│  DATABÁZE = SERVER SE STRUKTUROU A DATY                       │
│                                                               │
│  Návrh (DDL, schema.sql)                                      │
│  ├─ Tabulky (ads, pipeline_runs) = "listy"                    │
│  ├─ Sloupce (url, title, ...) = "políčka formuláře"           │
│  ├─ Constraints (UNIQUE, NOT NULL) = pravidla vyplňování      │
│  └─ Indexy = pořadí v šanonu (rychlost hledání)               │
│                                                               │
│  Plnění (DML, db.py)                                          │
│  └─ INSERT/UPDATE/ON CONFLICT = "vyplňování formulářů"        │
│                                                               │
│  Dotazování (DQL, psql)                                       │
│  └─ SELECT/GROUP BY/JOIN = "otázky k šanonu"                  │
│                                                               │
│  ROLE AUTORA: navrhuje formuláře, plní je, ptá se na ně       │
└───────────────────────────────────────────────────────────────┘
```

---

## 9. Co autor NÁPOVĚDUJE teď vs co je stále blackbox

### Teď ví (P > 0.8):
- Jak vzniká databáze (DDL → DML → DQL, v tomto pořadí)
- Že sloupce jsou design, ne vstupní data (dokázáno na vlastních datech)
- Že SQL je deklarativní programovací jazyk
- Jak funguje dedup (UNIQUE + ON CONFLICT + xmax trik)
- Kde co je (kontejner, volume, port, psql)

### Ještě neví (známé neznámé — další učební cíl):
- **JOIN v praxi** — koncept vysvětlen (sekce 5.4.4), ale autor ho zatím neprovedl na reálných datech
- **Indexy do hloubky** — kdy se vyplatí, B-stromy, trade-offy
- **Transakce a ACID** — atomicita, konzistence, izolace
- **Migrace** — jak měnit schéma bez ztráty dat (ALTER TABLE v produkci)
- **Normalizace** — kdy rozdělit tabulky, kdy nechat (1NF–3NF)

---

## 10. Slovníček

| Pojem | Význam |
|-------|--------|
| **DDL** | Data Definition Language — navrhuje strukturu (CREATE TABLE) |
| **DML** | Data Manipulation Language — plní data (INSERT, UPDATE) |
| **DQL** | Data Query Language — čte data (SELECT) |
| **Deklarativní** | Říkáš CO, ne JAK (databáze optimalizuje) |
| **Constraint** | Pravidlo na sloupec (UNIQUE, NOT NULL) |
| **Index** | Datová struktura pro rychlé hledání |
| **JSONB** | Sloupec pro proměnlivá/polostrukturovaná data |
| **ON CONFLICT** | "Když porušíš UNIQUE, nechybuj — aktualizuj" |
| **Set-based myšlení** | Operace nad celou množinou, ne po řádcích |
| **JOIN** | Spojení více tabulek na základě shody klíče (jádro relačních DB) |
| **Schema** | Definice struktury databáze |

---

*Dokument vytvořen: 2026-08-15 | Autor: outpost2026 | Verze: 1.0*
*Provenance: source-read (schema.sql, db.py, models.py, live psql dotazy na reálných datech) + autoreflexe autora (přechod blackbox → částečný vhled)*
*Návaznost: edukace_db_prvni_kontakt_2026-08-15.md, postgresql_zakladni_prikazy_2026-08-15.md, IT_gramotnost_hranice_SQL_databazi_2026-08-15.md*