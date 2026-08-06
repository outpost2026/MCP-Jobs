from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from .config import PortalConfig, UserConfig
from .matcher import has_exclude_terms, matches_ad
from .models import Ad
from .providers import REGISTRY
from .providers.base import BaseScraper

logger = logging.getLogger(__name__)


def _location_filter(ad: Ad, locations: list[str]) -> bool:
    if not locations or not ad.location:
        return True
    ad_loc = ad.location.lower().strip()
    return any(loc.lower().strip() in ad_loc for loc in locations)


_SALARY_NUM_RE = re.compile(r"\d{1,3}(?:[ \u00a0]\d{3})+|\d+")


def _salary_filter(ad: Ad, min_salary: int) -> bool:
    if min_salary <= 0:
        return True
    salary = ad.salary or ad.price
    if not salary:
        return True
    raw_numbers = _SALARY_NUM_RE.findall(salary)
    numbers = [int(n.replace(" ", "").replace("\u00a0", "")) for n in raw_numbers]
    if not numbers:
        return True
    return any(n >= min_salary for n in numbers)


def _dedup(ads: list[Ad]) -> list[Ad]:
    seen_url: set[str] = set()
    seen_fuzzy: set[tuple[str, str, str]] = set()
    result: list[Ad] = []
    for ad in ads:
        url_key = ad.url
        fuzzy_key = (
            ad.title.lower().strip(),
            (ad.company or "").lower().strip(),
            (ad.location or "").lower().strip(),
        )
        if url_key not in seen_url and fuzzy_key not in seen_fuzzy:
            seen_url.add(url_key)
            seen_fuzzy.add(fuzzy_key)
            result.append(ad)
        elif url_key in seen_url:
            logger.warning("Dedup: duplicate URL dropped: %s", ad.url)
        else:
            logger.warning(
                "Dedup: fuzzy hit %r (company=%r, location=%r) dropped different URL %s",
                ad.title,
                ad.company,
                ad.location,
                ad.url,
            )
    return result


class SearchPipeline:
    def __init__(self, config: UserConfig):
        self.config = config

    def run(self) -> tuple[dict[str, list[Ad]], dict[str, dict], dict[str, int]]:
        pool, all_stats, pool_sizes = self._scrape_all()
        results: dict[str, list[Ad]] = {}

        # Lazy detail fetch: description doplnujeme jednou per URL
        # (stejny inzerat muze projit vice query). Sdileny HttpClient.
        detail_cache: dict[str, Optional[str]] = {}
        detail_providers: dict[str, BaseScraper] = {}

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
                if not ad.description:
                    if ad.url not in detail_cache:
                        if ad.portal not in detail_providers:
                            provider_cls = REGISTRY.get(ad.portal)
                            detail_providers[ad.portal] = (
                                provider_cls() if provider_cls else None
                            )
                        provider = detail_providers.get(ad.portal)
                        if provider:
                            try:
                                detail = provider.fetch_detail(ad)
                                if detail:
                                    detail_cache[ad.url] = detail
                            except Exception as e:
                                logger.warning(
                                    "detail fetch failed for %s: %s", ad.url, e
                                )
                    detail = detail_cache.get(ad.url)
                    if detail:
                        ad.description = detail
                if has_exclude_terms(
                    ad.title, qconf.exclude, description=ad.description or ""
                ):
                    continue
                if not _location_filter(ad, qconf.locations):
                    continue
                if not _salary_filter(ad, qconf.min_salary):
                    continue
                filtered.append(ad)

            results[name] = filtered

        return results, all_stats, pool_sizes

    def _scrape_one(
        self, portal_name: str, pconf: PortalConfig
    ) -> tuple[str, list[Ad], Optional[dict]]:
        """Scrape JEDNOHO portalu (bezi v samostatnem vlakne).

        Kazdy portal ma vlastni provider instanci + vlastni HttpClient
        (Session + throttle), takze mezi vlakny neni sdileny mutable stav.
        """
        provider = REGISTRY.get(portal_name)()
        pool: list[Ad] = []
        for cat in pconf.categories:
            try:
                ads = provider.scrape_all(cat.url, cat.pages, cat.params)
                logger.info(f"  {portal_name}: {cat.url} -> {len(ads)} ads")
                pool.extend(ads)
            except Exception as e:
                logger.error(f"  {portal_name}: {cat.url} -> error: {e}")
                provider.stats.errors.append(str(e))

        try:
            sd = provider.stats.to_dict()
        except Exception:
            sd = {}
        stats = None
        if sd.get("requests_ok") or sd.get("requests_failed"):
            stats = sd
        return portal_name, pool, stats

    def _scrape_all(self) -> tuple[list[Ad], dict[str, dict], dict[str, int]]:
        pool: list[Ad] = []
        all_stats: dict[str, dict] = {}

        tasks = [
            (name, pconf)
            for name, pconf in self.config.portals.items()
            if pconf.enabled and REGISTRY.get(name)
        ]

        workers = self.config.pipeline.max_workers or len(tasks)
        workers = max(1, min(workers, len(tasks)))

        if workers == 1 or len(tasks) <= 1:
            # Sekvencni beh (puvodni chovani) — determinismus zachovan.
            for name, pconf in tasks:
                _, got, stats = self._scrape_one(name, pconf)
                pool.extend(got)
                if stats:
                    all_stats[name] = stats
        else:
            logger.info(
                f"Scraping {len(tasks)} portals in parallel (max_workers={workers})"
            )
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futures = {
                    ex.submit(self._scrape_one, name, pconf): name
                    for name, pconf in tasks
                }
                for fut in as_completed(futures):
                    name = futures[fut]
                    try:
                        _, got, stats = fut.result()
                        pool.extend(got)
                        if stats:
                            all_stats[name] = stats
                    except Exception as e:
                        logger.error(f"  {name}: parallel scrape failed: {e}")

        deduped = _dedup(pool)
        pool_sizes: dict[str, int] = {}
        for ad in deduped:
            pool_sizes[ad.portal] = pool_sizes.get(ad.portal, 0) + 1
        return deduped, all_stats, pool_sizes

    @staticmethod
    def from_config(path: str | Path) -> SearchPipeline:
        config = UserConfig.from_yaml(path)
        return SearchPipeline(config)
