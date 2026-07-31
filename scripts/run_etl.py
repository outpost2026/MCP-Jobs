"""Run full ETL pipeline and save timestamped results."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections import Counter
from pathlib import Path

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)-8s %(name)s: %(message)s",
    stream=sys.stderr,
)

from mcp_jobs.config import UserConfig
from mcp_jobs.pipeline import SearchPipeline
from mcp_jobs.storage import CorrelationRecord, Storage

OUTPUT_DIR = Path("output")
DATA_DIR = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)


def _profile_tag(config: UserConfig) -> str:
    """Semantic tag for output files derived from config profile.

    'AI-NATIVE' -> 'AINATIVE', 'LEGACY-MANUAL' -> 'LEGACY_MANUAL', else 'default'.
    """
    tag = _profile_tag_from_profile(config.profile)
    return tag or "default"


def _profile_tag_from_profile(profile: str) -> str:
    tag = profile.upper()
    for ch in ("-", " ", "/", "\\", ":", "."):
        tag = tag.replace(ch, "_")
    tag = "_".join(p for p in tag.split("_") if p)
    return tag or "default"


def _write_markdown_report(output: dict, ts: str, profile_tag: str = "") -> Path:
    """Generate high-SNR human-readable MD report with clickable links."""
    lines: list[str] = []
    _a = lines.append
    profile = output.get("profile", "default")
    profile_tag = profile_tag or _profile_tag_from_profile(profile)

    _a("# MCP-Jobs Pipeline Report")
    _a("")
    _a(
        f"**Spuštěno:** {output['timestamp']} | **Trvání:** {output['elapsed_seconds']}s | **Matched:** {output['total_matched']}"
    )
    _a(f"**Profil (config):** `{profile}`")
    portals = ", ".join(output["config"]["portals"])
    queries = ", ".join(output["config"]["queries"])
    _a(f"**Portály:** {portals} | **Query:** {queries}")
    _a("")

    _a("## Přehled")
    _a("")
    _a("| # | Query | Počet | Portály |")
    _a("|---|-------|-------|---------|")

    summary = output["summary"]
    sorted_queries = sorted(summary.items(), key=lambda x: -x[1]["count"])
    for idx, (qname, qdata) in enumerate(sorted_queries, 1):
        portals_str = ", ".join(qdata["portals"])
        _a(f"| {idx} | {qname} | {qdata['count']} | {portals_str} |")

    _a("")

    for idx, (qname, qdata) in enumerate(sorted_queries, 1):
        if qdata["count"] == 0:
            _a(f"## {idx}. {qname} — 0 matchingů")
            _a("")
            continue

        portals_str = ", ".join(qdata["portals"])
        _a(f"## {idx}. {qname} — {qdata['count']} matchingů")
        _a("")
        _a(f"Portály: {portals_str}")
        _a("")

        sample = qdata["sample"]
        for si, ad in enumerate(sample, 1):
            title = ad.get("title", "Inzerát")
            url = ad.get("url", "")
            if url:
                _a(f"{si}. **[{title}]({url})**")
            else:
                _a(f"{si}. **{title}**")

            meta_parts = []
            if ad.get("salary"):
                meta_parts.append(f"{ad['salary']}")
            if ad.get("company"):
                meta_parts.append(ad["company"])
            if ad.get("location"):
                meta_parts.append(ad["location"])
            if ad.get("portal"):
                meta_parts.append(f"({ad['portal']})")
            if meta_parts:
                _a(f"   — {' | '.join(meta_parts)}")

        _a("")

        # Show count note if there are more ads beyond the sample
        if qdata["count"] > 5:
            _a(f"> +{qdata['count'] - 5} dalších inzerátů (celkem {qdata['count']})")
            _a("")

    md_path = OUTPUT_DIR / f"etl_{ts}.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    # Update latest per-profile
    latest_md = OUTPUT_DIR / f"etl_latest_{profile_tag}.md"
    latest_md.write_text("\n".join(lines), encoding="utf-8")

    return md_path


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
    profile_tag = _profile_tag(config)
    print(f"Profile: {config.profile} (tag={profile_tag})", file=sys.stderr)

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

    # Summary with per-query breakdown + selected top fields
    summary = {}
    for qname, ads in results.items():
        sample = []
        for a in ads[:5]:
            d = a.to_dict()
            sample.append(
                {
                    "title": d.get("title", ""),
                    "portal": d.get("portal", ""),
                    "company": d.get("company", ""),
                    "location": d.get("location", ""),
                    "salary": d.get("salary", ""),
                    "url": d.get("url", ""),
                }
            )
        summary[qname] = {
            "count": len(ads),
            "portals": sorted(set(a.portal for a in ads)),
            "sample": sample,
        }

    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_seconds": round(elapsed, 1),
        "total_matched": total_ads,
        "profile": config.profile,
        "config_file": args.config,
        "config": {
            "portals": list(config.portals.keys()),
            "queries": list(config.queries.keys()),
        },
        "summary": summary,
        "results": {q: [a.to_dict() for a in ads] for q, ads in results.items()},
    }

    filename = f"etl_{profile_tag}_{ts}.json"
    path = OUTPUT_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Update latest per-profile (copy on Windows)
    latest = OUTPUT_DIR / f"etl_latest_{profile_tag}.json"
    with open(latest, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nSaved: {path} ({len(output['results'])} queries)", file=sys.stderr)

    # Markdown human-readable report
    md_path = (
        _write_markdown_report(output, f"{profile_tag}_{ts}", profile_tag)
        if total_ads
        else None
    )
    if md_path:
        print(f"Report: {md_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
