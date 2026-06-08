from datetime import UTC, datetime

import fakeredis

from app.models.news_item import NewsItem
from app.tasks import pipeline


def _persist_news(db, title: str, content_hash: str) -> NewsItem:
    item = NewsItem(
        title=title,
        url="https://example.com/a",
        summary=title,
        source="Example",
        published_at=datetime.now(UTC),
        raw_text=title,
        content_hash=content_hash,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def test_filter_item_passes_returns_news_id(db, monkeypatch):
    item = _persist_news(db, "Сьогодні відбулося багато виборів", "h-pass")
    monkeypatch.setattr(pipeline, "SessionLocal", lambda: db_ctx(db))
    monkeypatch.setattr(pipeline, "_redis", lambda: fakeredis.FakeStrictRedis())
    monkeypatch.setattr(pipeline, "_load_keywords", lambda s: [_FakeKw("вибори")])

    out = pipeline.filter_item.run(str(item.id))
    assert out == str(item.id)


def test_filter_item_dropped_returns_none(db, monkeypatch):
    item = _persist_news(db, "Сьогодні гарна погода в місті", "h-drop")
    monkeypatch.setattr(pipeline, "SessionLocal", lambda: db_ctx(db))
    monkeypatch.setattr(pipeline, "_redis", lambda: fakeredis.FakeStrictRedis())
    monkeypatch.setattr(pipeline, "_load_keywords", lambda s: [_FakeKw("вибори")])

    out = pipeline.filter_item.run(str(item.id))
    assert out is None


class _FakeKw:
    def __init__(self, word: str, lang: str | None = None):
        self.word = word
        self.lang = lang


class db_ctx:
    """Wrap a test Session so `with SessionLocal() as s:` yields it without closing."""

    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, *exc):
        return False
