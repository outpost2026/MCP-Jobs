"""Sync local PostgreSQL to cloud (Neon/Supabase) for Community Cloud deployment.

Usage:
    # One-time sync
    python scripts/sync_to_cloud.py --cloud-url "postgresql://user:pass@host/dbname"

    # With schema init
    python scripts/sync_to_cloud.py --cloud-url "postgresql://..." --init-schema

    # Dry run (export only, no import)
    python scripts/sync_to_cloud.py --dry-run

Requires: psycopg[binary], same as MCP-Jobs core.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from mcp_jobs.db import connect, get_database_url


def export_local(conn) -> dict:
    """Export all ads and pipeline_runs from local DB."""
    ads = []
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM ads ORDER BY id")
        cols = [desc[0] for desc in cur.description]
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            # Convert non-serializable types
            for k, v in d.items():
                if hasattr(v, "isoformat"):
                    d[k] = v.isoformat()
                elif isinstance(v, (dict, list)):
                    d[k] = json.dumps(v, ensure_ascii=False)
            ads.append(d)

    runs = []
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM pipeline_runs ORDER BY id")
        cols = [desc[0] for desc in cur.description]
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            for k, v in d.items():
                if hasattr(v, "isoformat"):
                    d[k] = v.isoformat()
                elif isinstance(v, (dict, list)):
                    d[k] = json.dumps(v, ensure_ascii=False)
            runs.append(d)

    return {
        "ads": ads,
        "pipeline_runs": runs,
        "ads_count": len(ads),
        "runs_count": len(runs),
    }


def init_schema(conn) -> None:
    """Create tables in cloud DB from schema.sql."""
    schema_path = _REPO_ROOT / "data" / "schema.sql"
    if not schema_path.exists():
        print(f"ERROR: {schema_path} not found")
        return

    schema_sql = schema_path.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(schema_sql)
    print(f"Schema initialized from {schema_path.name}")


def import_cloud(conn, data: dict) -> None:
    """Import exported data into cloud DB via batch upsert."""
    ads = data["ads"]
    runs = data["pipeline_runs"]

    if not ads:
        print("No ads to import.")
        return

    # Upsert ads (batch)
    with conn.cursor() as cur:
        batch_size = 100
        for i in range(0, len(ads), batch_size):
            batch = ads[i : i + batch_size]
            values = []
            for ad in batch:
                values.append(
                    (
                        ad.get("url"),
                        ad.get("title"),
                        ad.get("company"),
                        ad.get("location"),
                        ad.get("salary"),
                        ad.get("description"),
                        ad.get("matched_keyword"),
                        ad.get("portal"),
                        ad.get("query_name"),
                        ad.get("profile"),
                        ad.get("first_seen"),
                        ad.get("last_seen"),
                        ad.get("status", "new"),
                        ad.get("fuzzy_title"),
                        ad.get("fuzzy_company"),
                        ad.get("fuzzy_location"),
                        json.dumps(ad.get("skills")) if ad.get("skills") else "[]",
                    )
                )
            cur.executemany(
                """
                INSERT INTO ads (url, title, company, location, salary, description,
                    matched_keyword, portal, query_name, profile, first_seen,
                    last_seen, status, fuzzy_title, fuzzy_company, fuzzy_location, skills)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (url) DO UPDATE SET
                    title = EXCLUDED.title,
                    company = EXCLUDED.company,
                    location = EXCLUDED.location,
                    salary = EXCLUDED.salary,
                    description = EXCLUDED.description,
                    matched_keyword = EXCLUDED.matched_keyword,
                    portal = EXCLUDED.portal,
                    query_name = EXCLUDED.query_name,
                    profile = EXCLUDED.profile,
                    last_seen = EXCLUDED.last_seen,
                    status = EXCLUDED.status,
                    fuzzy_title = EXCLUDED.fuzzy_title,
                    fuzzy_company = EXCLUDED.fuzzy_company,
                    fuzzy_location = EXCLUDED.fuzzy_location,
                    skills = EXCLUDED.skills
                """,
                values,
            )
        conn.commit()
        print(f"  Ads upserted: {len(ads)} ({len(ads) // batch_size + 1} batches)")

    # Upsert pipeline_runs
    if runs:
        with conn.cursor() as cur:
            for run in runs:
                cur.execute(
                    """
                    INSERT INTO pipeline_runs (id, profile, status, matched, raw,
                        started_at, completed_at, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (id) DO UPDATE SET
                        profile = EXCLUDED.profile,
                        status = EXCLUDED.status,
                        matched = EXCLUDED.matched,
                        raw = EXCLUDED.raw,
                        started_at = EXCLUDED.started_at,
                        completed_at = EXCLUDED.completed_at,
                        metadata = EXCLUDED.metadata
                    """,
                    (
                        run.get("id"),
                        run.get("profile"),
                        run.get("status"),
                        run.get("matched"),
                        run.get("raw"),
                        run.get("started_at"),
                        run.get("completed_at"),
                        run.get("metadata", "{}"),
                    ),
                )
            conn.commit()
            print(f"  Pipeline runs upserted: {len(runs)}")


def main():
    parser = argparse.ArgumentParser(description="Sync local MCP-Jobs DB to cloud")
    parser.add_argument("--cloud-url", help="Cloud PostgreSQL DATABASE_URL")
    parser.add_argument(
        "--init-schema", action="store_true", help="Create tables in cloud DB"
    )
    parser.add_argument("--dry-run", action="store_true", help="Export only, no import")
    parser.add_argument(
        "--export-file", help="Save export to JSON file (for manual import)"
    )
    args = parser.parse_args()

    # Connect to local DB
    local_url = get_database_url()
    if not local_url:
        print("ERROR: DATABASE_URL not set. Check your .env file.")
        sys.exit(1)

    print("Connecting to local DB...")
    local_conn = connect(local_url)

    # Export
    print("Exporting data...")
    data = export_local(local_conn)
    print(f"  Ads: {data['ads_count']}, Pipeline runs: {data['runs_count']}")
    local_conn.close()

    # Save to file if requested
    if args.export_file:
        export_path = Path(args.export_file)
        export_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  Exported to {export_path}")

    if args.dry_run:
        print("Dry run complete.")
        return

    # Import to cloud
    if not args.cloud_url:
        print("ERROR: --cloud-url required for import.")
        print(
            "  Example: python scripts/sync_to_cloud.py --cloud-url 'postgresql://...'"
        )
        sys.exit(1)

    print("Connecting to cloud DB...")
    cloud_conn = connect(args.cloud_url)

    if args.init_schema:
        print("Initializing schema...")
        init_schema(cloud_conn)

    print("Importing data...")
    import_cloud(cloud_conn, data)
    cloud_conn.close()

    print("Sync complete!")


if __name__ == "__main__":
    main()
