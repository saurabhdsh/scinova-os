"""Idempotent lab seed. Historical experiments pass through the Vi-CELL parser and ingestion pipeline."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.lab.catalog import (
    EXPECTED_READOUTS,
    historical_experiments,
    lot_dates,
    protocol_definitions,
    render_vicell_csv,
)
from app.lab.graph_bridge import link, publish
from app.lab.ingestion import ingest_bytes
from app.lab.models import (
    LabComplianceRule,
    LabDocumentSection,
    LabInstrument,
    LabLot,
    LabMaterial,
    LabProtocol,
    LabProtocolVersion,
    LabTrainingRecord,
)
from app.lab.operations import approve_plan, create_plan
from app.lab.results import compile_results
from app.models.db_models import Document, GraphNode, Project, ProjectMember, User


def seed_lab(db: Session) -> None:
    if db.query(LabProtocol).filter(LabProtocol.code == "SYN-CVP-001").first():
        return
    owner = db.query(User).filter(User.username == "scientist").first() or db.query(User).first()
    if owner is None:
        return
    _seed_lab_for_owner(db, owner)
    db.commit()


def _seed_lab_for_owner(db: Session, owner: User) -> None:
    project = db.query(Project).filter(Project.name == "Cell Viability Lab").first()
    if project is None:
        project = Project(
            name="Cell Viability Lab",
            description="Synthetic cell-viability workspace. Instrument files and protocol text are synthetic.",
            owner_id=owner.id,
        )
        db.add(project)
        db.flush()
        member_ids = {owner.id}
        for username in ("admin", "reviewer"):
            user = db.query(User).filter(User.username == username).first()
            if user is not None:
                member_ids.add(user.id)
        for user_id in member_ids:
            db.add(ProjectMember(project_id=project.id, user_id=user_id, role="owner" if user_id == owner.id else "member"))
        db.flush()

    dates = lot_dates()
    material = LabMaterial(name="Trypan blue 0.4% (synthetic)", material_type="stain", data_origin="synthetic", created_by="seed-script")
    db.add(material)
    db.flush()
    alternative = LabLot(
        material_id=material.id,
        lot_number="TB-LOT-778",
        expires_on=dates["alternative"],
        status="approved",
        data_origin="synthetic",
        created_by="seed-script",
    )
    near = LabLot(
        material_id=material.id,
        lot_number="TB-LOT-441",
        expires_on=dates["near_expiry"],
        status="near_expiry",
        data_origin="synthetic",
        created_by="seed-script",
    )
    db.add(alternative)
    db.add(near)
    db.flush()
    near.approved_alternative_lot_id = alternative.id

    current = LabInstrument(
        name="Vi-CELL XR 1042",
        model="Vi-CELL XR",
        serial_number="VC-XR-1042",
        calibration_status="current",
        calibration_due=dates["calibration_current"],
        data_origin="synthetic",
        created_by="seed-script",
    )
    overdue = LabInstrument(
        name="Vi-CELL XR 2088",
        model="Vi-CELL XR",
        serial_number="VC-XR-2088",
        calibration_status="calibration_due",
        calibration_due=dates["calibration_overdue"],
        data_origin="synthetic",
        created_by="seed-script",
    )
    db.add(current)
    db.add(overdue)
    db.flush()

    primary_version = None
    for spec in protocol_definitions():
        protocol = LabProtocol(
            code=spec["code"],
            title=spec["title"],
            status="approved",
            summary=spec["summary"],
            data_origin="synthetic",
            created_by="seed-script",
        )
        db.add(protocol)
        db.flush()
        document = Document(
            title=f"{spec['code']} {spec['version']} (synthetic SOP)",
            source_type="protocol",
            file_format="TXT",
            status="indexed",
            metadata_json={"data_origin": "synthetic", "lab_protocol_code": spec["code"]},
            user_id=owner.id,
            project_id=project.id,
        )
        db.add(document)
        db.flush()
        version = LabProtocolVersion(
            protocol_id=protocol.id,
            version_label=spec["version"],
            version_number=spec["version_number"],
            status="approved",
            parameters_json=spec["parameters"],
            success_criteria_json=spec["criteria"],
            sample_panel_json=spec["samples"],
            expected_readouts_json=list(EXPECTED_READOUTS),
            document_id=document.id,
            data_origin="synthetic",
            created_by="seed-script",
        )
        db.add(version)
        db.flush()
        for heading, body, citation in spec["sections"]:
            db.add(
                LabDocumentSection(
                    document_id=document.id,
                    protocol_version_id=version.id,
                    heading=heading,
                    body=body,
                    citation_label=citation,
                )
            )
        doc_node_owner = version
        publish(db, protocol, entity_type="Protocol", label=protocol.code, document_id=document.id)
        version_node = publish(db, version, entity_type="ProtocolVersion", label=f"{protocol.code} {version.version_label}", document_id=document.id)
        link(db, version_node, db.get(GraphNode, protocol.graph_node_id), "VERSION_OF")
        if spec["code"] == "SYN-CVP-001":
            primary_version = version
        del doc_node_owner

    for person, qualified, reason in (
        ("Priya Nair", True, None),
        ("Sarah Chen", True, None),
        ("Alex Rivera", False, "No qualification record for synthetic protocol SYN-CVP-001."),
    ):
        db.add(
            LabTrainingRecord(
                person_name=person,
                protocol_id=primary_version.protocol_id,
                qualified=qualified,
                gap_reason=reason,
                data_origin="synthetic",
                created_by="seed-script",
            )
        )
    for code, description in (
        ("COMP-001", "The scheduled operator must be qualified on the protocol."),
        ("COMP-002", "The scheduled instrument must have a current calibration."),
        ("COMP-003", "Critical reagent lots must have more than 30 days until expiry."),
    ):
        db.add(LabComplianceRule(code=code, description=description, blocks_execution=True, created_by="seed-script"))
    db.flush()

    for spec in historical_experiments(12):
        plan = create_plan(
            db,
            protocol_version_id=primary_version.id,
            actor="seed-script",
            title=f"Synthetic historical plan {spec['index']:02d}",
        )
        panel = []
        for sample in spec["samples"]:
            panel.append(
                {
                    "sample_code": sample["sample_id"],
                    "cell_line": "CHO-K1",
                    "cell_line_ontology": "CVCL:0214",
                    "passage": 12,
                    "qc_status": "pass",
                    "lineage": {"parent_vial": "SYN-VIAL-014", "data_origin": "synthetic_historical"},
                }
            )
        plan.sample_panel_json = panel
        plan.parameters_json = {
            **(plan.parameters_json or {}),
            "instrument_serial": "VC-XR-1042",
            "operator": "Priya Nair",
            "reagent_lot": "TB-LOT-778",
        }
        experiment = approve_plan(db, plan.id, "seed-script", "Synthetic historical baseline, pre-approved for comparison.")
        experiment.data_origin = "synthetic_historical"
        content = render_vicell_csv(spec["samples"], serial="VC-XR-1042")
        ingest_bytes(
            db,
            content=content,
            filename=f"vicell_hist_{spec['index']:02d}.csv",
            experiment_id=experiment.id,
            actor="seed-script",
            enforce_readiness=False,
        )
        compile_results(db, experiment.id, "seed-script")
        experiment.status = "completed"
        experiment.data_origin = "synthetic_historical"
    db.flush()
