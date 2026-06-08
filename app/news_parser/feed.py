from __future__ import annotations

import calendar
import socket
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import feedparser
import structlog

from app.news_parser.base import BaseParser, NewsItemData

if TYPE_CHECKING:
    from app.models.source import Source

logger = structlog.get_logger(__name__)


def _struct_time_to_utc(parsed_time) -> datetime | None:
    if not parsed_time:
        return None
    # parsed_time is a time.struct_time in UTC (feedparser normalizes to GMT).
    return datetime.fromtimestamp(calendar.timegm(parsed_time), tz=UTC)


class FeedParser(BaseParser):
    """RSS/Atom parser via feedparser with conditional GET support."""

    def fetch(self, source: Source) -> list[NewsItemData]:
        _old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(20)
        try:
            parsed = feedparser.parse(
                source.url,
                etag=source.etag,
                modified=source.modified,
            )
        finally:
            socket.setdefaulttimeout(_old_timeout)

        if getattr(parsed, "status", None) == 304:
            return []

        # Persist fresh conditional-GET validators back onto the source.
        new_etag = getattr(parsed, "etag", None)
        if new_etag is not None:
            source.etag = new_etag
        new_modified = getattr(parsed, "modified", None)
        if new_modified is not None:
            source.modified = new_modified

        # Only warn about bozo when we actually received entries — an unreachable
        # host or network error has no entries and should not be mislabelled
        # "malformed feed".
        if getattr(parsed, "bozo", 0) and parsed.entries:
            logger.warning(
                "feed.bozo",
                url=source.url,
                error=str(getattr(parsed, "bozo_exception", "")),
            )

        items: list[NewsItemData] = []
        for entry in parsed.entries:
            published_at = _struct_time_to_utc(
                getattr(entry, "published_parsed", None)
            ) or datetime.now(UTC)
            items.append(
                NewsItemData(
                    title=getattr(entry, "title", "") or "",
                    url=getattr(entry, "link", None),
                    summary=getattr(entry, "summary", None),
                    source=source.name,
                    published_at=published_at,
                    raw_text=None,
                )
            )
        return items
