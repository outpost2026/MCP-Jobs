from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from . import __version__
from .config import UserConfig
from .matcher import matches_ad
from .models import Ad
from .pipeline import SearchPipeline
from .providers import ACTIVE_PORTALS
from .storage import CorrelationRecord, Storage
from .utils import ensure_utf8_stdout

# P18: Console encoding safety — Windows cp1250 before any output
ensure_utf8_stdout()

logger = logging.getLogger(__name__)
mcp = FastMCP("MCP-Jobs")

# ── L2 Resource store ─────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent.parent
_QUERY_STORE_PATH = _ROOT / "data" / "query_store.json"
_CORRELATION_PATH = _ROOT / "data" / "correlation_cache.json"
_OUTPUT_DIR = _ROOT / "output"
_MAX_STORED = 50

_query_store: dict[str, dict] = {}


def _load_query_store() -> None:
    if _QUERY_STORE_PATH.exists():
        try:
            with _QUERY_STORE_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
            _query_store.update(data)
            logger.info("Loaded %d entries from %s", len(data), _QUERY_STORE_PATH)
        except Exception as e:
            logger.warning("Failed to load query store: %s", e)


def _save_query_store() -> None:
    _QUERY_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _QUERY_STORE_PATH.open("w", encoding="utf-8") as f:
        json.dump(_query_store, f, ensure_ascii=False, indent=2)


def _save_correlation(results: dict[str, list[Ad]], pool_sizes: dict[str, int]) -> None:
    from collections import Counter

    per_query_portal: dict[tuple[str, str], int] = Counter()
    for query_name, ads in results.items():
        for ad in ads:
            per_query_portal[(query_name, ad.portal)] += 1

    records = [
        CorrelationRecord(
            query=query,
            portal=portal,
            total_found=count,
            total_scraped=pool_sizes.get(portal, 0),
        )
        for (query, portal), count in per_query_portal.items()
    ]
    try:
        Storage.save_correlation(records, _CORRELATION_PATH)
    except Exception as e:
        logger.warning("Failed to save correlation cache: %s", e)


def _store_results(results_data: list[dict]) -> str:
    query_id = uuid.uuid4().hex[:8]
    _query_store[query_id] = {
        "data": results_data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "search_results",
    }
    # Keep max N entries, drop oldest
    if len(_query_store) > _MAX_STORED:
        ids = sorted(_query_store, key=lambda qid: _query_store[qid]["timestamp"])
        for qid in ids[: len(_query_store) - _MAX_STORED]:
            del _query_store[qid]
    _save_query_store()
    return query_id


# Load persisted store on module init
_load_query_store()


PORTAL_ALIASES: dict[str, str] = {
    "vše": "vše",
    "vse": "vše",
    "all": "vše",
    "bazos": "bazos",
    "jobs": "jobs",
    "pracecz": "pracecz",
    "prace": "pracecz",
}


@mcp.tool(description="Check server health and version.")
def health_check() -> dict:
    return {
        "status": "ok",
        "server": "mcp-jobs",
        "version": __version__,
        "phase": "05-l2-resources",
    }


def _run_pipeline(config: UserConfig) -> list[dict]:
    try:
        pipeline = SearchPipeline(config)
        results, scraper_stats, pool_sizes = pipeline.run()
    except Exception as e:
        logger.exception("Pipeline error")
        return [{"error": f"Pipeline error: {e}"}]

    output = []
    for query_name, ads in results.items():
        entry = {
            "query": query_name,
            "total_found": len(ads),
            "results": [a.to_dict() for a in ads],
        }
        if scraper_stats:
            entry["_stats"] = scraper_stats
        output.append(entry)
    if not output:
        return [{"message": "No results found."}]

    _save_correlation(results, pool_sizes)

    query_id = _store_results(output)
    output[0]["query_id"] = query_id
    output[0]["resource_uri"] = f"mcp-jobs://ads/{query_id}"
    try:
        Storage.save_timestamped(output, _OUTPUT_DIR)
    except Exception as e:
        logger.warning("Failed to persist output: %s", e)
    return output


@mcp.tool(
    description=(
        "Run the full search pipeline from a YAML config file path. "
        "Category bulk scrape + boolean filter + location/salary filter. "
        "Returns results per query defined in the config."
    )
)
def search_from_config(config_path: str) -> list[dict]:
    path = Path(config_path)
    if not path.exists():
        return [{"error": f"Config file not found: {config_path}"}]

    try:
        config = UserConfig.from_yaml(path)
    except Exception as e:
        return [{"error": f"Config parse error: {e}"}]

    return _run_pipeline(config)


