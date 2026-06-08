from datetime import UTC, datetime

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
