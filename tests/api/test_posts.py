import uuid
from datetime import UTC, datetime

from app.models.base import PostStatus
from app.models.news_item import NewsItem
from app.models.post import Post


def _seed_news(db):
    news = NewsItem(
        title="T",
        url="https://n",
        summary="s",
        source="src",
        published_at=datetime.now(UTC),
        raw_text="r",
        content_hash=uuid.uuid4().hex,
    )
    db.add(news)
    db.commit()
    db.refresh(news)
    return news


def test_list_posts_envelope(client, db_session):
    news = _seed_news(db_session)
    for st in (PostStatus.generated, PostStatus.published, PostStatus.failed):
        db_session.add(Post(news_id=news.id, generated_text="x", status=st))
    db_session.commit()

    resp = client.get("/api/v1/posts")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"data", "count"}
    assert body["count"] == 3
    assert len(body["data"]) == 3
    assert "news_id" in body["data"][0]


def test_list_posts_status_filter(client, db_session):
    news = _seed_news(db_session)
    db_session.add(Post(news_id=news.id, generated_text="a", status=PostStatus.failed))
    db_session.add(
        Post(news_id=news.id, generated_text="b", status=PostStatus.published)
    )
    db_session.commit()

    resp = client.get("/api/v1/posts", params={"status": "failed"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["data"][0]["status"] == "failed"


def test_list_posts_pagination_limit_offset(client, db_session):
    news = _seed_news(db_session)
    for _ in range(5):
        db_session.add(Post(news_id=news.id, generated_text="p", status=PostStatus.new))
    db_session.commit()

    resp = client.get("/api/v1/posts", params={"limit": 2, "offset": 0})
    body = resp.json()
    assert body["count"] == 5
    assert len(body["data"]) == 2


def test_list_posts_limit_over_cap_422(client):
    resp = client.get("/api/v1/posts", params={"limit": 1000})
    assert resp.status_code == 422
