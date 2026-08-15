# Edukační dokument: Port MCP serveru na standalone produkt

**Datum:** 2026-08-15 | **Autor:** outpost2026 (junior dev, praxe < 5 měsíců) | **Verze:** 1.0
**Kontext vlákna:** Výzkum možností vylepšení MCP-jobs pipeline → analýza `outprep` (clone repa šachového vývojáře) jako vzoru standalone produktu.

> ⚠️ **Pro koho je dokument určen:** pro mě samotného jako juniora, který se učí imerzně — každý koncept vysvětluji od základů, protože jsem se s ním v praxi ještě nesetkal. Není to návod pro experta, ale **výukový zápisník** zaznamenávající, co jsem se naučil při řešení reálného úkolu.

---

## 1. Proč čtu cizí repozitáře a co hledám

### 1.1 Imerzní učení

Když jsem řešil vylepšení MCP-lichess serveru, narazil jsem na repozitář `outprep` — standalone webovou aplikaci pro šachovou přípravu (skaut hráče, analýza zahájení, trénink proti botu). Je to **typický příklad imerzního učení**: při řešení *vlastního* problému nacházím domény a architektury SW, které jsem neznal, ale které by mohly rozšířit moje portfolio.

**Klíčová myšlenka:** nekopíruji řešení, ale **vstřebávám ontologii** — názvy, architektury, terminologii, důvody, proč se věci dělají tak, jak se dělají.

### 1.2 Co mě konkrétně zajímá

Zadal jsem si výzkumný cíl:
> "Lze přestavět MCP server (dnes spouštěný přes IDE jako opencode) na **standalone produkt** — samostatný software, který běží sám, s GUI na vlastním hostovaném webu (systeq.cz)?"

`outprep` je dokonalý případ: je to přesně ten typ standalone app, který si představuji, ale pro šachy.

---

## 2. MCP server vs. standalone produkt — zásadní rozdíl (deliverables)

### 2.1 Co dnes je MCP-jobs

Můj MCP-jobs je **MCP (Model Context Protocol) server**:
- Běží **jen když je volán z klienta** (např. z IDE opencode)
- Je to **knihovna/rozhraní**, ne samostatná aplikace
- Komunikuje přes **STDIO** (standard input/output) s hostitelským procesem
- Nemá vlastní UI — výstup konzumuje LLM agent v IDE
- Nemá vlastní perzistenci — data jen `output/*.json` a `.md`

```
[LLM/IDE (opencode)] ←STDIO→ [MCP-jobs server] → [scrape portálů] → [output/*.json,.md]
```

### 2.2 Co je standalone produkt (outprep model)

`outprep` je **webová aplikace**, která běží **sama**, bez toho, aby ji někdo musel volat:

```
[Browser uživatel] → [Next.js web (UI)] → [API routes] → [scrape/ETL] → [PostgreSQL]
                                                                   ↓
                                                          [Vercel Cron (automatický běh)]
```

| Vlastnost | MCP server | Standalone produkt |
|---|---|---|
| Spuštění | Na vyžádání z klienta | Samostatně (server, daemon) |
| Uživatelské rozhraní | Žádné (API/LLM) | Web GUI |
| Perzistence | Soubory | Databáze |
| Automatický běh | Ne (musí ho někdo zavolat) | **Cron/scheduler** |
| Distribuce | Konfigurace MCP | Nasadit na hosting / Docker |
| Uživatel | LLM agent | Člověk (nebo LLM) |

**Deliverable = forma, ve které produkt běží.** To je to, co chce uživatel posuzovat: ne koncepci pipeline, ale to, v jakém *formátu* běží.

---

## 3. Ontologie — slovníček pojmů (které jsem neznal a musím je vstřebat)

> Každý pojem vysvětluji na reálném příkladu z `outprep` nebo z vlastního MCP-jobs.

### 3.1 Monorepo & npm workspaces

**Monorepo** = jedno git repo obsahující více projektů (packages), které spolu souvisí a sdílí historii.

**npm workspaces** = mechanismus npm, který umožňuje monorepo. V `outprep/package.json`:
```json
"workspaces": ["packages/*"]
```
To znamená: vše v `packages/` je samostatný balíček, ale instalace závislostí je sdílená (jeden `node_modules` v kořeni).

