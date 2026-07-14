from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from ..models import Ad
from .base import BaseScraper


class JobsScraper(BaseScraper):
    BASE_URL = "https://www.jobs.cz"

    @property
    def name(self) -> str:
        return "jobs"

    def build_search_url(self, query: str) -> str:
        return f"{self.BASE_URL}/prace/?q={quote_plus(query)}"

    def scrape_all(self, url: str, max_pages: int = 10) -> list[Ad]:
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

        for card in soup.select("article.SearchResultCard"):
            try:
                title_el = card.select_one("a.SearchResultCard__titleLink")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                url = title_el.get("href", "")
                if url and not url.startswith("http"):
                    url = f"{self.BASE_URL}{url}"

                company = ""
                company_el = card.select_one(
                    ".SearchResultCard__footerItem span[translate='no'], "
                    ".SearchResultCard__footerItem"
                )
                if company_el:
                    company = company_el.get_text(strip=True)

                location = ""
                loc_el = card.select_one(
                    ".SearchResultCard__footerItem[data-test='serp-locality'], "
                    "li[data-test='serp-locality']"
                )
                if loc_el:
                    loc_span = loc_el.select_one("span:not(.accessibility-hidden), span")
                    location = loc_span.get_text(strip=True) if loc_span else loc_el.get_text(strip=True)

                date = ""
                date_el = card.select_one(".SearchResultCard__status")
                if date_el:
                    date_text = date_el.get_text(strip=True)
                    date = date_text.replace("Aktualizov\u00e1no ", "").strip()

                salary = ""
                salary_el = card.select_one(
                    "[class*='highlight'] li, "
                    "[class*='salary'], "
                    "[class*='price']"
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
                    date=date if date else None,
                    matched_keyword=query,
                )
                ads.append(ad)
            except Exception:
                continue

        return ads
