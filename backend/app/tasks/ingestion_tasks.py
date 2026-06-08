import logging

from app.celery_app import celery_app
from app.database import SessionLocal
from app.services.ingestion_pipeline import run_ingestion_pipeline

logger = logging.getLogger(__name__)


@celery_app.task(name="ingestion.run_pipeline", bind=True, max_retries=1)
def run_ingestion_task(self, job_id: str) -> None:
    db = SessionLocal()
    try:
        run_ingestion_pipeline(db, job_id)
    except Exception as exc:
        logger.exception("Celery ingestion failed for job %s", job_id)
        raise self.retry(exc=exc, countdown=30) from exc
    finally:
        db.close()
