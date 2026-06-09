import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Index, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TZDateTime

if TYPE_CHECKING:
    from app.models.post import Post


class NewsItem(Base):
    __tablename__ = "news_items"
    __table_args__ = (
        # unfiltered /news: ORDER BY published_at DESC
        Index("ix_news_items_published_at", "published_at"),
        # ?source= filter: WHERE source + ORDER BY published_at (also serves the
        # source grouping in publish_next)
        Index("ix_news_items_source_published_at", "source", "published_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str]
    url: Mapped[str | None]
    summary: Mapped[str | None]
    source: Mapped[str]
    published_at: Mapped[datetime] = mapped_column(TZDateTime)
    raw_text: Mapped[str | None]
    content_hash: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime, default=lambda: datetime.now(UTC)
    )

    posts: Mapped[list["Post"]] = relationship(back_populates="news")
