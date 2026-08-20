from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import ClassVar

from bs4 import BeautifulSoup

from ..http import HttpClient
from ..models import Ad
from .base import BaseScraper

logger = logging.getLogger(__name__)


class VolnamistaScraper(BaseScraper):
    BASE_URL = "https://www.volnamista.cz"

    # Potvrzeno dev console (2026-08-19): karty maji data-e2e="job-list-item-<id>",
    # title v a[data-e2e="detail-link"], firma v a[href^="/firma/"],
    # location+date v p oddelene en-dash, salary v .MuiChip-label.
    _CARD_SELECTOR = '[data-e2e^="job-list-item"]'
    _TITLE_SELECTOR = '[data-e2e="detail-link"]'
    _COMPANY_SELECTOR = 'a[href^="/firma/"]'
    _SALARY_SELECTOR = ".MuiChip-label"

    _JSONLD_SELECTOR: ClassVar[str] = 'script[type="application/ld+json"]'

    # Seznam.cz bot-detekce (provereno 2026-08-19): default HttpClient hlava
    # UA Chrome/120 + Accept hlavicku, coz vraci consent page misto obsahu.
    # Volnamista vyzaduje UA Chrome/126 BEZ Accept hlavicky (listing i detail).
    _SEZNAM_HEADERS: ClassVar[dict[str, str]] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/126.0 Safari/537.36"
        )
    }

    def __init__(
        self,
        http_client: HttpClient | None = None,
        url_allowlist: set[str] | None = None,
    ):
        super().__init__(http_client=http_client, url_allowlist=url_allowlist)
        # Pipeline/BaseScraper dodava default HttpClient (s Accept). Pro
        # volnamista jej prepiseme na Seznam-kompatibilni variantu. Mockeri
        # v testech (nemaji request_delay attr / nejsou HttpClient) se
        # respektuji, aby fetch_detail testy nezahltily sit.
        if http_client is None or isinstance(http_client, HttpClient):
            delay = getattr(http_client, "request_delay", 1.0) if http_client else 1.0
            self.http = HttpClient(
                request_delay=delay,
                headers=self._SEZNAM_HEADERS,
            )

    def fetch_detail(self, ad: Ad) -> str | None:
        if not ad.url:
            return None
        text = self.http.get_text(ad.url)
        if not text:
            return None
        return self._parse_detail_text(text)

    @staticmethod
    def _parse_detail_text(html_text: str) -> str | None:
        """Extrahej popis z detail stranky: primarne JSON-LD JobPosting,
        fallback __NEXT_DATA__ -> pageProps.jobAdvert.
        """
        try:
            soup = BeautifulSoup(html_text, "html.parser")
            for script in soup.select(VolnamistaScraper._JSONLD_SELECTOR):
                try:
                    data = json.loads(script.string or "")
                except (json.JSONDecodeError, TypeError):
                    continue
                if not isinstance(data, dict):
                    continue
                if data.get("@type") != "JobPosting":
                    continue
                desc = data.get("description")
                if isinstance(desc, str) and desc.strip():
                    return VolnamistaScraper._strip_html(desc)
            # Fallback: __NEXT_DATA__ -> pageProps.jobAdvert.description
            match = re.search(
                r'id="__NEXT_DATA__"[^>]*>\s*(\{.*?\})\s*</script>',
                html_text,
                re.DOTALL,
            )
            if match:
                try:
                    payload = json.loads(match.group(1))
                    job = (
                        payload.get("props", {})
                        .get("pageProps", {})
                        .get("jobAdvert", {})
                    )
                    desc = job.get("description_rich") or job.get("description")
                    if isinstance(desc, str) and desc.strip():
                        return VolnamistaScraper._strip_html(desc)
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.warning("Detail parse failed: %s", e)
            return None
        return None

    @staticmethod
    def _strip_html(html_text: str) -> str:
        return BeautifulSoup(html_text, "html.parser").get_text(" ", strip=True)

    @property
    def name(self) -> str:
        return "volnamista"

    def build_search_url(self, query: str) -> str:
        return f"{self.BASE_URL}/prace?q={query}"

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
                page_url = f"{url}{connector}strana={page}"

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

        cards = soup.select(self._CARD_SELECTOR)
        skipped = 0
        for card in cards:
            try:
                title_el = card.select_one(self._TITLE_SELECTOR)
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)

                url = ""
                href = title_el.get("href", "")
                if href:
                    if not href.startswith("http"):
                        href = f"{self.BASE_URL}{href}"
                    url = href

                company = ""
                company_el = card.select_one(self._COMPANY_SELECTOR)
                if company_el:
                    company = company_el.get_text(strip=True)

                location = ""
                date = ""
                loc_el = card.select_one("p")
                if loc_el:
                    parts = loc_el.get_text(strip=True).rsplit("\u2013", 1)
                    location = parts[0].strip()
                    if len(parts) == 2:
                        date = parts[1].strip()

                salary = ""
                salary_el = card.select_one(self._SALARY_SELECTOR)
                if salary_el:
                    salary = salary_el.get_text(strip=True).replace("\xa0", " ")

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
