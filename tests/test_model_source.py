import uuid
from datetime import datetime, timezone

from app.models.base import SourceType
from app.models.source import Source


def test_create_source_row(db):
    src = Source(type=SourceType.tg, name="AI News", url="@ainews", enabled=True)
    db.add(src)
    db.commit()
    db.refresh(src)

    assert isinstance(src.id, uuid.UUID)
    assert src.type is SourceType.tg
    assert src.enabled is True
    assert src.last_seen_msg_id is None
    assert src.etag is None
    assert src.modified is None
    assert src.created_at.tzinfo is not None
    assert src.created_at.utcoffset() == timezone.utc.utcoffset(datetime.now())


def test_source_type_enum_round_trip(db):
    src = Source(type=SourceType.site, name="Blog", url="https://blog.example")
    db.add(src)
    db.commit()
    fetched = db.get(Source, src.id)
    assert fetched.type is SourceType.site


def test_source_enabled_defaults_true(db):
    src = Source(type=SourceType.site, name="Blog", url="https://blog.example")
    db.add(src)
    db.commit()
    db.refresh(src)
    assert src.enabled is True
