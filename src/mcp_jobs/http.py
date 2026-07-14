from __future__ import annotations

from typing import Optional

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class HttpClient:
    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "cs,sk;q=0.9,en;q=0.8",
    }

    def __init__(
        self,
        headers: Optional[dict] = None,
        timeout: int = 30,
        retries: int = 3,
        backoff_factor: float = 0.5,
    ):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(headers or self.DEFAULT_HEADERS)

        retry_strategy = Retry(
            total=retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods={"GET"},
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def get_soup(self, url: str, parser: str = "html.parser") -> Optional[BeautifulSoup]:
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            return BeautifulSoup(resp.text, parser)
        except requests.RequestException:
            return None

    def get_text(self, url: str) -> Optional[str]:
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text
        except requests.RequestException:
            return None

    def is_url_alive(self, url: str) -> bool:
        try:
            resp = self.session.head(url, timeout=10, allow_redirects=True)
            return resp.ok
        except requests.RequestException:
            return False
