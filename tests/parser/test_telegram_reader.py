from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.news_parser.telegram_reader as tr
from app.models.base import SourceType
from app.news_parser.base import NewsItemData
from app.news_parser.telegram_reader import TelegramReader


@pytest.fixture(autouse=True)
def clear_entity_cache():
    tr._entity_cache.clear()
    yield
    tr._entity_cache.clear()


def _make_source(last_seen=100):
    src = MagicMock()
    src.type = SourceType.tg
    src.url = "@ai_channel"
    src.name = "AI Channel"
    src.last_seen_msg_id = last_seen
    return src


def _make_message(msg_id: int, text: str):
    return SimpleNamespace(
        id=msg_id,
        message=text,
        date=datetime(2026, 6, 8, 12, 0, tzinfo=UTC),
    )


def _make_fake_client(entity, messages):
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get_entity = AsyncMock(return_value=entity)
    client.get_messages = AsyncMock(return_value=messages)
    return client


def test_telegram_reader_incremental_resolve_and_min_id():
    entity = SimpleNamespace(id=555, title="AI Channel")
    messages = [_make_message(102, "newest"), _make_message(101, "older")]
    fake_client = _make_fake_client(entity, messages)
    src = _make_source(last_seen=100)

    with patch(
        "app.news_parser.telegram_reader._build_client", return_value=fake_client
    ):
        items = TelegramReader().fetch(src)

    # resolve once
    fake_client.get_entity.assert_awaited_once_with("@ai_channel")
    # incremental min_id read off the resolved entity
    _, kwargs = fake_client.get_messages.call_args
    assert kwargs["min_id"] == 100
    # entity may be passed positionally or as a keyword argument
    entity_kwarg = kwargs.get("entity")
    entity_posarg = (
        fake_client.get_messages.call_args.args[0]
        if fake_client.get_messages.call_args.args
        else None
    )
    assert entity_kwarg == entity or entity_posarg == entity

    assert len(items) == 2
    assert all(isinstance(i, NewsItemData) for i in items)
    titles = {i.title for i in items}
    assert "newest" in titles
    # last_seen_msg_id bumped to newest id
    assert src.last_seen_msg_id == 102
    assert items[0].published_at.tzinfo == UTC
    assert items[0].source == "AI Channel"


def test_telegram_reader_no_new_messages_keeps_last_seen():
    entity = SimpleNamespace(id=555, title="AI Channel")
    fake_client = _make_fake_client(entity, [])
    src = _make_source(last_seen=100)
    with patch(
        "app.news_parser.telegram_reader._build_client", return_value=fake_client
    ):
        items = TelegramReader().fetch(src)
    assert items == []
    assert src.last_seen_msg_id == 100


def test_telegram_reader_skips_empty_message_text():
    entity = SimpleNamespace(id=555, title="AI Channel")
    messages = [_make_message(103, "has text"), _make_message(104, "")]
    fake_client = _make_fake_client(entity, messages)
    src = _make_source(last_seen=100)
    with patch(
        "app.news_parser.telegram_reader._build_client", return_value=fake_client
    ):
        items = TelegramReader().fetch(src)
    assert len(items) == 1
    assert items[0].title == "has text"
    # last_seen still tracks newest message id even if it had no text
    assert src.last_seen_msg_id == 104
