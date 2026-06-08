from __future__ import annotations

import asyncio
from datetime import UTC
from typing import TYPE_CHECKING

import structlog
from telethon import TelegramClient
from telethon.sessions import StringSession

from app.core.config import settings
from app.news_parser.base import BaseParser, NewsItemData

if TYPE_CHECKING:
    from app.models.source import Source

logger = structlog.get_logger(__name__)

# Resolved-entity cache: keep @username → entity across calls within a process
# so we never re-resolve every tick (FloodWait protection).
_entity_cache: dict[str, object] = {}


def _build_client() -> TelegramClient:
    return TelegramClient(
        StringSession(settings.TELETHON_STRING_SESSION.get_secret_value()),
        settings.TELEGRAM_API_ID,
        settings.TELEGRAM_API_HASH.get_secret_value(),
    )


def _title_from(text: str) -> str:
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    return first_line[:200]


async def _read(source: Source) -> list[NewsItemData]:
    client = _build_client()
    async with client:
        entity = _entity_cache.get(source.url)
        if entity is None:
            entity = await client.get_entity(source.url)
            _entity_cache[source.url] = entity

        messages = await client.get_messages(
            entity,
            min_id=source.last_seen_msg_id or 0,
            limit=100,
        )

    items: list[NewsItemData] = []
    max_id = source.last_seen_msg_id or 0
    for msg in messages:
        max_id = max(max_id, msg.id)
        text = (getattr(msg, "message", None) or "").strip()
        if not text:
            continue
        published_at = msg.date
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=UTC)
        items.append(
            NewsItemData(
                title=_title_from(text),
                url=None,
                summary=None,
                source=source.name,
                published_at=published_at,
                raw_text=text,
            )
        )

    if max_id > (source.last_seen_msg_id or 0):
        source.last_seen_msg_id = max_id
    return items


class TelegramReader(BaseParser):
    """Read-only incremental Telethon reader (resolve-once + cache, min_id)."""

    def fetch(self, source: Source) -> list[NewsItemData]:
        return asyncio.run(_read(source))
