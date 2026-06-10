from __future__ import annotations

import calendar
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import feedparser
import httpx
import structlog

from app.news_parser.base import BaseParser, NewsItemData
from app.news_parser.ssrf import UnsafeURLError, safe_get

if TYPE_CHECKING:
    from app.models.source import Source

logger = structlog.get_logger(__name__)

_TIMEOUT = 20.0


def _struct_time_to_utc(parsed_time) -> datetime | None:
    if not parsed_time:
        return None
    # parsed_time is a time.struct_time in UTC (feedparser normalizes to GMT).
    return datetime.fromtimestamp(calendar.timegm(parsed_time), tz=UTC)


class FeedParser(BaseParser):
    """RSS/Atom parser via feedparser with conditional GET support."""

    def fetch(self, source: Source) -> list[NewsItemData]:
        # Fetch via safe_get (SSRF-safe: re-validates every redirect hop) instead
        # of letting feedparser resolve/redirect through urllib unchecked. Pass
        # conditional-GET validators as HTTP headers and parse the bytes locally.
        headers: dict[str, str] = {}
        if source.etag:
            headers["If-None-Match"] = source.etag
        if source.modified:
            headers["If-Modified-Since"] = source.modified
        try:
            response = safe_get(source.url, timeout=_TIMEOUT, headers=headers)
        except UnsafeURLError as exc:
            logger.warning("feed.blocked_url", url=source.url, error=str(exc))
            return []
        except httpx.HTTPError as exc:
            logger.warning("feed.fetch_error", url=source.url, error=str(exc))
            return []

        if response.status_code == 304:
            return []

        # Persist fresh conditional-GET validators back onto the source.
        new_etag = response.headers.get("ETag")
        if new_etag is not None:
            source.etag = new_etag
        new_modified = response.headers.get("Last-Modified")
        if new_modified is not None:
            source.modified = new_modified

        parsed = feedparser.parse(response.content)

        # Distinguish a malformed-but-readable feed from a down/unreadable one so
        # neither is silent: bozo + entries is a parse warning; bozo + no entries
        # is an unreachable/empty feed (otherwise it returns [] with no trace and
        # never surfaces in logs or /api/v1/errors).
        if getattr(parsed, "bozo", 0):
            event = "feed.bozo" if parsed.entries else "feed.unreachable_or_malformed"
            logger.warning(
                event,
                url=source.url,
                status=getattr(parsed, "status", None),
                error=str(getattr(parsed, "bozo_exception", "")),
            )

        items: list[NewsItemData] = []
        for entry in parsed.entries:
            # Atom entries often carry only <updated> (updated_parsed) and no
            # <published>; fall back to it before stamping the parse moment.
            published_at = _struct_time_to_utc(
                getattr(entry, "published_parsed", None)
                or getattr(entry, "updated_parsed", None)
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
