from mcp_jobs.models import Ad
from mcp_jobs.providers.bazos import BazosScraper
from mcp_jobs.providers.jobs import JobsScraper
from mcp_jobs.providers.pracecz import PraceczScraper
from mcp_jobs.providers.nyx import NyxScraper
from mcp_jobs.providers import ACTIVE_PORTALS


BAZOS_HTML = """
<div class="inzeraty">
    <h2 class="nadpis"><a href="/detail/123">Python Developer</a></h2>
    <div class="datum">2026-07-13</div>
    <div class="popis">We need a Python developer for automation</div>
    <div class="sub">Praha</div>
    <div class="cena">50000 Kč</div>
    <div class="kategorie"><a>IT</a></div>
</div>
"""

JOBS_HTML = """
<article class="SearchResultCard">
    <header class="SearchResultCard__header">
        <h2 class="SearchResultCard__title">
            <a class="link-primary SearchResultCard__titleLink" href="/rpd/123/">Python Engineer</a>
        </h2>
        <div class="SearchResultCard__status SearchResultCard__status--default">Aktualizováno včera</div>
    </header>
    <footer class="SearchResultCard__footer">
        <ul class="SearchResultCard__footerList">
            <li class="SearchResultCard__footerItem"><span translate="no">Acme Corp</span></li>
            <li class="SearchResultCard__footerItem" data-test="serp-locality"><span translate="no">Brno</span></li>
        </ul>
    </footer>
</article>
"""

PRACECZ_HTML = """
<article class="JobCard-module-scss-module__ki5xOq__JobCard" id="advert-456">
    <header class="JobCardHeader-module-scss-module__A6YY6q__JobCardHeader">
        <h2 class="JobCardTitle-module-scss-module__WnovSW__JobCardTitle" data-testid="job-card-title">
            <a class="link-primary link-allow-visited-style" data-testid="advert-link" href="/nabidka/123/">Java Developer</a>
        </h2>
    </header>
    <div class="JobCardBody-module-scss-module__V4L_zG__JobCardBody">
        <ul class="Flex Flex--wrap Flex--alignmentXLeft Flex--alignmentYBaseline Flex--Flex--column Flex--tablet--row">
            <li class="Flex Flex--noWrap">
                <span class="accessibility-hidden">Lokalita:</span>
                <span class="typography-body-medium-semibold text-wrap-pretty">Ostrava</span>
            </li>
            <li class="Flex Flex--noWrap">
                <span class="accessibility-hidden">Název firmy:</span>
                <span class="typography-body-medium-regular text-wrap-pretty">Tech s.r.o.</span>
            </li>
        </ul>
    </div>
    <ul data-testid="search-results-item-highlights-part-one"><li>55000 Kč</li></ul>
</article>
"""

NYX_HTML = """
<section class="market-item">
    <h2><a href="/discussion/789/">CNC fréza na prodej</a></h2>
    <div class="perex">Prodám CNC frézu, rok 2020</div>
    <div class="price">150000 Kč</div>
    <div class="date">2026-07-10</div>
</section>
"""


def test_bazos_parse_listings():
    scraper = BazosScraper()
    ads = scraper.parse_listings(BAZOS_HTML, "python")
    assert len(ads) == 1
    assert ads[0].title == "Python Developer"
    assert ads[0].url == "https://www.bazos.cz/detail/123"
    assert ads[0].date == "2026-07-13"
    assert ads[0].description == "We need a Python developer for automation"
    assert ads[0].price == "50000 Kč"
    assert ads[0].matched_keyword == "python"


def test_bazos_empty_html():
    scraper = BazosScraper()
    ads = scraper.parse_listings("<html></html>", "python")
    assert ads == []


def test_bazos_no_results():
    scraper = BazosScraper()
    ads = scraper.parse_listings('<div class="inzeraty"></div>', "python")
    assert ads == []


def test_bazos_scrape_all_stops_on_empty():
    scraper = BazosScraper()
    ads = scraper.scrape_all("https://prace.bazos.cz/", max_pages=3)
    assert isinstance(ads, list)


def test_jobs_parse_listings():
    scraper = JobsScraper()
    ads = scraper.parse_listings(JOBS_HTML, "python+engineer")
    assert len(ads) == 1
    assert ads[0].title == "Python Engineer"
    assert ads[0].url == "https://www.jobs.cz/rpd/123/"
    assert ads[0].company == "Acme Corp"
    assert ads[0].location == "Brno"
    assert ads[0].date == "včera"
    assert ads[0].matched_keyword == "python+engineer"


def test_jobs_empty_html():
    scraper = JobsScraper()
    ads = scraper.parse_listings("<html></html>", "python")
    assert ads == []


def test_jobs_scrape_all_stops_on_empty():
    scraper = JobsScraper()
    ads = scraper.scrape_all("https://www.jobs.cz/prace/informatika/", max_pages=2)
    assert isinstance(ads, list)


def test_pracecz_parse_listings():
    scraper = PraceczScraper()
    ads = scraper.parse_listings(PRACECZ_HTML, "java")
    assert len(ads) == 1
    assert ads[0].title == "Java Developer"
    assert ads[0].url == "https://www.prace.cz/nabidka/123/"
    assert ads[0].company == "Tech s.r.o."
    assert ads[0].location == "Ostrava"
    assert ads[0].salary is not None
    assert "55000" in ads[0].salary
    assert ads[0].matched_keyword == "java"


def test_pracecz_empty_html():
    scraper = PraceczScraper()
    ads = scraper.parse_listings("<html></html>", "java")
    assert ads == []


def test_pracecz_scrape_all_stops_on_empty():
    scraper = PraceczScraper()
    ads = scraper.scrape_all("https://www.prace.cz/nabidky/", max_pages=2)
    assert isinstance(ads, list)


def test_nyx_parse_listings():
    scraper = NyxScraper()
    ads = scraper.parse_listings(NYX_HTML, "cnc")
    assert len(ads) == 1
    assert ads[0].title == "CNC fréza na prodej"
    assert ads[0].url == "https://nyx.cz/discussion/789/"
    assert ads[0].price == "150000 Kč"
    assert ads[0].description == "Prodám CNC frézu, rok 2020"
    assert ads[0].date == "2026-07-10"
    assert ads[0].matched_keyword == "cnc"


def test_nyx_empty_html():
    scraper = NyxScraper()
    ads = scraper.parse_listings("<html></html>", "cnc")
    assert ads == []


def test_nyx_scrape_all_returns_empty():
    scraper = NyxScraper()
    ads = scraper.scrape_all("https://nyx.cz/")
    assert ads == []


def test_active_portals_excludes_nyx():
    assert "nyx" not in ACTIVE_PORTALS
    assert "bazos" in ACTIVE_PORTALS
    assert "jobs" in ACTIVE_PORTALS
    assert "pracecz" in ACTIVE_PORTALS
    assert len(ACTIVE_PORTALS) == 3


def test_ad_to_dict():
    ad = Ad(title="Test", url="http://example.com", portal="bazos")
    d = ad.to_dict()
    assert d["title"] == "Test"
    assert d["url"] == "http://example.com"
    assert d["portal"] == "bazos"
    assert "scraped_at" in d
    assert d.get("company") is None


def test_ad_to_dict_all_fields():
    ad = Ad(
        title="Test", url="http://example.com", portal="jobs",
        company="Acme", location="Brno", salary="60000",
    )
    d = ad.to_dict()
    assert d["company"] == "Acme"
    assert d["location"] == "Brno"
    assert d["salary"] == "60000"
