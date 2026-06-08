"""User provisioning for admin CLI and API."""

import os
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.db_models import (
    AgentRun,
    AgentTaskSettings,
    ApprovalRequest,
    CustomTool,
    Document,
    DocumentChunk,
    IngestionJob,
    Project,
    ProjectMember,
    ScientificReport,
    User,
    WorkflowRun,
)
from app.services.quota_service import get_usage


class UsernameTakenError(ValueError):
    pass


class UserNotFoundError(ValueError):
    pass


class CannotDeleteSelfError(ValueError):
    pass


class CannotDeleteLastAdminError(ValueError):
    pass


def create_user(
    db: Session,
    *,
    username: str,
    password: str,
    role: str = "scientist",
    full_name: str | None = None,
) -> User:
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise UsernameTakenError(f"Username '{username}' already exists")

    user = User(
        username=username.strip(),
        password_hash=hash_password(password),
        role=role,
        full_name=(full_name or username).strip(),
    )
    db.add(user)
    db.flush()

    db.add(AgentTaskSettings(user_id=user.id, settings_json={}))
    db.commit()
    db.refresh(user)
    return user


def list_users_with_stats(db: Session) -> list[dict]:
    users = db.query(User).order_by(User.created_at.desc()).all()
    rows: list[dict] = []
    for user in users:
        usage = get_usage(db, user.id)
        rows.append({
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "full_name": user.full_name,
            "created_at": user.created_at or datetime.utcnow(),
            "document_count": usage["uploads_used"],
            "workflow_count": usage["workflows_used"],
        })
    return rows


def _delete_documents(db: Session, document_ids: list[str]) -> None:
    if not document_ids:
        return

    try:
        from app.services.chromadb_client import chromadb_client

        for doc_id in document_ids:
            chromadb_client.delete_document(doc_id)
    except Exception:
        pass

    db.query(DocumentChunk).filter(DocumentChunk.document_id.in_(document_ids)).delete(
        synchronize_session=False,
    )
    db.query(IngestionJob).filter(IngestionJob.document_id.in_(document_ids)).delete(
        synchronize_session=False,
    )

    docs = db.query(Document).filter(Document.id.in_(document_ids)).all()
    for doc in docs:
        if doc.file_path and os.path.isfile(doc.file_path):
            try:
                os.remove(doc.file_path)
            except OSError:
                pass
    db.query(Document).filter(Document.id.in_(document_ids)).delete(synchronize_session=False)


def _delete_project_tree(db: Session, project_id: str) -> None:
    doc_ids = [
        r[0]
        for r in db.query(Document.id).filter(Document.project_id == project_id).all()
    ]
    _delete_documents(db, doc_ids)

    run_ids = [
        r[0]
        for r in db.query(AgentRun.id).filter(AgentRun.project_id == project_id).all()
    ]
    wf_ids = [
        r[0]
        for r in db.query(WorkflowRun.id).filter(WorkflowRun.project_id == project_id).all()
    ]
    if run_ids:
        db.query(ApprovalRequest).filter(ApprovalRequest.agent_run_id.in_(run_ids)).delete(
            synchronize_session=False,
        )
        db.query(AgentRun).filter(AgentRun.id.in_(run_ids)).delete(synchronize_session=False)
    if wf_ids:
        db.query(ApprovalRequest).filter(ApprovalRequest.workflow_run_id.in_(wf_ids)).delete(
            synchronize_session=False,
        )
        db.query(WorkflowRun).filter(WorkflowRun.id.in_(wf_ids)).delete(synchronize_session=False)

    db.query(ScientificReport).filter(ScientificReport.project_id == project_id).delete(
        synchronize_session=False,
    )
    db.query(ProjectMember).filter(ProjectMember.project_id == project_id).delete(
        synchronize_session=False,
    )
    db.query(Project).filter(Project.id == project_id).delete(synchronize_session=False)


def delete_user(db: Session, user_id: str, *, actor_user_id: str) -> None:
    if user_id == actor_user_id:
        raise CannotDeleteSelfError("You cannot delete your own account")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise UserNotFoundError(f"User '{user_id}' not found")

    if user.role == "admin":
        admin_count = db.query(User).filter(User.role == "admin").count()
        if admin_count <= 1:
            raise CannotDeleteLastAdminError("Cannot delete the last admin account")

    owned_project_ids = [
        r[0] for r in db.query(Project.id).filter(Project.owner_id == user_id).all()
    ]
    for project_id in owned_project_ids:
        _delete_project_tree(db, project_id)

    remaining_doc_ids = [
        r[0] for r in db.query(Document.id).filter(Document.user_id == user_id).all()
    ]
    _delete_documents(db, remaining_doc_ids)

    run_ids = [r[0] for r in db.query(AgentRun.id).filter(AgentRun.user_id == user_id).all()]
    wf_ids = [r[0] for r in db.query(WorkflowRun.id).filter(WorkflowRun.user_id == user_id).all()]
    if run_ids:
        db.query(ApprovalRequest).filter(ApprovalRequest.agent_run_id.in_(run_ids)).delete(
            synchronize_session=False,
        )
        db.query(AgentRun).filter(AgentRun.id.in_(run_ids)).delete(synchronize_session=False)
    if wf_ids:
        db.query(ApprovalRequest).filter(ApprovalRequest.workflow_run_id.in_(wf_ids)).delete(
            synchronize_session=False,
        )
        db.query(WorkflowRun).filter(WorkflowRun.id.in_(wf_ids)).delete(synchronize_session=False)

    db.query(IngestionJob).filter(IngestionJob.user_id == user_id).delete(synchronize_session=False)
    db.query(ScientificReport).filter(ScientificReport.user_id == user_id).delete(
        synchronize_session=False,
    )
    db.query(ProjectMember).filter(ProjectMember.user_id == user_id).delete(synchronize_session=False)
    db.query(AgentTaskSettings).filter(AgentTaskSettings.user_id == user_id).delete(
        synchronize_session=False,
    )
    db.query(CustomTool).filter(CustomTool.registered_by == user_id).delete(
        synchronize_session=False,
    )

    db.delete(user)
    db.commit()
