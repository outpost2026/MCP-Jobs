# PostgreSQL: Základní pracovní nástroje — příkazy pro práci s MCP-Jobs DB

**Datum:** 2026-08-18 | **Autor:** outpost2026
**Účel:** Referenční dokument nejdůležitějších SQL příkazů a psql meta-příkazů pro práci s MCP-Jobs databází — s kontextovým vyhledáváním, variacemi, praktickými ads analýzami a dedup vzory, ověřeno na reálných datech (93 ads, 7 pipeline_runs, 2026-08-18)
**Návaznost:** `docs/edukace_db_prvni_kontakt_2026-08-15.md` (jak otevřít DB), `docs/sql_ontologie_mechanismy_2026-08-15.md` (mechanismy DDL/DML/DQL), `05_EPISTEMIKA/03_kognitivni_ontologie_nastroju/POSTGRESQL_ontologie_epistemika_2026-08-18.md` (ontologie + 8 pastí), `05_EPISTEMIKA/03_kognitivni_ontologie_nastroju/IT_gramotnost_hranice_SQL_databazi_2026-08-15.md`
**Provenance:** source-read (live dotazy přes `docker exec mcp-jobs-postgres psql` na reálných datech ETL běhů + dedup cvičení 2026-08-18)

---

## 0. Jak spustit

```powershell
# Interaktivní konzole (psql) — pager vypnut, nic neblokuje
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\db.ps1

# Jednorázový dotaz bez vstupu do konzole
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\db.ps1 query "SELECT * FROM ads LIMIT 5;"
```

Konvence v tomto dokumentu: příkazy psql (`\...`) piš do konzole. SQL (`SELECT...`) funguje v konzoli i přes `query "..."`.

---

## 1. psql meta-příkazy (začínají `\` — nejsou SQL)

### 1.1 Přehled o DB (co existuje)

| Příkaz | Význam | Příklad |
|--------|--------|---------|
| `\l` | Seznam databází | `\l` |
| `\l+` | Seznam databází + velikosti | `\l+` |
| `\dn` | Seznam schémat | `\dn` |
| `\du` | Seznam rolí/uživatelů | `\du` |
| `\dt` | Seznam tabulek | `\dt` |
| `\dt+` | Seznam tabulek + velikost a popis | `\dt+` |
| `\dt *.*` | Tabulky napříč schématy | `\dt *.*` |
| `\di` | Jen indexy | `\di` |
| `\df` | Jen funkce | `\df` |
| `\dv` | Jen pohledy (views) | `\dv` |

### 1.2 Detail struktury (co je v tabulce)

| Příkaz | Význam | Příklad |
|--------|--------|---------|
| `\d ads` | Struktura tabulky (sloupce, typy, indexy) | `\d ads` |
| `\d+ ads` | Struktura + komentáře | `\d+ ads` |
| `\d pipeline_runs` | Struktura druhé tabulky | `\d pipeline_runs` |
| `\d ads` + `\d pipeline_runs` | Víc tabulek najednou | `\d ads` `\d pipeline_runs` |

### 1.3 Přehled přes SQL (bez psql, funguje i přes `db.ps1 query`)

```sql
-- Sloupce tabulky (informační schéma — meta-data o datech)
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'ads'
ORDER BY ordinal_position;

-- Všechny tabulky v schématu
SELECT tablename FROM pg_tables WHERE schemaname = 'public';

-- Velikost tabulky (hezký formát)
SELECT pg_size_pretty(pg_total_relation_size('ads'));
```

### 1.4 Práce s konzolí

| Příkaz | Význam | Příklad |
|--------|--------|---------|
| `\q` | Ukončení psql | `\q` |
| `\timing` | Zapnout měření času dotazu | `\timing` |
| `\x` | Vertikální zobrazení (široké řádky) | `\x` pak `SELECT * FROM ads LIMIT 1;` |
| `\x off` | Zpět na normální zobrazení | `\x off` |
| `\conninfo` | Info o připojení | `\conninfo` |
| `\?` | Nápověda psql | `\?` |
| `\h SELECT` | Nápověda k SQL příkazu | `\h SELECT` |

---

## 2. SELECT — základ a variace

```sql
-- Všechny sloupce
SELECT * FROM ads;

-- Vybrané sloupce
SELECT title, company, location FROM ads;

-- Alias (přejmenování sloupce ve výstupu)
SELECT title AS nazev, company AS firma FROM ads;

-- Bez duplicit (DISTINCT)
SELECT DISTINCT portal FROM ads;
SELECT DISTINCT company FROM ads;

-- Kolik unikátních hodnot (COUNT + DISTINCT)
SELECT COUNT(DISTINCT company) FROM ads WHERE company IS NOT NULL;

-- Kolik řádků celkem
SELECT COUNT(*) FROM ads;

-- Limit + offset (stránkování)
SELECT title FROM ads ORDER BY id LIMIT 5;         -- prvních 5
SELECT title FROM ads ORDER BY id LIMIT 5 OFFSET 5; -- dalších 5
```

