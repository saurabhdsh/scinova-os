"""Lab fabric tables. Raw files have no mutation columns."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)

from app.database import Base
from app.models.db_models import gen_id


class LabRecord(Base):
    __abstract__ = True

    graph_node_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(128))


class LabProtocol(LabRecord):
    __tablename__ = "lab_protocols"

    id = Column(String, primary_key=True, default=gen_id)
    code = Column(String(64), unique=True, nullable=False)
    title = Column(String(512), nullable=False)
    status = Column(String(32), default="approved")
    summary = Column(Text)
    data_origin = Column(String(64), default="synthetic")


class LabProtocolVersion(LabRecord):
    __tablename__ = "lab_protocol_versions"

    id = Column(String, primary_key=True, default=gen_id)
    protocol_id = Column(String, ForeignKey("lab_protocols.id"), nullable=False, index=True)
    version_label = Column(String(32), nullable=False)
    version_number = Column(Integer, nullable=False)
    status = Column(String(32), default="approved")
    parameters_json = Column(JSON, default=dict)
    success_criteria_json = Column(JSON, default=list)
    sample_panel_json = Column(JSON, default=list)
    expected_readouts_json = Column(JSON, default=list)
    document_id = Column(String, ForeignKey("documents.id"))
    data_origin = Column(String(64), default="synthetic")


class LabDocumentSection(Base):
    __tablename__ = "lab_document_sections"

    id = Column(String, primary_key=True, default=gen_id)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    protocol_version_id = Column(String, ForeignKey("lab_protocol_versions.id"), index=True)
    heading = Column(String(256), nullable=False)
    body = Column(Text, nullable=False)
    citation_label = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class LabExperimentPlan(LabRecord):
    __tablename__ = "lab_experiment_plans"

    id = Column(String, primary_key=True, default=gen_id)
    protocol_version_id = Column(String, ForeignKey("lab_protocol_versions.id"), nullable=False, index=True)
    title = Column(String(512), nullable=False)
    version = Column(Integer, default=1)
    status = Column(String(32), default="draft")
    parameters_json = Column(JSON, default=dict)
    success_criteria_json = Column(JSON, default=list)
    sample_panel_json = Column(JSON, default=list)
    expected_readouts_json = Column(JSON, default=list)
    cited_insight_ids_json = Column(JSON, default=list)
    parent_plan_id = Column(String, nullable=True)
    produced_by = Column(String(32))
    data_origin = Column(String(64), default="synthetic")
    supersedes_id = Column(String, nullable=True)


class LabExperiment(LabRecord):
    __tablename__ = "lab_experiments"

    id = Column(String, primary_key=True, default=gen_id)
    plan_id = Column(String, ForeignKey("lab_experiment_plans.id"), nullable=False, index=True)
    title = Column(String(512), nullable=False)
    status = Column(String(32), default="planned")
    outcome = Column(String(32))
    produced_by = Column(String(32))
    source_document_id = Column(String, ForeignKey("documents.id"))
    data_origin = Column(String(64), default="synthetic")


class LabSample(LabRecord):
    __tablename__ = "lab_samples"

    id = Column(String, primary_key=True, default=gen_id)
    experiment_id = Column(String, ForeignKey("lab_experiments.id"), nullable=False, index=True)
    sample_code = Column(String(128), nullable=False, index=True)
    cell_line = Column(String(128))
    cell_line_ontology = Column(String(64))
    passage = Column(Integer)
    qc_status = Column(String(32), default="pass")
    lineage_json = Column(JSON, default=dict)
    data_origin = Column(String(64), default="synthetic")


class LabInstrument(LabRecord):
    __tablename__ = "lab_instruments"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String(256), nullable=False)
    model = Column(String(128), nullable=False)
    serial_number = Column(String(128), unique=True, nullable=False)
    calibration_status = Column(String(32), nullable=False)
    calibration_due = Column(Date)
    data_origin = Column(String(64), default="synthetic")


class LabRun(LabRecord):
    __tablename__ = "lab_runs"

    id = Column(String, primary_key=True, default=gen_id)
    experiment_id = Column(String, ForeignKey("lab_experiments.id"), nullable=False, index=True)
    instrument_id = Column(String, ForeignKey("lab_instruments.id"), index=True)
    run_code = Column(String(128), nullable=False)
    status = Column(String(32), default="scheduled")
    completeness_percent = Column(Float)
    expected_readouts_json = Column(JSON, default=list)
    data_origin = Column(String(64), default="synthetic")


class LabRunSchedule(LabRecord):
    __tablename__ = "lab_run_schedules"

    id = Column(String, primary_key=True, default=gen_id)
    run_id = Column(String, ForeignKey("lab_runs.id"), nullable=False, index=True)
    operator_name = Column(String(256))
    instrument_id = Column(String, ForeignKey("lab_instruments.id"))
    reagent_lot = Column(String(128))
    status = Column(String(32), default="scheduled")


class LabRawDataFile(LabRecord):
    """Immutable landing object. Application code never updates checksum or bytes."""

    __tablename__ = "lab_raw_data_files"
    __table_args__ = (UniqueConstraint("sha256", "experiment_id", name="uq_lab_raw_sha_experiment"),)

    id = Column(String, primary_key=True, default=gen_id)
    experiment_id = Column(String, ForeignKey("lab_experiments.id"), nullable=False, index=True)
    run_id = Column(String, ForeignKey("lab_runs.id"), index=True)
    instrument_id = Column(String, ForeignKey("lab_instruments.id"))
    sha256 = Column(String(64), nullable=False, index=True)
    byte_size = Column(Integer, nullable=False)
    filename = Column(String(512), nullable=False)
    landing_uri = Column(String(1024), nullable=False)
    landing_mode = Column(String(32), nullable=False)
    landing_external = Column(Boolean, default=False)
    parser_id = Column(String(64))
    parser_version = Column(String(64))
    instrument_serial_observed = Column(String(128))
    checksum_verified = Column(Boolean, default=False)
    data_origin = Column(String(64), default="synthetic")


class LabMeasurement(LabRecord):
    __tablename__ = "lab_measurements"

    id = Column(String, primary_key=True, default=gen_id)
    version = Column(Integer, default=1)
    status = Column(String(32), default="active", index=True)
    supersedes_id = Column(String, nullable=True)
    experiment_id = Column(String, ForeignKey("lab_experiments.id"), nullable=False, index=True)
    run_id = Column(String, ForeignKey("lab_runs.id"), index=True)
    sample_id = Column(String, ForeignKey("lab_samples.id"), index=True)
    raw_file_id = Column(String, ForeignKey("lab_raw_data_files.id"), index=True)
    readout_key = Column(String(64), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(64))
    ontology_id = Column(String(64))
    ontology_label = Column(String(256))
    unit_ontology_id = Column(String(64))
    mapping_confidence = Column(Float)
    mapping_method = Column(String(64))
    sample_code_observed = Column(String(128))
    produced_by = Column(String(32), default="LAB-A6")
    data_origin = Column(String(64), default="synthetic")
    raw_row_json = Column(JSON, default=dict)


class LabDataQualityFlag(LabRecord):
    __tablename__ = "lab_data_quality_flags"

    id = Column(String, primary_key=True, default=gen_id)
    experiment_id = Column(String, ForeignKey("lab_experiments.id"), index=True)
    run_id = Column(String, ForeignKey("lab_runs.id"), index=True)
    raw_file_id = Column(String, ForeignKey("lab_raw_data_files.id"))
    code = Column(String(64), nullable=False)
    message = Column(Text, nullable=False)
    sample_code = Column(String(128))
    status = Column(String(32), default="open")


class LabResult(LabRecord):
    __tablename__ = "lab_results"

    id = Column(String, primary_key=True, default=gen_id)
    version = Column(Integer, default=1)
    status = Column(String(32), default="active", index=True)
    supersedes_id = Column(String, nullable=True)
    experiment_id = Column(String, ForeignKey("lab_experiments.id"), nullable=False, index=True)
    metric = Column(String(64), nullable=False)
    value = Column(Float)
    unit = Column(String(64))
    criterion_id = Column(String(64))
    operator = Column(String(8))
    threshold = Column(Float)
    outcome = Column(String(32))
    measurement_ids_json = Column(JSON, default=list)
    calculation_json = Column(JSON, default=dict)
    produced_by = Column(String(32), default="LAB-A6")
    data_origin = Column(String(64), default="synthetic")


class LabInsight(LabRecord):
    __tablename__ = "lab_insights"

    id = Column(String, primary_key=True, default=gen_id)
    version = Column(Integer, default=1)
    status = Column(String(32), default="active", index=True)
    experiment_id = Column(String, ForeignKey("lab_experiments.id"), nullable=False, index=True)
    insight_type = Column(String(32), nullable=False)
    rule_id = Column(String(64))
    title = Column(String(512), nullable=False)
    statement = Column(Text, nullable=False)
    ai_generated = Column(Boolean, default=False)
    approved = Column(Boolean, default=False)
    model_version = Column(String(128))
    evidence_json = Column(JSON, default=dict)
    citations_json = Column(JSON, default=list)
    produced_by = Column(String(32), default="LAB-A6")
    data_origin = Column(String(64), default="synthetic")


class LabExperimentDossier(LabRecord):
    __tablename__ = "lab_experiment_dossiers"

    id = Column(String, primary_key=True, default=gen_id)
    experiment_id = Column(String, ForeignKey("lab_experiments.id"), nullable=False, index=True)
    version = Column(Integer, default=1)
    status = Column(String(32), default="pending_approval")
    publishable = Column(Boolean, default=False)
    ai_generated = Column(Boolean, default=True)
    model_version = Column(String(128))
    prompt_id = Column(String(128))
    llm_called = Column(Boolean, default=False)
    narrative_json = Column(JSON, default=dict)
    content_json = Column(JSON, default=dict)
    docx_path = Column(String(1024))
    pdf_path = Column(String(1024))
    approval_json = Column(JSON, default=dict)
    produced_by = Column(String(32), default="LAB-A6")
    data_origin = Column(String(64), default="synthetic")


class LabMaterial(LabRecord):
    __tablename__ = "lab_materials"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String(256), nullable=False)
    material_type = Column(String(64))
    data_origin = Column(String(64), default="synthetic")


class LabLot(LabRecord):
    __tablename__ = "lab_lots"

    id = Column(String, primary_key=True, default=gen_id)
    material_id = Column(String, ForeignKey("lab_materials.id"), nullable=False, index=True)
    lot_number = Column(String(128), unique=True, nullable=False)
    expires_on = Column(Date, nullable=False)
    status = Column(String(32), nullable=False)
    approved_alternative_lot_id = Column(String, nullable=True)
    data_origin = Column(String(64), default="synthetic")


class LabTrainingRecord(LabRecord):
    __tablename__ = "lab_training_records"

    id = Column(String, primary_key=True, default=gen_id)
    person_name = Column(String(256), nullable=False)
    protocol_id = Column(String, ForeignKey("lab_protocols.id"), index=True)
    qualified = Column(Boolean, default=False)
    gap_reason = Column(Text)
    data_origin = Column(String(64), default="synthetic")


class LabComplianceRule(LabRecord):
    __tablename__ = "lab_compliance_rules"

    id = Column(String, primary_key=True, default=gen_id)
    code = Column(String(64), unique=True, nullable=False)
    description = Column(Text, nullable=False)
    blocks_execution = Column(Boolean, default=True)


class LabReadinessIssue(LabRecord):
    __tablename__ = "lab_readiness_issues"

    id = Column(String, primary_key=True, default=gen_id)
    experiment_id = Column(String, ForeignKey("lab_experiments.id"), nullable=False, index=True)
    agent_id = Column(String(32), nullable=False)
    code = Column(String(64), nullable=False)
    severity = Column(String(32), default="blocking")
    message = Column(Text, nullable=False)
    status = Column(String(32), default="open")
    recommendation_json = Column(JSON, default=dict)
    resolution_json = Column(JSON, default=dict)


class LabGateDecision(Base):
    __tablename__ = "lab_gate_decisions"

    id = Column(String, primary_key=True, default=gen_id)
    gate = Column(String(8), nullable=False)
    experiment_id = Column(String, index=True)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String, nullable=False)
    decision = Column(String(32), nullable=False)
    actor = Column(String(128), nullable=False)
    comment = Column(Text)
    entity_version = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


class LabAgentJob(Base):
    __tablename__ = "lab_agent_jobs"

    id = Column(String, primary_key=True, default=gen_id)
    agent_id = Column(String(32), nullable=False, index=True)
    experiment_id = Column(String, index=True)
    trigger = Column(String(64), nullable=False)
    status = Column(String(32), default="RUNNING")
    correlation_id = Column(String(64), nullable=False, index=True)
    idempotency_key = Column(String(128), index=True)
    context_json = Column(JSON, default=dict)
    output_json = Column(JSON, default=dict)
    error_json = Column(JSON, default=dict)
    actor = Column(String(128))
    latency_ms = Column(Integer)
    model_version = Column(String(128))
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


class LabEvent(Base):
    __tablename__ = "lab_events"

    id = Column(String, primary_key=True, default=gen_id)
    event_type = Column(String(64), nullable=False, index=True)
    payload_json = Column(JSON, default=dict)
    published = Column(Boolean, default=False)
    suppressed_reason = Column(String(128))
    created_at = Column(DateTime, default=datetime.utcnow)


class LabSubscription(Base):
    __tablename__ = "lab_subscriptions"

    id = Column(String, primary_key=True, default=gen_id)
    event_type = Column(String(64), nullable=False, index=True)
    subscriber = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class LabRuleOverride(Base):
    """Build-later configuration hook. Empty unless an operator inserts a row."""

    __tablename__ = "lab_rule_overrides"

    id = Column(String, primary_key=True, default=gen_id)
    rule_id = Column(String(64), nullable=False, index=True)
    config_json = Column(JSON, default=dict)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


ENTITY_MODELS = {
    "experiment": LabExperiment,
    "experiment_plan": LabExperimentPlan,
    "protocol": LabProtocol,
    "protocol_version": LabProtocolVersion,
    "run": LabRun,
    "run_schedule": LabRunSchedule,
    "sample": LabSample,
    "instrument": LabInstrument,
    "raw_data_file": LabRawDataFile,
    "measurement": LabMeasurement,
    "data_quality_flag": LabDataQualityFlag,
    "result": LabResult,
    "insight": LabInsight,
    "experiment_dossier": LabExperimentDossier,
}
