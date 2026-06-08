from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import CurrentUser, get_current_user
from app.dependencies.project import OptionalProjectId
from app.models.db_models import (
    Agent, AgentRun, ApprovalRequest, AuditEvent, DataSource,
    Document, DocumentChunk, GraphNode, GraphRelationship, IngestionJob,
    RiskAlert, SLMProfile, ScientificEntity, ScientificReport,
    WorkflowRun, WorkflowTemplate, User,
)
from app.models.schemas import (
    AgentRunRequest, AgentRunResponse, AgentResponse,
    ApprovalRequest as ApprovalReq, ApprovalResponse,
    AuditEventResponse, DashboardStats, DataSourceResponse,
    DocumentChunkResponse, DocumentResponse, FabricSearchRequest,
    FabricSearchResult, FabricStatsResponse, GraphNeighborhoodResponse,
    GraphNodeCreate, GraphNodeResponse, GraphRelationshipCreate,
    GraphRelationshipResponse, GraphSearchResponse, GraphStatsResponse,
    IngestionJobResponse, RAGQueryRequest, RAGQueryResponse,
    ModelEvaluateRequest, ModelRouteRequest, ModelRoutingDecision,
    ReportGenerateRequest, ReportStatusUpdate, RiskAlertResponse, SLMProfileResponse,
    ScientificEntityResponse, ScientificReportResponse, AgentTaskSettingsResponse,
    AgentToolFabricBindingsResponse,
    AgentTaskSettingsUpdate, WorkflowRunRequest,
    WorkflowRunResponse, WorkflowTemplateResponse, QuotaStatusResponse,
    DocumentQCResponse, MeetingBriefRequest, CollaborationActivityResponse,
    ProjectCreateRequest, ProjectMemberAddRequest, ProjectResponse, ProjectMemberResponse,
    DockingRequest, LimsSyncRequest,
)
from app.services.agent_executor import execute_agent
from app.services.agent_settings_service import apply_agent_task_settings, get_agent_task_settings, save_agent_task_settings
from app.services.tool_fabric_service import (
    get_tool_fabric_catalog,
    suggested_roles_for_agent,
    default_bindings_for_agent,
    get_agent_tool_fabric_bindings_view,
)
from app.services.rag_service import run_rag_query
from app.config import settings
from app.services.ingestion_pipeline import (
    INGESTION_STAGES, semantic_search, start_ingestion,
)
from app.services.model_router import route_model
from app.services.workflow_orchestrator import execute_workflow_run, resume_workflow, run_workflow
from app.services.workflow_pipelines import list_workflow_pipelines
from app.services.workflow_export_service import (
    build_step_markdown,
    build_workflow_json_bytes,
    build_workflow_markdown,
    export_filename,
)
from app.services.governance_service import process_approval, run_gxp_check, acknowledge_risk_alert
from app.services.neo4j_client import neo4j_client
from app.services import graph_service
from app.services.report_service import generate_scientific_report, update_report_status
from app.services.report_export_service import export_report
from app.services.report_export_service import export_report
from app.services.external_integrations import integration_status
from app.services.chromadb_client import chromadb_client
from app.services import workspace as ws
from app.services.task_queue import enqueue_ingestion
from app.services.quota_service import assert_upload_allowed, assert_workflow_allowed, get_quota_status
from app.services.meeting_brief_service import generate_meeting_brief, get_collaboration_activity
from app.services.chemoinformatics_service import rdkit_available
from app.services.docking_service import run_docking_pipeline, vina_available
from app.services.lims_service import list_lims_plates, sync_lims_plate
from app.services.brief_export_service import export_brief
from app.services import project_service as proj

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/dashboard/stats", response_model=DashboardStats)
def get_dashboard_stats(
    current_user: CurrentUser,
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    agent_usage = {}
    for stage in ["Target Discovery", "Lead Identification", "Lead Optimization",
                  "Preclinical Studies", "Early Development & CMC", "Cross-Functional", "Foundation"]:
        count = db.query(Agent).filter(Agent.value_chain_stage == stage).count()
        agent_usage[stage] = count
    doc_q = ws.document_query_for_user(db, current_user.id, project_id)
    entity_q = ws.entity_query_for_user(db, current_user.id, project_id)
    wf_q = ws.workflow_query_for_user(db, current_user.id, project_id)
    return DashboardStats(
        total_documents=doc_q.count(),
        total_entities=entity_q.count(),
        graph_nodes=db.query(GraphNode).count(),
        graph_relationships=db.query(GraphRelationship).count(),
        active_agents=db.query(Agent).filter(Agent.status == "ready").count(),
        completed_workflows=wf_q.filter(WorkflowRun.status == "completed").count(),
        avg_time_saved_hours=6.2,
        productivity_gain_pct=18.5,
        open_risk_alerts=db.query(RiskAlert).filter(RiskAlert.status == "open").count(),
        agent_usage_by_stage=agent_usage,
    )


# --- Account ---

@router.get("/account/quotas", response_model=QuotaStatusResponse)
def get_my_quotas(current_user: CurrentUser, db: Session = Depends(get_db)):
    return get_quota_status(db, current_user)


# --- Data Fabric ---

@router.post("/ingest/upload", response_model=IngestionJobResponse)
async def upload_document(
    current_user: CurrentUser,
    file: UploadFile = File(...),
    source_type: str = Form("file_upload"),
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    assert_upload_allowed(db, current_user)
    if project_id:
        proj.assert_project_access(db, current_user.id, project_id)
    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty file")
    job = start_ingestion(
        db,
        file.filename or "upload.txt",
        content,
        source_type,
        user_id=current_user.id,
        project_id=project_id,
    )
    enqueue_ingestion(job.id)
    return job


@router.get("/ingest/status/{job_id}", response_model=IngestionJobResponse)
def get_ingestion_status(
    job_id: str,
    current_user: CurrentUser,
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    return ws.get_user_job(db, current_user.id, job_id, project_id)


@router.post("/ingest/retry/{job_id}", response_model=IngestionJobResponse)
def retry_ingestion(
    job_id: str,
    current_user: CurrentUser,
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    """Re-run a stuck or failed ingestion job."""
    job = ws.get_user_job(db, current_user.id, job_id, project_id)
    if job.status not in ("processing", "failed", "pending"):
        raise HTTPException(400, f"Job cannot be retried from status '{job.status}'")
    job.status = "processing"
    job.stage = "upload"
    job.progress = 0.0
    job.stages_completed = []
    job.error_message = None
    job.completed_at = None
    if job.document_id:
        doc = db.query(Document).filter(Document.id == job.document_id).first()
        if doc:
            doc.status = "processing"
    db.commit()
    db.refresh(job)
    enqueue_ingestion(job.id)
    return job


@router.get("/ingest/stages")
def get_ingestion_stages():
    return {"stages": INGESTION_STAGES}


@router.get("/documents", response_model=list[DocumentResponse])
def list_documents(
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 50,
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    return (
        ws.document_query_for_user(db, current_user.id, project_id)
        .order_by(Document.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: str,
    current_user: CurrentUser,
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    return ws.get_user_document(db, current_user.id, document_id, project_id)


@router.get("/documents/{document_id}/chunks", response_model=list[DocumentChunkResponse])
def get_document_chunks(
    document_id: str,
    current_user: CurrentUser,
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    ws.get_user_document(db, current_user.id, document_id, project_id)
    return (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
        .all()
    )


@router.get("/documents/{document_id}/qc", response_model=DocumentQCResponse)
def get_document_qc(
    document_id: str,
    current_user: CurrentUser,
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    doc = ws.get_user_document(db, current_user.id, document_id, project_id)
    qc = (doc.metadata_json or {}).get("qc_report")
    if not qc:
        raise HTTPException(404, "No QC report for this document (upload CSV/XLSX assay data)")
    return DocumentQCResponse(document_id=doc.id, **qc)


# --- Collaboration ---

@router.get("/collaboration/activity", response_model=CollaborationActivityResponse)
def collaboration_activity(
    current_user: CurrentUser,
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    return get_collaboration_activity(db, current_user.id, project_id=project_id)


@router.post("/collaboration/meeting-brief", response_model=ScientificReportResponse)
def create_meeting_brief(
    body: MeetingBriefRequest,
    current_user: CurrentUser,
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    return generate_meeting_brief(
        db,
        current_user.id,
        topic=body.topic,
        audience=body.audience,
        lookback_days=body.lookback_days,
        project_id=project_id,
    )


@router.get("/collaboration/meeting-brief/{report_id}/export")
def export_meeting_brief(
    report_id: str,
    current_user: CurrentUser,
    format: str = "markdown",
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    report = ws.get_user_report(db, current_user.id, report_id, project_id)
    if report.report_type != "meeting_brief":
        raise HTTPException(400, "Report is not a meeting brief")
    content, filename, media_type = export_brief(report, format)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/collaboration/chemoinformatics/status")
def chemoinformatics_status():
    return {
        "rdkit_available": rdkit_available(),
        "vina_available": vina_available(),
        "engine": "rdkit" if rdkit_available() else "heuristic",
    }


@router.post("/chemoinformatics/dock")
def run_docking(body: DockingRequest, current_user: CurrentUser):
    payload = {
        "query_smiles": body.query_smiles,
        "library": body.library,
        "top_k": body.top_k,
        "run_vina": body.run_vina,
    }
    if body.library:
        payload["compounds"] = body.library
    return run_docking_pipeline(payload)


# --- Projects ---

@router.get("/projects", response_model=list[ProjectResponse])
def list_projects(current_user: CurrentUser, db: Session = Depends(get_db)):
    return proj.list_projects_for_user(db, current_user.id)


@router.post("/projects", response_model=ProjectResponse)
def create_project(body: ProjectCreateRequest, current_user: CurrentUser, db: Session = Depends(get_db)):
    project = proj.create_project(db, current_user, body.name, body.description)
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "owner_id": project.owner_id,
        "role": "owner",
        "created_at": project.created_at,
    }


@router.get("/projects/{project_id}/members", response_model=list[ProjectMemberResponse])
def get_project_members(project_id: str, current_user: CurrentUser, db: Session = Depends(get_db)):
    return proj.list_project_members(db, current_user.id, project_id)


@router.post("/projects/{project_id}/members", response_model=ProjectMemberResponse)
def add_project_member(
    project_id: str,
    body: ProjectMemberAddRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    member = proj.add_project_member(
        db, project_id, current_user.id, body.username, role=body.role,
    )
    user = db.query(User).filter(User.id == member.user_id).first()
    return {
        "user_id": member.user_id,
        "username": user.username if user else body.username,
        "full_name": user.full_name if user else None,
        "role": member.role,
        "joined_at": member.created_at,
    }


# --- LIMS ---

@router.get("/integrations/lims/plates")
def lims_plates(current_user: CurrentUser, db: Session = Depends(get_db)):
    return list_lims_plates(db)


@router.post("/integrations/lims/sync/{plate_id}")
def lims_sync_plate(
    plate_id: str,
    current_user: CurrentUser,
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    assert_upload_allowed(db, current_user)
    if project_id:
        proj.assert_project_access(db, current_user.id, project_id)
    try:
        return sync_lims_plate(
            db, user_id=current_user.id, plate_id=plate_id, project_id=project_id,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/entities", response_model=list[ScientificEntityResponse])
def list_entities(
    current_user: CurrentUser,
    entity_type: str | None = None,
    document_id: str | None = None,
    skip: int = 0,
    limit: int = 100,
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    q = ws.entity_query_for_user(db, current_user.id, project_id)
    if entity_type:
        q = q.filter(ScientificEntity.entity_type == entity_type)
    if document_id:
        ws.assert_document_in_workspace(db, current_user.id, document_id, project_id)
        q = q.filter(ScientificEntity.source_document_id == document_id)
    return q.order_by(ScientificEntity.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/entities/{entity_id}", response_model=ScientificEntityResponse)
def get_entity(
    entity_id: str,
    current_user: CurrentUser,
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    entity = ws.entity_query_for_user(db, current_user.id, project_id).filter(ScientificEntity.id == entity_id).first()
    if not entity:
        raise HTTPException(404, "Entity not found")
    return entity


@router.post("/fabric/search", response_model=list[FabricSearchResult])
def fabric_search(
    body: FabricSearchRequest,
    current_user: CurrentUser,
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    if body.document_id:
        ws.assert_document_in_workspace(db, current_user.id, body.document_id, project_id)
    doc_ids = ws.document_ids_for_user(db, current_user.id, project_id)
    results = semantic_search(
        body.query,
        top_k=body.top_k,
        document_id=body.document_id,
        document_ids=None if body.document_id else doc_ids,
    )
    return [FabricSearchResult(**r) for r in results]


@router.get("/fabric/stats", response_model=FabricStatsResponse)
def fabric_stats(
    current_user: CurrentUser,
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    chroma_stats = chromadb_client.stats()
    doc_q = ws.document_query_for_user(db, current_user.id, project_id)
    return FabricStatsResponse(
        collection=chroma_stats["collection"],
        mode=chroma_stats["mode"],
        total_chunks=chroma_stats["total_chunks"],
        total_documents=doc_q.filter(Document.status == "indexed").count(),
        total_entities=ws.entity_query_for_user(db, current_user.id, project_id).count(),
    )


@router.get("/data-sources", response_model=list[DataSourceResponse])
def list_data_sources(db: Session = Depends(get_db)):
    return db.query(DataSource).all()


# --- Knowledge Graph ---

@router.post("/graph/node", response_model=GraphNodeResponse)
def create_graph_node(data: GraphNodeCreate, db: Session = Depends(get_db)):
    node = GraphNode(**data.model_dump())
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


@router.post("/graph/relationship", response_model=GraphRelationshipResponse)
def create_graph_relationship(data: GraphRelationshipCreate, db: Session = Depends(get_db)):
    rel = GraphRelationship(**data.model_dump())
    db.add(rel)
    db.commit()
    db.refresh(rel)
    return rel


@router.get("/graph/search", response_model=GraphSearchResponse)
def search_graph_route(
    current_user: CurrentUser,
    q: str = "",
    entity_type: str | None = None,
    document_id: str | None = None,
    live_only: bool = False,
    source: str = "auto",
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    if document_id:
        ws.assert_document_in_workspace(db, current_user.id, document_id, project_id)
    return graph_service.search_graph(
        db, q=q, entity_type=entity_type, document_id=document_id,
        live_only=live_only, source=source, user_id=current_user.id,
    )


@router.get("/graph/stats", response_model=GraphStatsResponse)
def graph_stats(
    current_user: CurrentUser,
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    neo = neo4j_client.stats()
    entity_q = ws.entity_query_for_user(db, current_user.id, project_id)
    entity_ids = [r[0] for r in entity_q.with_entities(ScientificEntity.id).all()]
    live_nodes = (
        db.query(GraphNode)
        .filter(GraphNode.entity_id.in_(entity_ids))
        .count()
        if entity_ids
        else 0
    )
    docs_with_graph = (
        entity_q.filter(ScientificEntity.source_document_id.isnot(None))
        .with_entities(ScientificEntity.source_document_id)
        .distinct()
        .count()
    )
    node_ids = (
        db.query(GraphNode.id).filter(GraphNode.entity_id.in_(entity_ids)).all()
        if entity_ids
        else []
    )
    node_id_set = {r[0] for r in node_ids}
    sql_rels = 0
    if node_id_set:
        sql_rels = db.query(GraphRelationship).filter(
            GraphRelationship.source_node_id.in_(node_id_set)
            | GraphRelationship.target_node_id.in_(node_id_set)
        ).count()
    active = graph_service.resolve_graph_source("auto")
    return GraphStatsResponse(
        sql_nodes=live_nodes,
        sql_relationships=sql_rels,
        neo4j_connected=neo.get("connected", False),
        neo4j_nodes=neo.get("nodes", 0),
        neo4j_relationships=neo.get("relationships", 0),
        documents_with_graph=docs_with_graph,
        live_ingested_nodes=live_nodes,
        active_graph_source=active,
    )


@router.post("/graph/sync")
def sync_graph_to_neo4j(db: Session = Depends(get_db)):
    """Bulk sync SQL graph → Neo4j."""
    result = graph_service.sync_graph_to_neo4j(db)
    neo = neo4j_client.stats()
    return {**result, "neo4j_stats": neo}


@router.get("/graph/neighborhood/{entity_id}", response_model=GraphNeighborhoodResponse)
def get_neighborhood_route(
    entity_id: str,
    current_user: CurrentUser,
    source: str = "auto",
    depth: int = 2,
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    ws.assert_graph_access(db, current_user.id, entity_id, project_id)
    result = graph_service.get_neighborhood(
        db, entity_id, source=source, depth=depth, user_id=current_user.id,
    )
    if not result:
        raise HTTPException(404, "Node not found")
    return result


@router.get("/graph/full", response_model=GraphSearchResponse)
def get_full_graph_route(
    current_user: CurrentUser,
    limit: int = 80,
    document_id: str | None = None,
    live_only: bool = False,
    source: str = "auto",
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    if document_id:
        ws.assert_document_in_workspace(db, current_user.id, document_id, project_id)
    return graph_service.get_full_graph(
        db, limit=limit, document_id=document_id, live_only=live_only, source=source,
        user_id=current_user.id,
    )


# --- Agents ---

@router.post("/rag/query", response_model=RAGQueryResponse)
def rag_query(
    body: RAGQueryRequest,
    current_user: CurrentUser,
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    """Direct RAG Q&A over the vector index (Phase 4)."""
    if body.document_id:
        ws.assert_document_in_workspace(db, current_user.id, body.document_id, project_id)
    doc_ids = ws.document_ids_for_user(db, current_user.id, project_id)
    result = run_rag_query(
        db,
        body.query,
        document_id=body.document_id,
        document_ids=None if body.document_id else doc_ids,
        top_k=body.top_k,
        model=settings.llm_model,
        agent_name=body.agent_name or "Semantic Q&A Assistant",
    )
    output = result["output"]
    return RAGQueryResponse(
        answer=output.get("answer", ""),
        mode=output.get("mode", "unknown"),
        confidence=result["confidence"],
        chunks_used=output.get("chunks_used", 0),
        model_used=output.get("model_used"),
        citations=result["citations"],
        findings=output.get("findings") or [],
    )


@router.get("/agents", response_model=list[AgentResponse])
def list_agents(
    category: str | None = None,
    value_chain_stage: str | None = None,
    slm_eligible: bool | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Agent)
    if category:
        q = q.filter(Agent.category == category)
    if value_chain_stage:
        q = q.filter(Agent.value_chain_stage == value_chain_stage)
    if slm_eligible is not None:
        q = q.filter(Agent.slm_eligible == slm_eligible)
    return q.order_by(Agent.value_chain_stage, Agent.name).all()


@router.get("/agents/{agent_id}", response_model=AgentResponse)
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent


@router.post("/agents/{agent_id}/run", response_model=AgentRunResponse)
def run_agent(
    agent_id: str,
    body: AgentRunRequest,
    current_user: CurrentUser,
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    if body.input_data.get("document_id"):
        ws.assert_document_in_workspace(db, current_user.id, body.input_data["document_id"], project_id)
    input_data = apply_agent_task_settings(db, current_user.id, agent, body.input_data)
    input_data["user_id"] = current_user.id
    if project_id:
        input_data["project_id"] = project_id
    if not input_data.get("document_id"):
        input_data.setdefault("document_ids", ws.document_ids_for_user(db, current_user.id, project_id))
    return execute_agent(db, agent, input_data, body.context, user_id=current_user.id, project_id=project_id)


@router.get("/agents/{agent_id}/runs", response_model=list[AgentRunResponse])
def get_agent_runs(agent_id: str, current_user: CurrentUser, db: Session = Depends(get_db)):
    return (
        db.query(AgentRun)
        .filter(AgentRun.agent_id == agent_id, AgentRun.user_id == current_user.id)
        .order_by(AgentRun.created_at.desc())
        .limit(20)
        .all()
    )


# --- Agent task settings ---

@router.get("/settings/agent-tasks", response_model=AgentTaskSettingsResponse)
def read_agent_task_settings(current_user: CurrentUser, db: Session = Depends(get_db)):
    return get_agent_task_settings(db, current_user.id)


@router.put("/settings/agent-tasks", response_model=AgentTaskSettingsResponse)
def update_agent_task_settings(body: AgentTaskSettingsUpdate, current_user: CurrentUser, db: Session = Depends(get_db)):
    return save_agent_task_settings(db, current_user.id, body.model_dump(exclude_unset=True))


@router.get("/settings/tool-fabric")
def read_tool_fabric_catalog(current_user: CurrentUser, db: Session = Depends(get_db)):
    return get_tool_fabric_catalog(db)


@router.get("/agents/{agent_id}/tool-fabric/defaults")
def get_agent_tool_fabric_defaults(agent_id: str, current_user: CurrentUser, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    return {
        "agent_id": agent.id,
        "agent_name": agent.name,
        "suggested_roles": suggested_roles_for_agent(agent),
        "default_bindings": default_bindings_for_agent(agent),
    }


@router.get("/agents/{agent_id}/tool-fabric/bindings", response_model=AgentToolFabricBindingsResponse)
def get_agent_tool_fabric_bindings(agent_id: str, current_user: CurrentUser, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    return get_agent_tool_fabric_bindings_view(db, current_user.id, agent)


# --- Workflows ---

@router.get("/workflows/pipelines")
def get_workflow_pipelines(db: Session = Depends(get_db)):
    return list_workflow_pipelines(db)


@router.get("/workflows/templates", response_model=list[WorkflowTemplateResponse])
def list_workflow_templates(db: Session = Depends(get_db)):
    return db.query(WorkflowTemplate).all()


@router.post("/workflows/run", response_model=WorkflowRunResponse)
def execute_workflow(
    body: WorkflowRunRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    template = db.query(WorkflowTemplate).filter(WorkflowTemplate.id == body.template_id).first()
    if not template:
        raise HTTPException(404, "Workflow template not found")
    assert_workflow_allowed(db, current_user)
    if project_id:
        proj.assert_project_access(db, current_user.id, project_id)
    run = run_workflow(db, template, body.name, body.input_data, user_id=current_user.id, project_id=project_id)
    background_tasks.add_task(execute_workflow_run, run.id)
    return run


@router.get("/workflows/{workflow_id}/status", response_model=WorkflowRunResponse)
def get_workflow_status(workflow_id: str, current_user: CurrentUser, db: Session = Depends(get_db)):
    return ws.get_user_workflow(db, current_user.id, workflow_id)


@router.get("/workflows/runs", response_model=list[WorkflowRunResponse])
def list_workflow_runs(
    current_user: CurrentUser,
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    return (
        ws.workflow_query_for_user(db, current_user.id, project_id)
        .order_by(WorkflowRun.created_at.desc())
        .limit(20)
        .all()
    )


@router.get("/workflows/{workflow_id}/export")
def export_workflow(
    workflow_id: str,
    current_user: CurrentUser,
    format: str = "markdown",
    db: Session = Depends(get_db),
):
    run = ws.get_user_workflow(db, current_user.id, workflow_id)
    fmt = format.lower()
    if fmt == "json":
        content = build_workflow_json_bytes(run)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{export_filename(run, ext="json")}"'},
        )
    if fmt == "markdown":
        content = build_workflow_markdown(run).encode("utf-8")
        return Response(
            content=content,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{export_filename(run, ext="md")}"'},
        )
    raise HTTPException(400, "format must be 'markdown' or 'json'")


@router.get("/workflows/{workflow_id}/steps/{step_index}/export")
def export_workflow_step(
    workflow_id: str,
    step_index: int,
    current_user: CurrentUser,
    format: str = "markdown",
    db: Session = Depends(get_db),
):
    run = ws.get_user_workflow(db, current_user.id, workflow_id)
    fmt = format.lower()
    if fmt != "markdown":
        raise HTTPException(400, "Per-step export supports format=markdown only")
    try:
        content = build_step_markdown(run, step_index).encode("utf-8")
    except IndexError:
        raise HTTPException(404, "Step not found")
    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{export_filename(run, step_index=step_index, ext="md")}"',
        },
    )


@router.post("/workflows/{workflow_id}/resume", response_model=WorkflowRunResponse)
def resume_workflow_run(
    workflow_id: str,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    approved: bool = True,
    db: Session = Depends(get_db),
):
    run = ws.get_user_workflow(db, current_user.id, workflow_id)
    if run.status not in ("pending_approval", "running"):
        raise HTTPException(400, f"Workflow cannot be resumed from status '{run.status}'")
    run = resume_workflow(db, workflow_id, approved=approved)
    if approved and run.status == "running":
        background_tasks.add_task(execute_workflow_run, run.id)
    return run


# --- SLM ---

@router.get("/models/slm", response_model=list[SLMProfileResponse])
def list_slm_profiles(db: Session = Depends(get_db)):
    return db.query(SLMProfile).all()


@router.post("/models/route", response_model=ModelRoutingDecision)
def route_model_endpoint(body: ModelRouteRequest):
    return route_model(body)


@router.post("/models/evaluate")
def evaluate_slm(body: ModelEvaluateRequest, db: Session = Depends(get_db)):
    profile = db.query(SLMProfile).filter(SLMProfile.id == body.slm_profile_id).first()
    if not profile:
        raise HTTPException(404, "SLM profile not found")
    return {
        "profile_id": profile.id,
        "profile_name": profile.name,
        "evaluation_status": "simulated_complete",
        "accuracy_score": profile.accuracy_score,
        "metrics": {"precision": 0.89, "recall": 0.87, "f1": 0.88, "latency_p95_ms": profile.latency_estimate_ms},
    }


# --- Governance ---

@router.get("/audit", response_model=list[AuditEventResponse])
def list_audit_events(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    return db.query(AuditEvent).order_by(AuditEvent.created_at.desc()).offset(skip).limit(limit).all()


@router.post("/approval")
def process_approval_endpoint(body: ApprovalReq, current_user: CurrentUser, db: Session = Depends(get_db)):
    try:
        return process_approval(
            db,
            body.approval_id,
            body.decision,
            actor=current_user.username,
            comment=body.comment,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/governance/gxp-check")
def gxp_check(db: Session = Depends(get_db)):
    return run_gxp_check(db)


@router.post("/risk-alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str, current_user: CurrentUser, db: Session = Depends(get_db)):
    try:
        alert = acknowledge_risk_alert(db, alert_id, actor=current_user.username)
        return {"status": "acknowledged", "alert_id": alert.id}
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/approvals", response_model=list[ApprovalResponse])
def list_approvals(db: Session = Depends(get_db)):
    return db.query(ApprovalRequest).order_by(ApprovalRequest.created_at.desc()).all()


@router.get("/risk-alerts", response_model=list[RiskAlertResponse])
def list_risk_alerts(db: Session = Depends(get_db)):
    return db.query(RiskAlert).order_by(RiskAlert.created_at.desc()).all()


# --- Reports ---

@router.get("/integrations/status")
def get_integrations_status(db: Session = Depends(get_db)):
    return integration_status(db)


@router.get("/reports", response_model=list[ScientificReportResponse])
def list_reports(
    current_user: CurrentUser,
    report_type: str | None = None,
    exclude_meeting_briefs: bool = True,
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    q = ws.report_query_for_user(db, current_user.id, project_id)
    if report_type:
        q = q.filter(ScientificReport.report_type == report_type)
    elif exclude_meeting_briefs:
        q = q.filter(ScientificReport.report_type != "meeting_brief")
    return q.order_by(ScientificReport.created_at.desc()).all()


@router.get("/reports/{report_id}", response_model=ScientificReportResponse)
def get_report(
    report_id: str,
    current_user: CurrentUser,
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    return ws.get_user_report(db, current_user.id, report_id, project_id)


@router.get("/reports/{report_id}/export")
def export_scientific_report(
    report_id: str,
    current_user: CurrentUser,
    format: str = "markdown",
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    report = ws.get_user_report(db, current_user.id, report_id, project_id)
    try:
        content, filename, media_type = export_report(report, format)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.patch("/reports/{report_id}/status", response_model=ScientificReportResponse)
def patch_report_status(
    report_id: str,
    body: ReportStatusUpdate,
    current_user: CurrentUser,
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    report = ws.get_user_report(db, current_user.id, report_id, project_id)
    try:
        return update_report_status(db, report, body.status, actor=current_user.username)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/reports/generate", response_model=ScientificReportResponse)
def generate_report(
    body: ReportGenerateRequest,
    current_user: CurrentUser,
    project_id: OptionalProjectId = None,
    db: Session = Depends(get_db),
):
    if body.source_data.get("document_id"):
        ws.assert_document_in_workspace(db, current_user.id, body.source_data["document_id"], project_id)
    if project_id:
        proj.assert_project_access(db, current_user.id, project_id)
    source_data = {
        **body.source_data,
        "initiated_by": current_user.username,
        "user_id": current_user.id,
        "project_id": project_id,
        "document_ids": ws.document_ids_for_user(db, current_user.id, project_id),
    }
    report = generate_scientific_report(
        db,
        report_type=body.report_type,
        title=body.title,
        source_data=source_data,
        user_id=current_user.id,
        project_id=project_id,
    )
    return report
