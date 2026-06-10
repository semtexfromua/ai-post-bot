import socket
from datetime import UTC
from unittest.mock import MagicMock, patch

import httpx
import respx

from app.models.base import SourceType
from app.news_parser.base import NewsItemData
from app.news_parser.site import SiteScraper


def _fake_getaddrinfo(host, *a, **k):
    ip = {"example.com": "93.184.216.34"}.get(host, host)
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]


PAGE_HTML = """<!DOCTYPE html>
<html>
  <head><title>Breaking: AI does things</title></head>
  <body>
    <article>
      <h1>Breaking: AI does things</h1>
      <p>The full article body with several sentences of content here.</p>
    </article>
  </body>
</html>
"""


def _make_source():
    src = MagicMock()
    src.type = SourceType.site
    src.url = "https://example.com/article"
    src.name = "Example Site"
    return src


@respx.mock
def test_site_scraper_extracts_title_and_text():
    respx.get("https://example.com/article").mock(
        return_value=httpx.Response(200, text=PAGE_HTML)
    )
    src = _make_source()
    with patch(
        "app.news_parser.site.trafilatura.extract",
        return_value="The full article body with several sentences of content here.",
    ):
        items = SiteScraper().fetch(src)

    assert len(items) == 1
    item = items[0]
    assert isinstance(item, NewsItemData)
    assert item.title == "Breaking: AI does things"
    assert item.url == "https://example.com/article"
    assert item.source == "Example Site"
    assert "full article body" in item.raw_text
    assert item.published_at.tzinfo == UTC


@respx.mock
def test_site_scraper_empty_extraction_returns_empty_list():
    respx.get("https://example.com/article").mock(
        return_value=httpx.Response(200, text=PAGE_HTML)
    )
    src = _make_source()
    with patch("app.news_parser.site.trafilatura.extract", return_value=None):
        items = SiteScraper().fetch(src)
    assert items == []


@respx.mock
def test_site_scraper_non_200_returns_empty_list():
    respx.get("https://example.com/article").mock(return_value=httpx.Response(404))
    src = _make_source()
    with patch("app.news_parser.site.logger.warning") as mock_warn:
        items = SiteScraper().fetch(src)
    assert items == []
    assert mock_warn.called


@respx.mock
def test_site_scraper_blocks_redirect_to_internal(monkeypatch):
    """A source that 302-redirects to a link-local metadata address must be
    blocked: the internal address is never fetched and nothing is scraped."""
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)
    respx.get("https://example.com/article").mock(
        return_value=httpx.Response(
            302, headers={"Location": "http://169.254.169.254/latest/meta-data/"}
        )
    )
    internal = respx.get("http://169.254.169.254/latest/meta-data/").mock(
        return_value=httpx.Response(200, text="<html><h1>secret</h1></html>")
    )
    items = SiteScraper().fetch(_make_source())
    assert items == []
    assert not internal.called  # the internal address was never requested


@respx.mock
def test_site_scraper_connect_error_returns_empty_list():
    respx.get("https://example.com/article").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    src = _make_source()
    items = SiteScraper().fetch(src)
    assert items == []
