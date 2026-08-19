from mcp_jobs.models import Ad
from mcp_jobs.providers import ACTIVE_PORTALS
from mcp_jobs.providers.bazos import BazosScraper
from mcp_jobs.providers.jenprace import JenpraceScraper
from mcp_jobs.providers.jobs import JobsScraper
from mcp_jobs.providers.pracecz import PraceczScraper

BAZOS_HTML = """
<div class="inzeraty">
    <div class="inzeratynadpis">
        <h2 class="nadpis"><a href="/detail/123">Python Developer</a></h2>
        <span class="velikost10"> -TOP- [13.7.2026]</span>
    </div>
    <div class="popis">We need a Python developer for automation</div>
    <div class="inzeratycena">50000 Kč</div>
    <div class="inzeratylok">Praha</div>
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

JENPRACE_HTML = """
<article id="miw6dj" data-cy="offer-slug-kuryr-v-praze" data-ii="1" class="item with-top with-reward">
    <h2 class="h4">
        <a class="container-link d-none d-md-inline-block"
           href="https://www.jenprace.cz/nabidka/miw6dj/kuryr-v-praze-a-okoli"
           data-cy="offer-link-label">
            <span class="offer-link me-md-3">Kurýr v Praze a okolí</span>
        </a>
    </h2>
    <span class="company fw-medium d-inline" data-cy="offer-ownership-company">
        <span class="d-none d-sm-inline">DOFEK COMPANY s.r.o.<span class="separator mx-2 d-none d-sm-inline">|</span></span>
        <span class="d-inline d-sm-none">DOFEK COMPANY&hellip;<span class="separator mx-2 d-none d-sm-inline">|</span></span>
    </span>
    <span class="locality fw-medium me-3 d-inline" data-cy="offer-locality">
        <span class="d-none d-sm-inline">Praha</span>
        <span class="d-inline d-sm-none">Praha</span>
    </span>
    <ul>
        <li title="Mzda 50 000 - 90 000 Kc" class="offer-label rewardLabel text-nowrap"
            data-cy="offer-label-reward">50 000 - 90 000 Kc</li>
    </ul>
    <div class="date-offer-list fs-small fw-medium" data-cy="offer-date-created">dnesni</div>
