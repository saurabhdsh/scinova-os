"""Shared contract for LAB-A1 through LAB-A6."""

from __future__ import annotations

import time
import uuid

from sqlalchemy.orm import Session

from app.config import settings
from app.lab.adapters import EnvSecretProvider, data_lake, landing_zone
from app.lab.catalog import current_csv
from app.lab.dossier import decide_dossier, generate_dossier
from app.lab.errors import LabError
from app.lab.graph_bridge import find_entity, lineage
from app.lab.ingestion import ingest_bytes
from app.lab.models import (
    LabAgentJob,
    LabExperiment,
    LabExperimentDossier,
    LabExperimentPlan,
    LabInsight,
    LabMeasurement,
    LabResult,
)
from app.lab.operations import (
    approve_plan,
    create_follow_up,
    create_plan,
    evaluate_readiness,
    resolve_issue,
    what_if,
)
from app.lab.parsers.base import REGISTRY
from app.lab.results import compile_results
from app.lab.rules import NARRATIVE_MODEL_VERSION
from app.lab.serialize import dump

AGENTS = {
    "LAB-A1": {
        "name": "Experiment Planning",
        "summary": "Selects an approved protocol version and creates an experiment plan.",
    },
    "LAB-A2": {
        "name": "Sample and Materials Readiness",
        "summary": "Checks sample metadata and reagent lot expiry.",
    },
    "LAB-A3": {
        "name": "Instrument Readiness",
        "summary": "Checks Vi-CELL calibration status.",
    },
    "LAB-A4": {
        "name": "Training and Competency",
        "summary": "Checks operator qualification against the protocol.",
    },
    "LAB-A5": {
        "name": "Compliance",
        "summary": "Holds execution while blocking readiness issues remain open.",
    },
    "LAB-A6": {
        "name": "Data and Results",
        "summary": "Ingests Vi-CELL files, compiles results, and drafts an experiment dossier.",
    },
}

import app.lab.parsers  # noqa: F401


