from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from ..models import Ad
from .base import BaseScraper

logger = logging.getLogger(__name__)


class NyxScraper(BaseScraper):
    """DEPRECATED: Nyx is not a job portal — requires authentication."""

    BASE_URL = "https://nyx.cz"

    @property
    def name(self) -> str:
        return "nyx"

    def build_search_url(self, query: str) -> str:
        return f"{self.BASE_URL}/?search={quote_plus(query)}&co=market"

    def scrape_all(self, url: str, max_pages: int = 5, params: dict[str, str] | None = None) -> list[Ad]:
        return []

    def parse_listings(self, html_text: str, query: str = "") -> list[Ad]:
        soup = BeautifulSoup(html_text, "html.parser")
        ads: list[Ad] = []

        cards = soup.select("section.market-item")
        skipped = 0
        for card in cards:
            try:
                title_el = card.select_one("h2 a[href^='/discussion/']")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                relative_url = title_el.get("href", "")
                url = f"{self.BASE_URL}{relative_url}" if relative_url.startswith("/") else relative_url

                desc_el = card.select_one(".content, .perex, p")
                description = desc_el.get_text(strip=True) if desc_el else ""

                price_el = card.select_one(".price, .cena, [class*=price]")
                price = price_el.get_text(strip=True) if price_el else None

                date_el = card.select_one("time, .date, [datetime]")
                date = date_el.get_text(strip=True) if date_el else None
                if not date and date_el and date_el.get("datetime"):
                    date = date_el["datetime"]

                ad = Ad(
                    title=title,
                    url=url,
                    portal=self.name,
                    description=description,
                    price=price,
                    date=date,
                    matched_keyword=query,
                )
                ads.append(ad)
            except Exception as e:
                skipped += 1
                logger.warning("%s: failed to parse card: %s", self.name, e)

        if cards and not ads:
            logger.error(
                "%s: found %d cards but parsed 0 ads — selector likely broken",
                self.name, len(cards))
        elif skipped:
            logger.info("%s: skipped %d/%d cards", self.name, skipped, len(cards))

        return ads
