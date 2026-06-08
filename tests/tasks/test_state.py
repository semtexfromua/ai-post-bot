import uuid
from datetime import UTC, datetime

from app.models.base import ErrorStage, PostStatus
from app.models.error_log import ErrorLog
from app.models.news_item import NewsItem
from app.models.post import Post
from app.tasks import state


def _make_post(db) -> Post:
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
    post = Post(news_id=news.id, generated_text="", status=PostStatus.new)
    db.add(post)
    db.flush()
    return post


def test_mark_generated_sets_text_and_status(db):
    post = _make_post(db)
    state.mark_generated(db, post, "hello world")
    db.refresh(post)
    assert post.status == PostStatus.generated
    assert post.generated_text == "hello world"


def test_mark_published_sets_message_id_and_timestamp(db):
    post = _make_post(db)
    state.mark_generated(db, post, "hello")
    state.mark_published(db, post, 9988)
    db.refresh(post)
    assert post.status == PostStatus.published
    assert post.tg_message_id == 9988
    assert post.published_at is not None


def test_mark_failed_sets_status_and_writes_error_log(db):
    post = _make_post(db)
    state.mark_failed(
        db,
        post=post,
        stage=ErrorStage.publish,
        message="forbidden",
        tb="trace...",
        news_id=post.news_id,
    )
    db.refresh(post)
    assert post.status == PostStatus.failed
    assert post.error == "forbidden"

    logs = db.query(ErrorLog).all()
    assert len(logs) == 1
    assert logs[0].stage == ErrorStage.publish
    assert logs[0].message == "forbidden"
    assert logs[0].traceback == "trace..."
    assert logs[0].post_id == post.id
    assert logs[0].news_id == post.news_id


def test_mark_failed_without_post_only_logs(db):
    state.mark_failed(
        db,
        stage=ErrorStage.parse,
        message="parse boom",
        source_id=uuid.uuid4(),
    )
    logs = db.query(ErrorLog).all()
    assert len(logs) == 1
    assert logs[0].stage == ErrorStage.parse
    assert logs[0].post_id is None
