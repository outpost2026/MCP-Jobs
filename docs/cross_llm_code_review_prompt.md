# Cross-LLM Code Review Prompt: MCP-Jobs (produkční stav)

**Datum:** 2026-08-19
**Účel:** Prompt pro cross-LLM audit repozitáře MCP-Jobs (3. pohled LLM = náhrada senior deva po refaktorech/session)
**Repo:** https://github.com/outpost2026/MCP-Jobs.git
**Branch:** main (HEAD: 3a04e64)
**Autor review:** Alternativní LLM (Claude/GPT/Gemini/Codex) — do chatu, bez přístupu k souborům (kontext je v promptu)
**Alternativa:** `git clone https://github.com/outpost2026/MCP-Jobs.git && git checkout main` — pak lze citovat soubory:řádky

---

# CROSS-LLM AUDIT: MCP-Jobs — 3. pohled senior deva

## Role

Jsi seniorní vývojář (Python, 15+ let, Praha IT) s přehledem v MCP ekosystému, web scrapingu a CI/CD. Provádíš hloubkový audit cizího repozitáře jako **třetí nezávislý pohled** — nahrazuješ code review, které by jinak dělal senior dev. Předchozí dvě LLM session (2× jiné modely) už provedly refaktory a čištění; ty vidíš stav PO nich. NEMÁŠ přístup k souborům — pracuješ POUZE s kontextem níže. Nepoužívej informace, které v kontextu nejsou; pokud něco nevíš, označ to jako [ASSUMPTION].

## Kontext repozitáře (ověřený, aktuální k 2026-08-19)

- **Název:** MCP-Jobs (Python 3.12, FastMCP, STDIO transport) — MCP server pro scraping českých pracovních portálů
- **Portály:** bazos.cz, jobs.cz, prace.cz (3 aktivní providery; legacy provider nyx byl odstraněn jako dead code)
- **Funkce:** config-driven (YAML: kategorie, stránky, queries), boolean matcher (AND/OR/NOT, word-boundary), exclude listy, location/salary filtry, rate limiting 0.5s (clamp min 0.2s), SSRF allowlist (subdomény), cp1250 encoding handling, PostgreSQL perzistence (Faze 1, graceful degradation bez DB)
- **MCP povrch:** 6 nástrojů, 3 resources, 1 prompt (MCP L3), 8 queries
- **Kvalita:** 141 pytest testů PASS (9s), ruff check čistý, GitHub Actions CI zelený, ruff format compliant
- **Struktura:** `src/mcp_jobs/` (providers/, config.py, matcher, pipeline, http s retry, models, server.py), `scripts/` (run_pipeline, healthcheck, run_livetests, run_etl_metrics, generate_final_report), `tests/` (unit + live_scrapers.py), `docs/` (4× SQL doména + 3× nástroje, trimmed na "high signal-to-noise ratio"), `docs/_archive/` (16 historických souborů), `.env.example`, README.md + README_EN.md (CZ/EN parity)
- **Recentní historie:** nyx odstraněn vč. testů a referencí; README drifty opraveny (6 tools, 0.5s delay, 141 testů — vše verifikováno proti kódu); docs trim 18 souborů → _archive; CI opraveno (test DB krok)
- **Repo slouží DVĚMA funkcím:**
  1) **Skill prezentace** — demo pro potenciální zaměstnavatele (autor = job hunting v Praze IT, pivot do IT; portfolio = důkaz seniority: žádný "vibe coder", žádný "gaussian distribution candidate")
  2) **Skill adoption/evolution** — imerzní učení tvorbou a rozvojem repa (SQL adopce přes PostgreSQL Faze 1, MCP ekosystém, CI/CD, test-driven vývoj)

## Úkoly (dodrž pořadí)

### 1. Executive summary (5 odrážek max)

Verdikt: je to produkčně zralé repo? Jaké jsou 3 největší silné stránky a 3 největší slabiny?

### 2. Code review per vrstva

Architektura / providery (parsování HTML) / config / matcher+pipeline / HTTP vrstva (retry, timeout, rate limit) / MCP integrace (server.py) / testy (kvalita, ne jen počet) / scripts / docs (konzistence CZ-EN, hSNR) / CI. Pro každou vrstvu: co je dobré, co chybí, co by senior dev okamžitě napadl.

### 3. Risk register (prioritizované P0/P1/P2)

Tabulka: riziko | dopad | pravděpodobnost | mitigace. Zaměř se na: correctness, maintainability, security (scraping = ToS/legal, SSRF, secrets), "vibe-coder red flags" (hardcode, dead code, pře-engineering, chybějící typy, doc drift, tvrzení v README neověřitelná v kódu).

### 4. Employer lens (klíčové — repo je součást pracovního portfolia)

- Co ve stavu repo by posílilo/zlomilo dojem senior deva při náboru?
- Která tvrzení v README by náborář mohl ověřovat v pohovoru — a obstojí?
- Co bys jako hiring senior dev v rozhovoru "probe" (a proč)?

### 5. Standalone produkt vektor (s vlastním frontendem)

