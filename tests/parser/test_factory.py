from unittest.mock import MagicMock

from app.models.base import SourceType
from app.news_parser.factory import get_parser
from app.news_parser.feed import FeedParser
from app.news_parser.site import SiteScraper
from app.news_parser.telegram_reader import TelegramReader


def _source(type_, url):
    src = MagicMock()
    src.type = type_
    src.url = url
    return src


def test_get_parser_tg_returns_telegram_reader():
    assert isinstance(get_parser(_source(SourceType.tg, "@chan")), TelegramReader)


def test_get_parser_site_feed_url_returns_feed_parser():
    assert isinstance(
        get_parser(_source(SourceType.site, "https://example.com/feed.xml")),
        FeedParser,
    )
    assert isinstance(
        get_parser(_source(SourceType.site, "https://example.com/rss")),
        FeedParser,
    )


def test_get_parser_site_plain_url_returns_site_scraper():
    assert isinstance(
        get_parser(_source(SourceType.site, "https://example.com/article")),
        SiteScraper,
    )
