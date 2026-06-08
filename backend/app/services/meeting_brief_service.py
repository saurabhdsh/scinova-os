"""Meeting briefs and collaboration activity for scientist decision support."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models.db_models import (
    AgentRun,
    ApprovalRequest,
    AuditEvent,
    Document,
    RiskAlert,
    ScientificReport,
    User,
    WorkflowRun,
)
from app.services.llm_output_utils import pick_text
from app.services.llm_service import llm_service
from app.services import workspace as ws

BRIEF_SYSTEM = """You are a pharma R&D meeting facilitator preparing a decision-ready brief.
Synthesize the provided workspace activity into a structured meeting brief.

Return JSON with:
- title: string
- summary: string (2-3 sentences for executives)
- answer: string (full brief in markdown: agenda, key findings, open questions)
- agenda: array of strings
- key_findings: array of strings (evidence-backed)
- decisions_needed: array of strings
- action_items: array of objects {owner, task, due_hint}
- risks: array of strings
- confidence: float 0-1"""


def _recent_documents(db: Session, user_id: str, since: datetime, limit: int = 8, project_id: str | None = None) -> list[dict]:
    rows = (
        ws.document_query_for_user(db, user_id, project_id)
        .filter(Document.created_at >= since)
        .order_by(Document.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "title": d.title,
            "source_type": d.source_type,
            "status": d.status,
            "qc_status": (d.metadata_json or {}).get("qc_report", {}).get("status"),
        }
        for d in rows
    ]


def get_collaboration_activity(db: Session, user_id: str, *, limit: int = 25, project_id: str | None = None) -> dict:
    since = datetime.utcnow() - timedelta(days=14)
    user = db.query(User).filter(User.id == user_id).first()

    pending_approvals = (
        db.query(ApprovalRequest)
        .filter(ApprovalRequest.status == "pending")
        .order_by(ApprovalRequest.created_at.desc())
        .limit(10)
        .all()
    )
    recent_workflows = (
        ws.workflow_query_for_user(db, user_id, project_id)
        .order_by(WorkflowRun.created_at.desc())
        .limit(8)
        .all()
    )
    recent_agents = (
        ws.agent_run_query_for_user(db, user_id, project_id)
        .order_by(AgentRun.created_at.desc())
        .limit(8)
        .all()
    )
    open_risks = (
        db.query(RiskAlert)
        .filter(RiskAlert.status.in_(["open", "investigating"]))
        .order_by(RiskAlert.created_at.desc())
        .limit(8)
        .all()
    )
    audit = (
        db.query(AuditEvent)
        .filter(AuditEvent.created_at >= since)
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "user": {"username": user.username if user else None, "full_name": user.full_name if user else None},
        "pending_approvals": [
            {"id": a.id, "title": a.title, "type": a.request_type, "requested_by": a.requested_by, "created_at": a.created_at.isoformat()}
            for a in pending_approvals
        ],
        "recent_workflows": [
            {"id": w.id, "name": w.name, "status": w.status, "created_at": w.created_at.isoformat()}
            for w in recent_workflows
        ],
        "recent_agent_runs": [
            {"id": r.id, "status": r.status, "agent_id": r.agent_id, "created_at": r.created_at.isoformat()}
            for r in recent_agents
        ],
        "open_risks": [
            {"id": r.id, "title": r.title, "severity": r.severity, "category": r.category}
            for r in open_risks
        ],
        "recent_documents": _recent_documents(db, user_id, since, project_id=project_id),
        "project_id": project_id,
        "audit_timeline": [
            {"event_type": e.event_type, "action": e.action, "actor": e.actor, "created_at": e.created_at.isoformat()}
            for e in audit
        ],
    }


def generate_meeting_brief(
    db: Session,
    user_id: str,
    *,
    topic: str,
    audience: str = "R&D leadership",
    lookback_days: int = 7,
    project_id: str | None = None,
) -> ScientificReport:
    since = datetime.utcnow() - timedelta(days=lookback_days)
    activity = get_collaboration_activity(db, user_id, project_id=project_id)

    context = {
        "topic": topic,
        "audience": audience,
        "lookback_days": lookback_days,
        "activity": activity,
    }

    llm_result = {}
    try:
        llm_result = llm_service.chat_json(
            system=BRIEF_SYSTEM,
            user=f"Prepare a meeting brief for this workspace activity:\n{context}",
            model=settings.llm_model,
        ) or {}
    except Exception:
        llm_result = {}

    title = llm_result.get("title") or f"Meeting Brief: {topic[:80]}"
    report = ScientificReport(
        id=str(uuid.uuid4()),
        title=title,
        report_type="meeting_brief",
        user_id=user_id,
        project_id=project_id,
        content_json={
            "summary": llm_result.get("summary") or f"Brief for {topic}",
            "body": pick_text(llm_result, "answer", "summary"),
            "agenda": llm_result.get("agenda") or [],
            "key_findings": llm_result.get("key_findings") or [],
            "decisions_needed": llm_result.get("decisions_needed") or [],
            "action_items": llm_result.get("action_items") or [],
            "risks": llm_result.get("risks") or activity.get("open_risks", []),
            "activity_snapshot": activity,
            "topic": topic,
            "audience": audience,
            "confidence": llm_result.get("confidence", 0.8),
        },
        status="draft",
    )
    db.add(report)
    db.add(AuditEvent(
        event_type="meeting_brief_generated",
        actor=activity["user"].get("username") or "system",
        resource_type="report",
        resource_id=report.id,
        action=f"Meeting brief generated: {title}",
        details_json={"topic": topic, "audience": audience},
    ))
    db.commit()
    db.refresh(report)
    return report
