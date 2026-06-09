import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status

from app.api.v1.deps import SessionDep
from app.models.news_item import NewsItem
from app.schemas.generate import GenerateRequest, GenerateResponse
from app.tasks.pipeline import generate_post

router = APIRouter(prefix="/generate", tags=["generate"])


@router.post(
    "",
    response_model=GenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ручний запуск генерації",
    description="Ставить таску генерації у чергу (202). Приймає `news_id` наявного "
    "NewsItem або довільний `text` (створює синтетичний NewsItem, source=\"manual\"). "
    "Лише генерація, без авто-публікації.",
)
def enqueue_generate(payload: GenerateRequest, db: SessionDep) -> GenerateResponse:
    if payload.news_id is not None:
        news = db.get(NewsItem, payload.news_id)
        if news is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="NewsItem not found"
            )
        news_id_arg = str(payload.news_id)
    else:
        # Ad-hoc text: persist a synthetic NewsItem so the standard generate task
        # can run unchanged. content_hash is per-request unique (manual generation
        # should never be deduped away). Generation only — not auto-published.
        text = payload.text or ""
        title = text.strip().splitlines()[0][:200] if text.strip() else "Ad-hoc"
        news = NewsItem(
            title=title,
            url=None,
            summary=text,
            source="manual",
            published_at=datetime.now(UTC),
            raw_text=text,
            content_hash=f"manual:{uuid.uuid4().hex}",
        )
        db.add(news)
        db.commit()
        db.refresh(news)
        news_id_arg = str(news.id)

    result = generate_post.delay(news_id_arg)
    return GenerateResponse(task_id=result.id, post_id=None)
