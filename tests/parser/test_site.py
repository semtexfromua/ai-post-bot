from datetime import UTC
from unittest.mock import MagicMock, patch

import httpx
import respx

from app.models.base import SourceType
from app.news_parser.base import NewsItemData
from app.news_parser.site import SiteScraper

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
    respx.get("https://example.com/article").mock(
        return_value=httpx.Response(404)
    )
    src = _make_source()
    with patch("app.news_parser.site.logger.warning") as mock_warn:
        items = SiteScraper().fetch(src)
    assert items == []
    assert mock_warn.called
