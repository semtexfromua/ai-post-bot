from datetime import UTC, datetime
from unittest.mock import patch

import openai
import pytest
from celery.exceptions import MaxRetriesExceededError, Retry

from app.ai import moderation as moderation_module
from app.ai.schemas import PostDraft
from app.models.base import ErrorStage, PostStatus
from app.models.error_log import ErrorLog
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


def _persist_news(db) -> NewsItem:
    item = NewsItem(
        title="Уряд оголосив нові вибори",
        url="https://example.com/a",
        summary="Деталі.",
        source="Example",
        published_at=datetime.now(UTC),
        raw_text="Повний текст.",
        content_hash="h-gen",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


class _Gen:
    def __init__(self, draft):
        self._draft = draft

    def generate(self, news):
        return self._draft


def test_generate_post_creates_generated(db, monkeypatch):
    item = _persist_news(db)
    monkeypatch.setattr(pipeline, "SessionLocal", lambda: db_ctx(db))
    monkeypatch.setattr(
        pipeline,
        "build_generator",
        lambda: _Gen(PostDraft(text="🗳️ Нові вибори! Підписуйтесь.", language="uk")),
    )
    monkeypatch.setattr(pipeline, "is_flagged", lambda text: False)

    post_id = pipeline.generate_post.run(str(item.id))

    import uuid

    post = db.get(Post, uuid.UUID(post_id))
    assert post is not None
    assert post.status == PostStatus.generated
    assert post.generated_text


def test_generate_post_moderation_flag_marks_failed_and_logs(db, monkeypatch):
    item = _persist_news(db)
    monkeypatch.setattr(pipeline, "SessionLocal", lambda: db_ctx(db))
    monkeypatch.setattr(
        pipeline,
        "build_generator",
        lambda: _Gen(PostDraft(text="заборонений зміст", language="uk")),
    )
    monkeypatch.setattr(pipeline, "is_flagged", lambda text: True)

    post_id = pipeline.generate_post.run(str(item.id))

    import uuid

    post = db.get(Post, uuid.UUID(post_id))
    assert post.status == PostStatus.failed
    logs = (
        db.query(ErrorLog).filter_by(stage=ErrorStage.generate, news_id=item.id).all()
    )
    assert len(logs) == 1


def test_generate_post_none_input_skips(db, monkeypatch):
    monkeypatch.setattr(pipeline, "SessionLocal", lambda: db_ctx(db))
    assert pipeline.generate_post.run(None) is None


class _TransientRateLimit(openai.RateLimitError):
    """Minimal transient error: openai.RateLimitError needs args we don't want here."""

    def __init__(self):
        pass


class _RaisingGen:
    def __init__(self, exc):
        self._exc = exc

    def generate(self, news):
        raise self._exc


def test_generate_post_transient_openai_error_retries_without_creating_post(
    db, monkeypatch
):
    item = _persist_news(db)
    monkeypatch.setattr(pipeline, "SessionLocal", lambda: db_ctx(db))
    monkeypatch.setattr(
        pipeline, "build_generator", lambda: _RaisingGen(_TransientRateLimit())
    )

    # Patch the bound task's retry to capture the call and short-circuit the
    # eager retry loop with a Retry sentinel (matches "raise self.retry(...)").
    sentinel = Retry("retrying")
    with patch.object(
        pipeline.generate_post, "retry", side_effect=sentinel
    ) as mock_retry:
        with pytest.raises(Retry):
            pipeline.generate_post.run(str(item.id))

    mock_retry.assert_called_once()
    # transient error must escalate to retry, not create a Post (no duplicates)
    assert db.query(Post).count() == 0


def test_generate_post_retries_exhausted_marks_failed(db, monkeypatch):
    import uuid

    item = _persist_news(db)
    monkeypatch.setattr(pipeline, "SessionLocal", lambda: db_ctx(db))
    monkeypatch.setattr(
        pipeline, "build_generator", lambda: _RaisingGen(_TransientRateLimit())
    )
    monkeypatch.setattr(pipeline, "is_flagged", lambda text: False)

    # Simulate exhausted retries: retry raises MaxRetriesExceededError instead of Retry.
    with patch.object(
        pipeline.generate_post,
        "retry",
        side_effect=MaxRetriesExceededError(),
    ):
        post_id = pipeline.generate_post.run(str(item.id))

    assert post_id is not None
    post = db.get(Post, uuid.UUID(post_id))
    assert post is not None
    assert post.status == PostStatus.failed
    logs = (
        db.query(ErrorLog).filter_by(stage=ErrorStage.generate, news_id=item.id).all()
    )
    assert len(logs) == 1


def test_generate_post_nontransient_error_marks_failed_no_retry(db, monkeypatch):
    import uuid

    item = _persist_news(db)
    monkeypatch.setattr(pipeline, "SessionLocal", lambda: db_ctx(db))
    monkeypatch.setattr(
        pipeline, "build_generator", lambda: _RaisingGen(ValueError("boom"))
    )
    monkeypatch.setattr(pipeline, "is_flagged", lambda text: False)

    with patch.object(pipeline.generate_post, "retry") as mock_retry:
        post_id = pipeline.generate_post.run(str(item.id))

    mock_retry.assert_not_called()
    assert post_id is not None
    post = db.get(Post, uuid.UUID(post_id))
    assert post is not None
    assert post.status == PostStatus.failed
    logs = (
        db.query(ErrorLog).filter_by(stage=ErrorStage.generate, news_id=item.id).all()
    )
    assert len(logs) == 1


def test_generate_post_over_length_marks_failed(db, monkeypatch):
    import uuid

    from app.core.config import settings

    item = _persist_news(db)
    monkeypatch.setattr(pipeline, "SessionLocal", lambda: db_ctx(db))
    long_text = "а" * (settings.POST_MAX_LEN + 1)
    monkeypatch.setattr(
        pipeline,
        "build_generator",
        lambda: _Gen(PostDraft(text=long_text, language="uk")),
    )
    monkeypatch.setattr(pipeline, "is_flagged", lambda text: False)

    post_id = pipeline.generate_post.run(str(item.id))

    assert post_id is not None
    post = db.get(Post, uuid.UUID(post_id))
    assert post is not None
    assert post.status == PostStatus.failed
    logs = (
        db.query(ErrorLog).filter_by(stage=ErrorStage.generate, news_id=item.id).all()
    )
    assert len(logs) == 1


def test_is_flagged_skipped_in_fake_mode(monkeypatch):
    monkeypatch.setenv("USE_FAKE_AI", "1")
    with patch.object(moderation_module, "_client") as mock_client:
        result = moderation_module.is_flagged("anything goes here")
    mock_client.moderations.create.assert_not_called()
    assert result is False
