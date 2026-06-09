import uuid
from datetime import UTC, datetime, timedelta

from app.models.news_item import NewsItem


def _seed_news(db, *, source="src", published_at=None):
    news = NewsItem(
        title="T",
        url="https://n",
        summary="s",
        source=source,
        published_at=published_at or datetime.now(UTC),
        raw_text="r",
        content_hash=uuid.uuid4().hex,
    )
    db.add(news)
    db.commit()
    db.refresh(news)
    return news


def test_list_news_envelope(client, db_session):
    for _ in range(3):
        _seed_news(db_session)

    resp = client.get("/api/v1/news")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"data", "count"}
    assert body["count"] == 3
    assert len(body["data"]) == 3
    assert {"id", "title", "source", "published_at"} <= set(body["data"][0])


def test_list_news_source_filter(client, db_session):
    _seed_news(db_session, source="a")
    _seed_news(db_session, source="b")

    resp = client.get("/api/v1/news", params={"source": "a"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["data"][0]["source"] == "a"


def test_list_news_orders_newest_published_first(client, db_session):
    now = datetime.now(UTC)
    _seed_news(db_session, source="old", published_at=now - timedelta(days=1))
    _seed_news(db_session, source="new", published_at=now)

    body = client.get("/api/v1/news").json()
    assert body["data"][0]["source"] == "new"


def test_list_news_pagination_limit_offset(client, db_session):
    for _ in range(5):
        _seed_news(db_session)

    body = client.get("/api/v1/news", params={"limit": 2, "offset": 0}).json()
    assert body["count"] == 5
    assert len(body["data"]) == 2


def test_list_news_limit_over_cap_422(client):
    resp = client.get("/api/v1/news", params={"limit": 1000})
    assert resp.status_code == 422


def test_list_news_stable_order_on_tied_published_at(client, db_session):
    # Same published_at on every row (typical for one RSS batch). Insert in REVERSE
    # of id-ascending order so only an explicit id tiebreaker yields a deterministic
    # order; without it the rows come back in insertion order.
    same = datetime.now(UTC)
    ids = sorted(uuid.uuid4() for _ in range(3))  # ascending
    for nid in reversed(ids):
        db_session.add(
            NewsItem(
                id=nid,
                title="T",
                url="https://n",
                summary="s",
                source="src",
                published_at=same,
                raw_text="r",
                content_hash=uuid.uuid4().hex,
            )
        )
    db_session.commit()

    data = client.get("/api/v1/news", params={"limit": 100}).json()["data"]
    assert [item["id"] for item in data] == [str(i) for i in ids]
