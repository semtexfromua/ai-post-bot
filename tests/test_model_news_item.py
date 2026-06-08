import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.news_item import NewsItem


def _item(**kw):
    base = {
        "title": "Big AI release",
        "url": "https://example.com/a",
        "summary": "summary",
        "source": "Example",
        "published_at": datetime(2026, 6, 8, tzinfo=timezone.utc),
        "raw_text": "raw",
        "content_hash": "h1",
    }
    base.update(kw)
    return NewsItem(**base)


def test_create_news_item_row(db):
    item = _item()
    db.add(item)
    db.commit()
    db.refresh(item)
    assert isinstance(item.id, uuid.UUID)
    assert item.content_hash == "h1"
    assert item.created_at.tzinfo is not None


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
