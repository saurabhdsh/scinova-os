"""Dispatch ingestion to Celery or run in a background thread when the worker is unavailable."""

import logging
import threading

from app.config import settings

logger = logging.getLogger(__name__)

INGESTION_TASK_NAME = "ingestion.run_pipeline"


def _celery_worker_ready() -> bool:
    """Return True if at least one worker has registered the ingestion task."""
    try:
        from app.celery_app import celery_app

        insp = celery_app.control.inspect(timeout=1.5)
        if not insp:
            return False
        registered = insp.registered()
        if not registered:
            return False
        return any(INGESTION_TASK_NAME in tasks for tasks in registered.values())
    except Exception as exc:
        logger.debug("Celery inspect failed: %s", exc)
        return False


def enqueue_ingestion(job_id: str) -> str:
    if not settings.use_celery:
        return _run_async(job_id)

    if not _celery_worker_ready():
        logger.warning(
            "No Celery worker registered for %s — running ingestion in background thread",
            INGESTION_TASK_NAME,
        )
        return _run_async(job_id)

    try:
        from app.tasks.ingestion_tasks import run_ingestion_task

        run_ingestion_task.delay(job_id)
        return "celery"
    except Exception as exc:
        logger.warning("Celery dispatch failed (%s), running ingestion inline", exc)
        return _run_async(job_id)


def _run_async(job_id: str) -> str:
    """Run pipeline in a background thread so the API returns immediately."""

    def _worker() -> None:
        from app.database import SessionLocal
        from app.services.ingestion_pipeline import run_ingestion_pipeline

        db = SessionLocal()
        try:
            run_ingestion_pipeline(db, job_id)
        except Exception:
            logger.exception("Background ingestion failed for job %s", job_id)
        finally:
            db.close()

    threading.Thread(target=_worker, daemon=True, name=f"ingest-{job_id[:8]}").start()
    return "inline_async"


def _run_sync(job_id: str) -> str:
    from app.database import SessionLocal
    from app.services.ingestion_pipeline import run_ingestion_pipeline

    db = SessionLocal()
    try:
        run_ingestion_pipeline(db, job_id)
    finally:
        db.close()
    return "inline"