@mcp.tool(
    description=(
        "Run the full search pipeline from inline YAML content (no file needed). "
        "Accepts the same YAML structure as config.yaml.example. "
        "Category bulk scrape + boolean filter + location/salary filter. "
        "Returns results per query defined in the YAML."
    )
)
def search_from_yaml(yaml_content: str) -> list[dict]:
    try:
        config = UserConfig.from_yaml_string(yaml_content)
    except Exception as e:
        return [{"error": f"YAML parse error: {e}"}]

    return _run_pipeline(config)


@mcp.tool(
    description=(
        "Ad-hoc category bulk search across CZ job portals. "
        "Scrapes ALL listings from given category URLs and applies boolean filter locally. "
        "Supports AND/OR/NOT boolean syntax, e.g. 'python AND developer NOT senior'. "
        "Use \\b word-boundary matching (cnc != elektrocnc)."
    )
)
def search_jobs_v2(
    query: str,
    portal: str = "vše",
    pages: int = 3,
) -> list[dict]:
    pages = max(1, min(pages, 50))
    portal_key = PORTAL_ALIASES.get(portal.lower().strip(), portal.lower().strip())
    portals_to_search: list[str] = []

    if portal_key == "vše":
        portals_to_search = list(ACTIVE_PORTALS.keys())
    elif portal_key in ACTIVE_PORTALS:
        portals_to_search = [portal_key]
    else:
        available = ", ".join(ACTIVE_PORTALS.keys())
        return [{"error": f"Unknown portal '{portal}'. Available: vše, {available}"}]

    results: list[dict] = []
    errors: list[str] = []
    all_stats: dict[str, dict] = {}

    for name in portals_to_search:
        provider_cls = ACTIVE_PORTALS[name]
        provider = provider_cls()
        try:
            category_url = _default_category(name)
            ads = provider.scrape_all(category_url, pages)

            sd = provider.stats.to_dict()
            if sd["requests_ok"] or sd["requests_failed"]:
                all_stats[name] = sd

            for ad in ads:
                if matches_ad(ad, query):
                    results.append(ad.to_dict())
        except Exception as e:
            errors.append(f"{name}: {e}")

    if not results:
        if errors:
            return [{"error": f"Portal errors: {' | '.join(errors)}"}]
        return [{"message": f"No results found for '{query}'."}]

    output = [
        {
            "query": query,
            "portal": portal,
            "total_found": len(results),
            "results": results,
        }
    ]
    if all_stats:
        output[0]["_stats"] = all_stats
    if errors and results:
        output[0]["errors"] = errors

    query_id = _store_results(output)
    output[0]["query_id"] = query_id
    output[0]["resource_uri"] = f"mcp-jobs://ads/{query_id}"
    try:
        Storage.save_timestamped(output, _OUTPUT_DIR)
    except Exception as e:
        logger.warning("Failed to persist output: %s", e)
    return output


@mcp.tool(description="List available portals and their default category URLs.")
def list_portals() -> list[dict]:
    return [
        {
            "name": name,
            "default_category": _default_category(name),
            "description": _portal_description(name),
        }
        for name in ACTIVE_PORTALS
    ]


# ── L2 Resources ──────────────────────────────────────────────────


@mcp.resource(
    uri="mcp-jobs://ads/list",
    name="ads_list",
    title="Available Search Results",
    description="List all available query result sets stored in this session",
    mime_type="application/json",
)
def list_ads_resources() -> str:
    entries = [
        {
            "query_id": qid,
            "timestamp": info["timestamp"],
            "query_count": len(info["data"]),
            "uris": [
                f"mcp-jobs://ads/{qid}",
                f"mcp-jobs://ads/{qid}/report",
            ],
        }
        for qid, info in _query_store.items()
    ]
    return json.dumps(entries, ensure_ascii=False, indent=2)


@mcp.resource(
    uri="mcp-jobs://ads/{query_id}",
    name="ads_by_id",
    title="Search Results by Query ID",
    description="Retrieve search results as JSON by query ID",
    mime_type="application/json",
)
def get_ads_resource(query_id: str) -> str:
    if query_id not in _query_store:
        raise ValueError(
            f"Unknown query_id '{query_id}'. "
            f"Use mcp-jobs://ads/list to see available IDs."
        )
    return json.dumps(_query_store[query_id]["data"], ensure_ascii=False, indent=2)


