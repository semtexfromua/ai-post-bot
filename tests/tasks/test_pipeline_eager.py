import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from celery import chain

from app.ai.generator import FakeGenerator
from app.models.base import PostStatus
from app.models.news_item import NewsItem
from app.models.post import Post
from app.tasks import pipeline
from app.tasks.celery_app import celery_app


@pytest.fixture
def eager():
    prev = celery_app.conf.task_always_eager, celery_app.conf.task_eager_propagates
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield
    celery_app.conf.task_always_eager, celery_app.conf.task_eager_propagates = prev


@pytest.fixture
def news(db):
    item = NewsItem(
        title="OpenAI ships thing",
        url="https://e.com/openai",
        summary="A summary with the keyword python in it",
        source="src",
        published_at=datetime.now(UTC),
        raw_text="full text about python and ai",
        content_hash=uuid.uuid4().hex,
    )
    db.add(item)
    db.commit()
    return item


def _patch_session(db):
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=db)
    cm.__exit__ = MagicMock(return_value=False)
    return patch.object(pipeline, "SessionLocal", return_value=cm)


def test_eager_chain_news_to_published(eager, news, db):
    import fakeredis

    fake = fakeredis.FakeStrictRedis()

    with (
        _patch_session(db),
        patch.object(pipeline, "get_redis", return_value=fake),
        patch.object(pipeline, "passes_filters", return_value=True),
        patch.object(pipeline, "build_generator", return_value=FakeGenerator()),
        patch.object(pipeline, "is_flagged", return_value=False),
        patch.object(pipeline.publisher, "publish", return_value=5150) as pub,
    ):
        flow = chain(
            pipeline.filter_item.s(str(news.id)),
            pipeline.generate_post.s(),
            pipeline.publish_post.s(),
        )
        flow.apply()  # eager, in-process

    pub.assert_called_once()
    post = db.query(Post).filter(Post.news_id == news.id).one()
    assert post.status == PostStatus.published
    assert post.tg_message_id == 5150
    assert post.generated_text  # non-empty
