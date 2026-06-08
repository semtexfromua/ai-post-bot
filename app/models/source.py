import uuid
from datetime import UTC, datetime

from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SourceType, TZDateTime


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    type: Mapped[SourceType]
    name: Mapped[str]
    url: Mapped[str] = mapped_column(unique=True)
    enabled: Mapped[bool] = mapped_column(default=True, index=True)
    last_seen_msg_id: Mapped[int | None]
    etag: Mapped[str | None]
    modified: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime, default=lambda: datetime.now(UTC)
    )
