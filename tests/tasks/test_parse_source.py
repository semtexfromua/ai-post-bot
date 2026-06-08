import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from app.models.base import ErrorStage
from app.models.error_log import ErrorLog
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


def test_parse_source_unknown_source_id_is_noop(db_session):
    """source is None (random UUID) → returns without error and enqueues no chain."""
    with (
        patch.object(pipeline, "SessionLocal", return_value=db_session),
        patch.object(pipeline, "get_parser") as mock_get_parser,
        patch.object(pipeline, "chain") as mock_chain,
    ):
        pipeline.parse_source(str(uuid.uuid4()))

    mock_get_parser.assert_not_called()
    mock_chain.assert_not_called()


def test_parse_source_fetch_failure_logs_error_and_does_not_raise(db_session):
    """parser.fetch raises -> task does NOT raise; exactly one ErrorLog(stage=parse)."""
    src = _seed_source(db_session)
    fake_parser = MagicMock()
    fake_parser.fetch.side_effect = RuntimeError("boom")

    with (
        patch.object(pipeline, "SessionLocal", return_value=db_session),
        patch.object(pipeline, "get_parser", return_value=fake_parser),
        patch.object(pipeline, "chain") as mock_chain,
    ):
        pipeline.parse_source(str(src.id))  # must not raise

    logs = db_session.query(ErrorLog).filter_by(stage=ErrorStage.parse).all()
    assert len(logs) == 1
    assert logs[0].source_id == src.id
    assert "boom" in logs[0].message
    mock_chain.assert_not_called()


def test_parse_source_concurrent_dup_skipped_batch_not_lost(db_session):
    """A concurrent INSERT collision (fast-path missed) must not drop the whole batch.

    Simulates a race: the fast-path db.scalar sees None for the dup item (concurrent
    worker hasn't committed yet), but the SAVEPOINT flush hits a UNIQUE constraint.
    The dup is skipped; the new item is still persisted and the chain is enqueued once.
    """
    src = _seed_source(db_session)
    dup_hash = content_hash("Dup", "https://example.com/dup")
    # Pre-seed the duplicate so the DB has the constraint violation ready.
    db_session.add(
        NewsItem(
            title="Dup",
            url="https://example.com/dup",
            summary="sum",
            source="Example",
            published_at=datetime(2026, 6, 8, tzinfo=UTC),
            raw_text="body",
            content_hash=dup_hash,
        )
    )
    db_session.commit()

    new_hash = content_hash("New", "https://example.com/new")
    fake_parser = MagicMock()
    fake_parser.fetch.return_value = [
        _news_data("Dup", "https://example.com/dup"),  # will collide
        _news_data("New", "https://example.com/new"),  # genuinely new
    ]

    # Patch db.scalar to return None for both items (simulates race: fast-path misses
    # the pre-existing dup because the concurrent worker hadn't committed yet).
    def _scalar_race(stmt, **kw):
        # Always report "not found" so the fast-path never skips anything and every
        # item reaches the SAVEPOINT INSERT — the dup will then raise IntegrityError.
        return None

    with (
        patch.object(pipeline, "SessionLocal", return_value=db_session),
        patch.object(pipeline, "get_parser", return_value=fake_parser),
        patch.object(pipeline, "chain") as mock_chain,
        patch.object(pipeline, "filter_item"),
        patch.object(pipeline, "generate_post"),
        patch.object(pipeline, "publish_post"),
        patch.object(db_session, "scalar", side_effect=_scalar_race),
    ):
        pipeline.parse_source(str(src.id))

    # Only the new item was inserted (dup still has exactly one row).
    dup_rows = db_session.query(NewsItem).filter_by(content_hash=dup_hash).all()
    assert len(dup_rows) == 1

    new_rows = db_session.query(NewsItem).filter_by(content_hash=new_hash).all()
    assert len(new_rows) == 1  # new item persisted

    # Chain enqueued exactly once — for the new item, not the dup.
    assert mock_chain.call_count == 1
    assert mock_chain.return_value.delay.call_count == 1


def test_parse_source_disabled_source_is_noop(db_session):
    """source.enabled == False → no fetch and no chain enqueued."""
    src = Source(
        type="site", name="Disabled", url="https://example.com/disabled", enabled=False
    )
    db_session.add(src)
    db_session.commit()
    db_session.refresh(src)

    with (
        patch.object(pipeline, "SessionLocal", return_value=db_session),
        patch.object(pipeline, "get_parser") as mock_get_parser,
        patch.object(pipeline, "chain") as mock_chain,
    ):
        pipeline.parse_source(str(src.id))

    mock_get_parser.assert_not_called()
    mock_chain.assert_not_called()
