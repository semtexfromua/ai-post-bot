from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.v1.deps import PaginationDep, SessionDep
from app.models.base import ErrorStage
from app.models.error_log import ErrorLog
from app.schemas.common import Page
from app.schemas.error_log import ErrorLogRead

router = APIRouter(prefix="/errors", tags=["errors"])


@router.get(
    "",
    response_model=Page[ErrorLogRead],
    summary="Журнал помилок",
    description="Залоговані фейли пайплайну (найновіші перші). "
    "Опційний фільтр `stage`: parse | generate | publish.",
)
def list_errors(
    db: SessionDep,
    pagination: PaginationDep,
    stage: ErrorStage | None = None,
) -> Page[ErrorLogRead]:
    count_stmt = select(func.count()).select_from(ErrorLog)
    # id tiebreaker -> stable pagination when created_at ties
    rows_stmt = select(ErrorLog).order_by(ErrorLog.created_at.desc(), ErrorLog.id)
    if stage is not None:
        count_stmt = count_stmt.where(ErrorLog.stage == stage)
        rows_stmt = rows_stmt.where(ErrorLog.stage == stage)
    total = db.scalar(count_stmt)
    rows = db.scalars(rows_stmt.offset(pagination.offset).limit(pagination.limit)).all()
    return Page[ErrorLogRead](data=rows, count=total or 0)
