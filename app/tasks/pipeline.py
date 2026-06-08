# stubs — completed in later phases
from app.tasks.celery_app import celery_app


@celery_app.task
def generate_post(news_id: str | None) -> str | None:
    raise NotImplementedError  # implemented in the AI/generation phase


@celery_app.task
def filter_item(news_id: str) -> str | None:
    raise NotImplementedError  # stub — completed in the filter phase


@celery_app.task
def publish_post(post_id: str | None) -> None:
    raise NotImplementedError  # stub — completed in the publish phase
