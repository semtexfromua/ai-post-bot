import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from aiogram.exceptions import TelegramForbiddenError

from app.models.base import ErrorStage, PostStatus
from app.models.error_log import ErrorLog
from app.models.news_item import NewsItem
from app.models.post import Post
from app.tasks import pipeline


@pytest.fixture
def generated_post(db):
    news = NewsItem(
        title="t",
        url="https://e.com/a",
        summary="s",
        source="src",
        published_at=datetime.now(UTC),
        raw_text="r",
        content_hash=uuid.uuid4().hex,
    )
    db.add(news)
    db.flush()
    post = Post(news_id=news.id, generated_text="ready text", status=PostStatus.generated)
    db.add(post)
    db.commit()
    return post


def _patch_session(db):
    """Make pipeline.SessionLocal() yield the test session (no real close)."""
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=db)
    cm.__exit__ = MagicMock(return_value=False)
    return patch.object(pipeline, "SessionLocal", return_value=cm)


def test_publish_post_publishes_generated(generated_post, db):
    with _patch_session(db), patch.object(
        pipeline.publisher, "publish", return_value=7777
    ) as pub:
        pipeline.publish_post.run(str(generated_post.id))

    pub.assert_called_once()
    db.refresh(generated_post)
    assert generated_post.status == PostStatus.published
    assert generated_post.tg_message_id == 7777


def test_publish_post_is_idempotent(generated_post, db):
    with _patch_session(db), patch.object(
        pipeline.publisher, "publish", return_value=7777
    ) as pub:
        pipeline.publish_post.run(str(generated_post.id))
        pipeline.publish_post.run(str(generated_post.id))  # second run = no-op

    pub.assert_called_once()  # published exactly once total
    db.refresh(generated_post)
    assert generated_post.status == PostStatus.published
    assert generated_post.tg_message_id == 7777


def test_publish_post_none_is_skip(db):
    with _patch_session(db), patch.object(pipeline.publisher, "publish") as pub:
        pipeline.publish_post.run(None)
    pub.assert_not_called()


def test_publish_post_forbidden_marks_failed_and_logs(generated_post, db):
    err = TelegramForbiddenError(method=MagicMock(), message="bot kicked")
    with _patch_session(db), patch.object(
        pipeline.publisher, "publish", side_effect=err
    ):
        pipeline.publish_post.run(str(generated_post.id))

    db.refresh(generated_post)
    assert generated_post.status == PostStatus.failed
    logs = db.query(ErrorLog).all()
    assert len(logs) == 1
    assert logs[0].stage == ErrorStage.publish
    assert logs[0].post_id == generated_post.id
