from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import ClassVar
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from ..models import Ad
from .base import BaseScraper

logger = logging.getLogger(__name__)


class PraceczScraper(BaseScraper):
    BASE_URL = "https://www.prace.cz"

    # Potvrzeno dev console (2026-07-31): popis v CSS-module div
    # s hashed class, ale prefix 'RichContent' je stabilní.
    _DETAIL_BODY_SELECTORS: ClassVar[list[str]] = [
        '[class*="RichContent"]',
        "div.RichContent",
    ]

    def fetch_detail(self, ad: Ad) -> str | None:
        if not ad.url:
            return None
        return self._fetch_detail_text(ad.url, self._DETAIL_BODY_SELECTORS)

    @property
    def name(self) -> str:
        return "pracecz"

    def build_search_url(self, query: str) -> str:
        return f"{self.BASE_URL}/nabidky/?q={quote_plus(query)}"

    def scrape_all(
        self, url: str, max_pages: int = 15, params: dict[str, str] | None = None
    ) -> list[Ad]:
        all_ads: list[Ad] = []
        seen_urls: set[str] = set()
        connector = "&" if "?" in url else "?"

        for page in range(1, max_pages + 1):
            page_url = f"{url}{connector}page={page}"

            text = self._fetch_page(page_url)
            if not text:
                break

            ads = self.parse_listings(text, "", page)
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

    def parse_listings(
        self, html_text: str, query: str = "", page: int = 1
    ) -> list[Ad]:
        soup = BeautifulSoup(html_text, "html.parser")
        ads: list[Ad] = []

        cards = soup.select("article[id^='advert-']")
        skipped = 0
        for card in cards:
            try:
                title_el = card.select_one("a[data-testid='advert-link']")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                url = title_el.get("href", "")
                if url and not url.startswith("http"):
                    url = f"{self.BASE_URL}{url}"

                company = ""
                company_el = card.select_one(
                    "span.typography-body-medium-regular.text-wrap-pretty"
                )
                if company_el:
                    company = company_el.get_text(strip=True)

                location = ""
                loc_el = card.select_one(
                    "span.typography-body-medium-semibold.text-wrap-pretty"
                )
                if loc_el:
                    location = loc_el.get_text(strip=True)

                salary = ""
                salary_el = card.select_one(
                    "[data-testid='search-results-item-highlights-part-one'] li, "
                    "[data-testid='search-results-item-highlights-part-one']"
                )
                if salary_el:
                    salary = salary_el.get_text(strip=True)

                # DEV NOTE: prace.cz merge salary+date v jednom stringu
                # "Plat:50 000 - 70 000 Kč/měsícJen pár hodin"
                # Oddělujeme podle known date patterns
                date = ""
                if salary:
                    # Extract date from salary string (merged by portal)
                    date_match = re.search(
                        r"(Přidáno\s+)?(dnes|včera|před\s+\d+\s+\w+|"
                        r"Jen\s+pár\s+hodin|Dnešní|Zítra|Končí\s+za\s+\d+\s+\w+)",
                        salary,
                    )
                    if date_match:
                        date = date_match.group(0).strip()
                        salary = salary[: date_match.start()].strip()

                # Also extract date from dedicated date element
                if not date:
                    date_el = card.select_one("span.typography-body-small-regular")
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
            if page <= 1:
                logger.error(
                    "%s: container selector returned 0 cards — likely broken (page layout change)",
                    self.name,
                )
            else:
                logger.info(
                    "%s: 0 cards on page %d — end of listing reached, stopping",
                    self.name,
                    page,
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
