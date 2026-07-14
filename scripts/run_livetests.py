"""
Live test runner — saves structured results to data/ after each run.
Usage:
  python scripts/run_livetests.py          # full suite
  python scripts/run_livetests.py --quick   # 1 page per portal only
"""
from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ensure src is on path
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT / "src"))

from mcp_jobs.server import (
    search_jobs_v2,
    search_from_yaml,
    search_from_config,
    list_portals,
    PORTAL_ALIASES,
    ACTIVE_PORTALS,
)
from mcp_jobs.matcher import matches_ad, evaluate_boolean, strip_diacritics
from mcp_jobs.models import Ad
from mcp_jobs.config import UserConfig
from mcp_jobs.pipeline import SearchPipeline
from mcp_jobs.providers import REGISTRY

DATA_DIR = _ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

QUICK = "--quick" in sys.argv

LOG: list[dict[str, Any]] = []
PHASE = "00-UNSET"


def log(event: str, detail: str = "", **kw: Any) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
        "event": event,
        "detail": detail,
        **kw,
    }
    LOG.append(entry)
    status = "OK" if not kw.get("error") else "ERR"
    print(f"  [{status}] {event}")
    if detail:
        print(f"       {detail[:300]}")
    if kw.get("error"):
        print(f"       ERROR: {kw['error']}")
    if kw.get("anomaly"):
        print(f"       ANOMALY: {kw['anomaly']}")


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        log(f"PASS: {name}", detail)
    else:
        log(f"FAIL: {name}", detail, error="Assertion failed")


PAGES = 1 if QUICK else 2
pages_label = "1" if QUICK else "2"

# ═══════════════════════════════════════════════════════
PHASE = "01-SERVER-META"
log(f"Live test run — {datetime.now(timezone.utc).isoformat()}")
log(f"Mode: {'quick' if QUICK else 'full'}, pages={pages_label}")

p = list_portals()
check(f"list_portals returns {len(p)} portals", len(p) == 3)
for portal in p:
    check(
        f"portal '{portal['name']}' has default_category",
        bool(portal.get("default_category")),
        f"category={portal.get('default_category')}",
    )
check("ACTIVE_PORTALS excludes nyx", "nyx" not in ACTIVE_PORTALS)
check("ACTIVE_PORTALS count", len(ACTIVE_PORTALS) == 3)

# ═══════════════════════════════════════════════════════
PHASE = "02-PORTAL-SCRAPE"

for portal_name in ("jobs", "bazos", "pracecz"):
    log(f"Scraping {portal_name} (1 page)")
    try:
        r = search_jobs_v2("programator", portal=portal_name, pages=1)
        check(f"{portal_name} returns list", isinstance(r, list))
        if isinstance(r, list) and r:
            if "error" in r[0]:
                log(f"{portal_name} error", error=r[0]["error"])
            elif "message" in r[0]:
                log(f"{portal_name}: 0 results", r[0]["message"])
            elif "total_found" in r[0]:
                check(f"{portal_name} OK", r[0]["total_found"] >= 0, f"total={r[0]['total_found']}")
                if r[0]["total_found"] > 0:
                    for ad in r[0]["results"][:3]:
                        log(f"  result: {ad['title']}", f"company={ad.get('company','?')}")
    except Exception as e:
        log(f"{portal_name} exception", error=f"{type(e).__name__}: {e}")

log("Scraping ALL portals combined (1 page)")
try:
    r_all = search_jobs_v2("python", portal="all", pages=1)
    check("all returns list", isinstance(r_all, list))
    if isinstance(r_all, list) and r_all:
        if "error" in r_all[0]:
            log("all error", error=r_all[0]["error"])
        elif "message" in r_all[0]:
            log("all: no results", r_all[0]["message"])
        elif "total_found" in r_all[0]:
            check("all OK", r_all[0]["total_found"] >= 0, f"total={r_all[0]['total_found']}")
except Exception as e:
    log("all exception", error=f"{type(e).__name__}: {e}")

# ═══════════════════════════════════════════════════════
PHASE = "03-BOOLEAN-MATCHER"
log("Testing boolean matcher")

# Diacritics
check("diacritics: programator -> Programátor",
      matches_ad(Ad(title="Programátor Python", url="http://x", portal="jobs"), "programator"))
check("diacritics reverse: programátor -> Programator",
      matches_ad(Ad(title="Programator", url="http://x", portal="jobs"), "programátor"))
check("diacritics: vyvojar -> Vývojář",
      matches_ad(Ad(title="Vývojář Java", url="http://x", portal="jobs"), "vyvojar"))

