from __future__ import annotations

import traceback
import uuid

import openai
import redis as redis_lib
import structlog
import structlog.contextvars
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
    TelegramServerError,
)
from celery import chain
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.ai.formatting import format_post
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

logger = structlog.get_logger(__name__)

LOCK_KEY = "m4:lock:collect"
# Crash-safety net only: collect_sources releases the lock explicitly in a finally
# block right after enqueuing. The TTL just frees the lock if the worker dies mid-run
# so a stuck key can't suppress every future cycle.
LOCK_TTL_SECONDS = 10 * 60

# Transient OpenAI failures worth retrying (rate-limit / network / 5xx); a retry
# must never duplicate a Post, hence generation runs before the Post is created.
_OPENAI_TRANSIENT = (
    openai.RateLimitError,
    openai.APITimeoutError,
    openai.APIConnectionError,
    openai.InternalServerError,
)


_redis_client: redis_lib.Redis | None = None


def get_redis() -> redis_lib.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis_lib.Redis.from_url(settings.REDIS_URL)
    return _redis_client


def _load_keywords(session) -> list[Keyword]:
    return list(session.execute(select(Keyword)).scalars().all())


def _source_enabled(session, source_name: str) -> bool:
    """Source filter (spec §4): an item is allowed unless its originating Source
    is currently disabled. NewsItem.source holds the Source.name (set by parsers).
    name is not unique, so drop only when matching rows exist AND all are disabled;
    an unmatched source (e.g. synthetic "manual" items) is always allowed.
    """
    matching = session.scalars(
        select(Source.enabled).where(Source.name == source_name)
    ).all()
    return (not matching) or any(matching)


@celery_app.task(bind=True, name="app.tasks.pipeline.generate_post", max_retries=5)
def generate_post(self, news_id: str | None) -> str | None:
    """Generate a post for a NewsItem.

    None input -> early return (chain stopped upstream).
    Generation runs BEFORE the Post row is created so a transient retry can never
    leave a duplicate Post behind. Transient OpenAI errors -> self.retry. A
    non-transient generation failure (e.g. refusal) or a moderation/length guard
    failure -> Post(status=failed) + ErrorLog(stage=generate). Returns post_id.
    """
    if news_id is None:
        return None

    structlog.contextvars.bind_contextvars(news_id=news_id)
    # Single-flight per news_id: worker-default runs at concurrency>1, so two tasks
    # for the same item (e.g. a double POST /generate) could both pass the idempotency
    # check below and create duplicate Posts. A short Redis lock collapses that window;
    # sequential redelivery stays covered by the in-DB idempotency check.
    gen_lock = f"m4:lock:gen:{news_id}"
    r = get_redis()
    if not r.set(gen_lock, "1", nx=True, ex=300):
        logger.info("generate.locked", news_id=news_id)
        return None
    try:
        return _generate_locked(self, news_id)
    finally:
        r.delete(gen_lock)


