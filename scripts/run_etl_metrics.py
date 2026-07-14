"""Full ETL pipeline with detailed per-provider metrics."""
from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from collections import defaultdict

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)-8s %(name)s: %(message)s",
    stream=sys.stderr,
)

from mcp_jobs.config import UserConfig
from mcp_jobs.pipeline import SearchPipeline

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


class TimedPipeline(SearchPipeline):
    """Extends SearchPipeline with per-provider timing."""

    def __init__(self, config):
        super().__init__(config)
        self.provider_stats: dict[str, dict] = {}

    def _scrape_all(self) -> list:
        from mcp_jobs.providers import REGISTRY
        from mcp_jobs.pipeline import _dedup as dd
        pool = []
        for portal_name, pconf in self.config.portals.items():
            if not pconf.enabled:
                continue
            cls = REGISTRY.get(portal_name)
            if not cls:
                continue
            provider = cls()
            for cat in (pconf.categories or []):
                t0 = time.time()
                try:
                    ads = provider.scrape_all(cat.url, cat.pages, cat.params)
                    t1 = time.time()
                    print(f"  {portal_name}: +{len(ads)} ads in {t1-t0:.1f}s", file=sys.stderr)
                    pool.extend(ads)
                    self.provider_stats[f"{portal_name}/{cat.url[:40]}"] = {
                        "portal": portal_name,
                        "elapsed_s": round(t1 - t0, 2),
                        "matched": len(ads),
                        "pages": cat.pages,
                        "error": None,
                    }
                except Exception as e:
                    t1 = time.time()
                    print(f"  {portal_name}: ERROR {e}", file=sys.stderr)
                    self.provider_stats[f"{portal_name}/{cat.url[:40]}"] = {
                        "portal": portal_name,
                        "elapsed_s": round(t1 - t0, 2),
                        "matched": 0,
                        "pages": cat.pages,
                        "error": str(e)[:200],
                    }
        return dd(pool)


