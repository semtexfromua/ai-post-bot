import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from app.models.news_item import NewsItem


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


def test_generate_returns_202_and_enqueues(client, db_session):
    news = _seed_news(db_session)
    fake_result = MagicMock()
    fake_result.id = "task-123"
    with patch(
        "app.api.v1.routers.generate.generate_post.delay",
        return_value=fake_result,
    ) as delay:
        resp = client.post("/api/v1/generate", json={"news_id": str(news.id)})

    assert resp.status_code == 202
    body = resp.json()
    assert body["task_id"] == "task-123"
    delay.assert_called_once_with(str(news.id))


def test_generate_news_id_404_when_missing(client):
    with patch("app.api.v1.routers.generate.generate_post.delay") as delay:
        resp = client.post(
            "/api/v1/generate", json={"news_id": str(uuid.uuid4())}
        )
    assert resp.status_code == 404
    delay.assert_not_called()
