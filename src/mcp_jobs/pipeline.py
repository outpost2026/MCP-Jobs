from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from .config import UserConfig
from .matcher import has_exclude_terms, matches_ad
from .models import Ad
from .providers import REGISTRY

logger = logging.getLogger(__name__)


def _location_filter(ad: Ad, locations: list[str]) -> bool:
    if not locations or not ad.location:
        return True
    ad_loc = ad.location.lower().strip()
    return any(loc.lower().strip() in ad_loc for loc in locations)

_SALARY_NUM_RE = re.compile(r"\d{1,3}(?:[ \u00a0]\d{3})+|\d+")


def _salary_filter(ad: Ad, min_salary: int) -> bool:
    if min_salary <= 0 or not ad.salary:
        return True
    raw_numbers = _SALARY_NUM_RE.findall(ad.salary)
    numbers = [int(n.replace(" ", "").replace("\u00a0", "")) for n in raw_numbers]
    if not numbers:
        return True
    return any(n >= min_salary for n in numbers)


def _dedup(ads: list[Ad]) -> list[Ad]:
    seen_url: set[str] = set()
    seen_fuzzy: set[tuple[str, str]] = set()
    result: list[Ad] = []
    for ad in ads:
        url_key = ad.url
        fuzzy_key = (ad.title.lower().strip(), (ad.company or "").lower().strip())
        if url_key not in seen_url and fuzzy_key not in seen_fuzzy:
            seen_url.add(url_key)
            seen_fuzzy.add(fuzzy_key)
            result.append(ad)
    return result


class SearchPipeline:
    def __init__(self, config: UserConfig):
        self.config = config

    def run(self) -> dict[str, list[Ad]]:
        pool = self._scrape_all()
        results: dict[str, list[Ad]] = {}

        for name, qconf in self.config.queries.items():
            if not qconf.boolean:
                logger.warning("Query %r has empty boolean expression — skipping", name)
                continue

            filtered = []
            for ad in pool:
                if qconf.portals and ad.portal not in qconf.portals:
                    continue
                if not matches_ad(ad, qconf.boolean):
                    continue
                if has_exclude_terms(ad.title, qconf.exclude, description=ad.description or ""):
                    continue
                if not _location_filter(ad, qconf.locations):
                    continue
                if not _salary_filter(ad, qconf.min_salary):
                    continue
                filtered.append(ad)

            results[name] = filtered

        return results

    def _scrape_all(self) -> list[Ad]:
        pool: list[Ad] = []

        for portal_name, pconf in self.config.portals.items():
            if not pconf.enabled:
                continue
            provider_cls = REGISTRY.get(portal_name)
            if not provider_cls:
                logger.warning(f"Unknown portal '{portal_name}', skipping")
                continue

            provider = provider_cls()
            for cat in pconf.categories:
                try:
                    ads = provider.scrape_all(cat.url, cat.pages, cat.params)
                    logger.info(f"  {portal_name}: {cat.url} -> {len(ads)} ads")
                    pool.extend(ads)
                except Exception as e:
                    logger.error(f"  {portal_name}: {cat.url} -> error: {e}")

        return _dedup(pool)

    @staticmethod
    def from_config(path: str | Path) -> SearchPipeline:
        config = UserConfig.from_yaml(path)
        return SearchPipeline(config)
