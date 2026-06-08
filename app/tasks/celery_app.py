# stub — completed in a later phase
from celery import Celery

from app.core.config import settings

celery_app = Celery("m4", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
