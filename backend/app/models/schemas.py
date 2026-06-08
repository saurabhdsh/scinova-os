from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# --- Document & Data Fabric ---


class DocumentBase(BaseModel):
    title: str
    source_type: str
    file_format: Optional[str] = None
    status: str = "indexed"
    metadata_json: dict = Field(default_factory=dict)
    version: int = 1


class DocumentCreate(DocumentBase):
    pass


class DocumentResponse(DocumentBase):
    id: str
    file_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DataSourceResponse(BaseModel):
    id: str
    name: str
    source_type: str
    connector_status: str
    last_sync: Optional[datetime] = None
    document_count: int

    class Config:
        from_attributes = True


class IngestionJobResponse(BaseModel):
    id: str
    document_id: Optional[str] = None
    status: str
    stage: str
    progress: float
    stages_completed: list
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentChunkResponse(BaseModel):
    id: str
    document_id: str
    chunk_index: int
    content: str
    token_count: int
    chroma_id: Optional[str] = None
    metadata_json: dict

    class Config:
        from_attributes = True


class FabricSearchRequest(BaseModel):
    query: str
    top_k: int = 10
    document_id: Optional[str] = None


class FabricSearchResult(BaseModel):
    chunk_id: str
    content: str
    document_id: str
    chunk_index: int
    score: float
    metadata: dict = Field(default_factory=dict)


class FabricStatsResponse(BaseModel):
    collection: str
    mode: str
    total_chunks: int
    total_documents: int
    total_entities: int


class ScientificEntityResponse(BaseModel):
    id: str
    name: str
    entity_type: str
    description: Optional[str] = None
    ontology_id: Optional[str] = None
    source_document_id: Optional[str] = None
    confidence: float
    metadata_json: dict

    class Config:
        from_attributes = True


# --- Knowledge Graph ---


class GraphNodeCreate(BaseModel):
    label: str
    node_type: str
    entity_id: Optional[str] = None
    properties_json: dict = Field(default_factory=dict)
    evidence_json: list = Field(default_factory=list)


class GraphNodeResponse(BaseModel):
    id: str
    label: str
    node_type: str
    entity_id: Optional[str] = None
    properties_json: dict
    evidence_json: list

    class Config:
        from_attributes = True


class GraphRelationshipCreate(BaseModel):
    source_node_id: str
    target_node_id: str
    relationship_type: str
    properties_json: dict = Field(default_factory=dict)
    evidence_json: list = Field(default_factory=list)
    confidence: float = 0.8


class GraphRelationshipResponse(BaseModel):
    id: str
    source_node_id: str
    target_node_id: str
    relationship_type: str
    properties_json: dict
    evidence_json: list
    confidence: float

    class Config:
        from_attributes = True


class GraphSearchResponse(BaseModel):
    nodes: list[GraphNodeResponse]
    relationships: list[GraphRelationshipResponse]
    graph_source: str = "sql"
    graph_hint: str | None = None


class GraphNeighborhoodResponse(BaseModel):
    center_node: GraphNodeResponse
    nodes: list[GraphNodeResponse]
    relationships: list[GraphRelationshipResponse]
    source_chunks: list[DocumentChunkResponse] = Field(default_factory=list)
    neo4j_connected: bool = False
    graph_source: str = "sql"
    traversal_depth: int = 1


class GraphStatsResponse(BaseModel):
    sql_nodes: int
    sql_relationships: int
    neo4j_connected: bool
    neo4j_nodes: int = 0
    neo4j_relationships: int = 0
    documents_with_graph: int = 0
    live_ingested_nodes: int = 0
    active_graph_source: str = "sql"


# --- Agents ---


class AgentResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    category: str
    value_chain_stage: str
    input_types: list
    output_types: list
    tools_used: list
    model_used: Optional[str] = None
    slm_eligible: bool
    risk_level: str
    human_approval_required: bool
    status: str

    class Config:
        from_attributes = True


class AgentRunRequest(BaseModel):
    input_data: dict = Field(default_factory=dict)
    context: Optional[str] = None
    # input_data supports: query, task_type (qa|query|analysis), document_id, top_k, custom_instructions


class AgentTaskSettingsResponse(BaseModel):
    global_instructions: str = ""
    task_instructions: dict[str, str] = Field(default_factory=dict)
    agent_instructions: dict[str, str] = Field(default_factory=dict)
    agent_tool_bindings: dict[str, dict[str, str]] = Field(default_factory=dict)


