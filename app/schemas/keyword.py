import uuid

from app.schemas.base import APIModel


class KeywordCreate(APIModel):
    word: str
    lang: str | None = None


class KeywordUpdate(APIModel):
    word: str | None = None
    lang: str | None = None


class KeywordRead(APIModel):
    id: uuid.UUID
    word: str
    lang: str | None
