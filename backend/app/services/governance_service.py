"""Governance — approvals, audit trail, risk checks, workflow resume."""

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.db_models import AgentRun, ApprovalRequest, AuditEvent, RiskAlert, WorkflowRun


def create_approval_request(
    db: Session,
    *,
    title: str,
    request_type: str,
    requested_by: str = "system",
    agent_run_id: str | None = None,
    workflow_run_id: str | None = None,
    details: dict | None = None,
) -> ApprovalRequest:
    approval = ApprovalRequest(
        id=str(uuid.uuid4()),
        title=title,
        request_type=request_type,
        status="pending",
        agent_run_id=agent_run_id,
        workflow_run_id=workflow_run_id,
        requested_by=requested_by,
        details_json=details or {},
    )
    db.add(approval)
    db.flush()

    db.add(AuditEvent(
        event_type="approval_requested",
        actor=requested_by,
        resource_type="approval",
        resource_id=approval.id,
        action=f"Approval requested: {title}",
        details_json={
            "request_type": request_type,
            "agent_run_id": agent_run_id,
            "workflow_run_id": workflow_run_id,
        },
    ))
    return approval


def process_approval(
    db: Session,
    approval_id: str,
    decision: str,
    actor: str = "scientist",
    comment: str | None = None,
) -> dict:
    approval = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
    if not approval:
        raise ValueError("Approval request not found")
    if approval.status != "pending":
        raise ValueError(f"Approval already {approval.status}")

    approval.status = decision
    approval.details_json = {
        **(approval.details_json or {}),
        "decision_comment": comment,
        "decided_at": datetime.utcnow().isoformat(),
        "decided_by": actor,
    }

    db.add(AuditEvent(
        event_type="approval_decision",
        actor=actor,
        resource_type="approval",
        resource_id=approval.id,
        action=f"Approval {decision}: {approval.title}",
        details_json={"decision": decision, "comment": comment},
    ))

    result = {"approval_id": approval.id, "decision": decision, "resumed": False}

    if approval.agent_run_id:
        agent_run = db.query(AgentRun).filter(AgentRun.id == approval.agent_run_id).first()
        if agent_run:
            agent_run.status = "completed" if decision == "approved" else "rejected"
            if decision == "rejected":
                agent_run.output_json = {
                    **(agent_run.output_json or {}),
                    "rejected_by_governance": True,
                    "rejection_comment": comment,
                }
            agent_run.completed_at = datetime.utcnow()

    if approval.workflow_run_id and decision == "approved":
        from app.services.workflow_orchestrator import resume_workflow

        run = resume_workflow(db, approval.workflow_run_id, approved=True)
        result["resumed"] = True
        result["workflow_status"] = run.status
    elif approval.workflow_run_id and decision == "rejected":
        from app.services.workflow_orchestrator import resume_workflow

        run = resume_workflow(db, approval.workflow_run_id, approved=False)
        result["workflow_status"] = run.status

    if decision == "rejected" and approval.request_type in ("high_risk_agent", "workflow_step"):
        _maybe_create_risk_alert(db, approval, comment)

    db.commit()
    return result


def _maybe_create_risk_alert(db: Session, approval: ApprovalRequest, comment: str | None):
    db.add(RiskAlert(
        id=str(uuid.uuid4()),
        title=f"Rejected: {approval.title[:120]}",
        description=comment or "Human reviewer rejected an automated recommendation.",
        severity="medium",
        category="governance",
        status="open",
        source="Governance Engine",
    ))


def run_gxp_check(db: Session) -> dict:
    pending_approvals = db.query(ApprovalRequest).filter(ApprovalRequest.status == "pending").count()
    open_high_risks = db.query(RiskAlert).filter(
        RiskAlert.status == "open",
        RiskAlert.severity == "high",
    ).count()
    failed_workflows = db.query(WorkflowRun).filter(WorkflowRun.status == "failed").count()
    rejected_runs = db.query(AgentRun).filter(AgentRun.status == "rejected").count()

    checks = [
        {
            "name": "Audit trail active",
            "status": "pass",
            "detail": f"{db.query(AuditEvent).count()} events recorded",
        },
        {
            "name": "Pending human approvals",
            "status": "pass" if pending_approvals <= 3 else "attention",
            "detail": f"{pending_approvals} awaiting review",
        },
        {
            "name": "High-severity risk alerts",
            "status": "pass" if open_high_risks == 0 else "fail",
            "detail": f"{open_high_risks} open high-severity alerts",
        },
        {
            "name": "Workflow integrity",
            "status": "pass" if failed_workflows == 0 else "attention",
            "detail": f"{failed_workflows} failed workflow runs",
        },
        {
            "name": "Agent rejection rate",
            "status": "pass" if rejected_runs <= 2 else "attention",
            "detail": f"{rejected_runs} rejected agent runs",
        },
    ]

    overall = "pass"
    if any(c["status"] == "fail" for c in checks):
        overall = "fail"
    elif any(c["status"] == "attention" for c in checks):
        overall = "attention"

    return {"status": overall, "checks": checks, "evaluated_at": datetime.utcnow().isoformat()}


def acknowledge_risk_alert(db: Session, alert_id: str, actor: str = "scientist") -> RiskAlert:
    alert = db.query(RiskAlert).filter(RiskAlert.id == alert_id).first()
    if not alert:
        raise ValueError("Risk alert not found")
    alert.status = "acknowledged"
    db.add(AuditEvent(
        event_type="risk_acknowledged",
        actor=actor,
        resource_type="risk_alert",
        resource_id=alert.id,
        action=f"Risk alert acknowledged: {alert.title}",
        details_json={"severity": alert.severity},
    ))
    db.commit()
    db.refresh(alert)
    return alert
