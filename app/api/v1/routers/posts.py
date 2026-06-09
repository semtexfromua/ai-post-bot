from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.v1.deps import PaginationDep, SessionDep
from app.models.base import PostStatus
from app.models.post import Post
from app.schemas.common import Page
from app.schemas.post import PostRead

router = APIRouter(prefix="/posts", tags=["posts"])


@router.get(
    "",
    response_model=Page[PostRead],
    summary="Історія постів",
    description="Список згенерованих постів (найновіші перші). "
    "Опційний фільтр `status`: new | generated | published | failed.",
)
def list_posts(
    db: SessionDep,
    pagination: PaginationDep,
    status: PostStatus | None = None,
) -> Page[PostRead]:
    count_stmt = select(func.count()).select_from(Post)
    # id tiebreaker -> stable pagination when created_at ties
    rows_stmt = select(Post).order_by(Post.created_at.desc(), Post.id)
    if status is not None:
        count_stmt = count_stmt.where(Post.status == status)
        rows_stmt = rows_stmt.where(Post.status == status)
    total = db.scalar(count_stmt)
    rows = db.scalars(rows_stmt.offset(pagination.offset).limit(pagination.limit)).all()
    return Page[PostRead](data=rows, count=total or 0)
