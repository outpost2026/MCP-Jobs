# Deploy MCP-Jobs Dashboard to Streamlit Community Cloud

Zero-cost deployment for portfolio demo. Live URL: `mcp-jobs.streamlit.app`

## Prerequisites

- GitHub repo `outpost2026/MCP-Jobs` (public or GitHub Pro for private)
- Neon or Supabase account (free tier)
- Local DB running with data (`mcpjobs` user, `mcpjobs` DB)

## Step 1: Create Cloud Database

### Option A: Neon (recommended)

1. Sign up at https://neon.tech
2. Create project → copy connection string:
   ```
   postgresql://neondb_owner:xxxx@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
3. Free tier: 512 MB storage, 100 compute hours/month

### Option B: Supabase

1. Sign up at https://supabase.com
2. Create project → Settings → Connection string → URI
3. Free tier: 500 MB storage

## Step 2: Sync Data to Cloud

```powershell
# One-time sync with schema init
$env:DATABASE_URL = "postgresql://mcpjobs:mcpjobs@localhost:5432/mcpjobs"
python scripts/sync_to_cloud.py `
  --cloud-url "postgresql://neondb_owner:xxxx@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require" `
  --init-schema

# Verify
python scripts/sync_to_cloud.py `
  --cloud-url "postgresql://..." `
  --dry-run --export-file data/cloud_export.json
```

## Step 3: Configure Community Cloud

1. Go to https://share.streamlit.io
2. Sign in with GitHub
3. Click **"Create app"**
4. Settings:
   - **Repository:** `outpost2026/MCP-Jobs`
   - **Branch:** `main`
   - **Main file path:** `dashboard/app.py`
5. Click **"Advanced settings"** → **Secrets**:
   ```toml
   DATABASE_URL = "postgresql://neondb_owner:xxxx@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require"
   MCPJOBS_DASH_PWD = "your-secure-password"
   ```
6. Click **"Deploy"**

App will be live at: `https://mcp-jobs.streamlit.app`

## Step 4: Ongoing Sync

After each local pipeline run, re-sync to cloud:

```powershell
python scripts/sync_to_cloud.py --cloud-url "postgresql://..."
```

Or add to pipeline (auto-sync after each run):

```yaml
# In config.yaml
post_run:
  - python scripts/sync_to_cloud.py --cloud-url "${CLOUD_DATABASE_URL}"
```

## Architecture

```
[Local PC]                    [Community Cloud]
PostgreSQL (Docker)           Streamlit app
  ↓ sync_to_cloud.py          ↓
Neon/Supabase (free tier) ←── DATABASE_URL secret
```

## Limitations

| Limit | Value | Mitigation |
|-------|-------|------------|
| RAM | 1 GB | Dashboard uses ~200 MB with 183 ads |
| Sleep | 7 days | Visit once a week to keep alive |
| Auth | Password only | MCPJOBS_DASH_PWD secret |
| Custom domain | No | `.streamlit.app` URL |
| DB size | 512 MB (Neon free) | Sufficient for 10k+ ads |

## Troubleshooting

**App crashes on start:**
- Check secrets are set correctly in Advanced settings
- Verify cloud DB connection string with `psql` or pgAdmin

**Data not showing:**
- Run `sync_to_cloud.py` again
- Check `ads` table has rows in cloud DB

**App sleeps (slow first visit):**
- Normal for Community Cloud. Cold start ~30-60s.
- Visit weekly to prevent sleep.
