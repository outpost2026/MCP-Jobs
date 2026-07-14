"""
Live integration test — scrapes all 4 CZ portals and saves results to data/.
Run with: python tests/test_live_scrapers.py [--save]
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from mcp_jobs.utils import ensure_utf8_stdout

ensure_utf8_stdout()

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from mcp_jobs.providers import REGISTRY
from mcp_jobs.http import HttpClient


QUERIES = {
    "bazos": "python",
    "jobs": "python developer",
    "pracecz": "programátor",
    "nyx": "CNC",
}


def test_scraper(name: str, query: str, save: bool = False) -> dict:
    print(f"\n{'='*60}")
    print(f"  {name.upper()} — query: '{query}'")
    print(f"{'='*60}")

    scraper_cls = REGISTRY[name]
    scraper = scraper_cls()

    search_url = scraper.build_search_url(query)
    print(f"  URL: {search_url}")

    raw_dir = REPO_ROOT / "data" / name
    result: dict = {
        "portal": name,
        "query": query,
        "search_url": search_url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "unknown",
        "ads": [],
        "ad_count": 0,
        "error": None,
        "raw_html_saved": False,
    }

    # Fetch raw HTML
    try:
        start = time.monotonic()
        text = scraper.http.get_text(search_url)
        elapsed = time.monotonic() - start
        print(f"  HTTP GET: {elapsed:.2f}s, len={len(text) if text else 0}")
    except Exception as e:
        result["status"] = "http_error"
        result["error"] = str(e)
        print(f"  [ERR] HTTP ERROR: {e}")
        return result

    # Save raw HTML (always when --save, even for empty responses)
    if save:
        html_path = raw_dir / f"raw_{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        raw_content = text if text else ""
        html_path.write_text(raw_content, encoding="utf-8")
        result["raw_html_saved"] = True
        result["raw_html_size"] = len(raw_content)
        print(f"  [SAVED] Raw HTML: {html_path.name} ({len(raw_content)} bytes)")

    if not text:
        result["status"] = "empty_response"
        result["error"] = "No text returned from HTTP GET"
        print(f"  [ERR] EMPTY RESPONSE")
        return result

    # Parse listings
    try:
        ads = scraper.parse_listings(text, query)
        elapsed = time.monotonic() - start
        print(f"  Parsing: {elapsed:.2f}s, ads={len(ads)}")
    except Exception as e:
        result["status"] = "parse_error"
        result["error"] = str(e)
        print(f"  [ERR] PARSE ERROR: {e}")
        return result

    result["status"] = "ok" if ads else "no_results"
    result["ads"] = [a.to_dict() for a in ads]
    result["ad_count"] = len(ads)

    def _safe(text: str) -> str:
        return text.encode("cp1250", errors="replace").decode("cp1250")

    for a in ads[:5]:
        ok = "[OK]" if a.title else "[WARN]"
        print(f"    {ok} {_safe(a.title or 'NO TITLE')}")
        print(f"       URL: {a.url}")
        if a.company:
            print(f"       Company: {_safe(a.company)}")
        if a.location:
            print(f"       Location: {_safe(a.location)}")
        if a.salary or a.price:
            print(f"       {'Salary' if a.salary else 'Price'}: {_safe(a.salary or a.price)}")

    # Save results JSON
    if save:
        json_path = raw_dir / f"results_{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  [SAVED] Results: {json_path.name}")

    return result


def main():
    save = "--save" in sys.argv
    if save:
        print("[SAVE] Save mode ON — raw HTML and JSON will be written to data/")

    results = {}
    summary_path = REPO_ROOT / "data" / "logs" / f"live_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    for name, query in QUERIES.items():
        results[name] = test_scraper(name, query, save=save)
        # Polite delay between portals
        if name != list(QUERIES.keys())[-1]:
            time.sleep(1.5)

    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    all_ok = True
    for name, r in results.items():
        if r["status"] == "ok":
            status_icon = "[OK]"
        elif r["status"] == "no_results":
            status_icon = "[WARN]"
        else:
            status_icon = "[FAIL]"
        ad_info = f" ({r['ad_count']} ads)" if r["ad_count"] else ""
        print(f"  {status_icon} {name}: {r['status']}{ad_info}")
        if r.get("error"):
            print(f"       Error: {r['error']}")
        if r.get("raw_html_size"):
            print(f"       HTML: {r['raw_html_size']} bytes")
        if r["status"] != "ok":
            all_ok = False

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {n: {"status": r["status"], "ad_count": r["ad_count"], "error": r.get("error")} for n, r in results.items()},
        "all_ok": all_ok,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[SAVED] Summary: {summary_path}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
