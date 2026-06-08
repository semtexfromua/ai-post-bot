from __future__ import annotations

import traceback
import uuid

import redis as redis_lib
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
    TelegramServerError,
)
from celery import chain
from sqlalchemy import select

from app.ai.generator import build_generator
from app.ai.moderation import is_flagged
from app.core.config import settings
from app.core.db import SessionLocal
from app.filter.service import passes_filters
from app.models.base import ErrorStage, PostStatus, SourceType
from app.models.keyword import Keyword
from app.models.news_item import NewsItem
from app.models.post import Post
from app.models.source import Source
from app.news_parser.factory import get_parser
from app.news_parser.hashing import content_hash
from app.tasks.celery_app import celery_app
from app.tasks.state import mark_failed, mark_generated, mark_published
from app.telegram import publisher

LOCK_KEY = "m4:lock:collect"
LOCK_TTL_SECONDS = 25 * 60  # < beat interval (30m), > a full cycle


def get_redis() -> redis_lib.Redis:
    return redis_lib.Redis.from_url(settings.REDIS_URL)


# backward-compat alias used by filter_item tests
_redis = get_redis


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


@celery_app.task(
    name="app.tasks.pipeline.publish_post",
    bind=True,
    autoretry_for=(TelegramRetryAfter, TelegramServerError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def publish_post(self, post_id: str | None) -> None:
    """Idempotent publish: only publishes a post with status==generated."""
    if post_id is None:
        return
    with SessionLocal() as db:
        post = db.get(Post, uuid.UUID(post_id))
        if post is None or post.status != PostStatus.generated:
            return  # idempotent: only publish a generated post
        try:
            message_id = publisher.publish(
                settings.TELEGRAM_CHANNEL_ID, post.generated_text
            )
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            mark_failed(
                db,
                post=post,
                stage=ErrorStage.publish,
                message=str(exc),
                tb=traceback.format_exc(),
            )
            db.commit()
            return
        mark_published(db, post, message_id)
        db.commit()


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


@celery_app.task(name="app.tasks.pipeline.collect_sources")
def collect_sources() -> None:
    """Orchestrator: acquire lock, then enqueue parse_source per enabled source.

    tg sources go to the `tg` queue (single-concurrency Telethon constraint);
    site/RSS sources go to the `default` queue.
    """
    r = get_redis()
    acquired = r.set(LOCK_KEY, "1", nx=True, ex=LOCK_TTL_SECONDS)
    if not acquired:
        return  # previous cycle still running
    with SessionLocal() as db:
        sources = db.scalars(select(Source).where(Source.enabled.is_(True))).all()
        for source in sources:
            queue = "tg" if source.type == SourceType.tg else "default"
            parse_source.apply_async((str(source.id),), queue=queue)
