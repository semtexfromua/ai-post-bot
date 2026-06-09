from datetime import UTC, datetime

import fakeredis

from app.models.base import SourceType
from app.models.news_item import NewsItem
from app.models.source import Source
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


def _persist_source(db, *, name: str, enabled: bool, url: str) -> Source:
    src = Source(type=SourceType.site, name=name, url=url, enabled=enabled)
    db.add(src)
    db.commit()
    db.refresh(src)
    return src


def test_filter_item_passes_returns_news_id(db, monkeypatch):
    item = _persist_news(db, "Сьогодні відбулося багато виборів", "h-pass")
    monkeypatch.setattr(pipeline, "SessionLocal", lambda: db_ctx(db))
    monkeypatch.setattr(pipeline, "get_redis", lambda: fakeredis.FakeStrictRedis())
    monkeypatch.setattr(pipeline, "_load_keywords", lambda s: [_FakeKw("вибори")])

    out = pipeline.filter_item.run(str(item.id))
    assert out == str(item.id)


def test_filter_item_dropped_returns_none(db, monkeypatch):
    item = _persist_news(db, "Сьогодні гарна погода в місті", "h-drop")
    monkeypatch.setattr(pipeline, "SessionLocal", lambda: db_ctx(db))
    monkeypatch.setattr(pipeline, "get_redis", lambda: fakeredis.FakeStrictRedis())
    monkeypatch.setattr(pipeline, "_load_keywords", lambda s: [_FakeKw("вибори")])

    out = pipeline.filter_item.run(str(item.id))
    assert out is None


def test_filter_item_dropped_when_source_disabled(db, monkeypatch):
    # keyword matches, but the originating Source is disabled -> drop (spec §4 source filter)
    item = _persist_news(db, "Сьогодні відбулося багато виборів", "h-srcoff")
    _persist_source(db, name="Example", enabled=False, url="https://example.com/feed")
    monkeypatch.setattr(pipeline, "SessionLocal", lambda: db_ctx(db))
    monkeypatch.setattr(pipeline, "get_redis", lambda: fakeredis.FakeStrictRedis())
    monkeypatch.setattr(pipeline, "_load_keywords", lambda s: [_FakeKw("вибори")])

    out = pipeline.filter_item.run(str(item.id))
    assert out is None


def test_filter_item_passes_when_source_enabled(db, monkeypatch):
    item = _persist_news(db, "Сьогодні відбулося багато виборів", "h-srcon")
    _persist_source(db, name="Example", enabled=True, url="https://example.com/feed")
    monkeypatch.setattr(pipeline, "SessionLocal", lambda: db_ctx(db))
    monkeypatch.setattr(pipeline, "get_redis", lambda: fakeredis.FakeStrictRedis())
    monkeypatch.setattr(pipeline, "_load_keywords", lambda s: [_FakeKw("вибори")])

    out = pipeline.filter_item.run(str(item.id))
    assert out == str(item.id)


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
