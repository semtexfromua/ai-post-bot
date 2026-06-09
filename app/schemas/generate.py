import uuid

from pydantic import model_validator

from app.schemas.base import APIModel


class GenerateRequest(APIModel):
    news_id: uuid.UUID | None = None
    text: str | None = None

    @model_validator(mode="after")
    def require_news_id_or_text(self) -> "GenerateRequest":
        if self.news_id is None and self.text is None:
            raise ValueError("At least one of 'news_id' or 'text' must be provided")
        if self.news_id is not None and self.text is not None:
            raise ValueError("Provide only one of 'news_id' or 'text', not both")
        return self


class GenerateResponse(APIModel):
    task_id: str
    post_id: uuid.UUID | None = None
