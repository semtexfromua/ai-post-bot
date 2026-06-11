from unittest.mock import MagicMock

from app.models.base import SourceType
from app.news_parser.factory import get_parser
from app.news_parser.feed import FeedParser
from app.news_parser.telegram_reader import TelegramReader


def _source(type_, url):
    src = MagicMock()
    src.type = type_
    src.url = url
    return src


def test_get_parser_tg_returns_telegram_reader():
    assert isinstance(get_parser(_source(SourceType.tg, "@chan")), TelegramReader)


def test_get_parser_site_returns_feed_parser_regardless_of_url_shape():
    # site sources are RSS/Atom feeds only — no HTML-scraper fallback
    for url in (
        "https://example.com/feed.xml",
        "https://example.com/rss",
        "https://example.com/article",
    ):
        assert isinstance(get_parser(_source(SourceType.site, url)), FeedParser)