def _generate_locked(self, news_id: str) -> str | None:
    with SessionLocal() as session:
        item = session.get(NewsItem, uuid.UUID(news_id))
        if item is None:
            return None

        # 0) Idempotency: a redelivered task (acks_late worker loss after the Post
        # was committed but before the ack) must not create a second Post for the
        # same news_id. A prior non-failed Post -> no-op, return its id. This closes
        # the redelivery duplicate hole the way content_hash closes it for parsing.
        existing = session.scalar(
            select(Post).where(
                Post.news_id == item.id, Post.status != PostStatus.failed
            )
        )
        if existing is not None:
            return str(existing.id)

        # 1) Generate FIRST (no Post row yet) so a transient retry can't duplicate Posts.
        try:
            draft = build_generator().generate(item)
        except _OPENAI_TRANSIENT as exc:
            if self.request.retries >= (self.max_retries or 0):
                # retries exhausted -> record a failed Post + ErrorLog (audit trail)
                post = Post(news_id=item.id, generated_text="", status=PostStatus.new)
                session.add(post)
                session.flush()
                mark_failed(
                    session,
                    post=post,
                    stage=ErrorStage.generate,
                    message=f"OpenAI transient error, retries exhausted: {exc}",
                    tb=traceback.format_exc(),
                    news_id=item.id,
                )
                session.commit()
                logger.warning(
                    "generate.failed", news_id=news_id, reason="retries_exhausted"
                )
                return str(post.id)
            # Cap below the broker visibility_timeout (3600s) like publish_post, so a
            # large backoff can't let Redis redeliver this task mid-wait.
            raise self.retry(exc=exc, countdown=min(2**self.request.retries, 3000))
        except SoftTimeLimitExceeded:
            raise  # let Celery kill/retry the task; never a failed Post
        except Exception as exc:  # non-transient generation failure (e.g. refusal)
            post = Post(news_id=item.id, generated_text="", status=PostStatus.new)
            session.add(post)
            session.flush()
            mark_failed(
                session,
                post=post,
                stage=ErrorStage.generate,
                message=str(exc),
                tb=traceback.format_exc(),
                news_id=item.id,
            )
            session.commit()
            logger.warning("generate.failed", news_id=news_id, reason=str(exc))
            return str(post.id)

        # 2) Generation succeeded -> create the Post and run moderation/length guards.
        post = Post(news_id=item.id, generated_text="", status=PostStatus.new)
        session.add(post)
        session.flush()
        try:
            if is_flagged(draft.text):
                raise ValueError("moderation flagged generated text")
            # Build the final HTML payload (escaped body + source link + hashtags) and
            # guard ITS length — that's exactly what the publisher sends to Telegram.
            final_text = format_post(draft, item)
            if not draft.text.strip() or len(final_text) > settings.POST_MAX_LEN:
                raise ValueError("generated text empty or exceeds POST_MAX_LEN")
            mark_generated(session, post, final_text)
            logger.info("generate.ok", post_id=str(post.id), len=len(final_text))
        except SoftTimeLimitExceeded:
            raise  # let Celery kill/retry the task; never a failed Post
        except Exception as exc:  # noqa: BLE001 — log every failure, never raise out
            mark_failed(
                session,
                post=post,
                stage=ErrorStage.generate,
                message=str(exc),
                tb=traceback.format_exc(),
                news_id=item.id,
            )
            logger.warning("generate.failed", news_id=news_id, reason=str(exc))
        session.commit()
        return str(post.id)


@celery_app.task(name="app.tasks.pipeline.filter_item")
def filter_item(news_id: str) -> str | None:
    """Run filter gate. Returns news_id to continue the chain, or None to stop."""
    structlog.contextvars.bind_contextvars(news_id=news_id)
    with SessionLocal() as session:
        item = session.get(NewsItem, uuid.UUID(news_id))
        if item is None:
            return None
        keywords = _load_keywords(session)
        source_enabled = _source_enabled(session, item.source)
        ok = passes_filters(item, keywords, settings, source_enabled=source_enabled)
        if ok:
            logger.info("filter.passed", news_id=news_id)
        else:
            logger.info("filter.dropped", news_id=news_id)
        return news_id if ok else None


