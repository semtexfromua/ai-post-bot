from __future__ import annotations

from typing import TYPE_CHECKING

from app.models.base import SourceType
from app.news_parser.base import BaseParser
from app.news_parser.feed import FeedParser
from app.news_parser.telegram_reader import TelegramReader

if TYPE_CHECKING:
    from app.models.source import Source


def get_parser(source: Source) -> BaseParser:
    if source.type == SourceType.tg:
        return TelegramReader()
    return FeedParser()