---

## 3. WHERE — filtrování (jako auto-filtr v Excelu)

### 3.1 Přesná shoda

```sql
SELECT title, location FROM ads WHERE company = 'T-Mobile Czech Republic a.s.';
SELECT title FROM ads WHERE status = 'new';
SELECT title FROM ads WHERE portal = 'jobs';
```

### 3.2 Nerovnost a rozsahy

```sql
SELECT title FROM ads WHERE status <> 'new';          -- různé od (<> = !=)
SELECT title FROM ads WHERE id > 10;                  -- větší než
SELECT title FROM ads WHERE id BETWEEN 5 AND 10;      -- rozsah včetně krajů
SELECT title FROM ads WHERE id IN (1, 3, 7);          -- v seznamu
SELECT title FROM ads WHERE id NOT IN (1, 3, 7);      -- mimo seznam
```

### 3.3 Kombinace podmínek

```sql
-- AND = obě podmínky
SELECT title FROM ads WHERE status = 'new' AND portal = 'jobs';

-- OR = alespoň jedna
SELECT title FROM ads WHERE status = 'applied' OR status = 'seen';

-- Závorky mění prioritu
SELECT title FROM ads WHERE (status = 'new' OR status = 'seen') AND portal = 'jobs';

-- NOT = negace
SELECT title FROM ads WHERE NOT status = 'new';
```

---

## 4. Kontextové vyhledávání (ILIKE — jako Ctrl+F v Excelu)

**Klíčový vzor:** `ILIKE` = case-insensitive (nezáleží na velikosti písmen). `%` = cokoliv (0+ znaků), `_` = právě 1 znak.

```sql
-- Obsahuje slovo kdekoli
SELECT title FROM ads WHERE title ILIKE '%engineer%';

-- Slovo uprostřed
SELECT title FROM ads WHERE title ILIKE '%ai%';

-- Začíná na
SELECT title FROM ads WHERE title ILIKE 'junior%';

-- Končí na
SELECT title FROM ads WHERE title ILIKE '%python';

-- Kombinace více slov
SELECT title FROM ads WHERE title ILIKE '%python%' OR title ILIKE '%ai%';

-- Hledání ve více sloupcích
SELECT title, company FROM ads
WHERE title ILIKE '%python%' OR company ILIKE '%python%';

-- Hledání v názvu NEBO v popisu (nejdůležitější vzor pro job-hunt)
SELECT id, title, company, portal FROM ads
WHERE title ILIKE '%python%' OR description ILIKE '%python%';

-- Přesná shoda bez % (case-insensitive)
SELECT title FROM ads WHERE title ILIKE 'test job';
```

### 4.1 Hledání pomocí regeexu (SIMILAR TO — pokročilé)

```sql
-- Buď 'python' nebo 'ai' jako slovo
SELECT title FROM ads WHERE title ~* '(python|ai)';

-- Začíná na j nebo J
SELECT title FROM ads WHERE title ~* '^j';
```

**Pozn.:** pro běžné hledání stačí `ILIKE`. Regex je pro složitější vzory.

---

## 5. ORDER BY — řazení

```sql
-- Vzestupně (výchozí)
SELECT company FROM ads ORDER BY company;

-- Sestupně
SELECT company FROM ads ORDER BY company DESC;

-- Podle čísla
SELECT id, title FROM ads ORDER BY id DESC;

-- Podle více sloupců (firma, pak název)
SELECT company, title FROM ads ORDER BY company ASC, title ASC;

-- Podle aliasu
SELECT company AS firma, COUNT(*) AS pocet FROM ads GROUP BY company ORDER BY pocet DESC;
```

---

## 6. GROUP BY + COUNT — agregace (kontingenční tabulka)

```sql
-- Počet inzerátů podle firmy (sestupně)
SELECT company, COUNT(*) AS pocet FROM ads GROUP BY company ORDER BY pocet DESC;

-- Počet podle portálu
SELECT portal, COUNT(*) FROM ads GROUP BY portal;

-- Počet podle statusu
SELECT status, COUNT(*) FROM ads GROUP BY status;

-- Počet podle firmy, jen firmy s 2+ inzeráty (HAVING = filtr na agregát)
SELECT company, COUNT(*) AS pocet FROM ads GROUP BY company HAVING COUNT(*) >= 2 ORDER BY pocet DESC;

-- Další agregace
SELECT COUNT(*) AS celkem, MIN(id) AS min_id, MAX(id) AS max_id FROM ads;

-- Počet unikátních firem
SELECT COUNT(DISTINCT company) AS firem FROM ads WHERE company IS NOT NULL;

-- Top firmy podle počtu inzerátů
SELECT company, COUNT(*) FROM ads
WHERE company IS NOT NULL
GROUP BY company ORDER BY COUNT(*) DESC LIMIT 5;

-- Nové vs vrácené inzeráty (FILTER = podmíněné počítání v jedné agregaci)
SELECT status,
       COUNT(*) FILTER (WHERE first_seen = last_seen) AS nove,
       COUNT(*) FILTER (WHERE first_seen <> last_seen) AS vracene
FROM ads GROUP BY status;

-- Průměrné stáří inzerátu ve dnech
SELECT ROUND(AVG(CURRENT_DATE - first_seen)) AS prumer_dni FROM ads;

-- Nové inzeráty od včera
SELECT id, title, first_seen FROM ads
WHERE first_seen >= CURRENT_DATE - 1;
```

