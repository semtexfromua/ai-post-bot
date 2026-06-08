from datetime import datetime, timezone

from app.schemas.base import APIModel
from app.schemas.common import Page


class _Sample(APIModel):
    name: str
    when: datetime


class _Obj:
    name = "abc"
    when = datetime(2026, 6, 8, tzinfo=timezone.utc)


def test_apimodel_reads_from_attributes():
    obj = _Obj()
    out = _Sample.model_validate(obj)
    assert out.name == "abc"
    assert out.when == datetime(2026, 6, 8, tzinfo=timezone.utc)


def test_page_generic_envelope():
    page = Page[_Sample](data=[_Sample(name="x", when=_Obj.when)], count=1)
    dumped = page.model_dump()
    assert dumped["count"] == 1
    assert dumped["data"][0]["name"] == "x"