@mcp.resource(
    uri="mcp-jobs://ads/{query_id}/report",
    name="ads_report_by_id",
    title="Search Results Report (Markdown)",
    description="Retrieve search results as a markdown report by query ID",
    mime_type="text/markdown",
)
def get_ads_report_resource(query_id: str) -> str:
    if query_id not in _query_store:
        raise ValueError(
            f"Unknown query_id '{query_id}'. "
            f"Use mcp-jobs://ads/list to see available IDs."
        )

    data = _query_store[query_id]["data"]
    timestamp = _query_store[query_id]["timestamp"]

    # Reconstruct Ad objects for markdown generation
    ads_by_query: dict[str, list[Ad]] = {}
    for entry in data:
        qname = entry.get("query", "query")
        ads = []
        for ad_dict in entry.get("results", []):
            ads.append(
                Ad(
                    title=ad_dict.get("title", ""),
                    url=ad_dict.get("url", ""),
                    portal=ad_dict.get("portal", ""),
                    date=ad_dict.get("date"),
                    company=ad_dict.get("company"),
                    location=ad_dict.get("location"),
                    salary=ad_dict.get("salary"),
                    price=ad_dict.get("price"),
                    description=ad_dict.get("description"),
                    category_name=ad_dict.get("category_name"),
                    matched_keyword=ad_dict.get("matched_keyword", ""),
                    scraped_at=ad_dict.get("scraped_at", ""),
                )
            )
        ads_by_query[qname] = ads

    total_raw = sum(len(a) for a in ads_by_query.values())
    from .report import ReportMeta, render_report

    meta = ReportMeta(
        timestamp=timestamp,
        total_matched=total_raw,
        total_raw=total_raw,
        precision=round((total_raw / total_raw) * 100, 1) if total_raw else 0.0,
        portals=sorted(
            {a.portal for ads in ads_by_query.values() for a in ads if a.portal}
        ),
        queries=list(ads_by_query.keys()),
    )
    report = render_report(ads_by_query, meta)
    return report.markdown


@mcp.prompt(
    name="search_expert",
    title="Search Expert — Boolean Query Builder",
    description="Convert natural language job search criteria into a boolean query for MCP-Jobs",
)
def search_expert(
    query_description: str,
    location: str = "",
    min_salary: int = 0,
    exclude_terms: str = "",
) -> list[dict]:
    desc_words = [w.strip() for w in query_description.strip().split() if w.strip()]
    desc_expr = " AND ".join(f"({w})" for w in desc_words) if desc_words else ""
    parts = [desc_expr] if desc_expr else []
    if location.strip():
        loc_words = [w.strip() for w in location.strip().split() if w.strip()]
        loc_expr = " OR ".join(f"({w})" for w in loc_words)
        parts.append(f"({loc_expr})" if len(loc_words) > 1 else loc_expr)
    boolean_query = " AND ".join(parts) if parts else ""
    if exclude_terms.strip():
        exclude_list = [t.strip() for t in exclude_terms.split(",") if t.strip()]
        if exclude_list:
            not_part = " AND ".join(
                f"NOT ({' AND '.join(e.split())})" for e in exclude_list
            )
            boolean_query = (
                f"{boolean_query} AND {not_part}" if boolean_query else not_part
            )

    loc_val = repr(location) if location else ""
    excl_list = (
        [e.strip() for e in exclude_terms.split(",") if e.strip()]
        if exclude_terms
        else []
    )
    excl_val = ", ".join(repr(e) for e in excl_list)

    lines = [
        "## Generated Boolean Query",
        "```",
        boolean_query,
        "```",
        "",
        "### Usage",
        "",
        "**Option 1 — Quick search (ad-hoc):**",
        'Use `search_jobs_v2` with `query="{}"`'.format(boolean_query),
        "",
        "**Option 2 — Config file (full pipeline):**",
        "```yaml",
        "queries:",
        "  my_search:",
        '    boolean: "{}"'.format(boolean_query),
        "    locations: [{}]".format(loc_val),
        "    min_salary: {}".format(min_salary if min_salary > 0 else 0),
        "    exclude: [{}]".format(excl_val),
        "```",
        "",
        "### Boolean Syntax Reference",
        "- `AND` — both terms must match (e.g., `python AND developer`)",
        "- `OR` — either term matches (e.g., `python OR java`)",
        "- `NOT` — term must NOT be present (e.g., `NOT senior`)",
        "- Parentheses for grouping: `(python OR java) AND developer`",
        "- Word-boundary matching: `cnc` does NOT match `elektrocnc`",
        "- Diacritics-insensitive: `programátor` matches `programator`",
    ]
    return [{"role": "user", "content": "\n".join(lines)}]


def _default_category(name: str) -> str:
    defaults = {
        "bazos": "https://prace.bazos.cz/",
        "jobs": "https://www.jobs.cz/prace/praha/",
        "pracecz": "https://www.prace.cz/nabidky/",
    }
    return defaults.get(name, "")


def _portal_description(name: str) -> str:
    descriptions = {
        "bazos": "General classifieds portal (jobs, services, goods)",
        "jobs": "Dedicated job portal (jobs.cz network)",
        "pracecz": "Dedicated job portal (prace.cz network)",
    }
    return descriptions.get(name, "")
