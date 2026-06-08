from typing import Generic, TypeVar

from app.schemas.base import APIModel

T = TypeVar("T")


class Page(APIModel, Generic[T]):
    data: list[T]
    count: int
