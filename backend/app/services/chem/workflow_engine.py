"""In-process workflow record for scientific jobs.

Long jobs stay visible as READY or RUNNING. A failed tool stays failed.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


LIFECYCLE = ("CREATED", "VALIDATING", "READY", "RUNNING", "COMPLETED", "FAILED", "CANCELLED")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def open_workflow(session: dict[str, Any], *, kind: str, parameters: dict[str, Any], status: str = "CREATED") -> dict[str, Any]:
    if status not in LIFECYCLE:
        status = "CREATED"
    workflow = {
        "workflow_id": str(uuid.uuid4()),
        "kind": kind,
        "status": status,
        "parameters": parameters,
        "log": [{"status": status, "at": _now()}],
        "created_at": _now(),
        "updated_at": _now(),
        "error": None,
    }
    session.setdefault("workflows", [])
    session["workflows"].append(workflow)
    _sync_lists(session)
    return workflow


def transition(session: dict[str, Any], workflow_id: str, status: str, *, note: str | None = None, error: str | None = None) -> dict[str, Any] | None:
    if status not in LIFECYCLE:
        status = "FAILED"
    for workflow in session.get("workflows") or []:
        if workflow.get("workflow_id") != workflow_id:
            continue
        workflow["status"] = status
        workflow["updated_at"] = _now()
        if error:
            workflow["error"] = error
        workflow.setdefault("log", []).append({"status": status, "at": workflow["updated_at"], "note": note})
        _sync_lists(session)
        return workflow
    return None


def pending_generation(session: dict[str, Any]) -> dict[str, Any] | None:
    for workflow in reversed(session.get("workflows") or []):
        if workflow.get("kind") == "molecule_generation" and workflow.get("status") in {"READY", "CREATED"}:
            return workflow
    return None


def _sync_lists(session: dict[str, Any]) -> None:
    research = session.setdefault("research", {})
    research["pending_workflows"] = [
        row.get("workflow_id")
        for row in session.get("workflows") or []
        if row.get("status") in {"CREATED", "VALIDATING", "READY", "RUNNING"}
    ]
    research["completed_workflows"] = [
        row.get("workflow_id")
        for row in session.get("workflows") or []
        if row.get("status") in {"COMPLETED", "FAILED", "CANCELLED"}
    ]
