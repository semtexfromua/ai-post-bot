import uuid
from datetime import datetime

from app.models.base import ErrorStage
from app.schemas.base import APIModel


class ErrorLogRead(APIModel):
    id: uuid.UUID
    created_at: datetime
    stage: ErrorStage
    source_id: uuid.UUID | None
    news_id: uuid.UUID | None
    post_id: uuid.UUID | None
    message: str
