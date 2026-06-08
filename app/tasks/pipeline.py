from __future__ import annotations

import uuid

import redis as redis_lib
from celery import chain
from sqlalchemy import select

from app.ai.generator import build_generator
from app.ai.moderation import is_flagged
from app.core.config import settings
from app.core.db import SessionLocal
from app.filter.service import passes_filters
from app.models.base import ErrorStage, PostStatus
from app.models.keyword import Keyword
from app.models.news_item import NewsItem
from app.models.post import Post
from app.models.source import Source
from app.news_parser.factory import get_parser
from app.news_parser.hashing import content_hash
from app.tasks.celery_app import celery_app
from app.tasks.state import mark_failed, mark_generated


def _redis() -> redis_lib.Redis:
    return redis_lib.Redis.from_url(settings.REDIS_URL)


def _load_keywords(session) -> list[Keyword]:
    return list(session.execute(select(Keyword)).scalars().all())


@celery_app.task(name="app.tasks.pipeline.generate_post")
def generate_post(news_id: str | None) -> str | None:
    """Generate a post for a NewsItem.

    None input -> early return (chain stopped upstream).
    Happy path: generate -> moderation -> length guard -> Post(status=generated).
    On any failure: Post(status=failed) + ErrorLog(stage=generate). Returns post_id.
    """
    if news_id is None:
        return None

    with SessionLocal() as session:
        item = session.get(NewsItem, uuid.UUID(news_id))
        if item is None:
            return None

        # Explicitly set status=PostStatus.new so the NOT NULL constraint is satisfied.
        post = Post(news_id=item.id, generated_text="", status=PostStatus.new)
        session.add(post)
        session.flush()  # assign post.id for FK/ErrorLog wiring

        try:
            draft = build_generator().generate(item)
            text = draft.text
            if is_flagged(text):
                raise ValueError("moderation flagged generated text")
            if not text or len(text) > settings.POST_MAX_LEN:
                raise ValueError("generated text empty or exceeds POST_MAX_LEN")
            mark_generated(session, post, text)
        except Exception as exc:  # noqa: BLE001 — log every failure, never raise out
            mark_failed(
                session,
                post=post,
                stage=ErrorStage.generate,
                message=str(exc),
                news_id=item.id,
            )
        session.commit()
        return str(post.id)


@celery_app.task(name="app.tasks.pipeline.filter_item")
def filter_item(news_id: str) -> str | None:
    """Run filter gate. Returns news_id to continue the chain, or None to stop."""
    with SessionLocal() as session:
        item = session.get(NewsItem, uuid.UUID(news_id))
        if item is None:
            return None
        keywords = _load_keywords(session)
        ok = passes_filters(item, keywords, _redis(), settings)
        return news_id if ok else None


@celery_app.task(name="app.tasks.pipeline.publish_post")
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
