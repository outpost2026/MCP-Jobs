-- MCP-Jobs PostgreSQL schema (Faze 1 standalone pivot)
-- Idempotent: safe to run multiple times (IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS ads (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,            -- native dedup across runs
    title TEXT,
    company TEXT,
    location TEXT,
    salary TEXT,
    description TEXT,
    matched_keyword TEXT,
    portal TEXT,
    query_name TEXT,
    profile TEXT,
    first_seen DATE DEFAULT CURRENT_DATE,
    last_seen DATE DEFAULT CURRENT_DATE,
    status TEXT DEFAULT 'new'            -- new / seen / applied / rejected
);

-- Fuzzy dedup klic: normalizovany (title, company, location) klic pro
-- cross-portal dedup. Porovnani napric portaly vyzaduje normalizaci
-- (diakritika, en-dash, whitespace) — raw stringy by selhaly.
ALTER TABLE ads ADD COLUMN IF NOT EXISTS fuzzy_title TEXT;
ALTER TABLE ads ADD COLUMN IF NOT EXISTS fuzzy_company TEXT;
ALTER TABLE ads ADD COLUMN IF NOT EXISTS fuzzy_location TEXT;

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id SERIAL PRIMARY KEY,
    profile TEXT NOT NULL,
    status TEXT DEFAULT 'running',       -- running / completed / failed
    matched INT,
    raw INT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_ads_status ON ads (status);
CREATE INDEX IF NOT EXISTS idx_ads_portal ON ads (portal);
CREATE INDEX IF NOT EXISTS idx_ads_fuzzy_title ON ads (fuzzy_title, fuzzy_company, fuzzy_location);
CREATE INDEX IF NOT EXISTS idx_runs_profile ON pipeline_runs (profile);