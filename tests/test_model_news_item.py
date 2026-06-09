import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError, StatementError

from app.models.news_item import NewsItem


def _item(**kw):
    base = {
        "title": "Big AI release",
        "url": "https://example.com/a",
        "summary": "summary",
        "source": "Example",
        "published_at": datetime(2026, 6, 8, tzinfo=UTC),
        "raw_text": "raw",
        "content_hash": "h1",
    }
    base.update(kw)
    return NewsItem(**base)


def test_create_news_item_row(db):
    original_dt = datetime(2026, 6, 8, tzinfo=UTC)
    item = _item(published_at=original_dt)
    db.add(item)
    db.commit()
    db.refresh(item)
    assert isinstance(item.id, uuid.UUID)
    assert item.content_hash == "h1"
    assert item.created_at.tzinfo is not None
    assert item.published_at.tzinfo is not None
    assert item.published_at == original_dt


def test_naive_published_at_raises(db):
    item = _item(published_at=datetime(2026, 6, 8), content_hash="naive-hash")
    db.add(item)
    with pytest.raises(StatementError) as exc_info:
        db.flush()
    assert isinstance(exc_info.value.orig, ValueError)
    assert "tz-aware" in str(exc_info.value.orig)


def test_news_item_optional_fields_nullable(db):
    item = _item(url=None, summary=None, raw_text=None, content_hash="h2")
    db.add(item)
    db.commit()
    db.refresh(item)
    assert item.url is None
    assert item.summary is None
    assert item.raw_text is None


def test_content_hash_unique_rejects_duplicate(db):
    db.add(_item(content_hash="dup"))
    db.commit()
    db.add(_item(url="https://example.com/b", content_hash="dup"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_news_item_has_search_indexes():
    # ORDER BY published_at (unfiltered list) and WHERE source + ORDER BY (filtered)
    names = {ix.name for ix in NewsItem.__table__.indexes}
    assert "ix_news_items_published_at" in names
    assert "ix_news_items_source_published_at" in names
