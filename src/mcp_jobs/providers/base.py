from __future__ import annotations

import warnings
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from ..http import HttpClient
from ..models import Ad


class BaseScraper(ABC):
    def __init__(self, http_client: Optional[HttpClient] = None):
        self.http = http_client or HttpClient()

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def parse_listings(self, html_text: str, query: str = "") -> list[Ad]:
        ...

    @abstractmethod
    def scrape_all(self, url: str, max_pages: int = 5, params: dict[str, str] | None = None) -> list[Ad]:
        """Bulk scrape ALL listings from a category URL with pagination.
        
        Args:
            url: Base category URL.
            max_pages: Max pages to paginate through.
            params: Optional query parameters appended to every page URL.
                    Used by Bazos for location filter (hlokalita, humkreis).
                    Other providers ignore this parameter.
        """

    def build_search_url(self, query: str) -> str:
        raise NotImplementedError("build_search_url is deprecated, use scrape_all() instead")

    def scrape(self, query: str, max_results: int = 20) -> list[Ad]:
        warnings.warn(
            f"{type(self).__name__}.scrape() is deprecated, use scrape_all() + matches_ad()",
            DeprecationWarning, stacklevel=2,
        )
        url = self.build_search_url(query)
        text = self.http.get_text(url)
        if not text:
            return []
        ads = self.parse_listings(text, query)
        for ad in ads:
            ad.portal = self.name
            ad.scraped_at = datetime.now(timezone.utc).isoformat()
        return ads[:max_results]