def main() -> None:
    config = UserConfig.from_yaml("config.yaml")
    ts = time.strftime("%Y%m%d_%H%M%S")
    print(f"=== MCP-Jobs ETL Metrics | {ts} ===", file=sys.stderr)
    
    # ── Config overview ──
    total_categories = sum(len(p.categories or []) for p in config.portals.values())
    print(file=sys.stderr)
    print(f"Configuration:", file=sys.stderr)
    print(f"  Portals enabled: {sum(1 for p in config.portals.values() if p.enabled)}", file=sys.stderr)
    for name, portal in config.portals.items():
        if portal.enabled:
            cats = len(portal.categories or [])
            pages = sum(c.pages or 0 for c in (portal.categories or []))
            print(f"    {name}: {cats} categories, ~{pages} pages total", file=sys.stderr)
    print(f"  Queries: {len(config.queries)}", file=sys.stderr)
    for qname, q in config.queries.items():
        print(f"    {qname}: boolean={q.boolean[:60]}... portals={q.portals}", file=sys.stderr)

    # ── Run pipeline ──
    print(file=sys.stderr)
    print(f"Running pipeline...", file=sys.stderr)
    pipeline_start = time.time()
    pipeline = TimedPipeline(config)
    results = pipeline.run()
    pipeline_elapsed = time.time() - pipeline_start

    # ── Aggregate metrics ──
    total_ads = sum(len(ads) for ads in results.values())

    # Per-provider summary
    provider_agg: dict[str, dict] = defaultdict(lambda: {"calls": 0, "elapsed": 0.0, "matched": 0, "errors": 0})
    for key, stat in pipeline.provider_stats.items():
        name = stat["portal"]
        provider_agg[name]["calls"] += 1
        provider_agg[name]["elapsed"] += stat["elapsed_s"]
        provider_agg[name]["matched"] += stat["matched"]
        if stat["error"]:
            provider_agg[name]["errors"] += 1

    # Per-query summary
    print(file=sys.stderr)
    print(f"Results:", file=sys.stderr)
    print(f"  Total elapsed: {pipeline_elapsed:.1f}s", file=sys.stderr)
    print(f"  Total matched: {total_ads}", file=sys.stderr)

    query_summary = {}
    for qname, ads in sorted(results.items()):
        portals = sorted(set(a.portal for a in ads))
        query_summary[qname] = {
            "count": len(ads),
            "portals": portals,
        }
        print(f"  {qname}: {len(ads)} [{', '.join(portals)}]", file=sys.stderr)

    print(file=sys.stderr)
    print(f"Per-provider timing:", file=sys.stderr)
    for name, agg in sorted(provider_agg.items()):
        avg = agg["elapsed"] / max(agg["calls"], 1)
        print(f"  {name}: {agg['matched']} matched in {agg['elapsed']:.1f}s total ({agg['calls']} calls, avg {avg:.2f}s/call, {agg['errors']} errors)", file=sys.stderr)

    # ── Build detailed output ──
    sample_data = {}
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
        sample_data[qname] = {
            "count": len(ads),
            "portals": sorted(set(a.portal for a in ads)),
            "sample": sample,
        }

    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_seconds": round(pipeline_elapsed, 1),
        "total_matched": total_ads,
        "config": {
            "portals": {n: {"enabled": p.enabled, "category_count": len(p.categories or [])} for n, p in config.portals.items()},
            "queries": list(config.queries.keys()),
        },
        "provider_metrics": {k: dict(v) for k, v in provider_agg.items()},
        "provider_detail": pipeline.provider_stats,
        "query_summary": query_summary,
        "sample": sample_data,
        "results": {q: [a.to_dict() for a in ads] for q, ads in results.items()},
    }

    # ── Save ──
    filename = f"etl_metrics_{ts}.json"
    path = OUTPUT_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    latest = OUTPUT_DIR / "etl_metrics_latest.json"
    with open(latest, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(file=sys.stderr)
    print(f"Saved: {path}", file=sys.stderr)
    print(f"Saved: {latest}", file=sys.stderr)

    # ── Comparison with legacy ──
    print(file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print(f"COMPARISON: MCP-Jobs vs Legacy", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print(f"{'Metric':<35} {'MCP-Jobs':<15} {'Legacy':<15}", file=sys.stderr)
    print(f"{'-'*65}", file=sys.stderr)
    print(f"{'Pipeline time (s)':<35} {pipeline_elapsed:<15.1f} {'~210':<15}", file=sys.stderr)
    print(f"{'Speed factor':<35} {210/pipeline_elapsed:<15.1f}x {'1x':<15}", file=sys.stderr)

    # Legacy comparison per portal
    legacy_portal_data = {
        "bazos": {"ads": 36, "time_est": 80},
        "jobs": {"ads": 27, "time_est": 40},
        "pracecz": {"ads": 32, "time_est": 60},
        "nyx": {"ads": 17, "time_est": 30},
    }

    for portal in ["bazos", "jobs", "pracecz"]:
        mcp_matched = provider_agg.get(portal, {}).get("matched", 0)
        mcp_time = provider_agg.get(portal, {}).get("elapsed", 0)
        leg = legacy_portal_data.get(portal, {})
        speedup = leg.get("time_est", 60) / max(mcp_time, 0.1)
        print(f"{f'{portal} matched':<35} {mcp_matched:<15} {leg.get('ads',0):<15}", file=sys.stderr)
        print(f"{f'{portal} time (s)':<35} {mcp_time:<15.1f} {leg.get('time_est',0):<15}", file=sys.stderr)
        print(f"{f'{portal} speedup':<35} {speedup:<15.1f}x {'1x':<15}", file=sys.stderr)

    # Overall stats
    mcp_ads_per_s = total_ads / max(pipeline_elapsed, 0.1)
    legacy_ads_per_s = 112 / 210
    efficiency_gain = mcp_ads_per_s / max(legacy_ads_per_s, 0.001)
    print(f"{'Ads per second':<35} {mcp_ads_per_s:<15.2f} {legacy_ads_per_s:<15.2f}", file=sys.stderr)
    print(f"{'Efficiency gain':<35} {efficiency_gain:<15.1f}x {'1x':<15}", file=sys.stderr)
    print(file=sys.stderr)

    # Quality metrics
    print(f"{'Quality metrics':<35}", file=sys.stderr)
    print(f"{'  Salary/location filter':<35} {'YES':<15} {'NO':<15}", file=sys.stderr)
    print(f"{'  Boolean parser':<35} {'YES (full)':<15} {'basic AND':<15}", file=sys.stderr)
    print(f"{'  Dedup method':<35} {'URL+title':<15} {'URL only':<15}", file=sys.stderr)
    print(f"{'  JS rendering':<35} {'Playwright':<15} {'requests':<15}", file=sys.stderr)
    print(f"{'  Error handling':<35} {'structured':<15} {'silent':<15}", file=sys.stderr)
    print(f"{'  Unit tests':<35} {'79':<15} {'0':<15}", file=sys.stderr)
    print(file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)


if __name__ == "__main__":
    main()
