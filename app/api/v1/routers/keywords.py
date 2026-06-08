import uuid

from fastapi import APIRouter, status
from sqlalchemy import func, select

from app.api.v1.deps import PaginationDep, SessionDep, get_keyword_or_404
from app.models.keyword import Keyword
from app.schemas.common import Page
from app.schemas.keyword import KeywordCreate, KeywordRead, KeywordUpdate

router = APIRouter(prefix="/keywords", tags=["keywords"])


@router.get("", response_model=Page[KeywordRead])
def list_keywords(db: SessionDep, pagination: PaginationDep) -> Page[KeywordRead]:
    total = db.scalar(select(func.count()).select_from(Keyword))
    rows = db.scalars(
        select(Keyword)
        .order_by(Keyword.word)
        .offset(pagination.offset)
        .limit(pagination.limit)
    ).all()
    return Page[KeywordRead](data=rows, count=total or 0)


@router.post("", response_model=KeywordRead, status_code=status.HTTP_201_CREATED)
def create_keyword(payload: KeywordCreate, db: SessionDep) -> Keyword:
    keyword = Keyword(**payload.model_dump())
    db.add(keyword)
    db.commit()
    db.refresh(keyword)
    return keyword


@router.get("/{keyword_id}", response_model=KeywordRead)
def get_keyword(keyword_id: uuid.UUID, db: SessionDep) -> Keyword:
    return get_keyword_or_404(keyword_id, db)


@router.patch("/{keyword_id}", response_model=KeywordRead)
def update_keyword(
    keyword_id: uuid.UUID, payload: KeywordUpdate, db: SessionDep
) -> Keyword:
    keyword = get_keyword_or_404(keyword_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(keyword, field, value)
    db.commit()
    db.refresh(keyword)
    return keyword


@router.delete("/{keyword_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_keyword(keyword_id: uuid.UUID, db: SessionDep) -> None:
    keyword = get_keyword_or_404(keyword_id, db)
    db.delete(keyword)
    db.commit()
