from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import ClassVar
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from ..models import Ad
from .base import BaseScraper

logger = logging.getLogger(__name__)


class ProfesiaScraper(BaseScraper):
    BASE_URL = "https://www.profesia.cz"

    # Potvrzeno dev console (2026-08-19): standardni detail ma
    # div.details[itemprop="description"]; manpowergroup varianta nema wrapper
    # a pouziva primo .details-desc (Popis pozice).
    _DETAIL_BODY_SELECTORS: ClassVar[list[str]] = [
        'div.details[itemprop="description"]',
        "div.details",
        ".details-section .details-desc",
    ]

    def fetch_detail(self, ad: Ad) -> str | None:
        if not ad.url:
            return None
        return self._fetch_detail_text(ad.url, self._DETAIL_BODY_SELECTORS)

    @property
    def name(self) -> str:
        return "profesia"

    def build_search_url(self, query: str) -> str:
        return f"{self.BASE_URL}/prace/?q={query}"

    def _clean_detail_url(self, href: str) -> str:
        """Profesia listing linky obsahuji session parametr search_id —
        odstranime ho, jinak se URL lisi mezi behy (duplicita v DB).
        """
        parts = urlsplit(href)
        qs = [(k, v) for k, v in parse_qsl(parts.query) if k != "search_id"]
        query = urlencode(qs) if qs else ""
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, query, parts.fragment)
        )

    def scrape_all(
        self, url: str, max_pages: int = 5, params: dict[str, str] | None = None
    ) -> list[Ad]:
        all_ads: list[Ad] = []
        seen_urls: set[str] = set()
        connector = "&" if "?" in url else "?"

        for page in range(1, max_pages + 1):
            if page == 1:
                page_url = url
            else:
                page_url = f"{url}{connector}page_num={page}"

            text = self._fetch_page(page_url)
            if not text:
                break

            ads = self.parse_listings(text, "")
            new = 0
            for ad in ads:
                if ad.url not in seen_urls:
                    seen_urls.add(ad.url)
                    all_ads.append(ad)
                    new += 1
            if new == 0:
                break

        now = datetime.now(UTC).isoformat()
        for ad in all_ads:
            ad.portal = self.name
            ad.scraped_at = now

        return all_ads

    def parse_listings(self, html_text: str, query: str = "") -> list[Ad]:
        soup = BeautifulSoup(html_text, "html.parser")
        ads: list[Ad] = []

        cards = soup.select("li.list-row")
        skipped = 0
        for card in cards:
            try:
                title_el = card.select_one("h2 a span.title")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)

                url = ""
                link = card.select_one("h2 a")
                if link:
                    href = link.get("href", "")
                    if href and not href.startswith("http"):
                        href = f"{self.BASE_URL}{href}"
                    url = self._clean_detail_url(href)

                company = ""
                company_el = card.select_one("span.employer")
                if company_el:
                    company = company_el.get_text(strip=True)

                location = ""
                loc_el = card.select_one("span.job-location")
                if loc_el:
                    location = loc_el.get_text(strip=True)

                salary = ""
                salary_el = card.select_one("span.label.label-bordered")
                if salary_el:
                    salary = salary_el.get_text(strip=True)

                date = ""
                date_el = card.select_one(".list-footer .info strong")
                if date_el:
                    date = date_el.get_text(strip=True)

                ad = Ad(
                    title=title,
                    url=url,
                    portal=self.name,
                    company=company or None,
                    location=location or None,
                    salary=salary or None,
                    date=date or None,
                    matched_keyword=query,
                )
                ads.append(ad)
            except Exception as e:
                skipped += 1
                logger.warning("%s: failed to parse card: %s", self.name, e)

        if not cards:
            logger.error(
                "%s: container selector returned 0 cards — likely broken (page layout change)",
                self.name,
            )
        elif cards and not ads:
            logger.error(
                "%s: found %d cards but parsed 0 ads — selector likely broken",
                self.name,
                len(cards),
            )
        elif skipped:
            logger.info("%s: skipped %d/%d cards", self.name, skipped, len(cards))

        return ads
