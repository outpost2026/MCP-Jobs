"""Run full ETL pipeline and save timestamped results."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections import Counter
from pathlib import Path

from mcp_jobs.config import UserConfig
from mcp_jobs.pipeline import SearchPipeline
from mcp_jobs.storage import CorrelationRecord, Storage

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)-8s %(name)s: %(message)s",
    stream=sys.stderr,
)

OUTPUT_DIR = Path("output")
DATA_DIR = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", default="config.yaml", help="Path to YAML config file"
    )
    args = parser.parse_args()
    config = UserConfig.from_yaml(args.config)

    ts = time.strftime("%Y%m%d_%H%M%S")
    print(f"=== MCP-Jobs ETL | {ts} ===", file=sys.stderr)
    print(
        f"Portals: {len(config.portals)}, Queries: {len(config.queries)}",
        file=sys.stderr,
    )
    print(f"Profile: {config.profile}", file=sys.stderr)

    start = time.time()
    pipeline = SearchPipeline(config)
    results, _scraper_stats, pool_sizes = pipeline.run()
    elapsed = time.time() - start

    # Save correlation cache
    per_qp: dict[tuple[str, str], int] = Counter()
    for qname, ads in results.items():
        for ad in ads:
            per_qp[(qname, ad.portal)] += 1
    records = [
        CorrelationRecord(
            query=q,
            portal=p,
            total_found=c,
            total_scraped=pool_sizes.get(p, 0),
            timestamp=f"{time.strftime('%Y-%m-%dT%H:%M:%S')}.000000",
            errors=0,
        )
        for (q, p), c in per_qp.items()
    ]
    # Tag correlation records with the config profile for cross-config SNR separation
    for rec in records:
        rec.profile = config.profile
    try:
        Storage.save_correlation(records, DATA_DIR / "correlation_cache.json")
    except Exception as e:
        print(f"Warning: correlation cache failed: {e}", file=sys.stderr)

    total_ads = sum(len(ads) for ads in results.values())
    print(file=sys.stderr)
    print(f"Elapsed: {elapsed:.1f}s | Matched: {total_ads}", file=sys.stderr)

    for qname, ads in sorted(results.items()):
        portals = sorted(set(a.portal for a in ads))
        print(f"  {qname}: {len(ads)} [{', '.join(portals)}]", file=sys.stderr)

    # Canonical output list (same shape as MCP server: [{query, results}])
    entries = [
        {
            "query": qname,
            "total_found": len(ads),
            "results": [a.to_dict() for a in ads],
        }
        for qname, ads in results.items()
    ]

    saved = Storage.save_outputs(
        entries,
        OUTPUT_DIR,
        profile=config.profile,
        meta_overrides={
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "elapsed_seconds": round(elapsed, 1),
            "total_raw": sum(pool_sizes.values()),
            "config_file": args.config,
            "portals": list(config.portals.keys()),
            "queries": list(config.queries.keys()),
        },
    )
    for p in saved:
        print(f"Saved: {p}", file=sys.stderr)
    if not saved:
        print("Saved: nothing (dedup — identical to previous run)", file=sys.stderr)
    print(
        f"\nSaved: {len(entries)} queries (profile={config.profile})",
        file=sys.stderr,
    )
    # Faze 1: PostgreSQL persistence (graceful — DB disabled/failed = skip)
    try:
        from mcp_jobs.db import persist_run

        run_id = persist_run(
            results,
            profile=config.profile,
            matched=total_ads,
            raw=sum(pool_sizes.values()),
            elapsed_seconds=elapsed,
        )
        if run_id:
            print(f"DB: run {run_id} persisted", file=sys.stderr)
    except Exception as e:
        print(f"Warning: DB persistence skipped: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