**Konkrétní příklad z outprep** — 3 balíčky + 1 web:
```
outprep/
  src/                    # Next.js web (frontend + API)
  packages/engine/        # @outprep/engine — core bot logika (TS lib)
  packages/fide-pipeline/ # @outprep/fide-pipeline — ETL/CLI (download, parse, seed)
  packages/harness/       # @outprep/harness — CLI pro testování accuracy bota
```

**Proč se to dělá:** oddělení zodpovědnosti. ETL pipeline (náročný, dlouhý) nechceš míchat s webem (rychlý, uživatelsky orientovaný). Balíčky jsou samostatně testovatelné a znovupoužitelné.

**Analogii pro job-hunt:**
```
MCP-Jobs (aspirace)/
  src/            # web UI (Next.js)
  packages/etl/   # Python CLI (dnešní MCP-jobs scrape pipeline)
  packages/core/  # sdílená logika (matcher, report renderer)
```

### 3.2 CLI (Command Line Interface) pipeline jako separátní balíček

`outprep` oddělil ETL do samostatného CLI (`packages/fide-pipeline`). Spouští se:
```bash
npm run fide-pipeline -- full --from 924 --to 1633
npm run fide-pipeline -- smoke
```

V `packages/fide-pipeline/package.json` vidíme **commander** (CLI framework):
```json
"dependencies": { "commander": "^12.0.0", "p-limit": "^7.3.0", "postgres": "^3.4.8" }
```

**Proč je CLI oddělené od webu?**
- ETL je **dlouhý, paměťově náročný, dávkový** (parsování GB dat)
- Web je **rychlý, interaktivní, požadavek-odpověď**
- Když to namícháš, web se zablokuje při ETL běhu → **špatná architektura**
- CLI může běžet samostatně (cron, server), nezávisle na webu

**Můj MCP-jobs už tohle dělá** — mám `scripts/run_etl.py` jako CLI! Takže tento princip už znám, jen jsem ho neměl pojmenovaný.

### 3.3 Port — co to je a proč existuje

**Port** v SWE = číslo/identifikátor, na kterém proces "poslouchá" síťové požadavky. Čísla 0–65535. Konvence:
- **80** — HTTP (web)
- **443** — HTTPS (šifrovaný web)
- **5432** — PostgreSQL (databáze)
- **3000** — typický dev server (Next.js `npm run dev` → localhost:3000)
- **5000** — běžný dev backend (Python Flask/FastAPI)
- **6379** — Redis (cache)

**Důležité pro juniora:** každý protokol/jazyk má "svoje" dobře zavedené porty, ale **čísla jsou jen konvence** — můžeš použít jakýkoli volný. Důležité je, že:
1. Port musí být **unikátní na daném počítači** (dva procesy nemohou poslouchat stejný port)
2. Služby spolu komunikují přes porty (web → DB na 5432)

**Proč to děláme / proč se to dělá běžně:**
- Umožňuje **více aplikací na jednom serveru** (nginx na 80, rozděluje na různé appky na různých portech)
- **Izolace** — každá služba má svůj port, nemíchají se
- **Docker compose** definuje porty v `docker-compose.yml` (viz outprep: `"5432:5432"`)

**Příklad z outprep `docker-compose.yml`:**
```yaml
services:
  postgres:
    image: postgres:16
    ports:
      - "5432:5432"   # hostitelský port : kontejnerový port
```

**Různé jazyky = různé ekosystémy, ale stejný princip portů:**
| Jazyk/framework | Dev port | Poznámka |
|---|---|---|
| Python FastAPI | 8000 | `uvicorn app:app` |
| Python Flask | 5000 | klasika |
| Node/Express | 3000/8080 | `app.listen(3000)` |
| Next.js | 3000 | `next dev` |
| React/Vite | 5173 | `vite` |
| .NET | 5000/7000 | Kestrel |
| Java Spring | 8080 | standard |

**Názvosloví:** `localhost:3000` = loopback (jen lokální počítač). Nasazeno na server → `https://systeq.cz` bez portu (default 443).

### 3.4 API routes — backend jako součást webu

