"""Per-user and shared project workspace scoping."""

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.db_models import (
    AgentRun,
    Document,
    GraphNode,
    IngestionJob,
    ScientificEntity,
    ScientificReport,
    WorkflowRun,
)
from app.services.project_service import assert_project_access, project_ids_for_user, user_can_access_project


def _document_access_clause(user_id: str, project_ids: list[str]):
    clauses = [Document.user_id == user_id]
    if project_ids:
        clauses.append(Document.project_id.in_(project_ids))
    return or_(*clauses)


def document_query_for_user(db: Session, user_id: str, project_id: str | None = None):
    if project_id:
        assert_project_access(db, user_id, project_id)
        return db.query(Document).filter(Document.project_id == project_id)
    pids = project_ids_for_user(db, user_id)
    return db.query(Document).filter(_document_access_clause(user_id, pids))


def document_ids_for_user(db: Session, user_id: str, project_id: str | None = None) -> list[str]:
    return [r[0] for r in document_query_for_user(db, user_id, project_id).with_entities(Document.id).all()]


def get_user_document(db: Session, user_id: str, document_id: str, project_id: str | None = None) -> Document:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.user_id == user_id:
        if project_id and doc.project_id and doc.project_id != project_id:
            raise HTTPException(status_code=404, detail="Document not found")
        return doc
    if doc.project_id and user_can_access_project(db, user_id, doc.project_id):
        if project_id and doc.project_id != project_id:
            raise HTTPException(status_code=404, detail="Document not found")
        return doc
    raise HTTPException(status_code=404, detail="Document not found")


def get_user_job(db: Session, user_id: str, job_id: str, project_id: str | None = None) -> IngestionJob:
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    if job.user_id == user_id:
        if project_id and job.project_id and job.project_id != project_id:
            raise HTTPException(status_code=404, detail="Ingestion job not found")
        return job
    if job.project_id and user_can_access_project(db, user_id, job.project_id):
        if project_id and job.project_id != project_id:
            raise HTTPException(status_code=404, detail="Ingestion job not found")
        return job
    raise HTTPException(status_code=404, detail="Ingestion job not found")


def get_user_workflow(db: Session, user_id: str, workflow_id: str, project_id: str | None = None) -> WorkflowRun:
    run = db.query(WorkflowRun).filter(WorkflowRun.id == workflow_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    if run.user_id == user_id:
        if project_id and run.project_id and run.project_id != project_id:
            raise HTTPException(status_code=404, detail="Workflow run not found")
        return run
    if run.project_id and user_can_access_project(db, user_id, run.project_id):
        if project_id and run.project_id != project_id:
            raise HTTPException(status_code=404, detail="Workflow run not found")
        return run
    raise HTTPException(status_code=404, detail="Workflow run not found")


def get_user_report(db: Session, user_id: str, report_id: str, project_id: str | None = None) -> ScientificReport:
    report = db.query(ScientificReport).filter(ScientificReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.user_id == user_id:
        if project_id and report.project_id and report.project_id != project_id:
            raise HTTPException(status_code=404, detail="Report not found")
        return report
    if report.project_id and user_can_access_project(db, user_id, report.project_id):
        if project_id and report.project_id != project_id:
            raise HTTPException(status_code=404, detail="Report not found")
        return report
    raise HTTPException(status_code=404, detail="Report not found")


def assert_document_in_workspace(
    db: Session, user_id: str, document_id: str | None, project_id: str | None = None,
) -> None:
    if not document_id:
        return
    get_user_document(db, user_id, document_id, project_id)


def entity_query_for_user(db: Session, user_id: str, project_id: str | None = None):
    doc_ids = document_ids_for_user(db, user_id, project_id)
    q = db.query(ScientificEntity)
    if not doc_ids:
        return q.filter(ScientificEntity.id == "__none__")
    return q.filter(ScientificEntity.source_document_id.in_(doc_ids))


def workflow_query_for_user(db: Session, user_id: str, project_id: str | None = None):
    pids = project_ids_for_user(db, user_id)
    if project_id:
        assert_project_access(db, user_id, project_id)
        return db.query(WorkflowRun).filter(WorkflowRun.project_id == project_id)
    clauses = [WorkflowRun.user_id == user_id]
    if pids:
        clauses.append(WorkflowRun.project_id.in_(pids))
    return db.query(WorkflowRun).filter(or_(*clauses))


def agent_run_query_for_user(db: Session, user_id: str, project_id: str | None = None):
    pids = project_ids_for_user(db, user_id)
    if project_id:
        assert_project_access(db, user_id, project_id)
        return db.query(AgentRun).filter(AgentRun.project_id == project_id)
    clauses = [AgentRun.user_id == user_id]
    if pids:
        clauses.append(AgentRun.project_id.in_(pids))
    return db.query(AgentRun).filter(or_(*clauses))


def report_query_for_user(db: Session, user_id: str, project_id: str | None = None):
    pids = project_ids_for_user(db, user_id)
    if project_id:
        assert_project_access(db, user_id, project_id)
        return db.query(ScientificReport).filter(ScientificReport.project_id == project_id)
    clauses = [ScientificReport.user_id == user_id]
    if pids:
        clauses.append(ScientificReport.project_id.in_(pids))
    return db.query(ScientificReport).filter(or_(*clauses))


def assert_graph_access(db: Session, user_id: str, node_or_entity_id: str, project_id: str | None = None) -> None:
    doc_ids = document_ids_for_user(db, user_id, project_id)
    if not doc_ids:
        raise HTTPException(status_code=404, detail="Node not found")
    node = db.query(GraphNode).filter(
        (GraphNode.id == node_or_entity_id) | (GraphNode.entity_id == node_or_entity_id)
    ).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    if not node.entity_id:
        raise HTTPException(status_code=404, detail="Node not found")
    ent = db.query(ScientificEntity).filter(
        ScientificEntity.id == node.entity_id,
        ScientificEntity.source_document_id.in_(doc_ids),
    ).first()
    if not ent:
        raise HTTPException(status_code=404, detail="Node not found")
