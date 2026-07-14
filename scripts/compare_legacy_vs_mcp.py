"""
Comprehensive comparison: legacy scrapers vs MCP pipeline.

Scrapes with legacy-equivalent settings (same categories, pages, location filter)
and applies all 94 legacy topic keywords to identify coverage gaps.
"""
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mcp_jobs.http import HttpClient
from mcp_jobs.matcher import matches_ad, has_exclude_terms, strip_diacritics
from mcp_jobs.providers import REGISTRY

# ── Legacy-equivalent settings ──────────────────────────────────────

LEGACY_CONFIG = {
    "bazos": {
        "categories": [
            {"url": "https://prace.bazos.cz/", "pages": 15, "psc": "18000", "radius": "25"},
            {"url": "https://prace.bazos.cz/brigada/", "pages": 15, "psc": "18000", "radius": "25"},
        ]
    },
    "jobs": {
        "categories": [
            {"url": "https://www.jobs.cz/prace/praha/", "pages": 10},
            {"url": "https://www.jobs.cz/brigady/?locality%5B0%5D%5Bcode%5D=R200000&locality%5B0%5D%5Blabel%5D=Praha&locality%5B0%5D%5Bcoords%5D=50.08455%2C14.41778&locality%5B0%5D%5Bradius%5D=0", "pages": 10},
        ]
    },
    "pracecz": {
        "categories": [
            {"url": "https://www.prace.cz/nabidky/hlavni-mesto-praha/praha/", "pages": 15},
        ]
    },
}

# ── All 94 legacy topic keywords as boolean queries ──────────────────

LEGACY_TOPICS = """
zahradnik
udrzba+zelen
sekani+travy
zahradni prace
cnc
operator cnc
elektrikar
elektroinstalace
zapojeni+zasuvky
oprava+elektriny
udrzbar
spravce
truhlar
vyroba+ze+dreva
truhlarstvi
prace+s+masivem
oprava+strecha
opravy+strech
opravit+strechu
rekonstrukce+strechy
cisteni+okap
vycistit+okapy
vycisteni+okapu
zahrada+uklid
uklid+zahrady
uklidit+zahradu
priprava+zahrady
rezani+drevo
rezani+dreva
narezat+drevo
stipani+dreva
kaceni
kaceni+stromu
pokacet+strom
rizikove+kaceni
jarni+udrzba
jarni+uklid
priprava+na+sezonu
montaz+domek
montaz+domku
stavba+domku
postavit+domek
sestaveni+domku
stavba+pergola
stavba+pergoly
postavit+pergolu
montaz+pergoly
oprava+terasa
oprava+terasy
renovace+terasy
brouseni+terasy
drevnik
slozeni+nabytek
solar+oprava
servis+solar
oprava+fotovoltaiky
oprava+menice
solar+zapojeni
montaz+solar
zapojeni+panelu
instalace+fv
offgrid
off-grid
sobestacny+system
vymena+baterie
vymena+akumulatoru
nove+baterie+life
iot
internet+veci
data+mining
scraping
automatizace
python+developer
crawler
data+analyst
big+data
strojove+uceni
machine+learning
udrzbar+kone
udrzba+staj
oprava+ohrad
python+automation
web+scraping
etl+pipeline
python+skript
bms+monitoring
iot+monitoring
life+baterie
solar+servis
ostrovni+system
prace+se+drevem
cisteni+okapu
oprava+strechy
"""

TOPICS_LIST = [t.strip().replace("+", " ") for t in LEGACY_TOPICS.strip().split("\n") if t.strip()]

# ── Helpers ─────────────────────────────────────────────────────────

def build_bazos_url(base_url: str, offset: int, psc: str, radius: str) -> str:
    base_url = base_url.rstrip("/") + "/"
    url_path = base_url if offset == 0 else f"{base_url}{offset}/"
    return f"{url_path}?hledat=&hlokalita={psc}&humkreis={radius}&cenaod=&cenado=&order="

