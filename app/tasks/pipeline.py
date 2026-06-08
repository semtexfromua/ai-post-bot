# stub — completed in a later phase
from app.tasks.celery_app import celery_app


@celery_app.task
def generate_post(news_id: str | None) -> str | None:
    raise NotImplementedError  # implemented in the AI/generation phase