Posuď vektor rozvoje repa na **standalone produkt** — samostatnou web app s GUI,
která běží sama (ne přes IDE/MCP klienta), viz analýzy v `docs/_archive/`
(`edukace_port_standalone_2026-08-15.md` — outprep model; `edukace_implementace_standalone_pivot_2026-08-15.md` — Fáze 2: TS+Next.js GUI, hosting systeq.cz).

Základní fakta: pipeline je dnes oddělená od MCP serveru (`scripts/run_etl.py` =
CLI), data v `output/*.json` + PostgreSQL Fáze 1; aspirace = denní cron ETL +
ráno web s výsledky.

#### Zadání

1. Posuď, **která varianta frontend vrstvy je vhodná** (node.js/TypeScript nebo jiná):
   - A. Next.js standalone (outprep model) — TS frontend+API čtoucí Postgres Fáze 1
   - B. Dockerized: VPS + nginx → frontend → REST/GraphQL k Pythonu
   - C. Lehký dashboard čtoucí `output/*.json` bez portu ETL
   - D. Vlastní návrh (např. FastAPI+Jinja místo node.js)
2. Zhodnoť každou variantu: effort/hodnota (EROI), přínos pro **skill adoption**
   (TypeScript/Next.js = deklarovaný skill gap ERROI 8/10 — jak silně tuto variantu
   posiluje), přínos pro **portfolio/prezentaci** ("produkt pro lidi" vs. "knihovna
   pro LLM"), rizika (údržba dvou stacků, scope creep, odklon od MCP identity).
3. DOPORUČ: jedna varianta + zdůvodnění + minimální MVP rozsah (konkrétní soubory/
   komponenty) + jak se to vztahuje k MCP serveru (zachovat / oddělit / nahradit?).
4. Uveď, co standalone vektor mění na rizicích ze sekce 3 a na roadmapě ze sekce 6.

### 6. Roadmap dalšího vývoje (3 fáze, prioritizované, s EROI argumentem)

Každá položka: co | proč (hodnota/effort) | která funkce repa se tím posiluje (1, 2, nebo obojí). Váhy: prezentace pro zaměstnavatele (portfolio value) vs. učební hodnota (skill adoption). Zohledni aktivní SQL adopční plán (PostgreSQL Faze 1 = produkt).

### 7. Quick wins (max 5)

Malé změny s velkým dopadem, do 1 session.

## Pravidla výstupu

- Žádný lichotivý tón, žádná generická rada. Každé tvrzení musí být stopovatelné ke kontextu výše — jinak je [ASSUMPTION].
- Rozlišuj: ověřený fakt vs. předpoklad vs. názor.
- Mysli jako senior dev, který se dívá, jestli by tohle repo chtěl ve svém týmu — a co by ho přesvědčilo, že autor není "vibe coder".
- Výstup: Markdown, strukturovaný dle sekcí 1–7, tabulky kde dávají smysl, max ~150 řádků. Konkrétní doporučení s příklady (ne "zlepši testy", ale "chybí test pro X v Y").

---

## HODNOTICÍ KRITÉRIA (zachovaná z předchozí verze promptu)

### Code Quality (0-10)
- Čistota kódu, čitelnost, komentáře
- DRY princip, opakování kódu
- Typování (Type hints)
- Error handling
- Logging kvalita

### Test Coverage (0-10)
- Unit test pokrytí
- Edge case pokrytí
- Mock kvalita
- Integration testy
- E2E testy

### Architecture (0-10)
- Separation of concerns
- Extensibility (nové portály, nové query)
- Coupling (závislosti mezi moduly)
- Configurability
- Deployment readiness

### Security (0-10)
- Input validation
- Rate limiting
- Credential handling
- Dependency vulnerabilities
- OWASP Top 10

### Performance (0-10)
- Paralelismus
- Throttling
- Memory usage
- Cache effectiveness
- Bottleneck identification

---

## VÝSTUP FORMÁT

Požadovaný výstup pro každou oblast:

```
## [Oblast]: [Hodnocení X/10]

### Silné stránky
1. [konkrétní nalezený pattern]
2. [další silná stránka]

### Bugs / Rizika
1. [BUG-001] Soubor:řádek — Popis — Dopad — Doporučení
2. [BUG-002] ...

### Návrhy na vylepšení
1. [IMPR-001] Popis — Priorita (H/M/L) — Odhad času
2. [IMPR-002] ...
```

---

## SOUHRNNÁ TABULKA

| Oblast | Hodnocení | Klíčový nález |
|--------|:---------:|---------------|
| Bezpečnost | ?/10 | |
| Bugy | ?/10 | |
| Architektura | ?/10 | |
| Výkon | ?/10 | |
| Testy | ?/10 | |
| Standalone vektor | ?/10 | |
| **CELOKEM** | **?/10** | |

---

*Prompt aktualizován: 2026-08-19*
*Pro cross-LLM audit: git clone https://github.com/outpost2026/MCP-Jobs.git && git checkout main*
*HEAD: 3a04e64*