def invoke(db: Session, agent_id: str, experiment_id: str | None, trigger: str, context: dict | None, actor: str, idempotency_key: str | None = None) -> LabAgentJob:
    if agent_id not in AGENTS:
        raise LabError(f"Unknown agent {agent_id}.", status_code=404, code="unknown_agent")
    context = dict(context or {})
    stored_context = {key: value for key, value in context.items() if key != "content_bytes"}
    if isinstance(context.get("content_bytes"), (bytes, bytearray)):
        import hashlib

        stored_context["content_sha256"] = hashlib.sha256(context["content_bytes"]).hexdigest()
    if idempotency_key:
        existing = (
            db.query(LabAgentJob)
            .filter(LabAgentJob.agent_id == agent_id, LabAgentJob.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            if existing.context_json != stored_context or existing.trigger != trigger:
                raise LabError(
                    "Idempotency key was reused with a different request.",
                    status_code=409,
                    code="idempotency_conflict",
                )
            return existing
    job = LabAgentJob(
        agent_id=agent_id,
        experiment_id=experiment_id,
        trigger=trigger,
        status="RUNNING",
        correlation_id=str(uuid.uuid4()),
        idempotency_key=idempotency_key,
        context_json=stored_context,
        actor=actor,
        model_version=NARRATIVE_MODEL_VERSION,
    )
    db.add(job)
    db.flush()
    started = time.perf_counter()
    try:
        output = _dispatch(db, agent_id, experiment_id, trigger, context, actor)
        job.status = "SUCCEEDED"
        job.output_json = output
    except LabError as exc:
        job.status = "FAILED"
        job.error_json = exc.as_dict()
        job.latency_ms = int((time.perf_counter() - started) * 1000)
        job.completed_at = _now()
        db.flush()
        raise
    job.latency_ms = int((time.perf_counter() - started) * 1000)
    job.completed_at = _now()
    db.flush()
    return job


def get_status(db: Session, job_id: str) -> LabAgentJob:
    job = db.get(LabAgentJob, job_id)
    if job is None:
        raise LabError("Job not found.", status_code=404, code="not_found")
    return job


def get_outputs(db: Session, agent_id: str, experiment_id: str) -> dict:
    if agent_id not in AGENTS:
        raise LabError(f"Unknown agent {agent_id}.", status_code=404, code="unknown_agent")
    refs: list[dict] = []
    parent = db.get(LabExperiment, experiment_id)
    if agent_id == "LAB-A1":
        plan_ids = set()
        if parent is not None:
            plan_ids.add(parent.plan_id)
            refs.append({"entity_type": "experiment", "id": parent.id})
        follow_ups = db.query(LabExperimentPlan).filter(LabExperimentPlan.parent_plan_id.in_(plan_ids)).all() if plan_ids else []
        for plan in follow_ups:
            refs.append({"entity_type": "experiment_plan", "id": plan.id})
        if parent is not None and parent.plan_id:
            refs.append({"entity_type": "experiment_plan", "id": parent.plan_id})
    if agent_id == "LAB-A6":
        for model, name in (
            (LabMeasurement, "measurement"),
            (LabResult, "result"),
            (LabInsight, "insight"),
            (LabExperimentDossier, "experiment_dossier"),
        ):
            rows = db.query(model).filter(model.experiment_id == experiment_id, model.produced_by == "LAB-A6").all()
            refs.extend({"entity_type": name, "id": row.id} for row in rows)
    return {"agent_id": agent_id, "experiment_id": experiment_id, "refs": refs}


def explain(db: Session, agent_id: str, entity_ref: str) -> dict:
    if agent_id not in AGENTS:
        raise LabError(f"Unknown agent {agent_id}.", status_code=404, code="unknown_agent")
    kind, row = find_entity(db, entity_ref)
    if row is None:
        raise LabError("Entity not found.", status_code=404, code="not_found")
    chain = lineage(db, entity_ref)
    citations = []
    if kind == "insight":
        citations = row.citations_json or []
        text = row.statement
        ai_generated = bool(row.ai_generated)
    elif kind == "experiment_dossier":
        paragraphs = (row.narrative_json or {}).get("paragraphs") or []
        text = " ".join(item["text"] for item in paragraphs)
        citations = [cite for item in paragraphs for cite in item.get("citations") or []]
        ai_generated = True
    elif kind == "result":
        text = f"{row.metric} is {row.value} {row.unit}. Outcome {row.outcome}."
        citations = [{"entity_type": "Measurement", "id": mid} for mid in (row.measurement_ids_json or [])]
        ai_generated = False
    elif kind == "measurement":
        text = f"{row.readout_key} is {row.value} {row.unit}, mapped with confidence {row.mapping_confidence}."
        citations = [{"entity_type": "Measurement", "id": row.id}]
        ai_generated = False
    else:
        text = f"{kind} {row.id} is a fabric entity. See lineage for the scientific chain."
        ai_generated = False
    if ai_generated and not citations:
        raise LabError("AI narrative is missing citations.", status_code=500, code="uncited_narrative")
    return {
        "agent_id": agent_id,
        "entity_ref": entity_ref,
        "entity_type": kind,
        "ai_generated": ai_generated,
        "requires_scientist_approval": ai_generated,
        "model_version": getattr(row, "model_version", None) or "none",
        "llm_called": False,
        "text": text,
        "citations": citations,
        "lineage": chain,
        "label": "Machine-generated explanation." if ai_generated else "Deterministic explanation from stored fabric values.",
    }


def health(db: Session) -> dict:
    db_ok = True
    try:
        db.query(LabAgentJob).limit(1).all()
    except Exception as exc:  # noqa: BLE001
        db_ok = False
        db_error = str(exc)
    else:
        db_error = None
    zone = landing_zone()
    lake = data_lake()
    return {
        "status": "ok" if db_ok and REGISTRY else "degraded",
        "agents": list(AGENTS),
        "dependencies": {
            "database": "ok" if db_ok else db_error,
            "landing_zone": {"mode": zone.mode, "simulation": zone.simulation, "external": zone.external},
            "data_lake": {"mode": lake.mode, "simulation": lake.simulation, "external": lake.external},
            "parsers": {key: parser.version for key, parser in REGISTRY.items()},
            "secrets": EnvSecretProvider().status(),
            "experiment_completed_flag": bool(settings.lab_emit_experiment_completed),
            "retries": {"enabled": False, "scope": "NFR-07 build-later"},
        },
    }


def _dispatch(db, agent_id, experiment_id, trigger, context, actor) -> dict:
    if agent_id == "LAB-A1" and trigger == "create_plan":
        plan = create_plan(
            db,
            protocol_version_id=context["protocol_version_id"],
            actor=actor,
            title=context.get("title"),
            parameters=context.get("parameters"),
        )
        return {"entity_refs": [{"entity_type": "experiment_plan", "id": plan.id}]}
    if agent_id == "LAB-A1" and trigger == "approve_plan":
        experiment = approve_plan(db, context["plan_id"], actor, context.get("comment"))
        return {"entity_refs": [{"entity_type": "experiment", "id": experiment.id}, {"entity_type": "experiment_plan", "id": context["plan_id"]}]}
    if agent_id == "LAB-A1" and trigger == "what_if":
        return what_if(db, _require_experiment(experiment_id))
    if agent_id == "LAB-A1" and trigger == "follow_up":
        plan = create_follow_up(db, _require_experiment(experiment_id), actor)
        return {"entity_refs": [{"entity_type": "experiment_plan", "id": plan.id}], "change": {
            "parameter": "seeding_density_cells_per_ml",
            "value": plan.parameters_json.get("seeding_density_cells_per_ml"),
            "insight_ids": plan.cited_insight_ids_json,
        }}
    if agent_id in {"LAB-A2", "LAB-A3", "LAB-A4", "LAB-A5"} and trigger == "evaluate":
        issues = evaluate_readiness(db, _require_experiment(experiment_id), actor)
        mine = [row for row in issues if row.agent_id == agent_id]
        return {"issue_ids": [row.id for row in mine], "codes": [row.code for row in mine]}
    if agent_id == "LAB-A6" and trigger == "ingest":
        content = context.get("content_bytes")
        if content is None and context.get("fixture") == "vicell-current":
            content = current_csv()
        if isinstance(content, str):
            content = content.encode()
        if not isinstance(content, (bytes, bytearray)):
            raise LabError("Ingest requires file bytes or fixture=vicell-current.", status_code=422, code="file_required")
        summary = ingest_bytes(
            db,
            content=bytes(content),
            filename=context.get("filename") or "vicell.csv",
            experiment_id=_require_experiment(experiment_id),
            actor=actor,
            enforce_readiness=context.get("enforce_readiness", True),
        )
        return summary
    if agent_id == "LAB-A6" and trigger == "compile":
        return compile_results(db, _require_experiment(experiment_id), actor)
    if agent_id == "LAB-A6" and trigger == "dossier":
        dossier = generate_dossier(db, _require_experiment(experiment_id), actor)
        return {"entity_refs": [{"entity_type": "experiment_dossier", "id": dossier.id}], "publishable": dossier.publishable, "status": dossier.status}
    if trigger == "resolve_issue":
        issue = resolve_issue(db, context["issue_id"], actor, context.get("decision", ""), context.get("comment"))
        return {"issue_id": issue.id, "status": issue.status}
    if agent_id == "LAB-A6" and trigger == "decide_dossier":
        dossier = decide_dossier(db, context["dossier_id"], context["decision"], actor, context.get("comment"))
        return dump(dossier)
    raise LabError(f"{agent_id} does not implement trigger {trigger}.", status_code=422, code="unsupported_trigger")


def _require_experiment(experiment_id: str | None) -> str:
    if not experiment_id:
        raise LabError("experimentId is required for this trigger.", status_code=422, code="experiment_required")
    return experiment_id


def _now():
    from datetime import datetime

    return datetime.utcnow()
