import uuid

from app.schemas.base import APIModel


class GenerateRequest(APIModel):
    news_id: uuid.UUID | None = None
    text: str | None = None


class GenerateResponse(APIModel):
    task_id: str
    post_id: uuid.UUID | None = None
