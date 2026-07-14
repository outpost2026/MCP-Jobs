from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote_plus, urlencode

from bs4 import BeautifulSoup

from ..models import Ad
from .base import BaseScraper

logger = logging.getLogger(__name__)

_DATE_RE = re.compile(r"\[(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})\]")


class BazosScraper(BaseScraper):
    BASE_URL = "https://www.bazos.cz"

    @property
    def name(self) -> str:
        return "bazos"

    def build_search_url(self, query: str) -> str:
        return f"{self.BASE_URL}/search.php?hledat={quote_plus(query)}"

    def scrape_all(self, url: str, max_pages: int = 10, params: dict[str, str] | None = None) -> list[Ad]:
        all_ads: list[Ad] = []
        seen_urls: set[str] = set()
        query_suffix = ""
        if params:
            query_suffix = "?" + urlencode(params)

        for page in range(1, max_pages + 1):
            if page == 1:
                page_url = url
            else:
                offset = (page - 1) * 20
                page_url = f"{url.rstrip('/')}/{offset}/"
            if query_suffix:
                page_url += query_suffix

            text = self.http.get_text(page_url)
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

        now = datetime.now(timezone.utc).isoformat()
        for ad in all_ads:
            ad.portal = self.name
            ad.scraped_at = now

        return all_ads

    def parse_listings(self, html_text: str, query: str = "") -> list[Ad]:
        soup = BeautifulSoup(html_text, "html.parser")
        ads: list[Ad] = []

        cards = soup.select("div.inzeraty")
        skipped = 0
        for card in cards:
            try:
                title_el = card.select_one("h2.nadpis a")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                relative_url = title_el.get("href", "")
                url = relative_url if relative_url.startswith("http") else f"{self.BASE_URL}/{relative_url.lstrip('/')}"

                desc_el = card.select_one(".popis")
                description = desc_el.get_text(strip=True) if desc_el else ""

                date = ""
                date_el = card.select_one("span.velikost10")
                if date_el:
                    m = _DATE_RE.search(date_el.get_text())
                    if m:
                        date = f"{m.group(1)}.{m.group(2)}.{m.group(3)}"

                price_el = card.select_one(".inzeratycena")
                price = price_el.get_text(strip=True) if price_el else ""

                loc_el = card.select_one(".inzeratylok")
                location = loc_el.get_text(strip=True) if loc_el else ""

                category = ""

                ad = Ad(
                    title=title,
                    url=url,
                    portal=self.name,
                    date=date,
                    location=location,
                    price=price,
                    description=description,
                    category_name=category,
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
