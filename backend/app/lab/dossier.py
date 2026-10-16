"""Experiment dossier renditions. Narrative text is a labelled template. Numbers are copied from results."""

from __future__ import annotations

import hashlib
from pathlib import Path

from docx import Document as DocxDocument
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from app.config import settings
from app.lab.audit import record
from app.lab.errors import LabError
from app.lab.graph_bridge import link, publish
from app.lab.models import (
    LabExperiment,
    LabExperimentDossier,
    LabGateDecision,
    LabMeasurement,
    LabResult,
)
from app.lab.results import active_insights, active_results
from app.lab.rules import NARRATIVE_MODEL_VERSION, NARRATIVE_PROMPT, NARRATIVE_PROMPT_ID
from app.models.db_models import GraphNode


def generate_dossier(db: Session, experiment_id: str, actor: str) -> LabExperimentDossier:
    experiment = db.get(LabExperiment, experiment_id)
    if experiment is None:
        raise LabError("Experiment not found.", status_code=404, code="not_found")
    results = active_results(db, experiment_id)
    if not results:
        raise LabError("Compile results before generating a dossier.", status_code=409, code="results_required")
    insights = active_insights(db, experiment_id)
    measurements = (
        db.query(LabMeasurement)
        .filter(
            LabMeasurement.experiment_id == experiment_id,
            LabMeasurement.status == "active",
            LabMeasurement.sample_id.isnot(None),
        )
        .all()
    )
    reported = _reported_values(measurements, results)
    if any(not item["measurement_ids"] for item in reported):
        raise LabError("Refusing to publish a value that has no measurement id.", status_code=500, code="untraceable_value")
    narrative = _narrative(experiment, results, insights)
    version = (
        db.query(LabExperimentDossier).filter(LabExperimentDossier.experiment_id == experiment_id).count()
        + 1
    )
    prompt_sha = hashlib.sha256(NARRATIVE_PROMPT.encode()).hexdigest()
    dossier = LabExperimentDossier(
        experiment_id=experiment_id,
        version=version,
        status="pending_approval",
        publishable=False,
        ai_generated=True,
        model_version=NARRATIVE_MODEL_VERSION,
        prompt_id=NARRATIVE_PROMPT_ID,
        llm_called=False,
        narrative_json=narrative,
        content_json={
            "data_origin": "synthetic",
            "reported_values": reported,
            "result_ids": [row.id for row in results],
            "insight_ids": [row.id for row in insights],
            "prompt_sha256": prompt_sha,
            "llm_called": False,
        },
        produced_by="LAB-A6",
        data_origin="synthetic",
        created_by=actor,
    )
    db.add(dossier)
    db.flush()
    paths = _render(dossier, experiment, draft=True)
    dossier.docx_path = paths["docx"]
    dossier.pdf_path = paths["pdf"]
    node = publish(
        db,
        dossier,
        entity_type="ExperimentDossier",
        label=f"Dossier v{dossier.version}",
        document_id=experiment.source_document_id,
        extra={"publishable": False, "ai_generated": True},
    )
    for result in results:
        if result.graph_node_id:
            link(db, node, db.get(GraphNode, result.graph_node_id), "REPORTS")
    record(
        db,
        event_type="dossier_generated",
        actor=actor,
        resource_type="experiment_dossier",
        resource_id=dossier.id,
        action="Generated a draft experiment dossier",
        details={
            "experiment_id": experiment_id,
            "version": dossier.version,
            "prompt_id": NARRATIVE_PROMPT_ID,
            "prompt_sha256": prompt_sha,
            "model_version": NARRATIVE_MODEL_VERSION,
            "llm_called": False,
            "publishable": False,
        },
    )
    db.flush()
    return dossier


