from __future__ import annotations

import logging
import time
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urlparse

from ..http import HttpClient
from ..models import Ad

logger = logging.getLogger(__name__)


def is_url_allowed(url: str, allowed: set[str]) -> bool:
    """SEC-001: Overi, ze URL patri do allowlist domen.

    Prazdna allowlist = bez validace (testy). Podporuje subdomeny
    (host == d nebo host konci na .d).
    """
    if not allowed:
        return True
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    return any(host == d or host.endswith("." + d) for d in allowed)


@dataclass
class ScraperRunStats:
    portal: str
    requests_ok: int = 0
    requests_failed: int = 0
    response_times_ms: list[float] = field(default_factory=list)
    field_failures: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def total_requests(self) -> int:
        return self.requests_ok + self.requests_failed

    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.requests_failed / self.total_requests

    @property
    def avg_response_time_ms(self) -> float:
        if not self.response_times_ms:
            return 0.0
        return sum(self.response_times_ms) / len(self.response_times_ms)

    def to_dict(self) -> dict:
        return {
            "portal": self.portal,
            "requests_ok": self.requests_ok,
            "requests_failed": self.requests_failed,
            "error_rate": round(self.error_rate, 3),
            "avg_response_time_ms": round(self.avg_response_time_ms, 1),
            "field_failures": dict(self.field_failures),
            "errors": list(self.errors),
        }


class BaseScraper(ABC):
    def __init__(
        self,
        http_client: HttpClient | None = None,
        url_allowlist: set[str] | None = None,
    ):
        self.http = http_client or HttpClient()
        self._url_allowlist: set[str] = url_allowlist or set()
        self.stats = ScraperRunStats(portal=self.name)

    def _fetch_page(self, url: str) -> str | None:
        # THREAD-SAFE: Kazde vlaskno ma vlastni provider + HttpClient instanci
        # (pipeline._scrape_one). Stats NENI sdilen mezi vlakny.
        if not is_url_allowed(url, self._url_allowlist):
            logger.warning(
                "BLOCKED: URL %r is not in allowed domains, fetch skipped", url
            )
            return None
        start = time.perf_counter()
        text = self.http.get_text(url)
        elapsed_ms = (time.perf_counter() - start) * 1000

        if text is not None:
            self.stats.requests_ok += 1
        else:
            self.stats.requests_failed += 1

        self.stats.response_times_ms.append(elapsed_ms)
        return text

    def _track_field_failure(self, field: str) -> None:
        self.stats.field_failures[field] = self.stats.field_failures.get(field, 0) + 1

    def fetch_detail(self, ad: Ad) -> str | None:
        """Fetch full ad detail page and extract body text (description).

        Implemented by providers whose detail pages are server-rendered
        (plain HTTP GET, no headless). Returns extracted text or None.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not implement fetch_detail"
        )

    def _fetch_detail_text(self, url: str, selectors: list[str]) -> str | None:
        """Shared helper: GET detail URL, first matching selector's text."""
        text = self._fetch_page(url)
        if not text:
            return None
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(text, "html.parser")
            for sel in selectors:
                el = soup.select_one(sel)
                if el:
                    body = el.get_text(strip=True)
                    if body:
                        return body
        except Exception as e:
            logger.warning("Detail parse failed for %s: %s", url, e)
            return None
        return None

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def parse_listings(
        self, html_text: str, query: str = "", page: int = 1
    ) -> list[Ad]: ...

    @abstractmethod
    def scrape_all(
        self, url: str, max_pages: int = 5, params: dict[str, str] | None = None
    ) -> list[Ad]:
        """Bulk scrape ALL listings from a category URL with pagination.

        Args:
            url: Base category URL.
            max_pages: Max pages to paginate through.
            params: Optional query parameters appended to every page URL.
                    Used by Bazos for location filter (hlokalita, humkreis).
                    Other providers ignore this parameter.
        """

    def build_search_url(self, query: str) -> str:
        raise NotImplementedError(
            "build_search_url is deprecated, use scrape_all() instead"
        )

    def scrape(self, query: str, max_results: int = 20) -> list[Ad]:
        warnings.warn(
            f"{type(self).__name__}.scrape() is deprecated, use scrape_all() + matches_ad()",
            DeprecationWarning,
            stacklevel=2,
        )
        url = self.build_search_url(query)
        text = self.http.get_text(url)
        if not text:
            return []
        ads = self.parse_listings(text, query)
        for ad in ads:
            ad.portal = self.name
            ad.scraped_at = datetime.now(UTC).isoformat()
        return ads[:max_results]
