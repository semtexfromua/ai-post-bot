import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
    TelegramServerError,
)
from celery.exceptions import Retry

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
    post = Post(
        news_id=news.id, generated_text="ready text", status=PostStatus.generated
    )
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
    with (
        _patch_session(db),
        patch.object(pipeline.publisher, "publish", return_value=7777) as pub,
    ):
        pipeline.publish_post.run(str(generated_post.id))

    pub.assert_called_once()
    db.refresh(generated_post)
    assert generated_post.status == PostStatus.published
    assert generated_post.tg_message_id == 7777


def test_publish_post_is_idempotent(generated_post, db):
    with (
        _patch_session(db),
        patch.object(pipeline.publisher, "publish", return_value=7777) as pub,
    ):
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


def test_publish_post_retry_after_honors_cooldown(generated_post, db):
    """TelegramRetryAfter -> self.retry(countdown=retry_after)."""
    err = TelegramRetryAfter(method=MagicMock(), message="flood", retry_after=42)
    sentinel = Retry("retrying")
    with (
        _patch_session(db),
        patch.object(pipeline.publisher, "publish", side_effect=err),
        patch.object(
            pipeline.publish_post, "retry", side_effect=sentinel
        ) as mock_retry,
    ):
        with pytest.raises(Retry):
            pipeline.publish_post.run(str(generated_post.id))

    mock_retry.assert_called_once()
    assert mock_retry.call_args.kwargs["countdown"] == 42
    # transient flood control must not mark the post failed
    db.refresh(generated_post)
    assert generated_post.status == PostStatus.generated
    assert db.query(ErrorLog).count() == 0


def test_publish_post_forbidden_marks_failed_and_logs(generated_post, db):
    err = TelegramForbiddenError(method=MagicMock(), message="bot kicked")
    with (
        _patch_session(db),
        patch.object(pipeline.publisher, "publish", side_effect=err),
    ):
        pipeline.publish_post.run(str(generated_post.id))

    db.refresh(generated_post)
    assert generated_post.status == PostStatus.failed
    logs = db.query(ErrorLog).all()
    assert len(logs) == 1
    assert logs[0].stage == ErrorStage.publish
    assert logs[0].post_id == generated_post.id


def test_publish_post_already_has_tg_message_id_skips(generated_post, db):
    """Belt-and-suspenders: generated post with tg_message_id set must not re-publish."""
    generated_post.tg_message_id = 9999
    db.commit()

    with (
        _patch_session(db),
        patch.object(pipeline.publisher, "publish") as pub,
    ):
        pipeline.publish_post.run(str(generated_post.id))

    pub.assert_not_called()


def test_publish_post_server_error_retries(generated_post, db):
    """TelegramServerError -> self.retry is invoked; post stays generated; no ErrorLog."""
    err = TelegramServerError(method=MagicMock(), message="internal server error")
    sentinel = Retry("retrying")
    with (
        _patch_session(db),
        patch.object(pipeline.publisher, "publish", side_effect=err),
        patch.object(
            pipeline.publish_post, "retry", side_effect=sentinel
        ) as mock_retry,
    ):
        with pytest.raises(Retry):
            pipeline.publish_post.run(str(generated_post.id))

    mock_retry.assert_called_once()
    db.refresh(generated_post)
    assert generated_post.status == PostStatus.generated
    assert db.query(ErrorLog).count() == 0


def test_publish_post_server_error_exhausted_marks_failed(generated_post, db):
    """TelegramServerError at retry exhaustion -> Post(failed) + ErrorLog (spec §4.6)."""
    err = TelegramServerError(method=MagicMock(), message="internal server error")
    task = pipeline.publish_post
    with (
        _patch_session(db),
        patch.object(pipeline.publisher, "publish", side_effect=err),
    ):
        task.push_request(retries=task.max_retries)
        try:
            task.run(str(generated_post.id))
        finally:
            task.pop_request()

    db.refresh(generated_post)
    assert generated_post.status == PostStatus.failed
    logs = db.query(ErrorLog).filter_by(stage=ErrorStage.publish).all()
    assert len(logs) == 1
    assert logs[0].post_id == generated_post.id


def test_publish_post_retry_after_exhausted_marks_failed(generated_post, db):
    """TelegramRetryAfter at retry exhaustion -> Post(failed) + ErrorLog (spec §4.6)."""
    err = TelegramRetryAfter(method=MagicMock(), message="flood", retry_after=10)
    task = pipeline.publish_post
    with (
        _patch_session(db),
        patch.object(pipeline.publisher, "publish", side_effect=err),
    ):
        task.push_request(retries=task.max_retries)
        try:
            task.run(str(generated_post.id))
        finally:
            task.pop_request()

    db.refresh(generated_post)
    assert generated_post.status == PostStatus.failed
    assert db.query(ErrorLog).filter_by(stage=ErrorStage.publish).count() == 1


def test_publish_post_bad_request_marks_failed(generated_post, db):
    """TelegramBadRequest -> Post(status=failed) + ErrorLog(stage=publish); no retry."""
    err = TelegramBadRequest(method=MagicMock(), message="bad request")
    with (
        _patch_session(db),
        patch.object(pipeline.publisher, "publish", side_effect=err),
        patch.object(pipeline.publish_post, "retry") as mock_retry,
    ):
        pipeline.publish_post.run(str(generated_post.id))

    mock_retry.assert_not_called()
    db.refresh(generated_post)
    assert generated_post.status == PostStatus.failed
    logs = db.query(ErrorLog).all()
    assert len(logs) == 1
    assert logs[0].stage == ErrorStage.publish
