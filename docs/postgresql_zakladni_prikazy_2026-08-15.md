# PostgreSQL: Základní pracovní nástroje — příkazy pro práci s MCP-Jobs DB

**Datum:** 2026-08-15 | **Autor:** outpost2026
**Účel:** Referenční dokument nejdůležitějších SQL příkazů a psql meta-příkazů pro práci s MCP-Jobs databází — s kontextovým vyhledáváním a variacemi, ověřeno na reálných datech (26 ads, 12 firem, 2 portály)
**Návaznost:** `docs/edukace_db_prvni_kontakt_2026-08-15.md` (jak otevřít DB), `05_EPISTEMIKA/03_kognitivni_ontologie_nastroju/IT_gramotnost_hranice_SQL_databazi_2026-08-15.md`
**Provenance:** source-read (live dotazy přes `docker exec mcp-jobs-postgres psql` na reálných datech ETL běhů)

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

| Příkaz | Význam | Příklad |
|--------|--------|---------|
| `\l` | Seznam databází | `\l` |
| `\dt` | Seznam tabulek | `\dt` |
| `\d ads` | Struktura tabulky (sloupce, typy, indexy) | `\d ads` |
| `\d pipeline_runs` | Struktura druhé tabulky | `\d pipeline_runs` |
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
| Jak ukončíš psql? | `\q` |

---

## 12. Pravidla pro práci (bezpečnost)

1. **Vždy `WHERE`** u UPDATE a DELETE — jinak změníš/smažeš všechno.
2. **Transakce při experimentu** — `BEGIN` ... `ROLLBACK` chrání data.
3. **Středník `;`** ukončuje SQL příkaz. Zapomeneš-li ho, prompt `mcpjobs-#` čeká na pokračování — dopiš středník.
4. **`\q`** ukončí psql. Pager je vypnut (`-P pager=off`), takže nic neblokuje obrazovku.
5. **Data jsou reálná** — statusy `applied`/`seen`/`rejected` ovlivňují tvůj job-hunt workflow. Po experimentech je vrať do `new` (pokud nepokračuješ v reálném procesu).

---

*Dokument vytvořen: 2026-08-15 | Autor: outpost2026 | Verze: 1.0*
*Provenance: source-read (live psql dotazy na reálných datech ETL běhů, \d ads, \d pipeline_runs)*
*Návaznost: edukace_db_prvni_kontakt_2026-08-15.md (jak otevřít DB), IT_gramotnost_hranice_SQL_databazi_2026-08-15.md (teorie dvou vrstev)*