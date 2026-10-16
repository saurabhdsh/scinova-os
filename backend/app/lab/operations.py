"""Planning, readiness, gates, and follow-up plans."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.lab.adapters import eln_adapter
from app.lab.audit import record
from app.lab.errors import LabError
from app.lab.graph_bridge import link, publish
from app.lab.models import (
    LabComplianceRule,
    LabExperiment,
    LabExperimentPlan,
    LabGateDecision,
    LabInstrument,
    LabLot,
    LabProtocolVersion,
    LabReadinessIssue,
    LabRun,
    LabRunSchedule,
    LabSample,
    LabTrainingRecord,
)
from app.lab.results import recommendation
from app.lab.rules import load_rules
from app.models.db_models import GraphNode


def create_plan(
    db: Session,
    *,
    protocol_version_id: str,
    actor: str,
    title: str | None = None,
    parameters: dict | None = None,
) -> LabExperimentPlan:
    version = db.get(LabProtocolVersion, protocol_version_id)
    if version is None:
        raise LabError("Protocol version not found.", status_code=404, code="not_found")
    if version.status != "approved":
        raise LabError("Only an approved protocol version can be planned.", status_code=409, code="protocol_not_approved")
    merged = dict(version.parameters_json or {})
    if parameters:
        merged.update(parameters)
    plan = LabExperimentPlan(
        protocol_version_id=version.id,
        title=title or f"Plan from {version.version_label}",
        status="draft",
        parameters_json=merged,
        success_criteria_json=list(version.success_criteria_json or []),
        sample_panel_json=list(version.sample_panel_json or []),
        expected_readouts_json=list(version.expected_readouts_json or []),
        cited_insight_ids_json=[],
        produced_by="LAB-A1",
        data_origin="synthetic",
        created_by=actor,
    )
    db.add(plan)
    db.flush()
    publish(db, plan, entity_type="ExperimentPlan", label=plan.title, document_id=version.document_id)
    _link_plan_to_protocol(db, plan, version)
    record(
        db,
        event_type="plan_created",
        actor=actor,
        resource_type="experiment_plan",
        resource_id=plan.id,
        action="Created an experiment plan from an approved protocol version",
        details={"protocol_version_id": version.id, "parameters": merged},
    )
    return plan


def approve_plan(db: Session, plan_id: str, actor: str, comment: str | None = None) -> LabExperiment:
    plan = db.get(LabExperimentPlan, plan_id)
    if plan is None:
        raise LabError("Plan not found.", status_code=404, code="not_found")
    if plan.status == "approved":
        existing = db.query(LabExperiment).filter(LabExperiment.plan_id == plan.id).first()
        if existing:
            return existing
    if plan.status != "draft":
        raise LabError(f"Plan cannot be approved from status {plan.status}.", status_code=409, code="gate_closed")
    plan.status = "approved"
    version = db.get(LabProtocolVersion, plan.protocol_version_id)
    experiment = LabExperiment(
        plan_id=plan.id,
        title=plan.title.replace("Plan", "Experiment", 1) if plan.title.startswith("Plan") else plan.title,
        status="planned",
        produced_by="LAB-A1",
        source_document_id=version.document_id if version else None,
        data_origin="synthetic",
        created_by=actor,
    )
    db.add(experiment)
    db.flush()
    samples = []
    for spec in plan.sample_panel_json or []:
        sample = LabSample(
            experiment_id=experiment.id,
            sample_code=spec["sample_code"],
            cell_line=spec.get("cell_line"),
            cell_line_ontology=spec.get("cell_line_ontology"),
            passage=spec.get("passage"),
            qc_status=spec.get("qc_status", "pass"),
            lineage_json=spec.get("lineage") or {},
            data_origin="synthetic",
            created_by=actor,
        )
        db.add(sample)
        samples.append(sample)
    serial = (plan.parameters_json or {}).get("instrument_serial")
    instrument = db.query(LabInstrument).filter(LabInstrument.serial_number == serial).first() if serial else None
    if instrument is None:
        raise LabError(f"No instrument is registered for serial {serial}.", status_code=409, code="instrument_missing")
    run = LabRun(
        experiment_id=experiment.id,
        instrument_id=instrument.id,
        run_code=f"RUN-{experiment.id[:8]}",
        status="scheduled",
        expected_readouts_json=list(plan.expected_readouts_json or []),
        data_origin="synthetic",
        created_by=actor,
    )
    db.add(run)
    db.flush()
    schedule = LabRunSchedule(
        run_id=run.id,
        operator_name=(plan.parameters_json or {}).get("operator"),
        instrument_id=instrument.id,
        reagent_lot=(plan.parameters_json or {}).get("reagent_lot"),
        status="scheduled",
        created_by=actor,
    )
    db.add(schedule)
    db.flush()
    _record_gate(db, gate="G1", experiment_id=experiment.id, entity_type="experiment_plan", entity_id=plan.id, decision="approve", actor=actor, comment=comment, version=plan.version)
    exp_node = publish(db, experiment, entity_type="Experiment", label=experiment.title, document_id=experiment.source_document_id)
    plan_node = db.get(GraphNode, plan.graph_node_id) if plan.graph_node_id else None
    link(db, exp_node, plan_node, "EXECUTES")
    run_node = publish(db, run, entity_type="Run", label=run.run_code, document_id=experiment.source_document_id)
    link(db, exp_node, run_node, "HAS_RUN")
    inst_node = publish(db, instrument, entity_type="Instrument", label=instrument.serial_number, document_id=experiment.source_document_id)
    link(db, run_node, inst_node, "USES_INSTRUMENT")
    sched_node = publish(db, schedule, entity_type="RunSchedule", label=schedule.operator_name or "schedule", document_id=experiment.source_document_id)
    link(db, run_node, sched_node, "SCHEDULED_BY")
    for sample in samples:
        sample_node = publish(
            db,
            sample,
            entity_type="Sample",
            label=sample.sample_code,
            document_id=experiment.source_document_id,
            ontology_id=sample.cell_line_ontology,
        )
        link(db, exp_node, sample_node, "HAS_SAMPLE")
    return experiment


def evaluate_readiness(db: Session, experiment_id: str, actor: str) -> list[LabReadinessIssue]:
    experiment = _experiment(db, experiment_id)
    plan = db.get(LabExperimentPlan, experiment.plan_id)
    run = _run(db, experiment_id)
    schedule = db.query(LabRunSchedule).filter(LabRunSchedule.run_id == run.id).first()
    instrument = db.get(LabInstrument, run.instrument_id)
    created = []
    lot_number = (plan.parameters_json or {}).get("reagent_lot")
    lot = db.query(LabLot).filter(LabLot.lot_number == lot_number).first() if lot_number else None
    if lot is not None and (lot.expires_on - date.today()).days <= 30:
        alternative = db.get(LabLot, lot.approved_alternative_lot_id) if lot.approved_alternative_lot_id else None
        created.append(
            _issue(
                db,
                experiment,
                agent_id="LAB-A2",
                code="NEAR_EXPIRY",
                message=f"Lot {lot.lot_number} expires on {lot.expires_on.isoformat()}.",
                recommendation={
                    "action": "swap_lot",
                    "lot_number": alternative.lot_number if alternative else None,
                    "alternative_lot_id": alternative.id if alternative else None,
                },
                actor=actor,
            )
        )
    if instrument is not None and instrument.calibration_status != "current":
        alternate = (
            db.query(LabInstrument)
            .filter(LabInstrument.calibration_status == "current", LabInstrument.id != instrument.id)
            .first()
        )
        created.append(
            _issue(
                db,
                experiment,
                agent_id="LAB-A3",
                code="CALIBRATION_DUE",
                message=f"Instrument {instrument.serial_number} calibration status is {instrument.calibration_status}.",
                recommendation={
                    "action": "use_alternate_instrument",
                    "instrument_serial": alternate.serial_number if alternate else None,
                    "instrument_id": alternate.id if alternate else None,
                },
                actor=actor,
            )
        )
    operator = schedule.operator_name if schedule else None
    protocol_id = db.get(LabProtocolVersion, plan.protocol_version_id).protocol_id
    training = (
        db.query(LabTrainingRecord)
        .filter(LabTrainingRecord.person_name == operator, LabTrainingRecord.protocol_id == protocol_id)
        .first()
        if operator
        else None
    )
    if training is None or not training.qualified:
        qualified = (
            db.query(LabTrainingRecord)
            .filter(
                LabTrainingRecord.protocol_id == protocol_id,
                LabTrainingRecord.qualified.is_(True),
                LabTrainingRecord.person_name != operator,
            )
            .all()
        )
        alternate = next((row for row in qualified if row.person_name == "Priya Nair"), None)
        if alternate is None and qualified:
            alternate = qualified[0]
        created.append(
            _issue(
                db,
                experiment,
                agent_id="LAB-A4",
                code="TRAINING_GAP",
                message=f"Operator {operator} is not qualified on this protocol.",
                recommendation={
                    "action": "assign_alternate",
                    "operator_name": alternate.person_name if alternate else None,
                },
                actor=actor,
            )
        )
    violated = [row.code for row in db.query(LabComplianceRule).filter(LabComplianceRule.blocks_execution.is_(True)).all()]
    if created:
        created.append(
            _issue(
                db,
                experiment,
                agent_id="LAB-A5",
                code="COMPLIANCE_HOLD",
                message="Compliance rules block execution while calibration, training, or lot-expiry issues are open: " + ", ".join(violated),
                recommendation={"action": "resolve_blocking_issues", "rules": violated},
                actor=actor,
            )
        )
    experiment.status = "ready_for_ingestion" if not _open_blocking(db, experiment_id) else "readiness_blocked"
    record(
        db,
        event_type="readiness_evaluated",
        actor=actor,
        resource_type="experiment",
        resource_id=experiment.id,
        action="Evaluated readiness across LAB-A2 through LAB-A5",
        details={"open_issue_ids": [row.id for row in _open_blocking(db, experiment_id)], "status": experiment.status},
    )
    db.flush()
    return db.query(LabReadinessIssue).filter(LabReadinessIssue.experiment_id == experiment_id).all()


def resolve_issue(db: Session, issue_id: str, actor: str, decision: str, comment: str | None = None) -> LabReadinessIssue:
    issue = db.get(LabReadinessIssue, issue_id)
    if issue is None:
        raise LabError("Readiness issue not found.", status_code=404, code="not_found")
    if issue.status != "open":
        raise LabError("Issue is already closed.", status_code=409, code="gate_closed")
    if decision != "approve":
        _record_gate(
            db,
            gate="G2",
            experiment_id=issue.experiment_id,
            entity_type="readiness_issue",
            entity_id=issue.id,
            decision=decision,
            actor=actor,
            comment=comment,
            version=1,
        )
        if decision == "reject":
            issue.status = "rejected"
        return issue
    experiment = _experiment(db, issue.experiment_id)
    plan = db.get(LabExperimentPlan, experiment.plan_id)
    run = _run(db, experiment.id)
    schedule = db.query(LabRunSchedule).filter(LabRunSchedule.run_id == run.id).first()
    params = dict(plan.parameters_json or {})
    action = (issue.recommendation_json or {}).get("action")
    if action == "swap_lot":
        params["reagent_lot"] = issue.recommendation_json["lot_number"]
        if schedule:
            schedule.reagent_lot = params["reagent_lot"]
    elif action == "use_alternate_instrument":
        params["instrument_serial"] = issue.recommendation_json["instrument_serial"]
        run.instrument_id = issue.recommendation_json["instrument_id"]
        if schedule:
            schedule.instrument_id = run.instrument_id
    elif action == "assign_alternate":
        params["operator"] = issue.recommendation_json["operator_name"]
        if schedule:
            schedule.operator_name = params["operator"]
    elif action == "resolve_blocking_issues":
        still_open = (
            db.query(LabReadinessIssue)
            .filter(
                LabReadinessIssue.experiment_id == experiment.id,
                LabReadinessIssue.status == "open",
                LabReadinessIssue.id != issue.id,
                LabReadinessIssue.severity == "blocking",
            )
            .count()
        )
        if still_open:
            raise LabError(
                "Resolve the material, instrument, and training issues before releasing the compliance hold.",
                status_code=409,
                code="compliance_hold",
            )
    else:
        raise LabError("This issue has no approved corrective action.", status_code=409, code="no_action")
    plan.parameters_json = params
    issue.status = "resolved"
    issue.resolution_json = {"action": action, "actor": actor, "comment": comment, "parameters": params}
    _record_gate(
        db,
        gate="G2",
        experiment_id=experiment.id,
        entity_type="readiness_issue",
        entity_id=issue.id,
        decision="approve",
        actor=actor,
        comment=comment,
        version=1,
    )
    experiment.status = "ready_for_ingestion" if not _open_blocking(db, experiment.id) else "readiness_blocked"
    db.flush()
    return issue


def what_if(db: Session, experiment_id: str) -> dict:
    experiment = _experiment(db, experiment_id)
    plan = db.get(LabExperimentPlan, experiment.plan_id)
    insight = recommendation(db, experiment_id)
    proposed = dict(plan.parameters_json or {})
    change = None
    if insight is not None:
        evidence = insight.evidence_json or {}
        parameter = evidence.get("parameter")
        if parameter and evidence.get("proposed_value") is not None:
            proposed[parameter] = evidence["proposed_value"]
            change = {
                "parameter": parameter,
                "from": (plan.parameters_json or {}).get(parameter),
                "to": evidence["proposed_value"],
                "insight_id": insight.id,
                "rule_id": insight.rule_id,
            }
    return {
        "experiment_id": experiment_id,
        "persisted": False,
        "current_parameters": plan.parameters_json,
        "proposed_parameters": proposed,
        "change": change,
        "elapsed_scope": "what_if",
    }


def create_follow_up(db: Session, experiment_id: str, actor: str) -> LabExperimentPlan:
    experiment = _experiment(db, experiment_id)
    plan = db.get(LabExperimentPlan, experiment.plan_id)
    insight = recommendation(db, experiment_id)
    if insight is None:
        raise LabError("No recommendation insight is available for a follow-up plan.", status_code=409, code="insight_required")
    preview = what_if(db, experiment_id)
    if not preview["change"]:
        raise LabError("The recommendation does not change a parameter.", status_code=409, code="no_parameter_change")
    version = db.get(LabProtocolVersion, plan.protocol_version_id)
    follow = LabExperimentPlan(
        protocol_version_id=plan.protocol_version_id,
        title=f"Follow-up plan citing {insight.rule_id}",
        status="draft",
        parameters_json=preview["proposed_parameters"],
        success_criteria_json=list(plan.success_criteria_json or []),
        sample_panel_json=list(plan.sample_panel_json or []),
        expected_readouts_json=list(plan.expected_readouts_json or []),
        cited_insight_ids_json=[insight.id],
        parent_plan_id=plan.id,
        produced_by="LAB-A1",
        data_origin="synthetic",
        created_by=actor,
    )
    db.add(follow)
    db.flush()
    follow_node = publish(db, follow, entity_type="ExperimentPlan", label=follow.title, document_id=version.document_id if version else None)
    _link_plan_to_protocol(db, follow, version)
    if insight.graph_node_id:
        link(db, follow_node, db.get(GraphNode, insight.graph_node_id), "CITES_INSIGHT")
    if plan.graph_node_id:
        link(db, follow_node, db.get(GraphNode, plan.graph_node_id), "FOLLOWS_PLAN")
    record(
        db,
        event_type="follow_up_planned",
        actor=actor,
        resource_type="experiment_plan",
        resource_id=follow.id,
        action="Created a follow-up plan from a cited insight",
        details={
            "experiment_id": experiment_id,
            "insight_id": insight.id,
            "change": preview["change"],
            "parent_plan_id": plan.id,
        },
    )
    return follow


def storyline(db: Session, experiment_id: str) -> dict:
    experiment = _experiment(db, experiment_id)
    plan = db.get(LabExperimentPlan, experiment.plan_id)
    issues = db.query(LabReadinessIssue).filter(LabReadinessIssue.experiment_id == experiment_id).all()
    from app.lab.models import LabExperimentDossier, LabRawDataFile

    raw = db.query(LabRawDataFile).filter(LabRawDataFile.experiment_id == experiment_id).first()
    dossier = (
        db.query(LabExperimentDossier)
        .filter(LabExperimentDossier.experiment_id == experiment_id)
        .order_by(LabExperimentDossier.version.desc())
        .first()
    )
    follow = db.query(LabExperimentPlan).filter(LabExperimentPlan.parent_plan_id == plan.id).first()
    gates = (
        db.query(LabGateDecision)
        .filter(LabGateDecision.experiment_id == experiment_id)
        .order_by(LabGateDecision.created_at.asc())
        .all()
    )
    open_blocking = [row for row in issues if row.status == "open" and row.severity == "blocking"]
    change = None
    if follow is not None:
        before = (plan.parameters_json or {}).get("seeding_density_cells_per_ml")
        after = (follow.parameters_json or {}).get("seeding_density_cells_per_ml")
        change = {"parameter": "seeding_density_cells_per_ml", "from": before, "to": after, "insight_ids": follow.cited_insight_ids_json}
    moments = {
        "moment_1_planning": {"complete": plan.status == "approved", "plan_id": plan.id, "plan_status": plan.status},
        "moment_2_readiness": {
            "complete": bool(issues) and not open_blocking,
            "open_blocking": len(open_blocking),
            "issue_count": len(issues),
        },
        "moment_3_ingestion": {
            "complete": bool(raw and raw.checksum_verified),
            "raw_file_id": raw.id if raw else None,
            "sha256": raw.sha256 if raw else None,
            "completeness_percent": _run(db, experiment_id).completeness_percent,
        },
        "moment_4_results": {
            "complete": dossier is not None and experiment.outcome is not None,
            "outcome": experiment.outcome,
            "dossier_id": dossier.id if dossier else None,
            "dossier_status": dossier.status if dossier else None,
            "publishable": dossier.publishable if dossier else False,
        },
        "moment_5_learning": {
            "complete": bool(change and change["from"] != change["to"] and change["insight_ids"]),
            "follow_up_plan_id": follow.id if follow else None,
            "change": change,
        },
    }
    return {
        "experiment_id": experiment_id,
        "status": experiment.status,
        "data_origin": experiment.data_origin,
        "moments": moments,
        "gates": [
            {"gate": row.gate, "decision": row.decision, "actor": row.actor, "entity_id": row.entity_id, "created_at": row.created_at.isoformat() + "Z"}
            for row in gates
        ],
    }


def eln_status(dossier_id: str, title: str) -> dict:
    return eln_adapter().attach_report(dossier_id, title)


def _issue(db, experiment, *, agent_id, code, message, recommendation, actor) -> LabReadinessIssue:
    existing = (
        db.query(LabReadinessIssue)
        .filter(LabReadinessIssue.experiment_id == experiment.id, LabReadinessIssue.code == code, LabReadinessIssue.status == "open")
        .first()
    )
    if existing:
        return existing
    row = LabReadinessIssue(
        experiment_id=experiment.id,
        agent_id=agent_id,
        code=code,
        severity="blocking",
        message=message,
        recommendation_json=recommendation,
        created_by=actor,
    )
    db.add(row)
    db.flush()
    record(
        db,
        event_type="readiness_issue",
        actor=actor,
        resource_type="readiness_issue",
        resource_id=row.id,
        action=f"{agent_id} raised {code}",
        details={"experiment_id": experiment.id, "code": code, "recommendation": recommendation},
    )
    return row


def _record_gate(db, *, gate, experiment_id, entity_type, entity_id, decision, actor, comment, version):
    row = LabGateDecision(
        gate=gate,
        experiment_id=experiment_id,
        entity_type=entity_type,
        entity_id=entity_id,
        decision=decision,
        actor=actor,
        comment=comment,
        entity_version=version,
    )
    db.add(row)
    db.flush()
    record(
        db,
        event_type="gate_decision",
        actor=actor,
        resource_type=entity_type,
        resource_id=entity_id,
        action=f"{gate} {decision}",
        details={"gate": gate, "decision": decision, "experiment_id": experiment_id, "comment": comment, "version": version},
    )
    return row


def _link_plan_to_protocol(db, plan, version):
    if version is None or not plan.graph_node_id or not version.graph_node_id:
        return
    link(db, db.get(GraphNode, plan.graph_node_id), db.get(GraphNode, version.graph_node_id), "FOLLOWS")


def _experiment(db, experiment_id: str) -> LabExperiment:
    experiment = db.get(LabExperiment, experiment_id)
    if experiment is None:
        raise LabError("Experiment not found.", status_code=404, code="not_found")
    return experiment


def _run(db, experiment_id: str) -> LabRun:
    run = db.query(LabRun).filter(LabRun.experiment_id == experiment_id).order_by(LabRun.created_at.asc()).first()
    if run is None:
        raise LabError("Experiment has no run.", status_code=409, code="run_missing")
    return run


def _open_blocking(db, experiment_id: str) -> list[LabReadinessIssue]:
    return (
        db.query(LabReadinessIssue)
        .filter(
            LabReadinessIssue.experiment_id == experiment_id,
            LabReadinessIssue.status == "open",
            LabReadinessIssue.severity == "blocking",
        )
        .all()
    )


def apply_rule_parameter(current: dict, insight_evidence: dict) -> dict:
    """Pure helper used by tests and what-if. Does not invent a factor."""
    rules = load_rules(None)
    rule = rules[insight_evidence.get("rule_id", "LAB-RULE-NEXT-001")]
    updated = dict(current)
    parameter = insight_evidence.get("parameter") or rule["parameter"]
    if parameter in updated and isinstance(updated[parameter], (int, float)):
        updated[parameter] = round(float(updated[parameter]) * float(rule["factor"]), 4)
    return updated
