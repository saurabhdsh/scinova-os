"""Export workflow agent step outputs as Markdown or JSON."""

from __future__ import annotations

import json
import re
from datetime import datetime

from app.models.db_models import WorkflowRun
from app.services.llm_output_utils import coerce_text, pick_text


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "step").lower()).strip("-")[:48]


def _step_body(step: dict) -> str:
    output_json = step.get("output_json") or {}
    return pick_text(
        {"output": step.get("output"), "answer": output_json.get("answer"), "summary": output_json.get("summary")},
        "output",
        "answer",
        "summary",
    )


def build_step_markdown(run: WorkflowRun, step_index: int) -> str:
    steps = run.steps_json or []
    if step_index < 0 or step_index >= len(steps):
        raise IndexError("Step index out of range")

    step = steps[step_index]
    agent = step.get("agent", f"Step {step_index + 1}")
    body = _step_body(step)
    input_data = (run.output_json or {}).get("workflow_input", {})
    query = input_data.get("query", "")

    lines = [
        f"# {agent}",
        "",
        f"**Workflow:** {run.name}",
        f"**Step:** {step_index + 1} of {len(steps)}",
        f"**Status:** {step.get('status', 'unknown')}",
        f"**Model:** {step.get('model_selected', 'n/a')} ({step.get('model_type', 'n/a')})",
    ]
    if step.get("confidence") is not None:
        lines.append(f"**Confidence:** {step['confidence']:.0%}")
    if step.get("citations_count") is not None:
        lines.append(f"**Citations:** {step['citations_count']}")
    lines.extend(["", "## Research question", "", query, "", "## Agent output", "", body or "_No output recorded._", ""])
    return "\n".join(lines)


def build_workflow_markdown(run: WorkflowRun) -> str:
    steps = run.steps_json or []
    input_data = (run.output_json or {}).get("workflow_input", {})
    query = input_data.get("query", "")

    lines = [
        f"# Workflow Report: {run.name}",
        "",
        f"**Status:** {run.status}",
        f"**Completed:** {run.completed_at or 'in progress'}",
        f"**Average confidence:** {(run.confidence * 100):.0f}%" if run.confidence else "",
        "",
        "## Research question",
        "",
        query,
        "",
        "---",
        "",
    ]

    for i, step in enumerate(steps):
        agent = step.get("agent", f"Step {i + 1}")
        body = _step_body(step)
        lines.extend([
            f"## Step {i + 1}: {agent}",
            "",
            f"- **Status:** {step.get('status', 'pending')}",
            f"- **Model:** {step.get('model_selected', 'n/a')} ({step.get('model_type', 'n/a')})",
        ])
        if step.get("confidence") is not None:
            lines.append(f"- **Confidence:** {step['confidence']:.0%}")
        if step.get("citations_count") is not None:
            lines.append(f"- **Citations:** {step['citations_count']}")
        lines.extend(["", body or "_Pending or no output._", "", "---", ""])

    report_id = (run.output_json or {}).get("report_id")
    if report_id:
        lines.extend(["", f"**Consolidated report ID:** `{report_id}`", ""])

    return "\n".join(line for line in lines if line is not None)


def build_workflow_json(run: WorkflowRun) -> dict:
    input_data = (run.output_json or {}).get("workflow_input", {})
    steps_export = []
    for i, step in enumerate(run.steps_json or []):
        steps_export.append({
            "index": i,
            "agent": step.get("agent"),
            "status": step.get("status"),
            "model_selected": step.get("model_selected"),
            "model_type": step.get("model_type"),
            "confidence": step.get("confidence"),
            "citations_count": step.get("citations_count"),
            "started_at": step.get("started_at"),
            "completed_at": step.get("completed_at"),
            "output": _step_body(step),
            "output_json": step.get("output_json"),
            "agent_run_id": step.get("agent_run_id"),
        })

    return {
        "workflow_id": run.id,
        "workflow_name": run.name,
        "status": run.status,
        "confidence": run.confidence,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "exported_at": datetime.utcnow().isoformat(),
        "research_query": input_data.get("query"),
        "report_id": (run.output_json or {}).get("report_id"),
        "report_title": (run.output_json or {}).get("report_title"),
        "steps": steps_export,
    }


def export_filename(run: WorkflowRun, step_index: int | None = None, ext: str = "md") -> str:
    base = _slug(run.name or "workflow")
    if step_index is not None:
        steps = run.steps_json or []
        agent = _slug(steps[step_index].get("agent", f"step-{step_index + 1}"))
        return f"{base}-step-{step_index + 1}-{agent}.{ext}"
    return f"{base}-all-agents.{ext}"


def build_workflow_json_bytes(run: WorkflowRun) -> bytes:
    return json.dumps(build_workflow_json(run), indent=2, default=str).encode("utf-8")
