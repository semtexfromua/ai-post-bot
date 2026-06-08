import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.keyword import Keyword
from app.models.post import Post
from app.models.source import Source

SessionDep = Annotated[Session, Depends(get_db)]


class Pagination:
    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> None:
        self.limit = limit
        self.offset = offset


PaginationDep = Annotated[Pagination, Depends(Pagination)]


def get_source_or_404(source_id: uuid.UUID, db: SessionDep) -> Source:
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source not found"
        )
    return source


def get_post_or_404(post_id: uuid.UUID, db: SessionDep) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )
    return post


def get_keyword_or_404(keyword_id: uuid.UUID, db: SessionDep) -> Keyword:
    keyword = db.get(Keyword, keyword_id)
    if keyword is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Keyword not found"
        )
    return keyword
