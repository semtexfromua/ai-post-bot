from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.v1.deps import PaginationDep, SessionDep
from app.models.news_item import NewsItem
from app.schemas.common import Page
from app.schemas.news import NewsRead

router = APIRouter(prefix="/news", tags=["news"])


@router.get(
    "",
    response_model=Page[NewsRead],
    summary="Зібрані новини",
    description="Список зібраних новин (найновіші за `published_at` перші). "
    "Опційний фільтр `source` — точна назва джерела.",
)
def list_news(
    db: SessionDep,
    pagination: PaginationDep,
    source: str | None = None,
) -> Page[NewsRead]:
    count_stmt = select(func.count()).select_from(NewsItem)
    # id tiebreaker -> deterministic order across pages when published_at ties
    rows_stmt = select(NewsItem).order_by(NewsItem.published_at.desc(), NewsItem.id)
    if source is not None:
        count_stmt = count_stmt.where(NewsItem.source == source)
        rows_stmt = rows_stmt.where(NewsItem.source == source)
    total = db.scalar(count_stmt)
    rows = db.scalars(rows_stmt.offset(pagination.offset).limit(pagination.limit)).all()
    return Page[NewsRead](data=rows, count=total or 0)
