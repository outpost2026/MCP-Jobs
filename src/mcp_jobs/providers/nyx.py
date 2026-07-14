from __future__ import annotations

import re
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from ..models import Ad
from .base import BaseScraper


class NyxScraper(BaseScraper):
    """DEPRECATED: Nyx is not a job portal — requires authentication."""

    BASE_URL = "https://nyx.cz"

    @property
    def name(self) -> str:
        return "nyx"

    def build_search_url(self, query: str) -> str:
        return f"{self.BASE_URL}/?search={quote_plus(query)}&co=market"

    def scrape_all(self, url: str, max_pages: int = 5) -> list[Ad]:
        return []

    def parse_listings(self, html_text: str, query: str = "") -> list[Ad]:
        soup = BeautifulSoup(html_text, "html.parser")
        ads: list[Ad] = []

        for card in soup.select("section.market-item"):
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
            except Exception:
                continue

        return ads
