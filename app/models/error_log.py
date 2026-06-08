import uuid
from datetime import UTC, datetime

from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ErrorStage, TZDateTime


class ErrorLog(Base):
    __tablename__ = "error_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime, default=lambda: datetime.now(UTC), index=True
    )
    stage: Mapped[ErrorStage] = mapped_column(index=True)
    source_id: Mapped[uuid.UUID | None]
    news_id: Mapped[uuid.UUID | None]
    post_id: Mapped[uuid.UUID | None]
    message: Mapped[str]
    traceback: Mapped[str | None]
