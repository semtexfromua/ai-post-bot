import uuid
from datetime import UTC, datetime

from app.models.base import PostStatus
from app.models.news_item import NewsItem
from app.models.post import Post


def _news(db):
    item = NewsItem(
        title="t",
        url="https://example.com",
        summary=None,
        source="Example",
        published_at=datetime(2026, 6, 8, tzinfo=UTC),
        raw_text=None,
        content_hash=uuid.uuid4().hex,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def test_create_post_row_defaults_status_new(db):
    news = _news(db)
    post = Post(news_id=news.id, generated_text="hello")
    db.add(post)
    db.commit()
    db.refresh(post)
    assert isinstance(post.id, uuid.UUID)
    assert post.status is PostStatus.new
    assert post.published_at is None
    assert post.tg_message_id is None
    assert post.error is None
    assert post.created_at.tzinfo is not None


def test_post_status_enum_round_trip(db):
    news = _news(db)
    post = Post(
        news_id=news.id, generated_text="x", status=PostStatus.published
    )
    db.add(post)
    db.commit()
    fetched = db.get(Post, post.id)
    assert fetched.status is PostStatus.published


def test_post_news_relationship(db):
    news = _news(db)
    post = Post(news_id=news.id, generated_text="x")
    db.add(post)
    db.commit()
    db.refresh(post)
    assert post.news is not None
    assert post.news.id == news.id
    assert post in news.posts
