from __future__ import annotations

import uuid

from celery import chain

from app.core.db import SessionLocal
from app.models.news_item import NewsItem
from app.models.source import Source
from app.news_parser.factory import get_parser
from app.news_parser.hashing import content_hash
from app.tasks.celery_app import celery_app


@celery_app.task
def generate_post(news_id: str | None) -> str | None:
    raise NotImplementedError  # implemented in the AI/generation phase


@celery_app.task
def filter_item(news_id: str) -> str | None:
    raise NotImplementedError  # stub — completed in the filter phase


@celery_app.task
def publish_post(post_id: str | None) -> None:
    raise NotImplementedError  # stub — completed in the publish phase


@celery_app.task(name="app.tasks.pipeline.parse_source")
def parse_source(source_id: str) -> None:
    """Fetch a source, persist new NewsItems (dedup by content_hash),
    and enqueue a per-item chain(filter_item | generate_post | publish_post)
    for each newly-inserted item. Duplicate content_hash is a no-op.
    """
    with SessionLocal() as db:
        source = db.get(Source, uuid.UUID(source_id))
        if source is None or not source.enabled:
            return

        parser = get_parser(source)
        items = parser.fetch(source)

        new_ids: list[str] = []
        for data in items:
            chash = content_hash(data.title, data.url)
            exists = (
                db.query(NewsItem).filter(NewsItem.content_hash == chash).first()
            )
            if exists is not None:
                continue
            news = NewsItem(
                title=data.title,
                url=data.url,
                summary=data.summary,
                source=data.source,
                published_at=data.published_at,
                raw_text=data.raw_text,
                content_hash=chash,
            )
            db.add(news)
            db.flush()
            new_ids.append(str(news.id))

        # persist conditional-GET validators / last_seen_msg_id mutated by parser
        db.commit()

    for news_id in new_ids:
        chain(filter_item.s(news_id) | generate_post.s() | publish_post.s()).delay()
