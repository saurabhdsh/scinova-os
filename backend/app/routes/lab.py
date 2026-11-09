"""Lab fabric HTTP API. Mounted at /api/lab so existing /api/entities and /api/graph routes stay intact."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Header, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import CurrentUser
from app.lab.agents import AGENTS, explain, get_outputs, get_status, health, invoke
from app.lab.assistant import answer_question, draft_from_intent
from app.lab.audit import history
from app.lab.catalog import current_csv, planned_csv, sequencing_csv
from app.lab.dossier import decide_dossier, generate_dossier
from app.lab.errors import LabError
from app.lab.graph_bridge import lineage, query_relationships
from app.lab.ingestion import correct_measurement, ingest_bytes, reject_raw_mutation
from app.lab.models import (
    ENTITY_MODELS,
    LabDataQualityFlag,
    LabDocumentSection,
    LabEvent,
    LabExperiment,
    LabExperimentDossier,
    LabExperimentPlan,
    LabInstrument,
    LabProtocol,
    LabProtocolVersion,
    LabReadinessIssue,
    LabSubscription,
)
from app.lab.ontology import lookup, map_header, map_headers
from app.lab.operations import (
    approve_plan,
    create_follow_up,
    create_plan,
    create_protocol,
    eln_status,
    evaluate_readiness,
    resolve_issue,
    storyline,
    what_if,
)
from app.lab.results import active_insights, active_results, compile_results
from app.lab.serialize import dump, dumps
router = APIRouter(prefix="/lab", tags=["Lab Fabric"])

_READ_ROLES = {"scientist", "reviewer", "admin", "data_steward", "principal_investigator"}
_WRITE_ROLES = {"scientist", "admin", "data_steward", "principal_investigator"}
_APPROVE_ROLES = {"scientist", "reviewer", "admin", "principal_investigator"}


def _commit(db: Session, fn):
    try:
        result = fn()
        db.commit()
        return result
    except LabError:
        db.rollback()
        raise


def _role(user, allowed: set[str]) -> None:
    if user.role not in allowed:
        raise LabError("This lab action is not allowed for the current role.", status_code=403, code="forbidden")


@router.get("/overview")
def overview(user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _READ_ROLES)
    experiments = db.query(LabExperiment).order_by(LabExperiment.created_at.desc()).all()
    plans = {row.id: row for row in db.query(LabExperimentPlan).all()}
    versions = {row.id: row for row in db.query(LabProtocolVersion).all()}
    protocols = {row.id: row for row in db.query(LabProtocol).all()}
    experiment_rows = []
    for experiment in experiments:
        body = dump(experiment)
        plan = plans.get(experiment.plan_id)
        version = versions.get(plan.protocol_version_id) if plan is not None else None
        protocol = protocols.get(version.protocol_id) if version is not None else None
        body["protocol_code"] = protocol.code if protocol is not None else None
        body["protocol_title"] = protocol.title if protocol is not None else None
        experiment_rows.append(body)
    return {
        "data_origin_notice": "Protocol text, inventory, and Vi-CELL rows shipped with the demo are synthetic. Checksums, parsing, statistics, gates, and audit rows are application logic.",
        "protocols": dumps(db.query(LabProtocol).all()),
        "instruments": dumps(db.query(LabInstrument).all()),
        "experiments": experiment_rows,
        "agents": AGENTS,
    }


@router.get("/protocols")
def list_protocols(user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _READ_ROLES)
    versions = db.query(LabProtocolVersion).all()
    protocols = {row.id: row for row in db.query(LabProtocol).all()}
    return [
        {
            **dump(version),
            "protocol_code": protocols[version.protocol_id].code,
            "protocol_title": protocols[version.protocol_id].title,
        }
        for version in versions
    ]


@router.post("/protocols")
def post_protocol(payload: dict, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _WRITE_ROLES)

    def _run():
        return create_protocol(
            db,
            actor=user.username,
            title=payload.get("title") or "",
            parameters=payload.get("parameters"),
            success_criteria=payload.get("success_criteria"),
            exact=bool(payload.get("exact")),
        )

    return _commit(db, _run)


@router.get("/experiments")
def list_experiments(user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _READ_ROLES)
    return dumps(db.query(LabExperiment).order_by(LabExperiment.created_at.desc()).all())


@router.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: str, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _READ_ROLES)
    experiment = db.get(LabExperiment, experiment_id)
    if experiment is None:
        raise LabError("Experiment not found.", status_code=404, code="not_found")
    plan = db.get(LabExperimentPlan, experiment.plan_id)
    return {"experiment": dump(experiment), "plan": dump(plan) if plan else None, "storyline": storyline(db, experiment_id)}


@router.post("/plans")
def post_plan(payload: dict, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _WRITE_ROLES)

    def _run():
        plan = create_plan(
            db,
            protocol_version_id=payload["protocol_version_id"],
            actor=user.username,
            title=payload.get("title"),
            parameters=payload.get("parameters"),
            success_criteria=payload.get("success_criteria"),
        )
        return dump(plan)

    return _commit(db, _run)


@router.post("/plans/{plan_id}/approve")
def post_approve_plan(plan_id: str, payload: dict, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _APPROVE_ROLES)

    def _run():
        experiment = approve_plan(db, plan_id, user.username, payload.get("comment"), payload.get("title"))
        return dump(experiment)

    return _commit(db, _run)


@router.post("/experiments/{experiment_id}/readiness")
def post_readiness(experiment_id: str, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _WRITE_ROLES)

    def _run():
        rows = evaluate_readiness(db, experiment_id, user.username)
        return dumps(rows)

    return _commit(db, _run)


@router.post("/readiness/{issue_id}/resolve")
def post_resolve(issue_id: str, payload: dict, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _APPROVE_ROLES)

    def _run():
        issue = resolve_issue(db, issue_id, user.username, payload.get("decision", ""), payload.get("comment"))
        return dump(issue)

    return _commit(db, _run)


@router.get("/experiments/{experiment_id}/issues")
def list_issues(experiment_id: str, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _READ_ROLES)
    rows = db.query(LabReadinessIssue).filter(LabReadinessIssue.experiment_id == experiment_id).all()
    return dumps(rows)


@router.post("/experiments/{experiment_id}/ingest")
async def post_ingest(
    experiment_id: str,
    user: CurrentUser,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    _role(user, _WRITE_ROLES)
    content = await file.read()

    def _run():
        return ingest_bytes(db, content=content, filename=file.filename or "upload.csv", experiment_id=experiment_id, actor=user.username)

    return _commit(db, _run)


@router.get("/experiments/{experiment_id}/ingestion")
def get_ingestion(experiment_id: str, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _READ_ROLES)
    from app.lab.models import LabMeasurement, LabRawDataFile, LabRun

    raws = db.query(LabRawDataFile).filter(LabRawDataFile.experiment_id == experiment_id).all()
    flags = db.query(LabDataQualityFlag).filter(LabDataQualityFlag.experiment_id == experiment_id).all()
    runs = db.query(LabRun).filter(LabRun.experiment_id == experiment_id).all()
    measurements = db.query(LabMeasurement).filter(LabMeasurement.experiment_id == experiment_id, LabMeasurement.status == "active").all()
    return {"files": dumps(raws), "flags": dumps(flags), "runs": dumps(runs), "measurements": dumps(measurements)}


@router.post("/experiments/{experiment_id}/results")
def post_results(experiment_id: str, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _WRITE_ROLES)
    return _commit(db, lambda: compile_results(db, experiment_id, user.username))


@router.get("/experiments/{experiment_id}/results")
def get_results(experiment_id: str, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _READ_ROLES)
    return {
        "results": dumps(active_results(db, experiment_id)),
        "insights": dumps(active_insights(db, experiment_id)),
        "data_origin": "synthetic",
    }


@router.post("/experiments/{experiment_id}/dossier")
def post_dossier(experiment_id: str, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _WRITE_ROLES)

    def _run():
        dossier = generate_dossier(db, experiment_id, user.username)
        return dump(dossier)

    return _commit(db, _run)


@router.get("/dossiers/{dossier_id}")
def get_dossier(dossier_id: str, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _READ_ROLES)
    dossier = db.get(LabExperimentDossier, dossier_id)
    if dossier is None:
        raise LabError("Dossier not found.", status_code=404, code="not_found")
    payload = dump(dossier)
    payload["eln"] = eln_status(dossier.id, "Experiment dossier")
    return payload


@router.post("/dossiers/{dossier_id}/decision")
def post_dossier_decision(dossier_id: str, payload: dict, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _APPROVE_ROLES)

    def _run():
        dossier = decide_dossier(db, dossier_id, payload.get("decision", ""), user.username, payload.get("comment"))
        return dump(dossier)

    return _commit(db, _run)


@router.get("/dossiers/{dossier_id}/export")
def export_dossier(dossier_id: str, user: CurrentUser, format: str = "pdf", db: Session = Depends(get_db)):
    _role(user, _READ_ROLES)
    dossier = db.get(LabExperimentDossier, dossier_id)
    if dossier is None:
        raise LabError("Dossier not found.", status_code=404, code="not_found")
    path = dossier.pdf_path if format == "pdf" else dossier.docx_path
    if not path:
        raise LabError("Dossier file has not been rendered.", status_code=404, code="not_found")
    media = "application/pdf" if format == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    filename = f"experiment-dossier-v{dossier.version}.{'pdf' if format == 'pdf' else 'docx'}"
    return FileResponse(path, media_type=media, filename=filename, headers={"X-Dossier-Publishable": str(bool(dossier.publishable)).lower()})


@router.get("/experiments/{experiment_id}/what-if")
def get_what_if(experiment_id: str, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _READ_ROLES)
    return what_if(db, experiment_id)


@router.post("/experiments/{experiment_id}/follow-up")
def post_follow_up(experiment_id: str, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _WRITE_ROLES)
    return _commit(db, lambda: dump(create_follow_up(db, experiment_id, user.username)))


@router.get("/experiments/{experiment_id}/storyline")
def get_storyline(experiment_id: str, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _READ_ROLES)
    return storyline(db, experiment_id)


@router.get("/experiments/{experiment_id}/lineage")
def get_experiment_lineage(experiment_id: str, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _READ_ROLES)
    return lineage(db, f"experiment:{experiment_id}")


@router.get("/fixtures/vicell-current.csv")
def fixture_csv(user: CurrentUser):
    _role(user, _READ_ROLES)
    return Response(
        content=current_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=vicell-current-synthetic.csv"},
    )


@router.get("/fixtures/vicell-planned.csv")
def fixture_planned_csv(experiment_id: str, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _READ_ROLES)
    experiment = db.get(LabExperiment, experiment_id)
    if experiment is None:
        raise LabError("Experiment not found.", status_code=404, code="not_found")
    plan = db.get(LabExperimentPlan, experiment.plan_id)
    parameters = (plan.parameters_json or {}) if plan else {}
    version = db.get(LabProtocolVersion, plan.protocol_version_id) if plan else None
    protocol = db.get(LabProtocol, version.protocol_id) if version else None
    serial = str(parameters.get("instrument_serial") or "VC-XR-1042")
    code = getattr(protocol, "code", None)
    sequencing = code == "SYN-SEQ-001"
    content = sequencing_csv(serial) if sequencing else planned_csv(parameters.get("seeding_density_cells_per_ml"), code, serial)
    filename = "sequencing-summary-synthetic.csv" if sequencing else "vicell-planned-synthetic.csv"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/entities/{entity_type}")
def list_entities(entity_type: str, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _READ_ROLES)
    model = ENTITY_MODELS.get(entity_type)
    if model is None:
        raise LabError(f"Unknown entity type {entity_type}.", status_code=404, code="unknown_entity")
    return dumps(db.query(model).all())


@router.get("/entities/{entity_type}/{entity_id}")
def get_entity(entity_type: str, entity_id: str, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _READ_ROLES)
    model = ENTITY_MODELS.get(entity_type)
    if model is None:
        raise LabError(f"Unknown entity type {entity_type}.", status_code=404, code="unknown_entity")
    row = db.get(model, entity_id)
    if row is None:
        raise LabError("Entity not found.", status_code=404, code="not_found")
    return dump(row)


@router.post("/entities/{entity_type}/{entity_id}/corrections")
def post_correction(entity_type: str, entity_id: str, payload: dict, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _WRITE_ROLES)
    if entity_type == "raw_data_file":
        reject_raw_mutation()
    if entity_type != "measurement":
        raise LabError("Only measurements can be corrected with a new version.", status_code=409, code="not_correctable")

    def _run():
        revised = correct_measurement(db, entity_id, float(payload["value"]), payload.get("reason") or "scientist correction", user.username)
        return dump(revised)

    return _commit(db, _run)


@router.post("/graph/query")
def post_graph_query(payload: dict, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _READ_ROLES)
    return query_relationships(db, payload.get("start") or payload.get("entity_ref"), payload.get("relationship"), int(payload.get("depth") or 2))


@router.get("/graph/lineage/{entity_ref:path}")
def get_lineage(entity_ref: str, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _READ_ROLES)
    found = lineage(db, entity_ref)
    if not found:
        raise LabError("Entity not found.", status_code=404, code="not_found")
    return found


@router.get("/ontology/lookup")
def get_ontology(q: str, user: CurrentUser, limit: int = 10):
    _role(user, _READ_ROLES)
    return {"query": q, "terms": lookup(q, limit)}


@router.post("/ontology/map")
def post_ontology_map(payload: dict, user: CurrentUser):
    _role(user, _READ_ROLES)
    headers = payload.get("headers")
    if headers:
        return {"mappings": map_headers(headers)}
    if "header" not in payload:
        raise LabError("Provide header or headers.", status_code=422, code="header_required")
    return map_header(payload["header"])


@router.get("/documents/search")
def search_documents(q: str, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _READ_ROLES)
    needle = q.lower().strip()
    hits = []
    for section in db.query(LabDocumentSection).all():
        hay = f"{section.heading}\n{section.body}".lower()
        if needle and needle in hay:
            hits.append(
                {
                    "document_id": section.document_id,
                    "protocol_version_id": section.protocol_version_id,
                    "heading": section.heading,
                    "citation": section.citation_label,
                    "excerpt": section.body[:400],
                    "data_origin": "synthetic",
                }
            )
    return {"query": q, "hits": hits}


@router.post("/events/publish")
def post_event(payload: dict, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _WRITE_ROLES)

    def _run():
        from app.config import settings

        event_type = payload.get("event_type") or ""
        if event_type == "ExperimentCompleted" and not settings.lab_emit_experiment_completed:
            row = LabEvent(event_type=event_type, payload_json=payload.get("payload") or {}, published=False, suppressed_reason="feature_flag_disabled")
            db.add(row)
            db.flush()
            return dump(row)
        subscribers = [item.subscriber for item in db.query(LabSubscription).filter(LabSubscription.event_type == event_type).all()]
        row = LabEvent(
            event_type=event_type,
            payload_json={**(payload.get("payload") or {}), "subscribers": subscribers},
            published=True,
        )
        db.add(row)
        db.flush()
        return dump(row)

    return _commit(db, _run)


@router.post("/events/subscribe")
def post_subscribe(payload: dict, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _WRITE_ROLES)

    def _run():
        row = LabSubscription(event_type=payload["event_type"], subscriber=payload["subscriber"])
        db.add(row)
        db.flush()
        return dump(row)

    return _commit(db, _run)


@router.get("/audit/{entity_ref:path}")
def get_audit(entity_ref: str, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _READ_ROLES)
    rows = history(db, entity_ref)
    return [
        {
            "id": row.id,
            "event_type": row.event_type,
            "actor": row.actor,
            "resource_type": row.resource_type,
            "resource_id": row.resource_id,
            "action": row.action,
            "details": row.details_json,
            "created_at": row.created_at.isoformat() + "Z" if row.created_at else None,
        }
        for row in rows
    ]


@router.post("/assistant/ask")
def post_assistant_ask(payload: dict, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _READ_ROLES)
    question = str(payload.get("question") or "").strip()
    if not question:
        raise LabError("Ask a question.", status_code=400, code="question_required")
    if len(question) > 1000:
        raise LabError("Ask a shorter question.", status_code=400, code="question_too_long")
    history = payload.get("history") if isinstance(payload.get("history"), list) else []
    experiment_id = payload.get("experiment_id") or None
    draft = payload.get("draft") if isinstance(payload.get("draft"), dict) else None
    return answer_question(db, question[:1000], history[:8], experiment_id, draft)


@router.post("/assistant/draft")
def post_assistant_draft(payload: dict, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _READ_ROLES)
    intent = str(payload.get("intent") or "").strip()
    if len(intent) < 8:
        raise LabError("Describe what you want this experiment to do.", status_code=400, code="intent_required")
    return draft_from_intent(db, intent[:1000])


@router.get("/agents")
def list_agents(user: CurrentUser):
    _role(user, _READ_ROLES)
    return AGENTS


@router.post("/agents/{agent_id}/invoke")
def post_invoke(
    agent_id: str,
    payload: dict,
    user: CurrentUser,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    _role(user, _WRITE_ROLES)

    def _run():
        job = invoke(
            db,
            agent_id,
            payload.get("experiment_id") or payload.get("experimentId"),
            payload.get("trigger") or "",
            payload.get("context") or {},
            user.username,
            idempotency_key or payload.get("idempotency_key"),
        )
        body = dump(job)
        body["correlation_id"] = job.correlation_id
        return body

    return _commit(db, _run)


@router.get("/agents/jobs/{job_id}")
def job_status(job_id: str, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _READ_ROLES)
    return dump(get_status(db, job_id))


@router.get("/agents/{agent_id}/outputs")
def agent_outputs(agent_id: str, experimentId: str, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _READ_ROLES)
    return get_outputs(db, agent_id, experimentId)


@router.get("/agents/{agent_id}/explain")
def agent_explain(agent_id: str, entityRef: str, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _READ_ROLES)
    return explain(db, agent_id, entityRef)


@router.get("/agents/{agent_id}/health")
def agent_health(agent_id: str, user: CurrentUser, db: Session = Depends(get_db)):
    _role(user, _READ_ROLES)
    if agent_id not in AGENTS:
        raise LabError(f"Unknown agent {agent_id}.", status_code=404, code="unknown_agent")
    payload = health(db)
    payload["agent_id"] = agent_id
    return payload
