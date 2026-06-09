import uuid
from datetime import datetime

from app.schemas.base import APIModel


class NewsRead(APIModel):
    id: uuid.UUID
    title: str
    url: str | None
    summary: str | None
    source: str
    published_at: datetime
    raw_text: str | None
    created_at: datetime
