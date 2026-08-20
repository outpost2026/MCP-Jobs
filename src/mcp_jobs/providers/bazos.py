from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from urllib.parse import quote_plus, urlencode

from bs4 import BeautifulSoup

from ..models import Ad
from .base import BaseScraper

logger = logging.getLogger(__name__)

_DATE_RE = re.compile(r"\[(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})\]")


class BazosScraper(BaseScraper):
    BASE_URL = "https://www.bazos.cz"
    _SUBDOMAIN_RE = re.compile(r"(https?://[^/]+)")

    # DEV NOTE: Bazos neni pracovni portal — soukroma inzerce.
    # Company/seller info JEN z detailu, v contact linku s parametrem jmeno=
    # Priklad: <a href="hodnoceni.php?idmail=...&jmeno=www.masivnikuchyne.cz">www.masivnikuchyne.cz</a>
    _CONTACT_LINK_RE = re.compile(r"jmeno=([^&\"]+)")

    @property
    def name(self) -> str:
        return "bazos"

    def fetch_detail(self, ad: Ad) -> str | None:
        """Fetch bazos detail page for company/seller info.

        Bazos neni pracovni portal — company info neni v listing page.
        Jedinym zdrojem je contact link na detail strance s parametrem jmeno=.
        """
        if not ad.url:
            return None

        text = self._fetch_page(ad.url)
        if not text:
            return None

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(text, "html.parser")

            # Extract seller/company from contact link
            contact_links = soup.find_all("a", href=True)
            for link in contact_links:
                href = link.get("href", "")
                if "hodnoceni.php" in href or "idmail=" in href:
                    match = self._CONTACT_LINK_RE.search(href)
                    if match:
                        seller = match.group(1)
                        # URL decode
                        from urllib.parse import unquote

                        seller = unquote(seller)
                        if seller:
                            ad.company = seller
                            break

            # Extract description from detail page
            desc_selectors = [
                "div.inzeratydetail popis",  # bazos uses div.popis for description
                "div.popis",
                "div.inzeratydetail",
            ]
            for sel in desc_selectors:
                el = soup.select_one(sel)
                if el:
                    body = el.get_text(strip=True)
                    if body:
                        return body

            # Fallback: get all text from the ad detail div
            detail_div = soup.select_one("div.inzeratydetail")
            if detail_div:
                return detail_div.get_text(strip=True)

        except Exception as e:
            logger.warning("Bazos detail parse failed for %s: %s", ad.url, e)
            return None

        return None

    def build_search_url(self, query: str) -> str:
        return f"{self.BASE_URL}/search.php?hledat={quote_plus(query)}"

    @staticmethod
    def _extract_base(url: str) -> str:
        m = BazosScraper._SUBDOMAIN_RE.match(url)
        return m.group(1) if m else "https://www.bazos.cz"

    def scrape_all(
        self, url: str, max_pages: int = 10, params: dict[str, str] | None = None
    ) -> list[Ad]:
        all_ads: list[Ad] = []
        seen_urls: set[str] = set()
        query_suffix = ""
        if params:
            query_suffix = "?" + urlencode(params)
        base_domain = self._extract_base(url)

        for page in range(1, max_pages + 1):
            if page == 1:
                page_url = url
            else:
                offset = (page - 1) * 20
                page_url = f"{url.rstrip('/')}/{offset}/"
            if query_suffix:
                page_url += query_suffix

            text = self._fetch_page(page_url)
            if not text:
                break

            ads = self.parse_listings(text, "", base_domain, page)
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
        self,
        html_text: str,
        query: str = "",
        base_domain: str | None = None,
        page: int = 1,
    ) -> list[Ad]:
        soup = BeautifulSoup(html_text, "html.parser")
        ads: list[Ad] = []
        domain = base_domain or self.BASE_URL

        cards = soup.select("div.inzeraty")
        skipped = 0
        for card in cards:
            try:
                title_el = card.select_one("h2.nadpis a")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                raw_href = title_el.get("href", "")
                url = (
                    raw_href
                    if raw_href.startswith("http")
                    else f"{domain}/{raw_href.lstrip('/')}"
                )

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