def decide_dossier(db: Session, dossier_id: str, decision: str, actor: str, comment: str | None = None) -> LabExperimentDossier:
    dossier = db.get(LabExperimentDossier, dossier_id)
    if dossier is None:
        raise LabError("Dossier not found.", status_code=404, code="not_found")
    if dossier.status not in {"pending_approval", "revision_requested"}:
        raise LabError(f"Dossier is already {dossier.status}.", status_code=409, code="gate_closed")
    if decision not in {"approve", "reject", "revision_requested"}:
        raise LabError("Decision must be approve, reject, or revision_requested.", status_code=422, code="invalid_decision")
    experiment = db.get(LabExperiment, dossier.experiment_id)
    from datetime import datetime

    dossier.approval_json = {
        "decision": decision,
        "actor": actor,
        "comment": comment,
        "version": dossier.version,
        "decided_at": datetime.utcnow().isoformat() + "Z",
    }
    if decision == "approve":
        dossier.status = "approved"
        dossier.publishable = True
        experiment.status = "completed"
        paths = _render(dossier, experiment, draft=False)
        dossier.pdf_path = paths["pdf"]
        dossier.docx_path = paths["docx"]
        _maybe_emit_completed(db, experiment, actor)
    elif decision == "reject":
        dossier.status = "rejected"
        dossier.publishable = False
    else:
        dossier.status = "revision_requested"
        dossier.publishable = False
    gate = LabGateDecision(
        gate="G6",
        experiment_id=experiment.id,
        entity_type="experiment_dossier",
        entity_id=dossier.id,
        decision=decision,
        actor=actor,
        comment=comment,
        entity_version=dossier.version,
    )
    db.add(gate)
    db.flush()
    record(
        db,
        event_type="gate_decision",
        actor=actor,
        resource_type="experiment_dossier",
        resource_id=dossier.id,
        action=f"G6 {decision}",
        details={
            "gate": "G6",
            "decision": decision,
            "version": dossier.version,
            "experiment_id": experiment.id,
            "publishable": dossier.publishable,
            "comment": comment,
        },
    )
    return dossier


def _maybe_emit_completed(db: Session, experiment: LabExperiment, actor: str) -> None:
    from app.config import settings
    from app.lab.models import LabEvent, LabSubscription

    payload = {"experiment_id": experiment.id, "outcome": experiment.outcome, "data_origin": experiment.data_origin}
    if not settings.lab_emit_experiment_completed:
        db.add(
            LabEvent(
                event_type="ExperimentCompleted",
                payload_json=payload,
                published=False,
                suppressed_reason="feature_flag_disabled",
            )
        )
        record(
            db,
            event_type="event_suppressed",
            actor=actor,
            resource_type="experiment",
            resource_id=experiment.id,
            action="Suppressed ExperimentCompleted because the feature flag is off",
            details={"flag": "lab_emit_experiment_completed", **payload},
        )
        return
    subscribers = [row.subscriber for row in db.query(LabSubscription).filter(LabSubscription.event_type == "ExperimentCompleted").all()]
    db.add(
        LabEvent(
            event_type="ExperimentCompleted",
            payload_json={**payload, "subscribers": subscribers},
            published=True,
        )
    )
    record(
        db,
        event_type="event_published",
        actor=actor,
        resource_type="experiment",
        resource_id=experiment.id,
        action="Published ExperimentCompleted",
        details={**payload, "subscribers": subscribers},
    )


def _reported_values(measurements: list[LabMeasurement], results: list[LabResult]) -> list[dict]:
    reported = []
    for measurement in measurements:
        if measurement.readout_key not in {"viability_percent", "viable_cells_per_ml", "average_diameter_um"}:
            continue
        reported.append(
            {
                "label": f"{measurement.sample_code_observed} {measurement.readout_key}",
                "value": measurement.value,
                "unit": measurement.unit,
                "measurement_ids": [measurement.id],
                "result_id": None,
            }
        )
    for result in results:
        reported.append(
            {
                "label": result.metric,
                "value": result.value,
                "unit": result.unit,
                "measurement_ids": list(result.measurement_ids_json or []),
                "result_id": result.id,
                "outcome": result.outcome,
            }
        )
    return reported


