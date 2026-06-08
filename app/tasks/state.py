from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.base import ErrorStage, PostStatus
from app.models.error_log import ErrorLog
from app.models.post import Post


def mark_generated(db: Session, post: Post, text: str) -> None:
    post.generated_text = text
    post.status = PostStatus.generated
    db.flush()


def mark_failed(
    db: Session,
    *,
    post: Post | None = None,
    stage: ErrorStage,
    message: str,
    tb: str | None = None,
    source_id=None,
    news_id=None,
) -> None:
    if post is not None:
        post.status = PostStatus.failed
        post.error = message
        if news_id is None:
            news_id = post.news_id
    log = ErrorLog(
        stage=stage,
        source_id=source_id,
        news_id=news_id,
        post_id=post.id if post is not None else None,
        message=message,
        traceback=tb,
    )
    db.add(log)
    db.flush()


# mark_published comes in the publish phase (P5.x)
def mark_published(db: Session, post: Post, message_id: int) -> None:
    post.tg_message_id = message_id
    post.status = PostStatus.published
    post.published_at = datetime.now(UTC)
    db.flush()
