import inspect
from dataclasses import is_dataclass
from datetime import UTC, datetime

import pytest

from app.news_parser.base import BaseParser, NewsItemData


def test_news_item_data_is_dataclass_with_contract_fields():
    assert is_dataclass(NewsItemData)
    item = NewsItemData(
        title="Hello",
        url="https://example.com/a",
        summary="sum",
        source="Example",
        published_at=datetime(2026, 6, 8, tzinfo=UTC),
        raw_text="body",
    )
    assert item.title == "Hello"
    assert item.url == "https://example.com/a"
    assert item.summary == "sum"
    assert item.source == "Example"
    assert item.published_at.tzinfo is UTC
    assert item.raw_text == "body"


def test_news_item_data_allows_optional_none():
    item = NewsItemData(
        title="t",
        url=None,
        summary=None,
        source="src",
        published_at=datetime(2026, 6, 8, tzinfo=UTC),
        raw_text=None,
    )
    assert item.url is None
    assert item.summary is None
    assert item.raw_text is None


def test_base_parser_is_abstract():
    assert inspect.isabstract(BaseParser)
    with pytest.raises(TypeError):
        BaseParser()


def test_base_parser_fetch_signature():
    sig = inspect.signature(BaseParser.fetch)
    assert list(sig.parameters) == ["self", "source"]
