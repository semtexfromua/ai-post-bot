import uuid
from datetime import datetime

from pydantic import field_validator

from app.models.base import SourceType
from app.news_parser.ssrf import UnsafeURLError, reject_literal_private_ip
from app.schemas.base import APIModel

_ALLOWED_URL_PREFIXES = ("http://", "https://")


def _validate_source_url(value: str) -> str:
    if value.startswith("@"):
        return value  # telegram @username
    if not value.startswith(_ALLOWED_URL_PREFIXES):
        raise ValueError("url must be an http(s) URL or a @username")
    # Network-free SSRF guard: reject blatant internal targets at the API edge
    # (full DNS-based check runs at fetch time in the parsers).
    try:
        reject_literal_private_ip(value)
    except UnsafeURLError as exc:
        raise ValueError(str(exc)) from exc
    return value


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
