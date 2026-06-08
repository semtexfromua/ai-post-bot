import uuid
from datetime import datetime

from pydantic import field_validator

from app.models.base import SourceType
from app.schemas.base import APIModel

_ALLOWED_URL_PREFIXES = ("http://", "https://")


def _validate_source_url(value: str) -> str:
    if value.startswith("@"):
        return value  # telegram @username
    if value.startswith(_ALLOWED_URL_PREFIXES):
        return value
    raise ValueError("url must be an http(s) URL or a @username")


class SourceCreate(APIModel):
    type: SourceType
    name: str
    url: str
    enabled: bool = True

    @field_validator("url")
    @classmethod
    def _check_url(cls, v: str) -> str:
        return _validate_source_url(v)


class SourceUpdate(APIModel):
    type: SourceType | None = None
    name: str | None = None
    url: str | None = None
    enabled: bool | None = None

    @field_validator("url")
    @classmethod
    def _check_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_source_url(v)


class SourceRead(APIModel):
    id: uuid.UUID
    type: SourceType
    name: str
    url: str
    enabled: bool
    created_at: datetime
