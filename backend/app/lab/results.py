"""FR-RC results, historical comparison, and rule-based insights. All numbers come from stats.py."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.lab.audit import record
from app.lab.errors import LabError
from app.lab.graph_bridge import link, publish
from app.lab.models import (
    LabExperiment,
    LabExperimentPlan,
    LabInsight,
    LabMeasurement,
    LabResult,
    LabSample,
)
from app.lab.rules import NARRATIVE_MODEL_VERSION, load_rules
from app.lab.stats import coefficient_of_variation, compare, mean, outcome_label, round_sci, sample_stdev


def compile_results(db: Session, experiment_id: str, actor: str) -> dict:
    experiment = db.get(LabExperiment, experiment_id)
    if experiment is None:
        raise LabError("Experiment not found.", status_code=404, code="not_found")
    plan = db.get(LabExperimentPlan, experiment.plan_id)
    measurements = (
        db.query(LabMeasurement)
        .filter(
            LabMeasurement.experiment_id == experiment_id,
            LabMeasurement.status == "active",
            LabMeasurement.sample_id.isnot(None),
            LabMeasurement.readout_key == "viability_percent",
        )
        .all()
    )
    if not measurements:
        raise LabError("No matched viability measurements are available to compile.", status_code=409, code="no_measurements")

    _supersede(db, LabResult, experiment_id)
    _supersede(db, LabInsight, experiment_id)

    values = [item.value for item in measurements]
    ids = [item.id for item in measurements]
    avg = round_sci(mean(values), 4)
    cv = round_sci(coefficient_of_variation(values), 4)
    rules = load_rules(db)
    criteria = {item["id"]: item for item in (plan.success_criteria_json or [])}
    metric_values = {"mean_viability_percent": avg, "cv_percent": cv}
    results = []
    for metric, value in metric_values.items():
        criterion = next((item for item in criteria.values() if item.get("metric") == metric), None)
        if criterion is None and metric == "cv_percent":
            rule = rules["LAB-RULE-CV-001"]
            criterion = {"id": rule["id"], "metric": metric, "operator": "<=", "threshold": rule["threshold"], "unit": rule["unit"]}
            # A missing plan criterion still records the statistic, but only plan criteria decide pass/fail.
            passed = None
            outcome = "not_applicable"
        else:
            passed = compare(criterion["operator"], value, float(criterion["threshold"])) if criterion else None
            outcome = outcome_label(passed) if passed is not None else "not_applicable"
        result = LabResult(
            experiment_id=experiment_id,
            metric=metric,
            value=value,
            unit=(criterion or {}).get("unit", "percent"),
            criterion_id=(criterion or {}).get("id"),
            operator=(criterion or {}).get("operator"),
            threshold=(criterion or {}).get("threshold"),
            outcome=outcome,
            measurement_ids_json=ids,
            calculation_json={
                "method": "sample_cv_percent" if metric == "cv_percent" else "arithmetic_mean",
                "n": len(values),
                "values": values,
                "measurement_ids": ids,
                "data_origin": "synthetic",
            },
            produced_by="LAB-A6",
            data_origin="synthetic",
            created_by=actor,
        )
        db.add(result)
        results.append(result)
    db.flush()

    history = _historical_means(db, experiment, plan)
    insights = _insights(db, experiment, measurements, results, history, rules, actor)
    for result in results:
        node = publish(
            db,
            result,
            entity_type="Result",
            label=f"{result.metric} {result.outcome}",
            document_id=experiment.source_document_id,
            extra={"value": result.value, "outcome": result.outcome},
        )
        for measurement in measurements:
            if measurement.graph_node_id:
                from app.models.db_models import GraphNode

                link(db, node, db.get(GraphNode, measurement.graph_node_id), "AGGREGATES")
    for insight in insights:
        node = publish(
            db,
            insight,
            entity_type="Insight",
            label=insight.title,
            document_id=experiment.source_document_id,
            extra={"rule_id": insight.rule_id, "insight_type": insight.insight_type},
        )
        for result in results:
            if result.graph_node_id:
                from app.models.db_models import GraphNode

                link(db, node, db.get(GraphNode, result.graph_node_id), "BASED_ON")

    decided = [item for item in results if item.outcome in {"pass", "fail"}]
    experiment.outcome = "fail" if any(item.outcome == "fail" for item in decided) else "pass"
    experiment.status = "results_ready"
    record(
        db,
        event_type="results_compiled",
        actor=actor,
        resource_type="experiment",
        resource_id=experiment.id,
        action="Compiled experiment results and insights",
        details={
            "outcome": experiment.outcome,
            "result_ids": [item.id for item in results],
            "insight_ids": [item.id for item in insights],
            "model_version": NARRATIVE_MODEL_VERSION,
            "llm_called": False,
        },
    )
    db.flush()
    return {
        "experiment_id": experiment.id,
        "outcome": experiment.outcome,
        "results": [_result_dict(item) for item in results],
        "insights": [_insight_dict(item) for item in insights],
        "historical_comparator_ids": [item["experiment_id"] for item in history],
        "data_origin": "synthetic",
    }


def _supersede(db: Session, model, experiment_id: str) -> None:
    rows = db.query(model).filter(model.experiment_id == experiment_id, model.status == "active").all()
    for row in rows:
        row.status = "superseded"


def _historical_means(db: Session, experiment: LabExperiment, plan: LabExperimentPlan) -> list[dict]:
    cell_lines = {
        row[0]
        for row in db.query(LabSample.cell_line).filter(LabSample.experiment_id == experiment.id).all()
        if row[0]
    }
    others = (
        db.query(LabExperiment)
        .filter(LabExperiment.id != experiment.id, LabExperiment.outcome.isnot(None))
        .all()
    )
    comparable = []
    for other in others:
        other_plan = db.get(LabExperimentPlan, other.plan_id)
        if other_plan is None or other_plan.protocol_version_id != plan.protocol_version_id:
            continue
        other_lines = {
            row[0]
            for row in db.query(LabSample.cell_line).filter(LabSample.experiment_id == other.id).all()
        }
        if cell_lines and other_lines.isdisjoint(cell_lines):
            continue
        stats = _viability_stats(db, other.id)
        if stats is None:
            continue
        comparable.append({"experiment_id": other.id, **stats})
    return comparable


def _viability_stats(db: Session, experiment_id: str) -> dict | None:
    rows = (
        db.query(LabMeasurement)
        .filter(
            LabMeasurement.experiment_id == experiment_id,
            LabMeasurement.status == "active",
            LabMeasurement.sample_id.isnot(None),
            LabMeasurement.readout_key == "viability_percent",
        )
        .all()
    )
    if not rows:
        return None
    values = [row.value for row in rows]
    return {
        "mean": mean(values),
        "measurement_ids": [row.id for row in rows],
        "n": len(values),
    }


def _insights(db, experiment, measurements, results, history, rules, actor) -> list[LabInsight]:
    created = []
    abs_rule = rules["LAB-RULE-VIAB-ABS"]
    low = [item for item in measurements if compare(abs_rule["operator"], item.value, float(abs_rule["threshold"]))]
    if low:
        created.append(
            _insight(
                db,
                experiment,
                actor,
                insight_type="anomaly",
                rule_id=abs_rule["id"],
                title="Low viability measurement",
                statement=(
                    f"{len(low)} viability measurement(s) are below {abs_rule['threshold']} {abs_rule['unit']} "
                    f"({abs_rule['id']})."
                ),
                evidence={
                    "rule_id": abs_rule["id"],
                    "threshold": abs_rule["threshold"],
                    "operator": abs_rule["operator"],
                    "unit": abs_rule["unit"],
                    "calculated_values": [item.value for item in low],
                    "measurement_ids": [item.id for item in low],
                    "comparator_experiment_ids": [],
                    "comparator_measurement_ids": [],
                },
                citations=[{"entity_type": "Measurement", "id": item.id} for item in low],
            )
        )

    hist_rule = rules["LAB-RULE-VIAB-HIST"]
    mean_result = next(item for item in results if item.metric == "mean_viability_percent")
    if len(history) >= int(hist_rule["min_comparators"]) and mean_result.value is not None:
        hist_values = [item["mean"] for item in history]
        hist_mean = mean(hist_values)
        hist_sd = sample_stdev(hist_values)
        if hist_mean is not None and hist_sd is not None:
            threshold = hist_mean - (2 * hist_sd)
            if compare("<", mean_result.value, threshold):
                created.append(
                    _insight(
                        db,
                        experiment,
                        actor,
                        insight_type="anomaly",
                        rule_id=hist_rule["id"],
                        title="Viability below historical range",
                        statement=(
                            f"Mean viability {mean_result.value} is below the historical mean "
                            f"{round_sci(hist_mean, 4)} minus two sample standard deviations "
                            f"(threshold {round_sci(threshold, 4)})."
                        ),
                        evidence={
                            "rule_id": hist_rule["id"],
                            "threshold": round_sci(threshold, 4),
                            "operator": "<",
                            "unit": "percent",
                            "calculated_value": mean_result.value,
                            "historical_mean": round_sci(hist_mean, 4),
                            "historical_sd": round_sci(hist_sd, 4),
                            "comparator_experiment_ids": [item["experiment_id"] for item in history],
                            "comparator_measurement_ids": [mid for item in history for mid in item["measurement_ids"]],
                            "measurement_ids": mean_result.measurement_ids_json,
                        },
                        citations=[
                            {"entity_type": "Result", "id": mean_result.id},
                            *[{"entity_type": "Experiment", "id": item["experiment_id"]} for item in history],
                        ],
                    )
                )

    cv_result = next(item for item in results if item.metric == "cv_percent")
    cv_rule = rules["LAB-RULE-CV-001"]
    cv_threshold = float(cv_result.threshold if cv_result.threshold is not None else cv_rule["threshold"])
    if cv_result.value is not None and cv_result.value > cv_threshold:
        created.append(
            _insight(
                db,
                experiment,
                actor,
                insight_type="anomaly",
                rule_id=cv_rule["id"],
                title="High coefficient of variation",
                statement=f"Viability CV {cv_result.value} percent exceeds {cv_threshold} percent ({cv_rule['id']}).",
                evidence={
                    "rule_id": cv_rule["id"],
                    "threshold": cv_threshold,
                    "operator": ">",
                    "unit": "percent",
                    "calculated_value": cv_result.value,
                    "measurement_ids": cv_result.measurement_ids_json,
                    "comparator_experiment_ids": [item["experiment_id"] for item in history],
                    "comparator_measurement_ids": [],
                },
                citations=[{"entity_type": "Result", "id": cv_result.id}],
            )
        )

    next_rule = rules["LAB-RULE-NEXT-001"]
    if mean_result.outcome == "fail":
        current = (experiment and db.get(LabExperimentPlan, experiment.plan_id).parameters_json or {}).get(next_rule["parameter"])
        proposed = None
        if isinstance(current, (int, float)):
            proposed = round(float(current) * float(next_rule["factor"]), 4)
        created.append(
            _insight(
                db,
                experiment,
                actor,
                insight_type="recommendation",
                rule_id=next_rule["id"],
                title="Increase seeding density",
                statement=next_rule["description"],
                evidence={
                    "rule_id": next_rule["id"],
                    "parameter": next_rule["parameter"],
                    "operation": next_rule["operation"],
                    "factor": next_rule["factor"],
                    "current_value": current,
                    "proposed_value": proposed,
                    "supporting_result_id": mean_result.id,
                    "supporting_insight_ids": [item.id for item in created if item.insight_type == "anomaly"],
                    "measurement_ids": mean_result.measurement_ids_json,
                    "threshold": mean_result.threshold,
                    "calculated_value": mean_result.value,
                },
                citations=[
                    {"entity_type": "Result", "id": mean_result.id},
                    *[{"entity_type": "Insight", "id": item.id} for item in created if item.insight_type == "anomaly"],
                ],
            )
        )
    db.flush()
    return created


def _insight(db, experiment, actor, **kwargs) -> LabInsight:
    citations = kwargs.pop("citations")
    evidence = kwargs.pop("evidence")
    row = LabInsight(
        experiment_id=experiment.id,
        ai_generated=False,
        approved=False,
        model_version="deterministic-rules-v1",
        evidence_json=evidence,
        citations_json=citations,
        produced_by="LAB-A6",
        data_origin="synthetic",
        created_by=actor,
        **kwargs,
    )
    db.add(row)
    db.flush()
    return row


def _result_dict(row: LabResult) -> dict:
    return {
        "id": row.id,
        "metric": row.metric,
        "value": row.value,
        "unit": row.unit,
        "outcome": row.outcome,
        "criterion_id": row.criterion_id,
        "threshold": row.threshold,
        "operator": row.operator,
        "measurement_ids": row.measurement_ids_json,
    }


def _insight_dict(row: LabInsight) -> dict:
    return {
        "id": row.id,
        "insight_type": row.insight_type,
        "rule_id": row.rule_id,
        "title": row.title,
        "statement": row.statement,
        "ai_generated": row.ai_generated,
        "approved": row.approved,
        "evidence": row.evidence_json,
        "citations": row.citations_json,
    }


def active_results(db: Session, experiment_id: str) -> list[LabResult]:
    return (
        db.query(LabResult)
        .filter(LabResult.experiment_id == experiment_id, LabResult.status == "active")
        .all()
    )


def active_insights(db: Session, experiment_id: str) -> list[LabInsight]:
    return (
        db.query(LabInsight)
        .filter(LabInsight.experiment_id == experiment_id, LabInsight.status == "active")
        .all()
    )


def recommendation(db: Session, experiment_id: str) -> LabInsight | None:
    return (
        db.query(LabInsight)
        .filter(
            LabInsight.experiment_id == experiment_id,
            LabInsight.status == "active",
            LabInsight.insight_type == "recommendation",
        )
        .order_by(LabInsight.created_at.desc())
        .first()
    )