`outprep` používá **Next.js App Router** — backend je ve složce `src/app/api/`:
```
src/app/api/
  profile/[username]/route.ts      # GET profilu hráče
  lichess/[username]/route.ts      # Lichess proxy
  cron/twic-update/route.ts        # Vercel Cron endpoint
  opening-book/[username]/route.ts # zahajovací kniha
```

Každý `.ts` soubor v `api/` = **HTTP endpoint**. Když prohlížeč/klient zavolá `GET /api/profile/magnus`, Next.js spustí `route.ts`.

**Proč tohle dává smysl pro standalone:**
- **Jeden jazyk** (TypeScript) pro frontend i backend — nemusím psát Python API server zvlášť
- Next.js serverless — automaticky škáluje, bez správy serveru
- API routes může volat i **můj MCP server** přes HTTP (dnes STDIO, zítra HTTP)

**Zajímavost pro mě (junior):** outprep používá **NDJSON streaming** — místo poslání celé odpovědi najednou posílá řádky postupně. To umožňuje ukázat první část dat, zatímco se zbytek ještě počítá. Důležité pro dlouhé ETL/výpočty.

### 3.5 Databáze (PostgreSQL) — proč soubory nestačí

Toto je **největší architektonický posun** oproti mému MCP-jobs.

**Můj MCP-jobs dnes:** ukládá výsledky do `output/*.json` a `*.md` souborů. Každý run = nový soubor. Problémy:
- **Žádná historie** s dotazováním ("co bylo minulý týden?")
- **Žádné vztahy** mezi daty (inzerát ↔ query ↔ dedup)
- **Žádné dedup napříč runy** (ten samý inzerát se objeví každý den)
- **Soubory se hromadí**, nemá smysl je mazat podle relevance

**outprep používá PostgreSQL** (relační databáze). V `src/lib/db/schema.sql` vidíme tabulky:
- `players` (80K+ hráčů)
- `games` (3M+ her, PGN v TOAST komprimaci)
- `events` (agregované turnaje)
- `pipeline_runs` (sledování ETL běhů!)
- `online_profiles` (cache profilů)

**Proč je `pipeline_runs` tabulka brilantní** — to je přesně to, co MCP-jobs chybí:
```sql
CREATE TABLE pipeline_runs (
  id, run_type, identifier, status,   -- 'running' | 'completed' | 'failed'
  started_at, completed_at, metadata
);
```
→ **Auditovatelnost ELT.** Vím, kdy běh proběhl, jak dopadl, co zpracoval. Dnes to v MCP-jobs řeším jen soubory + correlation_cache.

**SQL výrazy, které bych měl znát (junior):**
- `CREATE TABLE` — definice tabulky
- `INDEX` — zrychlení dotazů (vyhledávání podle sloupce)
- `JSONB` — Postgres umí ukládat JSON sloupce (flexibilní data bez strict schématu)
- `UNIQUE INDEX` — zajištění, že se hodnota neopakuje (dedup!)
- `SERIAL` — auto-increment ID

**Analogii pro job-hunt (co bych vytvořil):**
```sql
CREATE TABLE ads (
  id SERIAL PRIMARY KEY,
  url TEXT NOT NULL UNIQUE,        -- dedup!
  title TEXT, company TEXT, location TEXT, salary TEXT,
  description TEXT,
  matched_keyword TEXT,
  first_seen DATE, last_seen DATE,  -- "znovu nabídnout po týdnu"
  status TEXT                        -- new / seen / applied / rejected
);

CREATE TABLE pipeline_runs (...);    -- audit ETL běhů
```

### 3.6 Provider-agnostic DB — nulový vendor lock-in

`outprep/src/lib/db/connection.ts` používá balíček `postgres` (porsager). To je **provider-agnostic** — funguje s jakýmkoli PostgreSQL hostem:
- Lokální Docker (dev)
- Neon (serverless Postgres, gratis tier)
- Supabase
- Railway
- Vercel Postgres

```ts
const connectionString = process.env.DATABASE_URL;
const rawSql = postgres(connectionString, { max: 10, idle_timeout: 20 });
```

**Proč to dělají:** nechtějí být závislí na jednom cloudu. Změna poskytovatele = změna jedné env proměnné, ne kódu.

**Pro mě:** `DATABASE_URL` v `.env` je konfigurace, ne kód. Stejný princip jako můj `config.yaml`.

