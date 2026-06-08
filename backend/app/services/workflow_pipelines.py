"""End-to-end workflow pipeline configurations and report finalization."""

import uuid

from sqlalchemy.orm import Session

from app.models.db_models import Agent, AuditEvent, ScientificReport, WorkflowRun, WorkflowTemplate

WORKFLOW_PIPELINES = [
    {
        "id": "pipeline-lit-hypothesis",
        "name": "Literature → Hypothesis",
        "description": "Mine indexed literature and PubMed, map knowledge, build and validate hypotheses, and produce a traceable hypothesis report.",
        "template_name": "Literature to Hypothesis",
        "query": (
            "JAK1 inhibition as a therapeutic target in rheumatoid arthritis — "
            "synthesize evidence from indexed studies and literature on efficacy, safety, and mechanism"
        ),
        "report_type": "hypothesis_report",
        "icon": "flask",
        "steps_highlight": ["Literature Miner", "Knowledge Scout", "Hypothesis Builder", "Scientific Writer"],
    },
    {
        "id": "pipeline-hypothesis-experiment",
        "name": "Hypothesis → Experiment Plan",
        "description": "Validate a hypothesis and generate a full experiment plan with DOE, outputting an experiment plan report.",
        "template_name": "Experiment Planning",
        "query": (
            "Design a preclinical validation program for JAK1 inhibitor therapy in rheumatoid arthritis — "
            "include in-vivo efficacy models, endpoints, and DOE for dose-response"
        ),
        "report_type": "experiment_plan",
        "icon": "beaker",
        "steps_highlight": ["Hypothesis Validation", "Experiment Planner", "DOE Designer"],
    },
    {
        "id": "pipeline-target-discovery",
        "name": "Target Discovery Brief",
        "description": "Pathway analysis, evidence scouting, biomarker scan, and target validation — produces a target discovery report.",
        "template_name": "Target Discovery",
        "query": (
            "Comprehensive target assessment for JAK1 in autoimmune disease — "
            "pathway role, druggability, biomarkers, and validation evidence"
        ),
        "report_type": "target_discovery",
        "icon": "target",
        "steps_highlight": ["Pathway Insight", "Evidence Scout", "Target Validation"],
    },
]


def list_workflow_pipelines(db: Session) -> list[dict]:
    """Return featured pipeline configs with resolved template IDs."""
    templates = {t.name: t for t in db.query(WorkflowTemplate).all()}
    pipelines = []
    for pipeline in WORKFLOW_PIPELINES:
        tmpl = templates.get(pipeline["template_name"])
        pipelines.append({
            **pipeline,
            "template_id": tmpl.id if tmpl else None,
            "step_count": len(tmpl.steps_json) if tmpl else 0,
            "available": tmpl is not None,
        })
    return pipelines


def finalize_workflow_report(db: Session, run: WorkflowRun) -> ScientificReport | None:
    """Synthesize a ScientificReport from completed workflow step outputs."""
    input_data = (run.output_json or {}).get("workflow_input", {})
    if not input_data.get("generate_report"):
        return None

    report_type = input_data.get("report_type", "study_report")
    steps_summary = []
    for step in run.steps_json or []:
        if step.get("status") != "completed":
            continue
        steps_summary.append({
            "agent": step.get("agent"),
            "output": (step.get("output") or "")[:2000],
            "confidence": step.get("confidence"),
            "citations": step.get("citations_count", 0),
        })

    if not steps_summary:
        return None

    from app.services.report_service import run_report_agent

    agent = db.query(Agent).filter(Agent.name == "Study Report Generator").first()
    if not agent:
        return None

    query = input_data.get("query") or run.name
    combined_context = "\n\n".join(
        f"### {s['agent']} (confidence {s.get('confidence', 'n/a')})\n{s['output']}"
        for s in steps_summary
    )

    result = run_report_agent(
        db,
        agent,
        {
            "query": f"Generate a comprehensive {report_type.replace('_', ' ')} from this workflow:\n{query}",
            "task_type": "report",
            "report_type": report_type,
            "prior_context": combined_context,
            "source_data": {
                "workflow_run_id": run.id,
                "workflow_name": run.name,
                "steps": steps_summary,
            },
            "top_k": 6,
        },
    )

    output = result["output"]
    report = ScientificReport(
        id=str(uuid.uuid4()),
        title=f"{run.name} — Report",
        report_type=report_type,
        content_json={
            "sections": output.get("section_names") or ["Executive Summary", "Methods", "Results", "Discussion"],
            "section_content": output.get("sections", []),
            "body": output.get("answer"),
            "summary": output.get("summary"),
            "word_count": output.get("word_count", 0),
            "figures": len(output.get("figures") or []),
            "citations": len(result["citations"]),
            "workflow_steps": len(steps_summary),
            "mode": output.get("mode"),
            "workflow_run_id": run.id,
        },
        status="draft",
        workflow_run_id=run.id,
    )
    db.add(report)

    db.add(AuditEvent(
        event_type="report_generated",
        actor=input_data.get("initiated_by", "system"),
        resource_type="report",
        resource_id=report.id,
        action=f"Workflow report generated for '{run.name}'",
        details_json={"workflow_run_id": run.id, "report_type": report_type, "steps": len(steps_summary)},
    ))
    db.commit()
    db.refresh(report)
    return report
