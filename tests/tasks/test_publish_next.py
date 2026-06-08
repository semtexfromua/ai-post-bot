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


def _news(db) -> NewsItem:
    n = NewsItem(
        title="t",
        url="https://e/x",
        summary="s",
        source="src",
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