### 3.7 Environment variables (.env)

`outprep/.env.example`:
```
DATABASE_URL=postgres://outprep:outprep@localhost:5432/outprep
CRON_SECRET=...
```

**Proč:** konfigurace (hesla, URL, secret) **nikdy nepatří do kódu/gitu**. `.env` je lokální soubor (gitignored), `.env.example` je šablona bez tajemství.

**Toto už znám z MCP-jobs** — mám `.gitignore` s `*.env`, `*.key`, `*.pem`, `credentials*` (bezpečnostní pravidla AGENTS.md).

### 3.8 Scheduling / Cron — automatizace bez člověka

**Cron** = plánovač, který spouští úlohy v pravidelných intervalech. Formát `vercel.json` v outprep:
```json
{
  "crons": [
    { "path": "/api/cron/twic-update", "schedule": "0 6 * * 1" },
    { "path": "/api/cron/fide-ratings", "schedule": "0 6 1 * *" }
  ]
}
```
- `0 6 * * 1` = každé pondělí 6:00 UTC
- `0 6 1 * *` = každý 1. den v měsíci 6:00

**Proč je tohle esence standalone ELT:** MCP-jobs dnes musím spouštět ručně z IDE. **Produkční ELT běží sám** — denně v noci scrapne, zpracuje, uloží. Ráno otevřeš web a vidíš výsledky.

**Pro job-hunt:** cron každý den v 5:00 → scrape portálů → uložit do DB → vygenerovat report.

### 3.9 Monitoring (healthchecks.io)

outprep v `api/cron/twic-update/route.ts`:
```ts
if (!hasErrors && process.env.HEALTHCHECKS_TWIC_URL) {
  fetch(process.env.HEALTHCHECKS_TWIC_URL).catch(() => {});
}
```

**healthchecks.io** = služba "dead man's switch". Cron na konci pingne URL. Pokud ping nepřijde (pipeline spadla, server nesvítí), healthchecks pošle upozornění (email).

**Proč:** cron mlčí = nevíš, jestli běží. Tohle zajistí, že víš o selhání dřív, než si všimneš, že nejsou data.

### 3.10 Migrace — bezpečná evoluce schématu

`outprep` má idempotentní migrace (`src/lib/db/migrations/`):
- `IF NOT EXISTS`
- Column-existence checks

**Idempotentní** = dá se spustit vícekrát bez chyby. Proč: nasazení není 100% deterministické, můžeš migraci spustit dvakrát. Idempotence to udělá bezpečným.

---

## 4. Porovnání: můj MCP-jobs vs. outprep model

| Vrstva | MCP-jobs (dnes) | outprep (standalone vzor) | Chybí mi? |
|---|---|---|---|
| **Spouštění** | Manuální z IDE (opencode) | Vercel Cron / server | ✅ ANO |
| **Perzistence** | `output/*.json,.md` | PostgreSQL (relační + JSONB) | ✅ ANO |
| **Historie/dedup napříč runy** | Částečně (correlation_cache) | DB UNIQUE indexy | ✅ ANO |
| **UI** | Žádné | Next.js web GUI | ✅ ANO |
| **Backend API** | MCP (STDIO) | Next.js API routes (HTTP) | ✅ ANO |
| **Monitorování** | Ruční kontrola | healthchecks.io | ✅ ANO |
| **Testování** | pytest (jednotkové) | vitest + harness (integration) | Částečně |
| **CI/CD** | Žádné | husky + lint-staged + Playwright | ✅ ANO |
| **CLI ETL** | `run_etl.py` | `fide-pipeline` CLI | ✅ MÁM |
| **Report renderer** | `report.py` (MD+HTML) | — (jiná doména) | ✅ MÁM |

---

## 5. Tři cesty portu (deliverables) — s hodnocením confidence

> **Confidence (conf)** = moje míra přesvědčení, že dané řešení zvýší produkční kvalitu a je proveditelné (0–1). Není to vědecká metrika, ale odhad juniora na základě toho, že to *někdo reálně udělal* (outprep je důkaz proveditelnosti).

### A. Next.js standalone na systeq.cz (conf 0.9)