@celery_app.task(
    bind=True,
    name="app.tasks.pipeline.publish_post",
    max_retries=5,
)
def publish_post(self, post_id: str | None) -> None:
    """Idempotent publish: only publishes a post with status==generated.

    TelegramRetryAfter -> retry honoring Telegram's requested cooldown.
    TelegramServerError -> retry with exponential backoff.
    TelegramForbiddenError / TelegramBadRequest -> permanent failure, no retry.
    """
    if post_id is None:
        return
    structlog.contextvars.bind_contextvars(post_id=post_id)
    with SessionLocal() as db:
        post = db.get(Post, uuid.UUID(post_id))
        if post is None or post.status != PostStatus.generated:
            return  # idempotent: only publish a generated post
        if post.tg_message_id is not None:
            return  # belt-and-suspenders: already published, never re-send
        try:
            message_id = publisher.publish(
                settings.TELEGRAM_CHANNEL_ID, post.generated_text
            )
        except (TelegramRetryAfter, TelegramServerError) as exc:
            if self.request.retries >= (self.max_retries or 0):
                # retries exhausted -> mark failed + ErrorLog (spec §4 invariant 6),
                # symmetric with generate_post; never leave a post stuck in `generated`.
                mark_failed(
                    db,
                    post=post,
                    stage=ErrorStage.publish,
                    message=f"Telegram transient error, retries exhausted: {exc}",
                    tb=traceback.format_exc(),
                )
                db.commit()
                logger.warning(
                    "publish.failed", post_id=post_id, reason="retries_exhausted"
                )
                return
            countdown = (
                exc.retry_after
                if isinstance(exc, TelegramRetryAfter)
                else 2**self.request.retries
            )
            # Cap below the broker visibility_timeout (3600s, celery_app.py) so a
            # long Telegram flood-wait can't let Redis redeliver this task to
            # another consumer mid-wait and double-send.
            countdown = min(countdown, 3000)
            raise self.retry(countdown=countdown, exc=exc)
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            mark_failed(
                db,
                post=post,
                stage=ErrorStage.publish,
                message=str(exc),
                tb=traceback.format_exc(),
            )
            db.commit()
            logger.warning("publish.failed", post_id=post_id, error=str(exc))
            return
        mark_published(db, post, message_id)
        db.commit()
        logger.info("publish.ok", post_id=post_id, message_id=message_id)


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

        new_ids: list[str] = []
        try:
            parser = get_parser(source)
            items = parser.fetch(source)

            # Cap to the newest N so a huge feed (or a fresh-DB first run) can't
            # flood downstream generation/publishing.
            if len(items) > settings.MAX_ITEMS_PER_PARSE:
                items = sorted(items, key=lambda d: d.published_at, reverse=True)[
                    : settings.MAX_ITEMS_PER_PARSE
                ]

            for data in items:
                chash = content_hash(data.title, data.url)
                # Fast path: skip obvious duplicates without attempting an INSERT.
                exists = db.scalar(
                    select(NewsItem).where(NewsItem.content_hash == chash)
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
                try:
                    with db.begin_nested():  # SAVEPOINT — rolls back only this item
                        db.add(news)
                        db.flush()
                except IntegrityError:
                    continue  # concurrent duplicate — skip, keep the rest
                new_ids.append(str(news.id))

            # persist conditional-GET validators / last_seen_msg_id mutated by parser
            db.commit()
            logger.info(
                "parse_source.done",
                source_id=source_id,
                fetched=len(items),
                new=len(new_ids),
            )
        except SoftTimeLimitExceeded:
            raise  # let Celery kill the task; a timeout is not a parse failure
        except Exception as exc:  # noqa: BLE001 — one bad source must not crash the batch
            db.rollback()
            mark_failed(
                db,
                post=None,
                stage=ErrorStage.parse,
                source_id=source.id,
                message=str(exc),
                tb=traceback.format_exc(),
            )
            db.commit()
            logger.warning("parse_source.failed", source_id=source_id, error=str(exc))
            return

    # Filter + generate each new item into a pool of ready (status=generated) posts.
    # Publishing is decoupled: publish_next drips one post per scheduled tick so the
    # channel gets ~1 post per interval instead of a burst.
    for news_id in new_ids:
        chain(filter_item.s(news_id) | generate_post.s()).delay()


@celery_app.task(name="app.tasks.pipeline.publish_next")
def publish_next() -> None:
    """Drip publisher: enqueue exactly one ready post per tick. Picks from the
    source that has gone longest without being published (never-published sources
    first), then the newest ready item within that source. This rotates the channel
    across sources instead of letting the highest-volume feed dominate.
    """
    with SessionLocal() as db:
        last_published = (
            select(
                NewsItem.source.label("source"),
                func.max(Post.published_at).label("last_at"),
            )
            .join(Post, Post.news_id == NewsItem.id)
            .where(Post.status == PostStatus.published)
            .group_by(NewsItem.source)
            .subquery()
        )
        # Source gate, symmetric with filter_item/_source_enabled: never publish a
        # post whose source is currently disabled. An unmatched source (e.g. a
        # synthetic "manual" item with no Source row) stays allowed.
        src_enabled = (
            select(Source.id)
            .where(Source.name == NewsItem.source, Source.enabled.is_(True))
            .exists()
        )
        src_known = select(Source.id).where(Source.name == NewsItem.source).exists()
        post = db.scalars(
            select(Post)
            .join(NewsItem, NewsItem.id == Post.news_id)
            .outerjoin(last_published, last_published.c.source == NewsItem.source)
            .where(
                Post.status == PostStatus.generated,
                or_(src_enabled, ~src_known),
            )
            .order_by(
                last_published.c.last_at.asc().nulls_first(),
                Post.created_at.desc(),
            )
            .limit(1)
        ).first()
        post_id = str(post.id) if post is not None else None
    if post_id is None:
        logger.info("publish_next.idle")
        return
    publish_post.delay(post_id)
    logger.info("publish_next.queued", post_id=post_id)


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
    try:
        with SessionLocal() as db:
            sources = db.scalars(select(Source).where(Source.enabled.is_(True))).all()
            for source in sources:
                queue = "tg" if source.type == SourceType.tg else "default"
                parse_source.apply_async((str(source.id),), queue=queue)
    finally:
        # Release as soon as enqueuing is done — the lock guards only this brief
        # orchestration window, not the parse_source tasks it fans out.
        r.delete(LOCK_KEY)
