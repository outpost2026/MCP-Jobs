from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from ..models import Ad
from .base import BaseScraper


class PraceczScraper(BaseScraper):
    BASE_URL = "https://www.prace.cz"

    @property
    def name(self) -> str:
        return "pracecz"

    def build_search_url(self, query: str) -> str:
        return f"{self.BASE_URL}/nabidky/?q={quote_plus(query)}"

    def scrape_all(self, url: str, max_pages: int = 15) -> list[Ad]:
        all_ads: list[Ad] = []
        seen_urls: set[str] = set()
        connector = "&" if "?" in url else "?"

        for page in range(1, max_pages + 1):
            page_url = f"{url}{connector}page={page}"

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

        for card in soup.select("article[id^='advert-']"):
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

                ad = Ad(
                    title=title,
                    url=url,
                    portal=self.name,
                    company=company if company else None,
                    location=location if location else None,
                    salary=salary if salary else None,
                    matched_keyword=query,
                )
                ads.append(ad)
            except Exception:
                continue

        return ads
