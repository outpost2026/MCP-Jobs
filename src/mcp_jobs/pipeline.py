from __future__ import annotations

import logging
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


def _salary_filter(ad: Ad, min_salary: int) -> bool:
    if min_salary <= 0 or not ad.salary:
        return True
    numbers = [int(s) for s in ad.salary.split() if s.replace(".", "", 1).lstrip("-").isdigit()]
    return any(n >= min_salary for n in numbers)


def _unique_by_url(ads: list[Ad]) -> list[Ad]:
    seen: set[str] = set()
    result: list[Ad] = []
    for ad in ads:
        if ad.url not in seen:
            seen.add(ad.url)
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

        return _unique_by_url(pool)

    @staticmethod
    def from_config(path: str | Path) -> SearchPipeline:
        config = UserConfig.from_yaml(path)
        return SearchPipeline(config)
