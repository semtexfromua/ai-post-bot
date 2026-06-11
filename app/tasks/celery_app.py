from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

# No result backend: task_ignore_result=True below and nothing ever reads
# task results (chains pass values via the message protocol, not the backend).
celery_app = Celery(
    "m4",
    broker=settings.REDIS_URL,
    include=["app.tasks.pipeline"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    task_ignore_result=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_soft_time_limit=120,
    task_time_limit=150,
    broker_transport_options={"visibility_timeout": 3600},
    task_default_queue="default",
    task_routes={
        # publish_post always on the tg queue (single-client constraint).
        # parse_source is routed per-source at CALL time by collect_sources
        # (queue="tg" for tg sources), so it needs no static route here.
        "app.tasks.pipeline.publish_post": {"queue": "tg"},
    },
    beat_schedule={
        "collect": {
            "task": "app.tasks.pipeline.collect_sources",
            "schedule": crontab(minute="0,30"),
        },
        # Drip one post every 30 min, offset from collect so freshly generated
        # posts are ready before we publish.
        "publish": {
            "task": "app.tasks.pipeline.publish_next",
            "schedule": crontab(minute="15,45"),
        },
    },
)
