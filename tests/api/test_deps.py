import uuid

import pytest
from fastapi import HTTPException

from app.api.v1.deps import Pagination, get_source_or_404
from app.models.base import SourceType
from app.models.source import Source


def test_pagination_defaults():
    p = Pagination()
    assert p.limit == 20
    assert p.offset == 0


def test_pagination_caps_limit():
    p = Pagination(limit=100, offset=5)
    assert p.limit == 100
    assert p.offset == 5


def test_get_source_or_404_found(db_session):
    src = Source(type=SourceType.site, name="N", url="https://x")
    db_session.add(src)
    db_session.commit()
    db_session.refresh(src)
    got = get_source_or_404(src.id, db_session)
    assert got.id == src.id


def test_get_source_or_404_missing(db_session):
    with pytest.raises(HTTPException) as exc:
        get_source_or_404(uuid.uuid4(), db_session)
    assert exc.value.status_code == 404