# Word boundaries preserved with diacritics
check("wb: cnc vs elektrocnc",
      not matches_ad(Ad(title="ElektroCNC", url="http://x", portal="jobs"), "cnc"))
check("wb: nara vs naradi",
      not matches_ad(Ad(title="Nářadí", url="http://x", portal="jobs"), "nara"))

# Boolean logic
check("AND", matches_ad(Ad(title="Python Developer", url="http://x", portal="jobs"), "python AND developer"))
check("AND fail", not matches_ad(Ad(title="Python Tester", url="http://x", portal="jobs"), "python AND developer"))
check("OR", matches_ad(Ad(title="Java Dev", url="http://x", portal="jobs"), "python OR java"))
check("NOT", not matches_ad(Ad(title="Python Junior", url="http://x", portal="jobs"), "python NOT junior"))
check("NOT pass", matches_ad(Ad(title="Python Senior", url="http://x", portal="jobs"), "python NOT junior"))
check("parens", matches_ad(Ad(title="Java Developer", url="http://x", portal="jobs"), "(python OR java) AND developer"))
check("empty query", matches_ad(Ad(title="Anything", url="http://x", portal="jobs"), ""))

# strip_diacritics unit
for inp, exp in [("programátor", "programator"), ("vývojář", "vyvojar"), ("řízení", "rizeni"), ("", "")]:
    result = strip_diacritics(inp)
    check(f"strip_diacritics({inp!r}) == {exp!r}", result == exp, f"got {result!r}")

# ═══════════════════════════════════════════════════════
PHASE = "04-YAML-PIPELINE"
log("Testing YAML pipeline")

yaml_simple = """
portals:
  jobs:
    enabled: true
    categories:
      - url: 'https://www.jobs.cz/prace/praha/'
        pages: 1
  bazos:
    enabled: false
    categories: []
  pracecz:
    enabled: false
    categories: []
queries:
  test_q:
    boolean: 'technik'
    portals: ['jobs']
"""
try:
    r4 = search_from_yaml(yaml_simple)
    check("yaml returns list", isinstance(r4, list))
    if isinstance(r4, list) and r4:
        if "error" in r4[0]:
            log("yaml error", error=r4[0]["error"])
        elif "message" in r4[0]:
            log("yaml: 0 results", r4[0]["message"])
        elif "total_found" in r4[0]:
            check("yaml query name", r4[0]["query"] == "test_q")
            log(f"yaml: {r4[0]['total_found']} results")
except Exception as e:
    log("yaml exception", error=f"{type(e).__name__}: {e}")

yaml_multi = """
portals:
  jobs:
    enabled: true
    categories:
      - url: 'https://www.jobs.cz/prace/praha/'
        pages: 1
  bazos:
    enabled: true
    categories:
      - url: 'https://prace.bazos.cz/'
        pages: 1
  pracecz:
    enabled: false
    categories: []
queries:
  it:
    boolean: 'programator OR vyvojar'
    portals: ['jobs']
  cnc:
    boolean: 'cnc OR frezar'
    portals: ['bazos']
"""
try:
    r5 = search_from_yaml(yaml_multi)
    check("multi-yaml returns list", isinstance(r5, list))
    if isinstance(r5, list) and r5:
        check("multi-yaml has 2 queries", len(r5) == 2, f"got {len(r5)}")
        names = {q.get("query") for q in r5}
        check("multi-yaml has 'it'", "it" in names)
        check("multi-yaml has 'cnc'", "cnc" in names)
except Exception as e:
    log("multi-yaml exception", error=f"{type(e).__name__}: {e}")

# error handling
for label, inp in [("invalid yaml", ": broken :"), ("empty yaml", "")]:
    try:
        r = search_from_yaml(inp)
        check(f"{label} returns error", isinstance(r, list) and r and "error" in r[0])
    except Exception as e:
        log(f"{label} exception", error=f"{type(e).__name__}: {e}")

# ═══════════════════════════════════════════════════════
PHASE = "05-CONFIG-ERRORS"
log("Testing config error handling")

check("nonexistent config returns error",
      isinstance(search_from_config("/nonexistent/path.yaml"), list) and
      "error" in search_from_config("/nonexistent/path.yaml")[0])

check("unknown portal returns error",
      isinstance(search_jobs_v2("python", portal="nonexistent"), list) and
      "error" in search_jobs_v2("python", portal="nonexistent")[0])

