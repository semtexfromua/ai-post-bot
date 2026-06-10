from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx
import structlog
import trafilatura
from selectolax.lexbor import LexborHTMLParser

from app.news_parser.base import BaseParser, NewsItemData
from app.news_parser.ssrf import UnsafeURLError, safe_get

if TYPE_CHECKING:
    from app.models.source import Source

logger = structlog.get_logger(__name__)

_TIMEOUT = 20.0


def _extract_title(tree: LexborHTMLParser) -> str:
    h1 = tree.css_first("article h1") or tree.css_first("h1")
    if h1 is not None:
        text = h1.text(strip=True)
        if text:
            return text
    title_node = tree.css_first("title")
    if title_node is not None:
        return title_node.text(strip=True)
    return ""


class SiteScraper(BaseParser):
    """HTML fallback parser: httpx GET + selectolax title + trafilatura body."""

    def fetch(self, source: Source) -> list[NewsItemData]:
        try:
            # safe_get re-validates every redirect hop (SSRF guard); a redirect to
            # an internal address is blocked before the request is made.
            response = safe_get(
                source.url,
                timeout=_TIMEOUT,
                headers={"User-Agent": "m4-news-bot/1.0"},
            )
        except UnsafeURLError as exc:
            logger.warning("site.blocked_url", url=source.url, error=str(exc))
            return []
        except httpx.HTTPError as exc:
            logger.warning("site.fetch_error", url=source.url, error=str(exc))
            return []

        if response.status_code != 200:
            logger.warning(
                "site.bad_status", url=source.url, status=response.status_code
            )
            return []

        html = response.text
        tree = LexborHTMLParser(html)
        title = _extract_title(tree)

        body = trafilatura.extract(html)
        if not body:
            logger.warning("site.no_content", url=source.url)
            return []

        return [
            NewsItemData(
                title=title,
                url=source.url,
                summary=None,
                source=source.name,
                published_at=datetime.now(UTC),
                raw_text=body,
            )
        ]
