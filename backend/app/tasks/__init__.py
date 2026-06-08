"""Celery task modules — import here so workers register tasks on startup."""

from app.tasks import ingestion_tasks as ingestion_tasks  # noqa: F401
