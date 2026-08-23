"""Backfill skills JSONB for existing ads with descriptions.

Usage:
    python scripts/backfill_skills.py [--dry-run]

Reads all ads with description and empty/null skills, extracts IT skills
using SkillsCatalog, and updates the skills JSONB column.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure src/ is on path for standalone execution
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcp_jobs.db import connect, get_database_url, init_db
from mcp_jobs.skills_catalog import get_catalog

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def backfill_skills(dry_run: bool = False, force: bool = False) -> None:
    """Process all ads with description. With --force, re-score even existing skills."""
    url = get_database_url()
    if not url:
        logger.error("DATABASE_URL not set — aborting")
        sys.exit(1)

    conn = connect(url)
    init_db(conn)

    catalog = get_catalog()
    logger.info("Catalog loaded: %d skills", catalog.skill_count)

    # Fetch ads needing backfill
    where = "WHERE description IS NOT NULL AND description != ''"
    rows = conn.execute(
        "SELECT id, title, company, description FROM ads " + where
    ).fetchall()

    logger.info("Found %d ads needing skill extraction", len(rows))

    if not rows:
        logger.info("Nothing to backfill")
        return

    updated = 0
    errors = 0

    for row in rows:
        ad_id = row[0]
        company = row[2] or ""
        description = row[3] or ""

        try:
            ts = catalog.tech_score(description)
            domain_score, domain_detail = catalog.domain_score(description)
            employer_tier = catalog.employer_tier(company)
            loc_score, loc_detail = catalog.location_score(description)

            skills_data = {
                "score": ts.score,
                "coverage": ts.coverage,
                "mentioned_weighted": ts.mentioned_weighted,
                "compression_ratio": ts.compression_ratio,
                "density_bonus": ts.density_bonus,
                "matches": [
                    {
                        "skill_id": m.skill_id,
                        "display_name": m.display_name,
                        "category": m.category,
                        "weight": m.weight,
                        "match_type": m.match_type,
                    }
                    for m in ts.matches
                ],
                "domain": {"score": domain_score, "detail": domain_detail},
                "employer_tier": employer_tier,
                "location": {"score": loc_score, "detail": loc_detail},
            }

            if dry_run:
                if ts.matches:
                    logger.info(
                        "[DRY-RUN] ad_id=%d score=%.1f skills=%d %s",
                        ad_id,
                        ts.score,
                        len(ts.matches),
                        [m.skill_id for m in ts.matches[:5]],
                    )
                updated += 1
            else:
                conn.execute(
                    "UPDATE ads SET skills = %s WHERE id = %s",
                    (conn.jsonb(skills_data), ad_id),
                )
                updated += 1
                if updated % 50 == 0:
                    logger.info("  ... %d ads processed", updated)

        except Exception as e:
            logger.warning("Error processing ad %d: %s", ad_id, e)
            errors += 1

    logger.info("Backfill complete: %d updated, %d errors", updated, errors)
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill skills for existing ads")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done without writing"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-score ALL ads (overwrite existing skills)",
    )
    args = parser.parse_args()
    backfill_skills(dry_run=args.dry_run, force=args.force)
