"""Run full ETL pipeline and save timestamped results."""
from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)-8s %(name)s: %(message)s",
    stream=sys.stderr,
)

from mcp_jobs.config import UserConfig
from mcp_jobs.pipeline import SearchPipeline

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def main() -> None:
    config = UserConfig.from_yaml("config.yaml")

    ts = time.strftime("%Y%m%d_%H%M%S")
    print(f"=== MCP-Jobs ETL | {ts} ===", file=sys.stderr)
    print(f"Portals: {len(config.portals)}, Queries: {len(config.queries)}", file=sys.stderr)

    start = time.time()
    pipeline = SearchPipeline(config)
    results = pipeline.run()
    elapsed = time.time() - start

    total_ads = sum(len(ads) for ads in results.values())
    print(file=sys.stderr)
    print(f"Elapsed: {elapsed:.1f}s | Matched: {total_ads}", file=sys.stderr)

    for qname, ads in sorted(results.items()):
        portals = sorted(set(a.portal for a in ads))
        print(f"  {qname}: {len(ads)} [{', '.join(portals)}]", file=sys.stderr)

    # Summary with per-query breakdown + selected top fields
    summary = {}
    for qname, ads in results.items():
        sample = []
        for a in ads[:5]:
            d = a.to_dict()
            sample.append({
                "title": d.get("title", ""),
                "portal": d.get("portal", ""),
                "company": d.get("company", ""),
                "location": d.get("location", ""),
                "salary": d.get("salary", ""),
                "url": d.get("url", ""),
            })
        summary[qname] = {
            "count": len(ads),
            "portals": sorted(set(a.portal for a in ads)),
            "sample": sample,
        }

    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_seconds": round(elapsed, 1),
        "total_matched": total_ads,
        "config": {
            "portals": list(config.portals.keys()),
            "queries": list(config.queries.keys()),
        },
        "summary": summary,
        "results": {q: [a.to_dict() for a in ads] for q, ads in results.items()},
    }

    filename = f"etl_{ts}.json"
    path = OUTPUT_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Update latest symlink (copy on Windows)
    latest = OUTPUT_DIR / "etl_latest.json"
    with open(latest, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nSaved: {path} ({len(output['results'])} queries)", file=sys.stderr)


if __name__ == "__main__":
    main()