Kopíruje outprep model 1:1:
- Monorepo: `src/` (web) + `packages/etl` (Python CLI) + `packages/core`
- API routes volají Python ETL (přes subprocess) NEBO ETL portnu do TS
- Deploy na **Vercel** (gratis) + **Neon** (gratis Postgres)
- Cron: Vercel Cron pro denní scrape
- GUI: dashboard inzerátů, priority, dedup, filter, **export PDF** (mám už HTML+CSS renderer s Calibri/A4!)
- Doména systeq.cz → Vercel

**Výhody:** plně managed, žádná správa serveru, škálování zdarma. **Nevýhody:** Python ETL na serverless je ošemetné (long-running, paměť) — buď port na TS, nebo samostatný worker.

### B. Dockerized standalone server (conf 0.85)

- Python FastMCP server **zabalím do Docker image**, běží jako služba
- Vlastní VPS (systeq.cz) s nginx → frontend → REST/GraphQL k Pythonu
- Docker Compose: `python-etl` + `postgres` + `web` (viz outprep docker-compose)

**Výhody:** Python zůstává, plná kontrola, běží kdekoliv. **Nevýhody:** musím spravovat server, security, updaty, zálohy.

### C. CLI + tenký web hybrid (conf 0.8)

- ETL zůstane CLI (dnešní `run_etl.py`)
- Přidám tenký web, který CLI spouští a čte výstup
- Nejméně práce, ale méně "app feel" a cron/monitoring zůstávají ruční

**Doporučení pro mě (juniora):** začít **variantou C** (nejmenší skok, naučím se Next.js API routes + UI na stávajícím Python ETL), pak postupně přesunout k **A nebo B**. Imerzní učení = malé, zvládnutelné kroky.

---

## 6. SWE nástroje, které zvyšují produkční kvalitu (conf > 0.8)

Na základě outprep — co MCP-jobs **konkrétně chybí** a jaké nástroje/řešení to řeší:

| Nástroj/řešení | Conf | Problém, který řeší | Reálný příklad z outprep |
|---|---|---|---|
| **PostgreSQL + schema + migrace** | 0.9 | Perzistence, dedup, historie, dotazování | `src/lib/db/schema.sql`, `migrations/` |
| **Scheduling (Vercel Cron / cron)** | 0.9 | ELT musí běžet sám bez IDE | `vercel.json` crons |
| **healthchecks.io** | 0.85 | Vědět, že ETL proběhl | `twic-update/route.ts` fetch |
| **Provider-agnostic DB client** | 0.85 | Nulový vendor lock-in | `connection.ts` (postgres pkg) |
| **CI/CD (GitHub Actions)** | 0.85 | Build+test na push, chytí regrese | husky + lint-staged |
| **Testování ETL dat** | 0.8 | Ověřit, že transformace dává smysl | `harness` (replay + accuracy) |
| **Rate limiting / retry / backoff** | 0.85 | Nezpůsobit problémy scrapovaným serverům | `request_delay` (outprep i MCP-jobs) |
| **Orchestrátor (Dagster/Airflow/Prefect)** | 0.3 | Pro single-user job-hunt **overkill** | outprep ho NEMÁ — jen CLI + cron |

> **Důležité ponaučení pro juniora:** ne každý problém vyžaduje těžké nástroje. outprep zpracovává **miliony her bez orchestrátoru** — používá prostý CLI + cron. Stejně tak job-hunt (desítky inzerátů denně) orchestrátor nepotřebuje. **Jednoduchost je vlastnost.**

---

## 7. Jak se šachy liší od job-huntu (abych nepřekopíroval zbytečně)

| Aspekt | outprep (šachy) | Můj job-hunt | Důsledek |
|---|---|---|---|
| Objem dat | 3M+ her, 80K hráčů, GB | desítky inzerátů/den | Nepotřebuji bulk infra |
| Write-heavy | Ano (bulk seed) | Ano, ale malý | Jednoduché INSERT |
| Náročnost ETL | Obří (TWIC, GB parsing) | Malá (4 portály) | Nepotřebuji multi-pass streaming |
| Latence | Streaming nutný | Streaming bonus | NDJSON je hezké, ne nutné |
| Scheduling | Týdně/měsíčně | **Denně** (nové inzeráty) | Cron kritičtější |

