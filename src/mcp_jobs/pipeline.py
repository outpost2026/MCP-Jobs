from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from .config import PortalConfig, UserConfig
from .matcher import has_exclude_terms, matches_ad
from .models import Ad
from .providers import REGISTRY

logger = logging.getLogger(__name__)

# Sentinel pro cached failed detail fetch — odlisny od None (" jeste nezkouseno").
_FAILED = object()


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

        # ── Faze 1: Collect unikatni URL pres vsechny query ────────
        # Stejny ad muze projit vice query — detail fetch chceme jen 1x per URL.
        urls_needing_detail: set[str] = set()
        for qconf in self.config.queries.values():
            if not qconf.boolean:
                continue
            for ad in pool:
                if not ad.description and ad.url not in urls_needing_detail:
                    if qconf.portals and ad.portal not in qconf.portals:
                        continue
                    if matches_ad(ad, qconf.boolean):
                        urls_needing_detail.add(ad.url)

        # ── Faze 2: Parallel detail fetch (per-portal throttle) ────
        detail_cache: dict[str, Optional[str]] = {}
        if urls_needing_detail:
            self._fetch_details_parallel(urls_needing_detail, pool, detail_cache)

        # ── Faze 3: Filter query nad naplnenou cache ───────────────
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
                # Aplikuj cached detail (uspech i neuspech = cached).
                if not ad.description:
                    cached = detail_cache.get(ad.url)
                    if cached is not _FAILED and cached:
                        ad.description = cached
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

    def _fetch_details_parallel(
        self,
        urls: set[str],
        pool: list[Ad],
        detail_cache: dict[str, Optional[str]],
    ) -> None:
        """Paralelni detail fetch — seskupeny per-portal.

        Kazdy portal ma vlastni ThreadPoolExecutor s vlastnim throttle
        (pres HttpClient), takze neni riziko prekroceni rate limitu.
        Neuspech se zapise do detail_cache jako _FAILED, aby se
        opakovane query na stejnou padlou URL nedely retry.
        """
        # Map URL -> portal pro grouping
        url_portal: dict[str, str] = {}
        for ad in pool:
            if ad.url in urls:
                url_portal[ad.url] = ad.portal

        # Group by portal
        by_portal: dict[str, list[str]] = {}
        for url, portal in url_portal.items():
            by_portal.setdefault(portal, []).append(url)

        def _fetch_one(url: str, portal_name: str) -> tuple[str, Optional[str]]:
            provider_cls = REGISTRY.get(portal_name)
            if not provider_cls:
                return url, None
            from .http import HttpClient

            provider = provider_cls(
                http_client=HttpClient(request_delay=self.config.pipeline.request_delay)
            )
            # Najdi ad objekt pro fetch_detail
            ad_obj = next((a for a in pool if a.url == url), None)
            if not ad_obj:
                return url, None
            try:
                detail = provider.fetch_detail(ad_obj)
                return url, detail
            except Exception as e:
                logger.warning("detail fetch failed for %s: %s", url, e)
                return url, None

        workers = self.config.pipeline.max_workers or len(by_portal)
        workers = max(1, min(workers, len(by_portal)))

        if workers == 1 or len(by_portal) <= 1:
            for portal_name, portal_urls in by_portal.items():
                for url in portal_urls:
                    url, detail = _fetch_one(url, portal_name)
                    detail_cache[url] = detail if detail else _FAILED
        else:
            logger.info(
                f"Fetching details for {len(urls)} URLs across {len(by_portal)} portals "
                f"(max_workers={workers})"
            )
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futures = {}
                for portal_name, portal_urls in by_portal.items():
                    for url in portal_urls:
                        fut = ex.submit(_fetch_one, url, portal_name)
                        futures[fut] = url
                for fut in as_completed(futures):
                    try:
                        url, detail = fut.result()
                        detail_cache[url] = detail if detail else _FAILED
                    except Exception as e:
                        url = futures[fut]
                        logger.warning("detail fetch future failed for %s: %s", url, e)
                        detail_cache[url] = _FAILED

    def _scrape_one(
        self, portal_name: str, pconf: PortalConfig
    ) -> tuple[str, list[Ad], Optional[dict]]:
        """Scrape JEDNOHO portalu (bezi v samostatnem vlakne).

        Kazdy portal ma vlastni provider instanci + vlastni HttpClient
        (Session + throttle), takze mezi vlakny neni sdileny mutable stav.
        """
        from .http import HttpClient

        provider_cls = REGISTRY.get(portal_name)
        provider = provider_cls(
            http_client=HttpClient(request_delay=self.config.pipeline.request_delay)
        )
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

    @staticmethod
    def _validate_url(url: str, allowed: set[str]) -> bool:
        """SEC-001: Overi, ze URL patri do allowlist domen."""
        if not allowed:
            return True  # Prazdna allowlist = bez validace (testy).
        try:
            host = urlparse(url).hostname or ""
        except Exception:
            return False
        return any(host == d or host.endswith("." + d) for d in allowed)

    def _scrape_all(self) -> tuple[list[Ad], dict[str, dict], dict[str, int]]:
        pool: list[Ad] = []
        all_stats: dict[str, dict] = {}

        tasks = [
            (name, pconf)
            for name, pconf in self.config.portals.items()
            if pconf.enabled and REGISTRY.get(name)
        ]

        # SEC-001: Validace category URL proti allowlist.
        allowed = set(self.config.pipeline.url_allowlist)
        for name, pconf in tasks:
            for cat in pconf.categories:
                if not self._validate_url(cat.url, allowed):
                    logger.error(
                        "BLOCKED: category URL %r for portal %r is not in "
                        "allowed domains: %s",
                        cat.url,
                        name,
                        allowed,
                    )
                    raise ValueError(
                        f"Category URL {cat.url!r} for portal {name!r} "
                        f"not in allowed domains: {allowed}"
                    )

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
