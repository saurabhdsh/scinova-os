import logging

from celery import Celery

from app.config import settings

logger = logging.getLogger(__name__)

broker = settings.celery_broker_url or settings.redis_url
backend = settings.celery_result_backend or settings.redis_url

celery_app = Celery("scinova", broker=broker, backend=backend)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=60 * 45,
    worker_prefetch_multiplier=1,
    imports=("app.tasks.ingestion_tasks",),
)

# Register task modules when the worker loads this app
celery_app.autodiscover_tasks(["app.tasks"])