---

## 7. UPDATE + SET — změna stavu

```sql
-- Aktualizace jednoho řádku podle id
UPDATE ads SET status = 'applied' WHERE id = 7;

-- Hromadně podle podmínky
UPDATE ads SET status = 'seen' WHERE company = 'T-Mobile Czech Republic a.s.';

-- Více sloupců najednou
UPDATE ads SET status = 'applied', last_seen = CURRENT_DATE WHERE id = 7;

-- RETURNING = vrať změněné řádky (kontrola)
UPDATE ads SET status = 'rejected' WHERE id = 7 RETURNING id, title, status;

-- Kolik řádků změněno
UPDATE ads SET status = 'new' WHERE status = 'seen';
-- → "UPDATE 3" = počet změněných
```

**Pravidlo:** `UPDATE` bez `WHERE` změní **všechny** řádky. Vždy kontroluj `WHERE`.

---

## 8. Transakce — bezpečné zkoušení (nauč se to)

```sql
BEGIN;                                    -- začni transakci
UPDATE ads SET status = 'seen' WHERE status = 'new';
SELECT status, COUNT(*) FROM ads GROUP BY status;   -- podívej se, co by se stalo
ROLLBACK;                                 -- zruš vše od BEGIN (nic se nezměnilo)
```

```sql
BEGIN;
UPDATE ads SET status = 'seen' WHERE status = 'new';
COMMIT;                                   -- potvrď změny natrvalo
```

**Význam:** mezi `BEGIN` a `ROLLBACK`/`COMMIT` nic neprojde do databáze natrvalo. Je to "Ctrl+Z" pro DB. Používej při experimentování.

### 8.1 SAVEPOINT — záchytný bod uprostřed transakce

Užitečné, když chceš vrátit jen ČÁST změn, ne celou transakci.

```sql
BEGIN;
UPDATE ads SET status = 'seen' WHERE status = 'new';   -- dávka 1
SAVEPOINT bod1;                                        -- checkpoint po dávce 1
UPDATE ads SET status = 'applied' WHERE status = 'seen'; -- dávka 2
ROLLBACK TO SAVEPOINT bod1;                            -- zruš jen dávku 2
COMMIT;                                                -- dávka 1 zůstane
```

**Rozdíl:** `ROLLBACK` vrací všechno, `ROLLBACK TO SAVEPOINT` vrací jen část.

---

## 9. DELETE — mazání (s opatrností)

```sql
-- Smaž jeden řádek
DELETE FROM ads WHERE id = 7;

-- Smaž řádky podle podmínky
DELETE FROM ads WHERE status = 'rejected';

-- Vrať smazané
DELETE FROM ads WHERE id = 7 RETURNING id, title;
```

**Bezpečně:** `DELETE FROM ads;` bez WHERE smaže VŠE. Vždy `WHERE`. Pro jistotu testuj v transakci (`BEGIN; DELETE ...; ROLLBACK;`).

### 9.1 Dedup — mazání redundantní podmnožiny (reálné cvičení)

Dedup nemusí být jen `DELETE` duplicitních URL. Často je to identifikace **redundantní podmnožiny** — zde: ads z profilu `default` (smazaný config, run 7).

```sql
-- Krok 1: Ověř, co se smaže (DRY-RUN, žádná změna)
SELECT COUNT(*) FROM ads WHERE profile = 'default';

-- Krok 2: Self-JOIN — jsou opravdu duplicitní s jiným profilem?
-- (url má UNIQUE → 0 řádků = každá url jen pod jedním profilem)
SELECT a.id AS default_id, b.id AS legacy_id, a.url
FROM ads a JOIN ads b ON a.url = b.url
WHERE a.profile = 'default' AND b.profile = 'LEGACY-MANUAL';

-- Krok 3: Bezpečné mazání v transakci (airbag)
BEGIN;
DELETE FROM ads WHERE profile = 'default' RETURNING id, title, query_name;
SELECT COUNT(*) FROM ads;   -- kontrola po smazání
ROLLBACK;                    -- nebo COMMIT, když jsi si jistý

-- Krok 4: Mazání auditu (pipeline_runs je rodič, ads je dítě — bez FK)
-- Pořadí: nejdřív děti, pak rodič
BEGIN;
DELETE FROM ads WHERE profile = 'default';
DELETE FROM pipeline_runs WHERE profile = 'default';
COMMIT;
```

