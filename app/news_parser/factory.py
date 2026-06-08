from __future__ import annotations

from typing import TYPE_CHECKING

from app.models.base import SourceType
from app.news_parser.base import BaseParser
from app.news_parser.feed import FeedParser
from app.news_parser.site import SiteScraper
from app.news_parser.telegram_reader import TelegramReader

if TYPE_CHECKING:
    from app.models.source import Source

_FEED_HINTS = ("rss", "feed", "atom", ".xml")


def _looks_like_feed(url: str) -> bool:
    lowered = url.lower()
    return any(hint in lowered for hint in _FEED_HINTS)


def get_parser(source: Source) -> BaseParser:
    if source.type == SourceType.tg:
        return TelegramReader()
    if _looks_like_feed(source.url):
        return FeedParser()
    return SiteScraper()