class AgentTaskSettingsUpdate(BaseModel):
    global_instructions: Optional[str] = None
    task_instructions: Optional[dict[str, str]] = None
    agent_instructions: Optional[dict[str, str]] = None
    agent_tool_bindings: Optional[dict[str, dict[str, str]]] = None


class AgentToolFabricBindingItem(BaseModel):
    role_id: str
    role_label: str
    tool_id: str
    tool_label: str
    runtime_status: str
    is_custom: bool = False
    is_user_override: bool = False


class AgentToolFabricBindingsResponse(BaseModel):
    agent_id: str
    agent_name: str
    bindings: list[AgentToolFabricBindingItem] = Field(default_factory=list)
    has_custom_overrides: bool = False
    suggested_roles: list[str] = Field(default_factory=list)


class RAGQueryRequest(BaseModel):
    query: str
    document_id: Optional[str] = None
    top_k: int = Field(default=8, ge=1, le=20)
    agent_name: Optional[str] = "Semantic Q&A Assistant"


class RAGQueryResponse(BaseModel):
    answer: str
    mode: str
    confidence: float
    chunks_used: int
    model_used: Optional[str] = None
    citations: list
    findings: list = Field(default_factory=list)


class AgentRunResponse(BaseModel):
    id: str
    agent_id: str
    status: str
    input_json: dict
    output_json: dict
    model_selected: Optional[str] = None
    routing_reason: Optional[str] = None
    citations_json: list
    logs_json: list
    confidence: Optional[float] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Workflows ---


class WorkflowTemplateResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    value_chain_stage: Optional[str] = None
    steps_json: list

    class Config:
        from_attributes = True


class WorkflowRunRequest(BaseModel):
    template_id: str
    name: Optional[str] = None
    input_data: dict = Field(default_factory=dict)


class WorkflowRunResponse(BaseModel):
    id: str
    template_id: Optional[str] = None
    name: str
    status: str
    steps_json: list
    current_step: int
    confidence: Optional[float] = None
    output_json: dict
    evidence_json: list
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- SLM ---


class SLMProfileResponse(BaseModel):
    id: str
    name: str
    model_name: str
    model_type: Optional[str] = None
    task_scope: Optional[str] = None
    fine_tuning_dataset: Optional[str] = None
    token_cost_estimate: Optional[float] = None
    latency_estimate_ms: Optional[int] = None
    accuracy_score: Optional[float] = None
    evaluation_status: str
    deployment_status: str
    fallback_model: Optional[str] = None
    allowed_agents: list

    class Config:
        from_attributes = True


class ModelRouteRequest(BaseModel):
    agent_name: str
    task_type: str
    risk_level: str
    user_query: str
    context: Optional[str] = None


class ModelRoutingDecision(BaseModel):
    selected_model: str
    reason_for_selection: str
    fallback_model: str
    human_review_required: bool
    model_type: str  # "slm" or "frontier"


class ModelEvaluateRequest(BaseModel):
    slm_profile_id: str
    test_dataset: Optional[str] = None


# --- Governance ---


class AuditEventResponse(BaseModel):
    id: str
    event_type: str
    actor: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    action: Optional[str] = None
    details_json: dict
    created_at: datetime

    class Config:
        from_attributes = True


class RiskAlertResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    severity: str
    category: Optional[str] = None
    status: str
    source: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ApprovalRequest(BaseModel):
    approval_id: str
    decision: str  # approved / rejected
    comment: Optional[str] = None


class ApprovalResponse(BaseModel):
    id: str
    title: str
    request_type: Optional[str] = None
    status: str
    requested_by: Optional[str] = None
    agent_run_id: Optional[str] = None
    workflow_run_id: Optional[str] = None
    details_json: dict
    created_at: datetime

    class Config:
        from_attributes = True


# --- Reports ---


class ScientificReportResponse(BaseModel):
    id: str
    title: str
    report_type: str
    content_json: dict
    status: str
    workflow_run_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ReportGenerateRequest(BaseModel):
    report_type: str
    title: str
    source_data: dict = Field(default_factory=dict)


class ReportStatusUpdate(BaseModel):
    status: str


# --- Auth ---


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str
    user_id: str
    full_name: str | None = None


class UserResponse(BaseModel):
    id: str
    username: str
    role: str
    full_name: str | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=2, max_length=128)
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(default="scientist", pattern="^(admin|scientist|reviewer)$")
    full_name: str | None = None