# ═══════════════════════════════════════════════════════
PHASE = "06-ALIASES"
log("Testing portal aliases")

alias_tests: list[tuple[str, str]] = [
    ("all", "vše"), ("vse", "vše"), ("VSE", "vše"),
    ("bazos", "bazos"), ("BAZOS", "bazos"),
    ("jobs", "jobs"), ("JOBS", "jobs"),
    ("pracecz", "pracecz"), ("prace", "pracecz"), ("PRACE", "pracecz"),
]
for inp, exp in alias_tests:
    got = PORTAL_ALIASES.get(inp.lower().strip(), inp.lower().strip())
    check(f"alias '{inp}' -> '{exp}'", got == exp, f"got '{got}'")

# ═══════════════════════════════════════════════════════
PHASE = "07-EDGE-CASES"
log("Testing edge cases")

# empty query — should match all
try:
    r_empty = search_jobs_v2("", portal="jobs", pages=1)
    check("empty query returns list", isinstance(r_empty, list))
    if isinstance(r_empty, list) and r_empty and "total_found" in r_empty[0]:
        check("empty query matches all", r_empty[0]["total_found"] > 0, f"total={r_empty[0]['total_found']}")
except Exception as e:
    log("empty query exception", error=f"{type(e).__name__}: {e}")

# 0 pages
try:
    r_0 = search_jobs_v2("python", portal="jobs", pages=0)
    check("0 pages returns list", isinstance(r_0, list))
    if isinstance(r_0, list) and r_0 and "total_found" in r_0[0]:
        check("0 pages = 0 results", r_0[0]["total_found"] == 0)
except Exception as e:
    log("0 pages exception", error=f"{type(e).__name__}: {e}")

# long query
try:
    long_q = " AND ".join([f"term{i}" for i in range(50)])
    r_long = search_jobs_v2(long_q, portal="jobs", pages=1)
    check("long query returns list", isinstance(r_long, list))
except Exception as e:
    log("long query exception", error=f"{type(e).__name__}: {e}")

# ═══════════════════════════════════════════════════════
PHASE = "08-REGISTRY"
log("Checking REGISTRY")

check("REGISTRY has all 4 providers", len(REGISTRY) == 4)
for name, cls in REGISTRY.items():
    try:
        inst = cls()
        check(f"provider '{name}' OK", inst.name == name)
    except Exception as e:
        log(f"provider '{name}' init failed", error=f"{type(e).__name__}: {e}")

# ═══════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════
errors = [e for e in LOG if e.get("error")]
anomalies = [e for e in LOG if e.get("anomaly")]
passes = [e for e in LOG if e["event"].startswith("PASS:")]
fails = [e for e in LOG if e["event"].startswith("FAIL:")]

summary = {
    "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"),
    "mode": "quick" if QUICK else "full",
    "pages": PAGES,
    "total_checks": len(passes) + len(fails),
    "passed": len(passes),
    "failed": len(fails),
    "errors": len(errors),
    "anomalies": len(anomalies),
    "verdict": "ALL_PASS" if not errors and not fails else "ISSUES_FOUND",
    "anomaly_list": [a["anomaly"] for a in anomalies],
    "error_list": [e["detail"] for e in errors],
}

print()
print("=" * 60)
print("  LIVE TEST SUMMARY")
print("=" * 60)
print(f"  Total checks:  {summary['total_checks']}")
print(f"  Passed:        {summary['passed']}")
print(f"  Failed:        {summary['failed']}")
print(f"  Errors:        {summary['errors']}")
print(f"  Anomalies:     {summary['anomalies']}")

if summary["error_list"]:
    print("  Errors:")
    for e in summary["error_list"]:
        print(f"    - {e}")
if summary["anomaly_list"]:
    print("  Anomalies:")
    for a in summary["anomaly_list"]:
        print(f"    - {a}")
print(f"  Verdict: {summary['verdict']}")
print("=" * 60)

# ── Save results ────────────────────────────────────
timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
log_file = DATA_DIR / f"livetest_{timestamp}.json"
summary_file = DATA_DIR / "livetest_latest.json"

with open(log_file, "w", encoding="utf-8") as f:
    json.dump({"summary": summary, "log": LOG}, f, ensure_ascii=False, indent=2)

with open(summary_file, "w", encoding="utf-8") as f:
    json.dump({"summary": summary, "log": LOG}, f, ensure_ascii=False, indent=2)

print(f"\nResults saved:")
print(f"  {log_file}")
print(f"  {summary_file}")

exit(1 if fails or errors else 0)