def scrape_legacy_equivalent() -> dict:
    """Scrape all portals with legacy-equivalent settings."""
    http = HttpClient()
    pool = {}

    # Bazos
    pool["bazos"] = []
    provider_bazos = REGISTRY["bazos"]()
    for cat in LEGACY_CONFIG["bazos"]["categories"]:
        scraped_urls = set()
        for page in range(cat["pages"]):
            offset = page * 20
            url = build_bazos_url(cat["url"], offset, cat["psc"], cat["radius"])
            text = http.get_text(url)
            if not text:
                break
            ads = provider_bazos.parse_listings(text, "")
            new = 0
            for ad in ads:
                if ad.url not in scraped_urls:
                    scraped_urls.add(ad.url)
                    ad.portal = "bazos"
                    pool["bazos"].append(ad)
                    new += 1
            if new == 0:
                break
    print(f"  bazos: {len(pool['bazos'])}")

    # Jobs
    pool["jobs"] = []
    provider_jobs = REGISTRY["jobs"]()
    for cat in LEGACY_CONFIG["jobs"]["categories"]:
        scraped_urls = set()
        connector = "&" if "?" in cat["url"] else "?"
        for page in range(1, cat["pages"] + 1):
            url = f"{cat['url']}{connector}page={page}"
            text = http.get_text(url)
            if not text:
                break
            ads = provider_jobs.parse_listings(text, "")
            new = 0
            for ad in ads:
                if ad.url not in scraped_urls:
                    scraped_urls.add(ad.url)
                    ad.portal = "jobs"
                    pool["jobs"].append(ad)
                    new += 1
            if new == 0:
                break
    print(f"  jobs: {len(pool['jobs'])}")

    # Pracecz
    pool["pracecz"] = []
    provider_pracecz = REGISTRY["pracecz"]()
    for cat in LEGACY_CONFIG["pracecz"]["categories"]:
        scraped_urls = set()
        connector = "&" if "?" in cat["url"] else "?"
        for page in range(1, cat["pages"] + 1):
            url = f"{cat['url']}{connector}page={page}"
            text = http.get_text(url)
            if not text:
                break
            ads = provider_pracecz.parse_listings(text, "")
            new = 0
            for ad in ads:
                if ad.url not in scraped_urls:
                    scraped_urls.add(ad.url)
                    ad.portal = "pracecz"
                    pool["pracecz"].append(ad)
                    new += 1
            if new == 0:
                break
    print(f"  pracecz: {len(pool['pracecz'])}")

    return pool


def safe_print(text):
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("utf-8", errors="replace").decode("utf-8"))


def analyze_coverage(pool: dict):
    """Apply all 94 legacy topic keywords and log matches per topic per portal."""
    report = {"per_topic": {}, "per_portal": {}, "unmatched": {}}

    for portal_name, ads in pool.items():
        portal_topic_matches = Counter()
        portal_unmatched = []

        for ad in ads:
            text = " ".join(filter(None, [ad.title, ad.description, ad.company]))
            matched = False
            matched_topic = None

            for topic in TOPICS_LIST:
                # Build boolean: split on spaces, join with AND
                terms = topic.split()
                if len(terms) == 1:
                    boolean = terms[0]
                else:
                    boolean = " AND ".join(terms)

                if matches_ad(ad, boolean):
                    matched = True
                    matched_topic = topic
                    portal_topic_matches[topic] += 1
                    break  # first-match-wins like legacy

            if not matched:
                portal_unmatched.append(ad.title)

        report["per_portal"][portal_name] = {
            "total": len(ads),
            "matched": len(ads) - len(portal_unmatched),
            "unmatched": len(portal_unmatched),
        }
        report["unmatched"][portal_name] = portal_unmatched[:20]  # first 20
        report["per_topic"][portal_name] = dict(portal_topic_matches.most_common())

    return report


def apply_mcp_config(pool: dict):
    """Apply current MCP config.yaml queries and report."""

    # Simulate the 3 MCP queries
    MCP_QUERIES = {
        "python_jobs": {
            "boolean": "(python OR developer OR programator OR vyvojar) NOT senior",
            "exclude": ["agentura", "nabizim", "nabizime", "prodavame", "hledam praci",
                       "hledame kolegu", "do tymu", "dodam", "firmy", "ico",
                       "jmenuji se", "nabor", "parta", "provadim", "provadime",
                       "prijmeme", "prijima objednavky", "lektor", "kurz"],
            "portals": ["jobs", "pracecz"],
        },
        "cnc_jobs": {
            "boolean": "(cnc OR frezar OR programovani OR serizovani)",
            "exclude": ["agentura", "do tymu", "dodam", "firmy", "hledam praci",
                       "hledame kolegu", "ico", "jmenuji se", "nabizim", "nabizime",
                       "nabor", "parta", "personalni", "pronajem", "provadim",
                       "provadime", "prijmeme", "prijima objednavky", "ubytovn",
                       "zprostredkovani"],
            "portals": ["bazos", "pracecz"],
        },
        "elektrikar": {
            "boolean": "(elektrikar OR elektroinstalace OR autoelektrikar)",
            "exclude": ["agentura", "autoskola", "do tymu", "dodam", "firmy",
                       "hledam praci", "hledame kolegu", "ico", "jmenuji se",
                       "nabizim", "nabizime", "nabor", "parta", "prodavame",
                       "provadim", "provadime", "prijmeme", "prijima objednavky",
                       "revize"],
            "portals": ["bazos", "pracecz", "jobs"],
        },
    }

    results = {}
    for qname, qconf in MCP_QUERIES.items():
        matches = []
        for portal_name in qconf["portals"]:
            for ad in pool.get(portal_name, []):
                if ad.portal not in qconf["portals"]:
                    continue
                if not matches_ad(ad, qconf["boolean"]):
                    continue
                if has_exclude_terms(ad.title, qconf["exclude"], description=ad.description or ""):
                    continue
                matches.append(ad)
        results[qname] = matches

    return results


