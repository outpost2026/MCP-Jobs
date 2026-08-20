from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import ClassVar
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from ..models import Ad
from .base import BaseScraper

logger = logging.getLogger(__name__)


class JenpraceScraper(BaseScraper):
    BASE_URL = "https://www.jenprace.cz"

    # Potvrzeno dev console (2026-08-19): hlavní popis v div.offer-content
    # (sekce O nás / Co tě čeká / Co očekáváme / Co nabízíme).
    _DETAIL_BODY_SELECTORS: ClassVar[list[str]] = [
        "div.offer-content",
        "div.content",
    ]

    def fetch_detail(self, ad: Ad) -> str | None:
        """Fetch jenprace detail page: description + missing summary fields.

        Summary grid (items-box-cont) je server-rendered mimo .offer-content:
          company  -> [data-cy="company-value"]
          locality -> [data-cy="locality-detail-value"]
        Chybějící company/location se doplní do ad objektu (vzor bazos),
        aby se propsaly do DB (upsert_ads: company, location sloupce).
        """
        if not ad.url:
            return None

        text = self._fetch_page(ad.url)
        if not text:
            return None

        soup = BeautifulSoup(text, "html.parser")

        # Sumární pole z items-box gridu (jen pokud v listingu chyběla)
        if not ad.company:
            el = soup.select_one('[data-cy="company-value"] a')
            if el:
                ad.company = el.get_text(strip=True) or None
        if not ad.location:
            el = soup.select_one(
                '[data-cy="locality-detail-value"] a[href^="/nabidky/"]'
            )
            if el:
                ad.location = el.get_text(strip=True) or None

        # Popis nabídky (hlavní text)
        for sel in self._DETAIL_BODY_SELECTORS:
            el = soup.select_one(sel)
            if el:
                body = el.get_text(strip=True)
                if body:
                    return body
        return None

    @property
    def name(self) -> str:
        return "jenprace"

    def build_search_url(self, query: str) -> str:
        return f"{self.BASE_URL}/nabidky?q={quote_plus(query)}"

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

        cards = soup.select("article.item")
        skipped = 0
        for card in cards:
            try:
                title_el = card.select_one("span.offer-link")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)

                url = ""
                link = card.select_one('a.container-link[data-cy="offer-link-label"]')
                if link:
                    url = link.get("href", "")
                if url and not url.startswith("http"):
                    url = f"{self.BASE_URL}{url}"

                company = ""
                company_el = card.select_one("span.company .d-none.d-sm-inline")
                if company_el:
                    # Desktop/mobile duplikace + separator '|' — očistit
                    sep = company_el.select_one(".separator")
                    if sep:
                        sep.decompose()
                    company = company_el.get_text(strip=True)

                location = ""
                loc_el = card.select_one("span.locality .d-none.d-sm-inline")
                if loc_el:
                    location = loc_el.get_text(strip=True)

                salary = ""
                salary_el = card.select_one("li.offer-label.rewardLabel")
                if salary_el:
                    salary = salary_el.get_text(strip=True)

                date = ""
                date_el = card.select_one("div.date-offer-list")
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
