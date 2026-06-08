import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def gen_id() -> str:
    return str(uuid.uuid4())


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=gen_id)
    title = Column(String(512), nullable=False)
    source_type = Column(String(64), nullable=False)
    file_path = Column(String(1024))
    file_format = Column(String(32))
    status = Column(String(32), default="indexed")
    metadata_json = Column(JSON, default=dict)
    version = Column(Integer, default=1)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    project_id = Column(String, ForeignKey("projects.id"), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String(256), nullable=False)
    source_type = Column(String(64), nullable=False)
    connector_status = Column(String(32), default="active")
    last_sync = Column(DateTime)
    document_count = Column(Integer, default=0)
    config_json = Column(JSON, default=dict)


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id = Column(String, primary_key=True, default=gen_id)
    document_id = Column(String, ForeignKey("documents.id"))
    status = Column(String(32), default="pending")
    stage = Column(String(64), default="upload")
    progress = Column(Float, default=0.0)
    stages_completed = Column(JSON, default=list)
    error_message = Column(Text)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    project_id = Column(String, ForeignKey("projects.id"), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True, default=gen_id)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    token_count = Column(Integer, default=0)
    chroma_id = Column(String(128))
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String(256), nullable=False)
    description = Column(Text)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ProjectMember(Base):
    __tablename__ = "project_members"

    id = Column(String, primary_key=True, default=gen_id)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(32), default="member")
    created_at = Column(DateTime, default=datetime.utcnow)


class ScientificEntity(Base):
    __tablename__ = "scientific_entities"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String(512), nullable=False)
    entity_type = Column(String(64), nullable=False)
    description = Column(Text)
    ontology_id = Column(String(128))
    source_document_id = Column(String, ForeignKey("documents.id"))
    confidence = Column(Float, default=0.85)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class GraphNode(Base):
    __tablename__ = "graph_nodes"

    id = Column(String, primary_key=True, default=gen_id)
    label = Column(String(512), nullable=False)
    node_type = Column(String(64), nullable=False)
    entity_id = Column(String, ForeignKey("scientific_entities.id"))
    properties_json = Column(JSON, default=dict)
    evidence_json = Column(JSON, default=list)


class GraphRelationship(Base):
    __tablename__ = "graph_relationships"

    id = Column(String, primary_key=True, default=gen_id)
    source_node_id = Column(String, ForeignKey("graph_nodes.id"), nullable=False)
    target_node_id = Column(String, ForeignKey("graph_nodes.id"), nullable=False)
    relationship_type = Column(String(128), nullable=False)
    properties_json = Column(JSON, default=dict)
    evidence_json = Column(JSON, default=list)
    confidence = Column(Float, default=0.8)


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String(256), nullable=False)
    description = Column(Text)
    category = Column(String(64), nullable=False)
    value_chain_stage = Column(String(64), nullable=False)
    input_types = Column(JSON, default=list)
    output_types = Column(JSON, default=list)
    tools_used = Column(JSON, default=list)
    model_used = Column(String(128))
    slm_eligible = Column(Boolean, default=False)
    risk_level = Column(String(32), default="low")
    human_approval_required = Column(Boolean, default=False)
    status = Column(String(32), default="ready")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(String, primary_key=True, default=gen_id)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    status = Column(String(32), default="running")
    input_json = Column(JSON, default=dict)
    output_json = Column(JSON, default=dict)
    model_selected = Column(String(128))
    routing_reason = Column(Text)
    citations_json = Column(JSON, default=list)
    logs_json = Column(JSON, default=list)
    confidence = Column(Float)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    project_id = Column(String, ForeignKey("projects.id"), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    agent = relationship("Agent")


class WorkflowTemplate(Base):
    __tablename__ = "workflow_templates"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String(256), nullable=False)
    description = Column(Text)
    value_chain_stage = Column(String(64))
    steps_json = Column(JSON, default=list)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id = Column(String, primary_key=True, default=gen_id)
    template_id = Column(String, ForeignKey("workflow_templates.id"))
    name = Column(String(256), nullable=False)
    status = Column(String(32), default="running")
    steps_json = Column(JSON, default=list)
    current_step = Column(Integer, default=0)
    confidence = Column(Float)
    output_json = Column(JSON, default=dict)
    evidence_json = Column(JSON, default=list)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    project_id = Column(String, ForeignKey("projects.id"), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


class SLMProfile(Base):
    __tablename__ = "slm_profiles"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String(256), nullable=False)
    model_name = Column(String(256), nullable=False)
    model_type = Column(String(64))
    task_scope = Column(Text)
    fine_tuning_dataset = Column(String(256))
    token_cost_estimate = Column(Float)
    latency_estimate_ms = Column(Integer)
    accuracy_score = Column(Float)
    evaluation_status = Column(String(32), default="pending")
    deployment_status = Column(String(32), default="placeholder")
    fallback_model = Column(String(256))
    allowed_agents = Column(JSON, default=list)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String, primary_key=True, default=gen_id)
    event_type = Column(String(64), nullable=False)
    actor = Column(String(128))
    resource_type = Column(String(64))
    resource_id = Column(String)
    action = Column(String(128))
    details_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class RiskAlert(Base):
    __tablename__ = "risk_alerts"

    id = Column(String, primary_key=True, default=gen_id)
    title = Column(String(256), nullable=False)
    description = Column(Text)
    severity = Column(String(32), default="medium")
    category = Column(String(64))
    status = Column(String(32), default="open")
    source = Column(String(128))
    created_at = Column(DateTime, default=datetime.utcnow)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(String, primary_key=True, default=gen_id)
    title = Column(String(256), nullable=False)
    request_type = Column(String(64))
    status = Column(String(32), default="pending")
    agent_run_id = Column(String, ForeignKey("agent_runs.id"))
    workflow_run_id = Column(String, ForeignKey("workflow_runs.id"))
    requested_by = Column(String(128))
    details_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class ScientificReport(Base):
    __tablename__ = "scientific_reports"

    id = Column(String, primary_key=True, default=gen_id)
    title = Column(String(512), nullable=False)
    report_type = Column(String(64), nullable=False)
    content_json = Column(JSON, default=dict)
    status = Column(String(32), default="draft")
    workflow_run_id = Column(String)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    project_id = Column(String, ForeignKey("projects.id"), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_id)
    username = Column(String(128), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(32), default="scientist")
    full_name = Column(String(256))
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentTaskSettings(Base):
    __tablename__ = "agent_task_settings"

    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    settings_json = Column(JSON, default=dict)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CustomTool(Base):
    __tablename__ = "custom_tools"
    __table_args__ = (UniqueConstraint("tool_id", name="uq_custom_tools_tool_id"),)

    id = Column(String, primary_key=True, default=gen_id)
    tool_id = Column(String(64), nullable=False, index=True)
    label = Column(String(256), nullable=False)
    description = Column(Text)
    role_id = Column(String(64), nullable=False, index=True)
    endpoint_url = Column(String(2048), nullable=False)
    http_method = Column(String(16), default="POST")
    auth_type = Column(String(32), default="none")
    auth_header_name = Column(String(128))
    auth_secret = Column(String(512))
    request_template = Column(JSON, default=dict)
    status = Column(String(32), default="active")
    registered_by = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
