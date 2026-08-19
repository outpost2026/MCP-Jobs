"""SEC-001 SSRF regresni testy: detail-fetch cesta musi respektovat url_allowlist.

Fix 2026-08-19 (audit #3): drive se validovala jen category URL v pipeline,
ad.url z scrapovane HTML prochazel do fetch_detail bez kontroly.
"""

from mcp_jobs.providers.base import BaseScraper, is_url_allowed


class _RecordingClient:
    """Fake HttpClient — zaznamenava, ktere URL by se realne stahly."""

    def __init__(self):
        self.fetched: list[str] = []

    def get_text(self, url: str) -> str | None:
        self.fetched.append(url)
        return "<html><body>ok</body></html>"


class _DummyScraper(BaseScraper):
    @property
    def name(self) -> str:
        return "dummy"

    def parse_listings(self, html_text: str, query: str = "") -> list:
        return []

    def scrape_all(self, url, max_pages=5, params=None):
        return []


def test_fetch_page_blocks_url_outside_allowlist():
    client = _RecordingClient()
    scraper = _DummyScraper(http_client=client, url_allowlist={"bazos.cz", "jobs.cz"})
    text = scraper._fetch_page("http://evil.example.com/phish")
    assert text is None
    assert client.fetched == []


def test_fetch_page_allows_subdomain_of_allowlist():
    client = _RecordingClient()
    scraper = _DummyScraper(http_client=client, url_allowlist={"bazos.cz"})
    text = scraper._fetch_page("https://www.bazos.cz/detail/123")
    assert text is not None
    assert client.fetched == ["https://www.bazos.cz/detail/123"]


def test_fetch_page_allowed_when_allowlist_empty():
    client = _RecordingClient()
    scraper = _DummyScraper(http_client=client, url_allowlist=set())
    text = scraper._fetch_page("http://anywhere.example.com/x")
    assert text is not None


def test_fetch_detail_blocks_outside_allowlist():
    from mcp_jobs.models import Ad

    client = _RecordingClient()

    class _DetailScraper(_DummyScraper):
        def fetch_detail(self, ad):
            return self._fetch_page(ad.url)

    detail_scraper = _DetailScraper(http_client=client, url_allowlist={"bazos.cz"})
    ad = Ad(title="x", url="http://169.254.169.254/latest/meta-data/", portal="dummy")
    assert detail_scraper.fetch_detail(ad) is None
    assert client.fetched == []


def test_is_url_allowed_exact_and_subdomain():
    allowed = {"bazos.cz"}
    assert is_url_allowed("https://bazos.cz/x", allowed)
    assert is_url_allowed("https://www.bazos.cz/x", allowed)
    assert is_url_allowed("https://sub.deep.bazos.cz/x", allowed)
    assert not is_url_allowed("https://evil-bazos.cz/x", allowed)
    assert not is_url_allowed("https://bazos.evil.cz/x", allowed)
    assert not is_url_allowed("https://localhost:5432/x", allowed)


def test_is_url_allowed_empty_allowlist_passes():
    assert is_url_allowed("http://localhost/x", set())