**Pedagogický klíč:** `HAVING` filtruje agregované skupiny (ne řádky), self-JOIN odhalí, zda je duplicita v URL nebo v tagu (profil/query).

---

## 10. Práce s pipeline_runs (JSONB metadata)

`pipeline_runs` obsahuje JSONB sloupec `metadata` — audit běhů pipeline.

```sql
-- Všechny běhy
SELECT id, status, matched, raw, started_at FROM pipeline_runs;

-- JSONB: hodnota z metadata (operátor ->)
SELECT id, metadata->>'new_ads' AS nove_inzeraty, metadata->>'elapsed_seconds' AS sekundy
FROM pipeline_runs;

-- JSONB: kontrola existence klíče
SELECT id FROM pipeline_runs WHERE metadata ? 'new_ads';

-- Počet běhů na profil
SELECT profile, COUNT(*) FROM pipeline_runs GROUP BY profile;
```

---

## 11. Kontrolní otázky (ověř, že rozumíš)

| Otázka | Odpověď |
|--------|---------|
| Jak najdeš všechny inzeráty firmy X? | `SELECT * FROM ads WHERE company = 'X';` |
| Jak najdeš inzeráty obsahující "python"? | `SELECT * FROM ads WHERE title ILIKE '%python%';` |
| Kolik inzerátů máš celkem? | `SELECT COUNT(*) FROM ads;` |
| Která firma má nejvíc inzerátů? | `SELECT company, COUNT(*) FROM ads GROUP BY company ORDER BY COUNT(*) DESC LIMIT 1;` |
| Jak označíš inzerát jako "applied"? | `UPDATE ads SET status = 'applied' WHERE id = N;` |
| Jak zrušíš změnu, kterou sis omylem udělal? | Transakce: `BEGIN; ... ROLLBACK;` (před COMMIT) |
| Jak najdeš inzeráty, které jsou "python" v názvu NEBO popisu? | `SELECT * FROM ads WHERE title ILIKE '%python%' OR description ILIKE '%python%';` |
| Jak zjistíš počet ads per profil? | `SELECT profile, COUNT(*) FROM ads GROUP BY profile;` |
| Jak zjistíš, co je v tabulce za sloupce? | `\d ads` (nebo `information_schema.columns`) |
| Jak zrušíš jen část změn v transakci? | `SAVEPOINT bod1; ... ROLLBACK TO SAVEPOINT bod1;` |
| Jak ukončíš psql? | `\q` |

---

## 12. Pravidla pro práci (bezpečnost)

1. **Vždy `WHERE`** u UPDATE a DELETE — jinak změníš/smažeš všechno.
2. **Transakce při experimentu** — `BEGIN` ... `ROLLBACK` chrání data.
3. **Středník `;`** ukončuje SQL příkaz. Zapomeneš-li ho, prompt `mcpjobs-#` čeká na pokračování — dopiš středník.
4. **`\q`** ukončí psql. Pager je vypnut (`-P pager=off`), takže nic neblokuje obrazovku.
5. **Data jsou reálná** — statusy `applied`/`seen`/`rejected` ovlivňují tvůj job-hunt workflow. Po experimentech je vrať do `new` (pokud nepokračuješ v reálném procesu).
6. **`WHERE` nevidí agregace, `HAVING` ano** — `WHERE COUNT(*) > 5` selže, `HAVING COUNT(*) > 5` funguje.
7. **SELECT \* bez LIMIT je riziko** — data převyšují intuici. Vždy `LIMIT` u průzkumu.
8. **NULL není 0** — porovnání s NULL vrací `UNKNOWN`. Používej `IS NULL` / `IS NOT NULL` / `COALESCE`.

---

*Dokument vytvořen: 2026-08-15 | Aktualizováno: 2026-08-18 | Autor: outpost2026 | Verze: 2.0*
*Provenance: source-read (live psql dotazy na reálných datech ETL běhů, \d ads, \d pipeline_runs, dedup cvičení 2026-08-18: 93 ads, 7 pipeline_runs)*
*Návaznost: edukace_db_prvni_kontakt_2026-08-15.md (jak otevřít DB), sql_ontologie_mechanismy_2026-08-15.md (mechanismy DDL/DML/DQL), POSTGRESQL_ontologie_epistemika_2026-08-18.md (ontologie + 8 pastí), IT_gramotnost_hranice_SQL_databazi_2026-08-15.md (teorie dvou vrstev)*