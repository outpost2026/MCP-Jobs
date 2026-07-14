"""
Pipeline test script — runs the full pipeline with exclude filtering
and logs results to data/pipeline_test_log.json
"""
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mcp_jobs.config import UserConfig
from mcp_jobs.pipeline import SearchPipeline

LOG = Path(__file__).resolve().parent.parent / "data" / "pipeline_test_log.json"
log_data = {"run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"), "phases": []}

config = UserConfig.from_yaml(Path(__file__).resolve().parent.parent / "config.yaml")
pipeline = SearchPipeline(config)

# Phase 1: scrape pool
print("=== Phase 1: Scrape pool ===")
pool = pipeline._scrape_all()
portal_counts = Counter(a.portal for a in pool)
print(f"Pool total: {len(pool)}")
for p, c in portal_counts.items():
    print(f"  {p}: {c}")
log_data["phases"].append({"phase": "scrape", "pool_total": len(pool), "portal_counts": dict(portal_counts)})

# Phase 2: run queries
print("\n=== Phase 2: Queries ===")
results = pipeline.run()
for qname, ads in results.items():
    print(f"\n--- {qname} ({len(ads)} ads) ---")
    for a in ads:
        excl_hit = False
        qconf = config.queries.get(qname)
        if qconf and qconf.exclude:
            from mcp_jobs.matcher import has_exclude_terms
            excl_hit = has_exclude_terms(a.title, qconf.exclude, description=a.description or "")
        print(f"  [{a.portal}] {a.title[:70]}")
        if a.location:
            print(f"    location={a.location}")
        if a.salary:
            print(f"    salary={a.salary}")
        if a.company:
            print(f"    company={a.company}")
        if excl_hit:
            print(f"    ** WOULD BE EXCLUDED **")
    print()

log_data["queries"] = {qname: [a.to_dict() for a in ads] for qname, ads in results.items()}

LOG.parent.mkdir(parents=True, exist_ok=True)
with LOG.open("w", encoding="utf-8") as f:
    json.dump(log_data, f, ensure_ascii=False, indent=2)
print(f"Log saved: {LOG}")
