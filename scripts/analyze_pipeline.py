"""
Pipeline analysis — runs config.yaml through the full pipeline,
captures all results, debug info, anomalies, and writes a structured
report to data/.
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT / "src"))

from mcp_jobs.server import search_from_config
from mcp_jobs.matcher import strip_diacritics

DATA_DIR = _ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = _ROOT / "config.yaml"

report = {
    "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"),
    "config_file": str(CONFIG_PATH),
    "started_at": datetime.now(timezone.utc).isoformat(),
    "phases": [],
    "queries": [],
    "anomalies": [],
    "debug": [],
    "portal_stats": {},
    "summary": {},
}

def debug(msg: str, **kw):
    entry = {"msg": msg, **kw}
    report["debug"].append(entry)
    print(f"  DEBUG: {msg}")

def anomaly(msg: str, **kw):
    entry = {"msg": msg, **kw}
    report["anomalies"].append(entry)
    print(f"  ANOMALY: {msg}")

# ── Parse config ───────────────────────────────────
print("=" * 60)
print("  PIPELINE ANALYSIS")
print(f"  Config: {CONFIG_PATH}")
print("=" * 60)

if not CONFIG_PATH.exists():
    print(f"  ERROR: config.yaml not found at {CONFIG_PATH}")
    sys.exit(1)

# ── Run pipeline ───────────────────────────────────
print("\n--- Running pipeline ---")
t0 = time.time()

try:
    results = search_from_config(str(CONFIG_PATH))
    elapsed = time.time() - t0
    report["elapsed_seconds"] = round(elapsed, 2)
    print(f"  Elapsed: {elapsed:.2f}s")
except Exception as e:
    report["elapsed_seconds"] = round(time.time() - t0, 2)
    report["fatal_error"] = f"{type(e).__name__}: {e}"
    print(f"  FATAL: {e}")
    traceback.print_exc()
    _write_report()
    sys.exit(1)

# ── Analyze results ────────────────────────────────
print(f"\n--- Results ({len(results)} query groups) ---")

for entry in results:
    qname = entry.get("query", "?")
    if "error" in entry:
        print(f"\n  [{qname}] ERROR: {entry['error']}")
        report["queries"].append({"query": qname, "error": entry["error"]})
        continue

    if "message" in entry:
        print(f"\n  [{qname}] {entry['message']}")
        report["queries"].append({"query": qname, "total": 0, "message": entry["message"]})
        debug(f"Query '{qname}' returned no results — boolean too strict or empty pool")
        continue

    ads = entry.get("results", [])
    total = entry.get("total_found", len(ads))
    errors = entry.get("errors", [])

    q_result = {
        "query": qname,
        "total": total,
        "errors": errors,
        "ads": ads,
    }
    report["queries"].append(q_result)

    print(f"\n  [{qname}] {total} ads found")
    if errors:
        for e in errors:
            anomaly(f"Query '{qname}': {e}")

    # Per-ad analysis
    portals_seen = Counter()
    companies_seen = Counter()
    locations_seen = Counter()
    title_lens = []
    missing_fields = Counter()

    for ad in ads:
        portals_seen[ad.get("portal", "?")] += 1
        companies_seen[ad.get("company", "N/A")] += 1
        locations_seen[ad.get("location", "N/A")] += 1
        title_lens.append(len(ad.get("title", "")))

        for field in ("title", "url", "portal"):
            if not ad.get(field):
                missing_fields[field] += 1

    if title_lens:
        avg_len = sum(title_lens) / len(title_lens)
        q_result["stats"] = {
            "portals": dict(portals_seen),
            "companies": dict(companies_seen.most_common(10)),
            "locations": dict(locations_seen.most_common(10)),
            "avg_title_len": round(avg_len, 1),
            "min_title_len": min(title_lens),
            "max_title_len": max(title_lens),
            "missing_fields": dict(missing_fields),
        }

    # Anomaly detection
    if len(set(ad.get("url") for ad in ads)) < len(ads):
        dupes = len(ads) - len(set(ad.get("url") for ad in ads))
        anomaly(f"Query '{qname}': {dupes} duplicate URLs in results")

    if missing_fields:
        anomaly(f"Query '{qname}': missing fields: {dict(missing_fields)}")

    if not errors and total == 0:
        anomaly(f"Query '{qname}': 0 results — possible causes: boolean too strict, wrong portal filter, empty category pool")

    # Show top results
    for i, ad in enumerate(ads[:5], 1):
        loc = ad.get("location") or ad.get("price") or ""
        print(f"    {i}. {ad['title']}")
        print(f"       portal={ad['portal']} company={ad.get('company','?')} {loc}")
        if "matched_keyword" in ad and ad["matched_keyword"]:
            print(f"       keyword={ad['matched_keyword']}")

    if len(ads) > 5:
        print(f"       ... and {len(ads)-5} more")

# ── Portal-level stats ─────────────────────────────
print("\n--- Portal scrape stats ---")
for ad in [a for q in report["queries"] if "ads" in q for a in q["ads"]]:
    p = ad.get("portal", "?")
    if p not in report["portal_stats"]:
        report["portal_stats"][p] = {"total_matched": 0, "queries": set()}
    report["portal_stats"][p]["total_matched"] += 1
    report["portal_stats"][p]["queries"].add(ad.get("matched_keyword", "?"))

for pname, pdata in report["portal_stats"].items():
    pdata["queries"] = list(pdata["queries"])
    print(f"  {pname}: {pdata['total_matched']} matched ads")

# ── Summary ────────────────────────────────────────
total_ads = sum(q.get("total", 0) for q in report["queries"] if "total" in q)
query_count = len(report["queries"])
query_with_results = sum(1 for q in report["queries"] if q.get("total", 0) > 0)
query_with_errors = sum(1 for q in report["queries"] if q.get("errors"))

report["summary"] = {
    "queries_total": query_count,
    "queries_with_results": query_with_results,
    "queries_with_errors": query_with_errors,
    "total_ads": total_ads,
    "anomalies_count": len(report["anomalies"]),
    "elapsed_seconds": report.get("elapsed_seconds", 0),
    "verdict": "ISSUES_FOUND" if report["anomalies"] or query_with_errors else "CLEAN",
}

print()
print("=" * 60)
print("  SUMMARY")
print("=" * 60)
print(f"  Queries:         {query_count} total, {query_with_results} with results, {query_with_errors} with errors")
print(f"  Total ads:       {total_ads}")
print(f"  Anomalies:       {len(report['anomalies'])}")
print(f"  Elapsed:         {report['elapsed_seconds']}s")
print(f"  Verdict:         {report['summary']['verdict']}")

if report["anomalies"]:
    print()
    print("  ANOMALIES:")
    for a in report["anomalies"]:
        print(f"    - {a['msg']}")

print()
print(f"  Full report saved to data/")

# ── Save report ────────────────────────────────────
timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
report_file = DATA_DIR / f"pipeline_report_{timestamp}.json"
latest_file = DATA_DIR / "pipeline_latest.json"

with open(report_file, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
with open(latest_file, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print(f"  {report_file}")
print(f"  {latest_file}")
print("=" * 60)
