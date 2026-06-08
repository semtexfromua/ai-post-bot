from fastapi import APIRouter, HTTPException, status

from app.api.v1.deps import SessionDep
from app.models.news_item import NewsItem
from app.schemas.generate import GenerateRequest, GenerateResponse
from app.tasks.pipeline import generate_post

router = APIRouter(prefix="/generate", tags=["generate"])


@router.post("", response_model=GenerateResponse, status_code=status.HTTP_202_ACCEPTED)
def enqueue_generate(payload: GenerateRequest, db: SessionDep) -> GenerateResponse:
    news_id_arg: str | None = None
    if payload.news_id is not None:
        news = db.get(NewsItem, payload.news_id)
        if news is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="NewsItem not found"
            )
        news_id_arg = str(payload.news_id)
    # payload.text is an ad-hoc prompt forwarded to the generation pipeline in a later phase;
    # for now the task receives news_id_arg=None for ad-hoc requests.
    result = generate_post.delay(news_id_arg)
    return GenerateResponse(task_id=result.id, post_id=None)
