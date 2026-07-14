from mcp_jobs.models import Ad
from mcp_jobs.pipeline import SearchPipeline, _location_filter, _salary_filter, _dedup


class FakeProvider:
    def __init__(self, ads: list[Ad]):
        self.ads = ads

    def scrape_all(self, url: str, max_pages: int = 5) -> list[Ad]:
        return self.ads


def test_location_filter_empty():
    ad = Ad(title="Test", url="http://x", portal="jobs", location="Brno")
    assert _location_filter(ad, []) is True
    assert _location_filter(ad, ["brno"]) is True


def test_location_filter_match():
    ad = Ad(title="Test", url="http://x", portal="jobs", location="Brno-město")
    assert _location_filter(ad, ["brno"]) is True


def test_location_filter_no_match():
    ad = Ad(title="Test", url="http://x", portal="jobs", location="Praha")
    assert _location_filter(ad, ["brno"]) is False


def test_salary_filter_empty():
    ad = Ad(title="Test", url="http://x", portal="jobs", salary=None)
    assert _salary_filter(ad, 0) is True
    assert _salary_filter(ad, 40000) is True


def test_salary_filter_match():
    ad = Ad(title="Test", url="http://x", portal="jobs", salary="50000 Kč")
    assert _salary_filter(ad, 40000) is True


def test_salary_filter_no_match():
    ad = Ad(title="Test", url="http://x", portal="jobs", salary="30000 Kč")
    assert _salary_filter(ad, 40000) is False


def test_unique_by_url():
    ads = [
        Ad(title="A", url="http://x/1", portal="jobs"),
        Ad(title="B", url="http://x/2", portal="jobs"),
        Ad(title="A dup", url="http://x/1", portal="jobs"),
    ]
    result = _dedup(ads)
    assert len(result) == 2
    assert result[0].title == "A"
    assert result[1].title == "B"


def test_unique_by_url_all_unique():
    ads = [
        Ad(title="A", url="http://x/1", portal="jobs"),
        Ad(title="B", url="http://x/2", portal="jobs"),
    ]
    result = _dedup(ads)
    assert len(result) == 2


def test_unique_by_url_empty():
    assert _dedup([]) == []


def test_salary_filter_thousand_separator():
    ad = Ad(title="Test", url="http://x", portal="jobs", salary="30 000 - 50 000 Kč")
    assert _salary_filter(ad, 40000) is True
    assert _salary_filter(ad, 60000) is False


def test_salary_filter_unparseable():
    ad = Ad(title="Test", url="http://x", portal="jobs", salary="Dohodou")
    assert _salary_filter(ad, 40000) is True


def test_dedup_normalized():
    ads = [
        Ad(title="CNC Programátor", url="http://x/1", portal="jobs", company="ABC s.r.o."),
        Ad(title="CNC Programátor", url="http://x/1", portal="jobs", company="ABC s.r.o."),
        Ad(title="  CNC Programátor  ", url="http://x/2", portal="jobs", company="  ABC S.R.O.  "),
    ]
    result = _dedup(ads)
    assert len(result) == 1
    assert result[0].url == "http://x/1"
