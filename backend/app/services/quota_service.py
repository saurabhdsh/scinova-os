"""Per-user upload and workflow quotas."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.models.db_models import Document, User, WorkflowRun


def quotas_apply_to(user: User) -> bool:
    return user.role != "admin"


def get_usage(db: Session, user_id: str) -> dict[str, int]:
    return {
        "uploads_used": db.query(Document).filter(Document.user_id == user_id).count(),
        "workflows_used": db.query(WorkflowRun).filter(WorkflowRun.user_id == user_id).count(),
    }


def get_quota_status(db: Session, user: User) -> dict:
    usage = get_usage(db, user.id)
    enabled = quotas_apply_to(user)
    uploads_remaining = None if not enabled else max(0, settings.quota_max_uploads - usage["uploads_used"])
    workflows_remaining = None if not enabled else max(0, settings.quota_max_workflows - usage["workflows_used"])
    return {
        "quotas_enabled": enabled,
        "max_uploads": settings.quota_max_uploads,
        "max_workflows": settings.quota_max_workflows,
        "uploads_used": usage["uploads_used"],
        "workflows_used": usage["workflows_used"],
        "uploads_remaining": uploads_remaining,
        "workflows_remaining": workflows_remaining,
        "uploads_allowed": not enabled or usage["uploads_used"] < settings.quota_max_uploads,
        "workflows_allowed": not enabled or usage["workflows_used"] < settings.quota_max_workflows,
    }


def assert_upload_allowed(db: Session, user: User) -> None:
    if not quotas_apply_to(user):
        return
    used = db.query(Document).filter(Document.user_id == user.id).count()
    if used >= settings.quota_max_uploads:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Upload limit reached ({used}/{settings.quota_max_uploads} documents). "
                "Contact your administrator."
            ),
        )


def assert_workflow_allowed(db: Session, user: User) -> None:
    if not quotas_apply_to(user):
        return
    used = db.query(WorkflowRun).filter(WorkflowRun.user_id == user.id).count()
    if used >= settings.quota_max_workflows:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Workflow limit reached ({used}/{settings.quota_max_workflows} runs). "
                "Contact your administrator."
            ),
        )
