import uuid
from datetime import UTC, datetime
from unittest.mock import patch

from app.models.base import PostStatus
from app.models.news_item import NewsItem
from app.models.post import Post
from app.tasks import pipeline


class db_ctx:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, *exc):
        return False


def _news(db, source="src") -> NewsItem:
    n = NewsItem(
        title="t",
        url="https://e/x",
        summary="s",
        source=source,
        published_at=datetime.now(UTC),
        raw_text="r",
        content_hash=uuid.uuid4().hex,
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


def test_publish_next_enqueues_only_newest_generated(db, monkeypatch):
    n = _news(db)
    older = Post(
        news_id=n.id,
        generated_text="old",
        status=PostStatus.generated,
        created_at=datetime(2026, 6, 1, tzinfo=UTC),
    )
    newer = Post(
        news_id=n.id,
        generated_text="new",
        status=PostStatus.generated,
        created_at=datetime(2026, 6, 8, tzinfo=UTC),
    )
    db.add_all([older, newer])
    db.commit()
    monkeypatch.setattr(pipeline, "SessionLocal", lambda: db_ctx(db))

    with patch.object(pipeline.publish_post, "delay") as delay:
        pipeline.publish_next.run()

    delay.assert_called_once_with(str(newer.id))  # exactly one, the newest


def test_publish_next_rotates_to_least_recently_published_source(db, monkeypatch):
    # Source A was just published; source B has never been published.
    na = _news(db, source="A")
    nb = _news(db, source="B")
    db.add(
        Post(
            news_id=na.id,
            generated_text="pubA",
            status=PostStatus.published,
            published_at=datetime(2026, 6, 9, tzinfo=UTC),
        )
    )
    # A's ready post is NEWER than B's — pure recency would pick A.
    gen_a = Post(
        news_id=na.id,
        generated_text="genA",
        status=PostStatus.generated,
        created_at=datetime(2026, 6, 9, 12, tzinfo=UTC),
    )
    gen_b = Post(
        news_id=nb.id,
        generated_text="genB",
        status=PostStatus.generated,
        created_at=datetime(2026, 6, 9, 1, tzinfo=UTC),
    )
    db.add_all([gen_a, gen_b])
    db.commit()
    monkeypatch.setattr(pipeline, "SessionLocal", lambda: db_ctx(db))

    with patch.object(pipeline.publish_post, "delay") as delay:
        pipeline.publish_next.run()

    # B's source is idle longest (never published) → wins despite A's newer item.
    delay.assert_called_once_with(str(gen_b.id))


def test_publish_next_idle_when_no_generated(db, monkeypatch):
    n = _news(db)
    db.add_all(
        [
            Post(news_id=n.id, generated_text="p", status=PostStatus.published),
            Post(news_id=n.id, generated_text="x", status=PostStatus.new),
            Post(news_id=n.id, generated_text="f", status=PostStatus.failed),
        ]
    )
    db.commit()
    monkeypatch.setattr(pipeline, "SessionLocal", lambda: db_ctx(db))

    with patch.object(pipeline.publish_post, "delay") as delay:
        pipeline.publish_next.run()

    delay.assert_not_called()
