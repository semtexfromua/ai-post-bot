from unittest.mock import MagicMock, patch

import fakeredis
import pytest

from app.models.base import SourceType
from app.models.source import Source
from app.tasks import pipeline


@pytest.fixture
def mixed_sources(db):
    rows = [
        Source(type=SourceType.site, name="a", url="https://a.com/rss", enabled=True),
        Source(type=SourceType.tg, name="b", url="@b", enabled=True),
        Source(type=SourceType.site, name="c", url="https://c.com/rss", enabled=False),
    ]
    db.add_all(rows)
    db.commit()
    return rows


def _patch_session(db):
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=db)
    cm.__exit__ = MagicMock(return_value=False)
    return patch.object(pipeline, "SessionLocal", return_value=cm)


def test_collect_sources_locks_and_routes_per_type(mixed_sources, db):
    fake = fakeredis.FakeStrictRedis()
    with _patch_session(db), patch.object(
        pipeline, "get_redis", return_value=fake
    ), patch.object(pipeline.parse_source, "apply_async") as enq:
        pipeline.collect_sources.run()

    assert enq.call_count == 2  # only enabled sources
    routed = {c.args[0][0]: c.kwargs["queue"] for c in enq.call_args_list}
    by_id = {str(s.id): s for s in mixed_sources}
    assert set(routed) == {sid for sid, s in by_id.items() if s.enabled}
    for sid, queue in routed.items():
        expected = "tg" if by_id[sid].type == SourceType.tg else "default"
        assert queue == expected  # tg sources -> single-client tg queue


def test_collect_sources_noop_when_lock_held(mixed_sources, db):
    fake = fakeredis.FakeStrictRedis()
    fake.set("m4:lock:collect", "1", nx=True, ex=300)  # pre-acquire
    with _patch_session(db), patch.object(
        pipeline, "get_redis", return_value=fake
    ), patch.object(pipeline.parse_source, "apply_async") as enq:
        pipeline.collect_sources.run()

    enq.assert_not_called()  # lock held → no enqueue
