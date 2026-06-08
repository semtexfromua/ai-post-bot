from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from app.models.news_item import NewsItem
from app.models.source import Source
from app.news_parser.base import NewsItemData
from app.news_parser.hashing import content_hash
from app.tasks import pipeline


def _seed_source(db) -> Source:
    src = Source(type="site", name="Example", url="https://example.com/rss")
    db.add(src)
    db.commit()
    db.refresh(src)
    return src


def _news_data(title, url):
    return NewsItemData(
        title=title,
        url=url,
        summary="sum",
        source="Example",
        published_at=datetime(2026, 6, 8, tzinfo=UTC),
        raw_text="body",
    )


def test_parse_source_persists_new_items_and_enqueues_chain(db_session):
    src = _seed_source(db_session)
    fake_parser = MagicMock()
    fake_parser.fetch.return_value = [
        _news_data("First", "https://example.com/1"),
        _news_data("Second", "https://example.com/2"),
    ]

    with (
        patch.object(pipeline, "SessionLocal", return_value=db_session),
        patch.object(pipeline, "get_parser", return_value=fake_parser),
        patch.object(pipeline, "chain") as mock_chain,
        patch.object(pipeline, "filter_item"),
        patch.object(pipeline, "generate_post"),
        patch.object(pipeline, "publish_post"),
    ):
        pipeline.parse_source(str(src.id))

    rows = db_session.query(NewsItem).all()
    assert len(rows) == 2
    hashes = {r.content_hash for r in rows}
    assert content_hash("First", "https://example.com/1") in hashes
    assert content_hash("Second", "https://example.com/2") in hashes
    # one chain enqueued per new item
    assert mock_chain.call_count == 2
    assert mock_chain.return_value.delay.call_count == 2


def test_parse_source_is_noop_on_duplicate_content_hash(db_session):
    src = _seed_source(db_session)
    # pre-existing row with the same hash the parser will produce
    existing_hash = content_hash("First", "https://example.com/1")
    db_session.add(
        NewsItem(
            title="First",
            url="https://example.com/1",
            summary="sum",
            source="Example",
            published_at=datetime(2026, 6, 8, tzinfo=UTC),
            raw_text="body",
            content_hash=existing_hash,
        )
    )
    db_session.commit()

    fake_parser = MagicMock()
    fake_parser.fetch.return_value = [_news_data("First", "https://example.com/1")]

    with (
        patch.object(pipeline, "SessionLocal", return_value=db_session),
        patch.object(pipeline, "get_parser", return_value=fake_parser),
        patch.object(pipeline, "chain") as mock_chain,
        patch.object(pipeline, "filter_item"),
        patch.object(pipeline, "generate_post"),
        patch.object(pipeline, "publish_post"),
    ):
        pipeline.parse_source(str(src.id))

    rows = db_session.query(NewsItem).filter_by(content_hash=existing_hash).all()
    assert len(rows) == 1  # no duplicate inserted
    mock_chain.assert_not_called()  # no chain for the duplicate
