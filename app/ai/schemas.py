from pydantic import BaseModel


class PostDraft(BaseModel):
    text: str
    language: str
    hashtags: list[str] = []
