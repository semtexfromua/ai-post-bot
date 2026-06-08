import uuid
from datetime import datetime

from app.models.base import PostStatus
from app.schemas.base import APIModel


class PostRead(APIModel):
    id: uuid.UUID
    news_id: uuid.UUID
    generated_text: str
    status: PostStatus
    published_at: datetime | None
    tg_message_id: int | None
    error: str | None
    created_at: datetime
