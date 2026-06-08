import uuid
from datetime import UTC, datetime

from sqlalchemy import ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PostStatus, TZDateTime
from app.models.news_item import NewsItem


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    news_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("news_items.id"), index=True)
    generated_text: Mapped[str]
    status: Mapped[PostStatus] = mapped_column(default=PostStatus.new, index=True)
    published_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    tg_message_id: Mapped[int | None]
    error: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime, default=lambda: datetime.now(UTC)
    )

    news: Mapped[NewsItem] = relationship(back_populates="posts")