def main():
    print("Scraping with legacy-equivalent settings...")
    pool = scrape_legacy_equivalent()

    total = sum(len(v) for v in pool.values())
    print(f"\nTotal pool: {total}")
    print()

    # Phase 1: Legacy topic coverage
    print("=" * 60)
    print("PHASE 1: Legacy 94-topic coverage (first-match-wins)")
    print("=" * 60)
    coverage = analyze_coverage(pool)

    # Print summary (avoid encoding issues)
    def safe_print(text):
        try:
            print(text)
        except UnicodeEncodeError:
            print(text.encode("utf-8", errors="replace").decode("utf-8"))

    for portal_name, stats in coverage["per_portal"].items():
        safe_print(f"\n{portal_name}: {stats['matched']}/{stats['total']} matched ({stats['unmatched']} unmatched)")
        safe_print("  Top topics:")
        for topic, count in list(coverage["per_topic"][portal_name].items())[:15]:
            safe_print(f"    {topic}: {count}")
        if coverage["unmatched"][portal_name]:
            safe_print(f"  Unmatched titles (first 10):")
            for t in coverage["unmatched"][portal_name][:10]:
                safe_print(f"    - {t}")

    # Phase 2: MCP config coverage
    safe_print("\n" + "=" * 60)
    safe_print("PHASE 2: Current MCP config.yaml coverage (3 queries)")
    safe_print("=" * 60)
    mcp_results = apply_mcp_config(pool)
    for qname, ads in mcp_results.items():
        safe_print(f"\n{qname}: {len(ads)} results")
        for a in ads:
            safe_print(f"  [{a.portal}] {a.title[:60]}")
            if a.description:
                safe_print(f"    desc: {(a.description or '')[:60]}")

    # Phase 3: Gap analysis
    safe_print("\n" + "=" * 60)
    safe_print("PHASE 3: Gap analysis")
    safe_print("=" * 60)

    # Which MCP queries cover which legacy topic areas
    topic_areas = {
        "python_jobs": ["python", "developer", "programator", "vyvojar", "data analyst", "machine learning",
                       "data mining", "scraping", "automatizace", "big data", "strojove uceni",
                       "python automation", "web scraping", "etl pipeline", "crawler"],
        "cnc_jobs": ["cnc", "frezar", "programovani", "serizovani", "operator cnc"],
        "elektrikar": ["elektrikar", "elektroinstalace", "autoelektrikar", "zapojeni", "oprava elektriny",
                      "solar", "fotovoltaika", "offgrid"],
    }

    legacy_area_hits = {}
    for area, topics in topic_areas.items():
        hits = 0
        for portal_name, topic_counts in coverage["per_topic"].items():
            for t, c in topic_counts.items():
                if any(kw in t for kw in topics):
                    hits += c
        legacy_area_hits[area] = hits

    mcp_hits = {q: len(v) for q, v in mcp_results.items()}

    safe_print(f"\nCoverage comparison (legacy topics vs MCP queries):")
    safe_print(f"{'Area':<20} {'Legacy hits':<15} {'MCP hits':<15} {'Capture rate':<15}")
    safe_print(f"{'-'*20} {'-'*15} {'-'*15} {'-'*15}")
    for area in ["python_jobs", "cnc_jobs", "elektrikar"]:
        lh = legacy_area_hits.get(area, 0)
        mh = mcp_hits.get(area, 0)
        rate = f"{mh}/{lh}" if lh else "N/A"
        safe_print(f"{area:<20} {lh:<15} {mh:<15} {rate:<15}")

    total_legacy = sum(v["matched"] for v in coverage["per_portal"].values())
    total_mcp = sum(len(v) for v in mcp_results.values())
    safe_print(f"\n{'TOTAL':<20} {total_legacy:<15} {total_mcp:<15} {(total_mcp/total_legacy*100 if total_legacy else 0):.0f}%")

    # Phase 4: Missing keywords
    all_legacy_topics_found = set()
    for tc in coverage["per_topic"].values():
        all_legacy_topics_found.update(tc.keys())

    safe_print(f"\nLegacy topics WITH matches BUT no MCP query covering them:")
    mcp_covered_keywords = set()
    for kw_list in topic_areas.values():
        mcp_covered_keywords.update(kw_list)

    uncovered = [t for t in all_legacy_topics_found
                 if not any(kw in t for kw in mcp_covered_keywords)]
    for t in sorted(uncovered)[:25]:
        total_hits = sum(coverage["per_topic"].get(p, {}).get(t, 0) for p in pool)
        safe_print(f"  {t}: {total_hits} hits across all portals")

    # Save report
    out_path = Path(__file__).resolve().parent.parent / "data" / "comparison_report.json"
    report = {
        "pool_sizes": {p: len(v) for p, v in pool.items()},
        "legacy_coverage": coverage["per_portal"],
        "mcp_results": {q: [a.to_dict() for a in v] for q, v in mcp_results.items()},
        "unmatched": coverage["unmatched"],
        "uncovered_topics": sorted(uncovered)[:30],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    safe_print(f"\nFull report saved: {out_path}")


if __name__ == "__main__":
    main()
