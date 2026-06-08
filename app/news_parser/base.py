from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.source import Source


@dataclass
class NewsItemData:
    title: str
    url: str | None
    summary: str | None
    source: str
    published_at: datetime
    raw_text: str | None


class BaseParser(ABC):
    @abstractmethod
    def fetch(self, source: Source) -> list[NewsItemData]: ...
