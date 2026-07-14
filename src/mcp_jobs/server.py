from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

from . import __version__
from .config import UserConfig
from .matcher import Matcher
from .pipeline import SearchPipeline
from .providers import REGISTRY

logger = logging.getLogger(__name__)
mcp = FastMCP("MCP-Jobs")

ACTIVE_PORTALS = {k: v for k, v in REGISTRY.items() if k != "nyx"}
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
        "phase": "03-category-bulk",
    }


def _run_pipeline(config: UserConfig) -> list[dict]:
    try:
        pipeline = SearchPipeline(config)
        results = pipeline.run()
    except Exception as e:
        logger.exception("Pipeline error")
        return [{"error": f"Pipeline error: {e}"}]

    output = []
    for query_name, ads in results.items():
        output.append({
            "query": query_name,
            "total_found": len(ads),
            "results": [a.to_dict() for a in ads],
        })
    return output if output else [{"message": "No results found."}]


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

    for name in portals_to_search:
        provider_cls = ACTIVE_PORTALS[name]
        provider = provider_cls()
        try:
            category_url = _default_category(name)
            ads = provider.scrape_all(category_url, pages)

            from .matcher import matches_ad
            for ad in ads:
                if matches_ad(ad, query):
                    results.append(ad.to_dict())
        except Exception as e:
            errors.append(f"{name}: {e}")

    if not results and not errors:
        return [{"message": f"No results found for '{query}'."}]

    output = [{"query": query, "portal": portal, "total_found": len(results), "results": results}]
    if errors:
        output[0]["errors"] = errors
    return output


@mcp.tool(
    description="List available portals and their default category URLs."
)
def list_portals() -> list[dict]:
    return [
        {
            "name": name,
            "default_category": _default_category(name),
            "description": _portal_description(name),
        }
        for name in ACTIVE_PORTALS
    ]


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
