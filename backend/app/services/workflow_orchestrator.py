"""Workflow orchestration — step-by-step agent execution with approval gates."""

import logging
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.db_models import Agent, AuditEvent, WorkflowRun, WorkflowTemplate
from app.models.schemas import ModelRouteRequest
from app.services.agent_executor import execute_agent
from app.services.agent_settings_service import apply_agent_task_settings
from app.services.governance_service import create_approval_request
from app.services.model_router import route_model
from app.services.agent_capabilities import get_specialized_task_type
from app.services.rag_service import agent_supports_rag
from app.services.workflow_pipelines import finalize_workflow_report
from app.services.llm_output_utils import coerce_text, pick_text
from app.services.output_style import polish_prose

logger = logging.getLogger(__name__)


def create_workflow_run(
    db: Session,
    template: WorkflowTemplate,
    name: str | None,
    input_data: dict,
    user_id: str | None = None,
    project_id: str | None = None,
) -> WorkflowRun:
    steps = []
    for i, step_def in enumerate(template.steps_json):
        steps.append({
            **step_def,
            "order": step_def.get("order", i + 1),
            "status": "pending",
            "requires_approval": step_def.get("requires_approval", False),
        })

    run = WorkflowRun(
        id=str(uuid.uuid4()),
        template_id=template.id,
        name=name or f"{template.name} - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
        status="running",
        steps_json=steps,
        current_step=0,
        output_json={"workflow_input": input_data},
        evidence_json=[],
        user_id=user_id,
        project_id=project_id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    db.add(AuditEvent(
        event_type="workflow_started",
        actor=input_data.get("initiated_by") or user_id or "system",
        resource_type="workflow",
        resource_id=run.id,
        action=f"Workflow '{template.name}' started",
        details_json={"template_id": template.id, "steps": len(steps)},
    ))
    db.commit()
    db.refresh(run)
    return run


def run_workflow(
    db: Session,
    template: WorkflowTemplate,
    name: str | None,
    input_data: dict,
    user_id: str | None = None,
    project_id: str | None = None,
) -> WorkflowRun:
    """Create a workflow run (returns immediately; call execute_workflow_run to process steps)."""
    return create_workflow_run(db, template, name, input_data, user_id=user_id, project_id=project_id)


def execute_workflow_run(run_id: str) -> None:
    """Process workflow steps in a background thread with a dedicated DB session."""
    db = SessionLocal()
    try:
        advance_workflow(db, run_id)
    except Exception as exc:
        logger.exception("Workflow %s failed: %s", run_id, exc)
        run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
        if run and run.status in ("running", "pending_approval"):
            run.status = "failed"
            run.output_json = {
                **(run.output_json or {}),
                "summary": f"Workflow failed: {exc}",
            }
            run.completed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


def resume_workflow(db: Session, run_id: str, approved: bool) -> WorkflowRun:
    run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    if not run:
        raise ValueError("Workflow run not found")

    steps = list(run.steps_json or [])
    idx = run.current_step or 0
    if idx >= len(steps):
        return run

    step = steps[idx]
    if not approved:
        step["status"] = "rejected"
        step["approval_status"] = "rejected"
        run.status = "rejected"
        run.steps_json = steps
        run.completed_at = datetime.utcnow()
        run.output_json = {
            **(run.output_json or {}),
            "summary": f"Workflow rejected at step '{step.get('agent')}'",
        }
        db.commit()
        db.refresh(run)
        return run

    step["status"] = "completed"
    step["approval_status"] = "approved"
    step["completed_at"] = datetime.utcnow().isoformat()
    run.steps_json = steps
    run.status = "running"
    run.current_step = idx + 1
    db.commit()
    db.refresh(run)
    return run


def advance_workflow(db: Session, run_id: str) -> WorkflowRun:
    run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    if not run:
        raise ValueError("Workflow run not found")

    steps = list(run.steps_json or [])
    input_data = (run.output_json or {}).get("workflow_input", {})
    evidence = list(run.evidence_json or [])

    start_idx = run.current_step or 0
    for i in range(start_idx, len(steps)):
        step = steps[i]
        if step.get("status") in ("completed", "rejected"):
            continue

        agent_name = step.get("agent", "")
        agent = db.query(Agent).filter(Agent.name == agent_name).first()
        if not agent:
            step["status"] = "failed"
            step["error"] = f"Agent not found: {agent_name}"
            run.status = "failed"
            run.steps_json = steps
            run.current_step = i
            db.commit()
            db.refresh(run)
            return run

        routing = route_model(ModelRouteRequest(
            agent_name=agent_name,
            task_type="workflow_step",
            risk_level=agent.risk_level,
            user_query=str(input_data),
        ))

        step["status"] = "running"
        step["started_at"] = datetime.utcnow().isoformat()
        step["model_selected"] = routing.selected_model
        step["model_type"] = routing.model_type
        run.steps_json = steps
        run.current_step = i
        db.commit()

        step_input = _build_step_input(input_data, step, steps[:i], agent)
        step_input = apply_agent_task_settings(db, run.user_id, agent, step_input)
        agent_run = execute_agent(
            db,
            agent,
            step_input,
            context=f"Workflow step {i + 1}/{len(steps)}: {run.name}",
            user_id=run.user_id,
        )

        output = agent_run.output_json or {}
        step["agent_run_id"] = agent_run.id
        step_text = coerce_text(output.get("answer") or output.get("summary") or output, max_len=4000)
        step["output"] = polish_prose(step_text) if isinstance(step_text, str) else step_text
        step["output_json"] = output
        step["confidence"] = agent_run.confidence
        step["citations_count"] = len(agent_run.citations_json or [])
        step["completed_at"] = datetime.utcnow().isoformat()

        evidence.append({
            "step": agent_name,
            "agent_run_id": agent_run.id,
            "citations": step["citations_count"],
            "confidence": agent_run.confidence,
        })

        needs_approval = (step.get("requires_approval") or agent_run.status == "pending_review") and not input_data.get("auto_approve")
        if needs_approval:
            step["status"] = "awaiting_approval"
            step["approval_status"] = "pending"
            approval = create_approval_request(
                db,
                title=f"Workflow '{run.name}' — approve step: {agent_name}",
                request_type="workflow_step",
                requested_by=input_data.get("initiated_by", "system"),
                workflow_run_id=run.id,
                agent_run_id=agent_run.id,
                details={
                    "workflow_run_id": run.id,
                    "step_index": i,
                    "agent_name": agent_name,
                    "step_output_preview": coerce_text(step["output"], max_len=300),
                },
            )
            step["approval_id"] = approval.id
            run.status = "pending_approval"
            run.steps_json = steps
            run.evidence_json = evidence
            run.current_step = i
            db.commit()
            db.refresh(run)
            return run

        step["status"] = "completed"
        step["approval_status"] = "not_required"
        run.steps_json = steps
        run.evidence_json = evidence
        db.commit()

    completed_steps = [s for s in steps if s.get("status") == "completed"]
    confidences = [s.get("confidence") or 0.0 for s in completed_steps]
    run.status = "completed"
    run.current_step = len(steps)
    run.steps_json = steps
    run.evidence_json = evidence
    run.confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.0
    run.output_json = {
        **(run.output_json or {}),
        "summary": f"Workflow completed with {len(completed_steps)} agent steps",
        "steps_completed": len(completed_steps),
        "final_output": completed_steps[-1]["output"] if completed_steps else "",
    }
    run.completed_at = datetime.utcnow()

    report = finalize_workflow_report(db, run)
    if report:
        run.output_json["report_id"] = report.id
        run.output_json["report_title"] = report.title

    db.add(AuditEvent(
        event_type="workflow_complete",
        actor="system",
        resource_type="workflow",
        resource_id=run.id,
        action=f"Workflow '{run.name}' completed",
        details_json={"steps": len(completed_steps), "confidence": run.confidence},
    ))
    db.commit()
    db.refresh(run)
    return run


def _build_step_input(input_data: dict, step: dict, prior_steps: list, agent: Agent) -> dict:
    base_query = input_data.get("query") or input_data.get("project") or "Scientific workflow analysis"
    if prior_steps:
        prior_outputs = []
        for ps in prior_steps:
            if ps.get("status") == "completed" and ps.get("output"):
                prior_outputs.append(f"[{ps.get('agent')}]: {coerce_text(ps['output'], max_len=400)}")
        if prior_outputs:
            base_query = f"{base_query}\n\nPrior workflow context:\n" + "\n".join(prior_outputs[-3:])

    task_type = "workflow_step"
    specialized = get_specialized_task_type(agent)
    if specialized:
        task_type = specialized
    elif agent_supports_rag(agent, {"query": base_query, "task_type": "qa"}):
        task_type = "qa"
    return {
        "query": base_query,
        "task_type": task_type,
        "top_k": 6,
        "document_id": input_data.get("document_id"),
        "auto_approve": input_data.get("auto_approve", False),
    }
