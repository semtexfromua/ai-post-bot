import uuid
from datetime import datetime

from app.models.base import SourceType
from app.schemas.base import APIModel


class SourceCreate(APIModel):
    type: SourceType
    name: str
    url: str
    enabled: bool = True


class SourceUpdate(APIModel):
    type: SourceType | None = None
    name: str | None = None
    url: str | None = None
    enabled: bool | None = None


class SourceRead(APIModel):
    id: uuid.UUID
    type: SourceType
    name: str
    url: str
    enabled: bool
    created_at: datetime