class UserAdminResponse(UserResponse):
    document_count: int = 0
    workflow_count: int = 0


class QuotaStatusResponse(BaseModel):
    quotas_enabled: bool
    max_uploads: int
    max_workflows: int
    uploads_used: int
    workflows_used: int
    uploads_remaining: int | None = None
    workflows_remaining: int | None = None
    uploads_allowed: bool
    workflows_allowed: bool


class DocumentQCResponse(BaseModel):
    document_id: str
    status: str
    score: float
    row_count: int
    column_count: int
    summary: str | None = None
    checks: list[dict] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    column_profile: list[dict] = Field(default_factory=list)
    assay_columns: list[str] = Field(default_factory=list)


class MeetingBriefRequest(BaseModel):
    topic: str
    audience: str = "R&D leadership"
    lookback_days: int = 7


class CollaborationActivityResponse(BaseModel):
    user: dict = Field(default_factory=dict)
    pending_approvals: list[dict] = Field(default_factory=list)
    recent_workflows: list[dict] = Field(default_factory=list)
    recent_agent_runs: list[dict] = Field(default_factory=list)
    open_risks: list[dict] = Field(default_factory=list)
    recent_documents: list[dict] = Field(default_factory=list)
    audit_timeline: list[dict] = Field(default_factory=list)
    project_id: str | None = None


class ProjectCreateRequest(BaseModel):
    name: str
    description: str | None = None


class ProjectMemberAddRequest(BaseModel):
    username: str
    role: str = "member"


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    owner_id: str
    role: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ProjectMemberResponse(BaseModel):
    user_id: str
    username: str
    full_name: str | None = None
    role: str
    joined_at: datetime | None = None


class DockingRequest(BaseModel):
    query_smiles: str
    library: list[dict] = Field(default_factory=list)
    top_k: int = 15
    run_vina: bool = False


class LimsSyncRequest(BaseModel):
    plate_id: str


# --- Custom Tool Fabric (admin) ---


class CustomToolCreateRequest(BaseModel):
    tool_id: str = Field(min_length=3, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=2, max_length=256)
    description: str | None = None
    role_id: str = Field(min_length=2, max_length=64)
    endpoint_url: str = Field(min_length=8, max_length=2048)
    http_method: str = Field(default="POST", pattern=r"^(GET|POST|PUT)$")
    auth_type: str = Field(default="none", pattern=r"^(none|bearer|api_key_header)$")
    auth_header_name: str | None = None
    auth_secret: str | None = None
    request_template: dict = Field(default_factory=dict)
    status: str = Field(default="active", pattern=r"^(active|disabled)$")


class CustomToolUpdateRequest(BaseModel):
    label: str | None = Field(default=None, min_length=2, max_length=256)
    description: str | None = None
    role_id: str | None = Field(default=None, min_length=2, max_length=64)
    endpoint_url: str | None = Field(default=None, min_length=8, max_length=2048)
    http_method: str | None = Field(default=None, pattern=r"^(GET|POST|PUT)$")
    auth_type: str | None = Field(default=None, pattern=r"^(none|bearer|api_key_header)$")
    auth_header_name: str | None = None
    auth_secret: str | None = None
    request_template: dict | None = None
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$")


class CustomToolResponse(BaseModel):
    id: str
    tool_id: str
    label: str
    description: str | None = None
    role_id: str
    role_label: str | None = None
    endpoint_url: str
    http_method: str
    auth_type: str
    auth_header_name: str | None = None
    auth_secret_configured: bool = False
    request_template: dict = Field(default_factory=dict)
    status: str
    is_custom: bool = True
    runtime_status: str = "available"
    registered_by: str
    registered_by_username: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class CustomToolTestRequest(BaseModel):
    sample_payload: dict = Field(default_factory=dict)


class CustomToolTestResponse(BaseModel):
    ok: bool
    status_code: int | None = None
    response_preview: str | None = None
    error: str | None = None
    latency_ms: int | None = None


# --- Dashboard ---


class DashboardStats(BaseModel):
    total_documents: int
    total_entities: int
    graph_nodes: int
    graph_relationships: int
    active_agents: int
    completed_workflows: int
    avg_time_saved_hours: float
    productivity_gain_pct: float
    open_risk_alerts: int
    agent_usage_by_stage: dict[str, int]