**Závěr:** učím se **patterny** (monorepo, DB persistence, cron, monitoring, provider-agnostic), ne přebírám těžkou infra.

---

## 8. Slovník pojmů (rychlá reference pro mě)

| Pojem | Význam |
|---|---|
| **Standalone** | Samostatně běžící aplikace (na rozdíl od závislé na klientovi) |
| **Deliverable** | Forma/výstup, ve kterém produkt běží a je doručen |
| **Monorepo** | Jedno repo s více balíčky |
| **npm workspaces** | Mechanismus monorepo v JS |
| **CLI** | Command Line Interface — program ovládaný z terminálu |
| **Port** | Číslo, na kterém služba poslouchá síť (80, 443, 5432, 3000...) |
| **API route** | HTTP endpoint v Next.js (`src/app/api/.../route.ts`) |
| **PostgreSQL** | Relační databáze (tabulky, řádky, SQL) |
| **JSONB** | JSON sloupec v Postgres (flexibilní data) |
| **Index** | Zrychlení dotazu v DB |
| **UNIQUE index** | Dedup v DB (hodnota se neopakuje) |
| **Schema** | Definice struktury DB (tabulky, sloupce) |
| **Migrace** | Evoluce schématu, idempotentní (bezpečně opakovatelná) |
| **Provider-agnostic** | Funguje s jakýmkoli poskytovatelem (bez vendor lock-in) |
| **Cron / Scheduler** | Automatický plánovač úloh |
| **healthchecks.io** | Dead-man's-switch monitoring cronu |
| **Env proměnná** | Konfigurace mimo kód (.env), nikdy v gitu |
| **Serverless** | Běží na cloudu bez správy serveru (Vercel, Neon) |
| **Docker / container** | Zabalená aplikace + závislosti, běží kdekoliv |
| **Vendor lock-in** | Závislost na jednom dodavateli, těžké migrovat |
| **NDJSON streaming** | Postupné posílání dat po řádcích (místo celé odpovědi) |
| **Idempotentní** | Dá se spustit vícekrát bez chyby |
| **Overkill** | Zbytečně moc nástroje na malý problém |

---

## 9. Co jsem se naučil (reflexe juniora)

1. **MCP server není standalone produkt** — je to rozhraní pro klienta. Standalone = samostatná web app s UI, DB, cronem, monitoringem.
2. **Deliverables = forma běhu.** Nezáleží jen na tom, *co* pipeline dělá, ale *jak a kde* běží.
3. **CLI ETL oddělený od webu** je osvědčený pattern (outprep: `fide-pipeline`). Můj `run_etl.py` už to dělá.
4. **Soubory nejsou databáze.** Pro historii, dedup a dotazování potřebuji PostgreSQL.
5. **Automatizace = cron + monitoring.** ELT musí běžet sám a vědět, že se mu něco stalo.
6. **Nepotřebuji orchestrátor pro malou pipeline** — jednoduchost je vlastnost, ne nedostatek.
7. **Porty jsou konvence, ne magie.** 3000 pro dev, 5432 pro Postgres, 443 pro web.
8. **Provider-agnostic DB** = změníš `.env`, ne kód.
9. **Imerzní učení funguje:** při řešení job-hunt pipeline jsem se naučil monorepo, DB schema, cron, monitoring — věci, které bych jinak studoval abstraktně.

---

## 10. Další kroky (navrhované)

1. **[Možnost] Vytvořit migrační plán** — mapovat stávající MCP-jobs moduly na novou architekturu (Postgres schema, API routes, UI komponenty, cron, monitor).
2. **[Možnost] Praktický mini-krok:** přidat do MCP-jobs **PostgreSQL persistence** místo čistě souborů (nejmenší skok, největší přínos pro produkční kvalitu).
3. **[Možnost] Nastavit healthchecks.io + cron** pro stávající `run_etl.py` — okamžitá automatizace bez velkého refaktoru.
4. **[Možnost] Vytvořit Next.js dashboard** čtoucí `output/*.json` — první standalone GUI, bez portu ETL.

---

*Edukační dokument vytvořen imerzní metodou — na základě analýzy `outprep` a vlastní MCP-jobs codebase. Všechny pojmy vysvětleny od základů pro juniora s praxí < 5 měsíců.*