def _narrative(experiment, results, insights) -> dict:
    paragraphs = []
    for result in results:
        cite = [{"entity_type": "Result", "id": result.id}]
        cite.extend({"entity_type": "Measurement", "id": mid} for mid in (result.measurement_ids_json or []))
        paragraphs.append(
            {
                "text": (
                    f"{result.metric} is {result.value} {result.unit or ''}. "
                    f"Criterion {result.criterion_id} ({result.operator} {result.threshold}) outcome is {result.outcome}."
                ).strip(),
                "citations": cite,
            }
        )
    for insight in insights:
        paragraphs.append(
            {
                "text": f"{insight.title}: {insight.statement}",
                "citations": insight.citations_json or [{"entity_type": "Insight", "id": insight.id}],
            }
        )
    return {
        "ai_generated": True,
        "requires_scientist_approval": True,
        "model_version": NARRATIVE_MODEL_VERSION,
        "prompt_id": NARRATIVE_PROMPT_ID,
        "llm_called": False,
        "label": "Machine-generated narrative. It restates deterministic calculations and is not an approved scientific conclusion.",
        "paragraphs": paragraphs,
        "experiment_title": experiment.title,
    }


def _render(dossier: LabExperimentDossier, experiment: LabExperiment, *, draft: bool) -> dict:
    root = Path(settings.lab_dossier_dir)
    root.mkdir(parents=True, exist_ok=True)
    suffix = "draft" if draft else "approved"
    pdf_path = root / f"{dossier.id}-{suffix}.pdf"
    docx_path = root / f"{dossier.id}-{suffix}.docx"
    banner = (
        "DRAFT — NOT PUBLISHABLE — machine-generated narrative requires scientist approval"
        if draft
        else "APPROVED — publishable. Machine-generated narrative was approved by a scientist."
    )
    values = dossier.content_json.get("reported_values") or []
    _write_pdf(pdf_path, experiment.title, banner, dossier, values)
    _write_docx(docx_path, experiment.title, banner, dossier, values)
    return {"pdf": str(pdf_path), "docx": str(docx_path)}


def _write_pdf(path: Path, title: str, banner: str, dossier: LabExperimentDossier, values: list[dict]) -> None:
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(path), pagesize=letter)
    story = [
        Paragraph("SYNTHETIC DATA", styles["Heading3"]),
        Paragraph(title, styles["Title"]),
        Paragraph(banner, styles["Normal"]),
        Spacer(1, 12),
        Paragraph(dossier.narrative_json.get("label", ""), styles["Italic"]),
    ]
    for paragraph in dossier.narrative_json.get("paragraphs") or []:
        cites = ", ".join(f"{item['entity_type']}:{item['id']}" for item in paragraph.get("citations") or [])
        story.append(Paragraph(paragraph["text"], styles["Normal"]))
        story.append(Paragraph(f"Citations: {cites}", styles["Italic"]))
        story.append(Spacer(1, 8))
    table_data = [["Value", "Amount", "Unit", "Measurement IDs"]]
    for item in values:
        table_data.append(
            [
                str(item["label"]),
                str(item["value"]),
                str(item.get("unit") or ""),
                ", ".join(item["measurement_ids"]),
            ]
        )
    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0891b2")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ]
        )
    )
    story.append(Spacer(1, 12))
    story.append(table)
    doc.build(story)


def _write_docx(path: Path, title: str, banner: str, dossier: LabExperimentDossier, values: list[dict]) -> None:
    document = DocxDocument()
    document.add_heading("SYNTHETIC DATA", level=2)
    document.add_heading(title, level=0)
    document.add_paragraph(banner)
    document.add_paragraph(dossier.narrative_json.get("label", ""))
    for paragraph in dossier.narrative_json.get("paragraphs") or []:
        document.add_paragraph(paragraph["text"])
        cites = ", ".join(f"{item['entity_type']}:{item['id']}" for item in paragraph.get("citations") or [])
        document.add_paragraph(f"Citations: {cites}")
    table = document.add_table(rows=1, cols=4)
    header = table.rows[0].cells
    header[0].text = "Value"
    header[1].text = "Amount"
    header[2].text = "Unit"
    header[3].text = "Measurement IDs"
    for item in values:
        cells = table.add_row().cells
        cells[0].text = str(item["label"])
        cells[1].text = str(item["value"])
        cells[2].text = str(item.get("unit") or "")
        cells[3].text = ", ".join(item["measurement_ids"])
    document.save(str(path))
