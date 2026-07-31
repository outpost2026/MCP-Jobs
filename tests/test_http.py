"""HTTP client tests — exception branches must log (C2 fix)."""

import logging

import requests

from mcp_jobs.http import HttpClient


class _ExplodingSession:
    """Fake session: raises RequestException on GET/HEAD."""

    def __init__(self):
        self.headers = {}

    def get(self, *args, **kwargs):
        raise requests.RequestException("boom")

    def head(self, *args, **kwargs):
        raise requests.RequestException("boom")


def test_get_text_logs_warning_on_exception(caplog):
    client = HttpClient(request_delay=0)
    client.session = _ExplodingSession()
    with caplog.at_level(logging.WARNING):
        result = client.get_text("http://example.com")
    assert result is None
    assert any("boom" in r.message for r in caplog.records)


def test_get_soup_logs_warning_on_exception(caplog):
    client = HttpClient(request_delay=0)
    client.session = _ExplodingSession()
    with caplog.at_level(logging.WARNING):
        result = client.get_soup("http://example.com")
    assert result is None
    assert any("boom" in r.message for r in caplog.records)


def test_is_url_alive_logs_warning_on_exception(caplog):
    client = HttpClient(request_delay=0)
    client.session = _ExplodingSession()
    with caplog.at_level(logging.WARNING):
        result = client.is_url_alive("http://example.com")
    assert result is False
    assert any("boom" in r.message for r in caplog.records)
