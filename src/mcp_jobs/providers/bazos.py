from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote_plus, urlencode

from bs4 import BeautifulSoup

from ..models import Ad
from .base import BaseScraper


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

        for card in soup.select("div.inzeraty"):
            try:
                title_el = card.select_one("h2.nadpis a")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                relative_url = title_el.get("href", "")
                url = relative_url if relative_url.startswith("http") else f"{self.BASE_URL}/{relative_url.lstrip('/')}"

                desc_el = card.select_one(".popis")
                description = desc_el.get_text(strip=True) if desc_el else ""

                date_el = card.select_one(".datum")
                date = date_el.get_text(strip=True) if date_el else ""

                location = ""
                price = ""
                for sub in card.select(".sub, .cena, .lokace"):
                    txt = sub.get_text(strip=True)
                    if "Kč" in txt or txt.replace(" ", "").replace(",", ".").replace("-", "").isdigit():
                        price = txt
                    elif txt and not txt.startswith("http"):
                        location = txt

                category_el = card.select_one(".kategorie a")
                category = category_el.get_text(strip=True) if category_el else ""

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
            except Exception:
                continue

        return ads