</article>
"""


def test_bazos_parse_listings():
    scraper = BazosScraper()
    ads = scraper.parse_listings(BAZOS_HTML, "python")
    assert len(ads) == 1
    assert ads[0].title == "Python Developer"
    assert ads[0].url == "https://www.bazos.cz/detail/123"
    assert ads[0].date == "13.7.2026"
    assert ads[0].description == "We need a Python developer for automation"
    assert ads[0].price == "50000 Kč"
    assert ads[0].matched_keyword == "python"


def test_bazos_empty_html():
    scraper = BazosScraper()
    ads = scraper.parse_listings("<html></html>", "python")
    assert ads == []


def test_bazos_broken_selector_logs(caplog):
    """M4 fix: no cards found -> error log (layout change detection)."""
    import logging

    scraper = BazosScraper()
    ads = scraper.parse_listings('<div class="totally-different">x</div>', "python")
    assert ads == []
    assert any("0 cards" in r.message for r in caplog.records)
    assert caplog.records[-1].levelno == logging.ERROR


def test_bazos_no_results():
    scraper = BazosScraper()
    ads = scraper.parse_listings('<div class="inzeraty"></div>', "python")
    assert ads == []


def test_bazos_scrape_all_stops_on_empty():
    scraper = BazosScraper()
    ads = scraper.scrape_all("https://prace.bazos.cz/", max_pages=3)
    assert isinstance(ads, list)


def test_bazos_subdomain_url():
    scraper = BazosScraper()
    ads = scraper.parse_listings(
        BAZOS_HTML, "python", base_domain="https://prace.bazos.cz"
    )
    assert len(ads) == 1
    assert ads[0].url == "https://prace.bazos.cz/detail/123"


def test_bazos_extract_base():
    assert (
        BazosScraper._extract_base("https://prace.bazos.cz/")
        == "https://prace.bazos.cz"
    )
    assert BazosScraper._extract_base("https://www.bazos.cz/") == "https://www.bazos.cz"
    assert (
        BazosScraper._extract_base("https://prace.bazos.cz/brigada/")
        == "https://prace.bazos.cz"
    )


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


def test_jobs_broken_selector_logs(caplog):
    """M4 fix: no cards found -> error log."""
    import logging

    scraper = JobsScraper()
    ads = scraper.parse_listings('<div class="totally-different">x</div>', "python")
    assert ads == []
    assert any("0 cards" in r.message for r in caplog.records)
    assert caplog.records[-1].levelno == logging.ERROR


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


def test_pracecz_broken_selector_logs(caplog):
    """M4 fix: no cards found -> error log."""
    import logging

    scraper = PraceczScraper()
    ads = scraper.parse_listings('<div class="totally-different">x</div>', "java")
    assert ads == []
    assert any("0 cards" in r.message for r in caplog.records)
    assert caplog.records[-1].levelno == logging.ERROR


def test_pracecz_scrape_all_stops_on_empty():
    scraper = PraceczScraper()
    ads = scraper.scrape_all("https://www.prace.cz/nabidky/", max_pages=2)
    assert isinstance(ads, list)


def test_jenprace_parse_listings():
    scraper = JenpraceScraper()
    ads = scraper.parse_listings(JENPRACE_HTML, "kuryr")
    assert len(ads) == 1
    assert ads[0].title == "Kurýr v Praze a okolí"
    assert ads[0].url == "https://www.jenprace.cz/nabidka/miw6dj/kuryr-v-praze-a-okoli"
    assert ads[0].company == "DOFEK COMPANY s.r.o."
    assert ads[0].location == "Praha"
    assert ads[0].salary == "50 000 - 90 000 Kc"
    assert ads[0].date == "dnesni"
    assert ads[0].matched_keyword == "kuryr"


def test_jenprace_parse_listings_relative_url():
    """Jenprace pouziva absolutni href v listing, ale relativni musi byt taky OK."""
    html = JENPRACE_HTML.replace(
        "https://www.jenprace.cz/nabidka/miw6dj/kuryr-v-praze-a-okoli",
        "/nabidka/miw6dj/kuryr-v-praze-a-okoli",
    )
    scraper = JenpraceScraper()
    ads = scraper.parse_listings(html, "kuryr")
    assert ads[0].url == "https://www.jenprace.cz/nabidka/miw6dj/kuryr-v-praze-a-okoli"


def test_jenprace_parse_listings_without_salary():
    """Karta bez mzdy (without with-reward) — salary musi byt None."""
    html = JENPRACE_HTML.replace(
        '<li title="Mzda 50 000 - 90 000 Kc" class="offer-label rewardLabel text-nowrap"',
        '<li title="Typ pracovniho uvazku - Plny uvazek" class="offer-label employmentLabel text-nowrap"',
    ).replace(
        'data-cy="offer-label-reward">50 000 - 90 000 Kc</li>',
        'data-cy="offer-label-employment-1">Plný úvazek</li>',
    )
    scraper = JenpraceScraper()
    ads = scraper.parse_listings(html, "kuryr")
    assert len(ads) == 1
    assert ads[0].salary is None


def test_jenprace_empty_html():
    scraper = JenpraceScraper()
    ads = scraper.parse_listings("<html></html>", "kuryr")
    assert ads == []


def test_jenprace_broken_selector_logs(caplog):
    """M4 fix: no cards found -> error log (layout change detection)."""
    import logging

    scraper = JenpraceScraper()
    ads = scraper.parse_listings('<div class="totally-different">x</div>', "kuryr")
    assert ads == []
    assert any("0 cards" in r.message for r in caplog.records)
    assert caplog.records[-1].levelno == logging.ERROR


def test_jenprace_scrape_all_stops_on_empty():
    scraper = JenpraceScraper()
    ads = scraper.scrape_all("https://www.jenprace.cz/nabidky/praha/", max_pages=2)
    assert isinstance(ads, list)


def test_jenprace_fetch_detail_fills_company_and_location():
    """fetch_detail doplni company/location z items-box gridu (vzor bazos)."""
    detail_html = """
    <div class="row items-box-cont mt-3 pb-5 gy-3">
        <div class="col-md-6 d-flex align-items-start items-box-outer company-item">
            <div class="fs-small headline" data-cy="company-label">Firma</div>
            <div class="value" data-cy="company-value">
                <a href="/firmy/dofek-company-s-r-o">DOFEK COMPANY s.r.o.</a>
            </div>
        </div>
        <div class="col-md-6 d-flex align-items-start items-box-outer locality-detail-item">
            <div class="fs-small headline" data-cy="locality-detail-label">Lokalita</div>
            <div class="value" data-cy="locality-detail-value">
                <a href="/nabidky/praha">Praha</a>
                <a href="#map-frame" class="show-map-iframe fs-small fw-normal">Zobrazit na mapě</a>
            </div>
        </div>
    </div>
    <div class="container container-lg-max">
        <div class="content">
            <div class="offer-content">
                <h2 data-cy="offer-about-us-title">O nás</h2>
                <div data-cy="offer-about-us-value"><p>Rozvoz nákupů v Praze a okolí.</p></div>
            </div>
        </div>
    </div>
    """

    class _DetailClient:
        def get_text(self, url):
            return detail_html

    scraper = JenpraceScraper(http_client=_DetailClient())
    ad = Ad(title="Kurýr", url="https://www.jenprace.cz/nabidka/x/y", portal="jenprace")
    desc = scraper.fetch_detail(ad)
    assert desc is not None
    assert "Rozvoz" in desc
    assert ad.company == "DOFEK COMPANY s.r.o."
    assert ad.location == "Praha"


def test_active_portals_excludes_nyx():
    assert "nyx" not in ACTIVE_PORTALS
    assert "bazos" in ACTIVE_PORTALS
    assert "jobs" in ACTIVE_PORTALS
    assert "pracecz" in ACTIVE_PORTALS
    assert "jenprace" in ACTIVE_PORTALS
    assert len(ACTIVE_PORTALS) == 4


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
        title="Test",
        url="http://example.com",
        portal="jobs",
        company="Acme",
        location="Brno",
        salary="60000",
    )
    d = ad.to_dict()
    assert d["company"] == "Acme"
    assert d["location"] == "Brno"
    assert d["salary"] == "60000"
