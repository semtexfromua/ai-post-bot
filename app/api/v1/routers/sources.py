import uuid

from fastapi import APIRouter, status
from sqlalchemy import func, select

from app.api.v1.deps import PaginationDep, SessionDep, get_source_or_404
from app.models.source import Source
from app.schemas.common import Page
from app.schemas.source import SourceCreate, SourceRead, SourceUpdate

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=Page[SourceRead])
def list_sources(db: SessionDep, pagination: PaginationDep) -> Page[SourceRead]:
    total = db.scalar(select(func.count()).select_from(Source))
    rows = db.scalars(
        select(Source)
        .order_by(Source.created_at)
        .offset(pagination.offset)
        .limit(pagination.limit)
    ).all()
    return Page[SourceRead](data=rows, count=total or 0)


@router.post("", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
def create_source(payload: SourceCreate, db: SessionDep) -> Source:
    source = Source(**payload.model_dump())
    db.add(source)
    db.commit()
    return source


@router.get("/{source_id}", response_model=SourceRead)
def get_source(source_id: uuid.UUID, db: SessionDep) -> Source:
    return get_source_or_404(source_id, db)


@router.patch("/{source_id}", response_model=SourceRead)
def update_source(
    source_id: uuid.UUID, payload: SourceUpdate, db: SessionDep
) -> Source:
    source = get_source_or_404(source_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    db.commit()
    return source


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: uuid.UUID, db: SessionDep) -> None:
    source = get_source_or_404(source_id, db)
    db.delete(source)
    db.commit()
