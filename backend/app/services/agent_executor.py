"""Agent execution service — RAG, specialized pipelines, and mock fallback."""

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.models.db_models import Agent, AgentRun, AuditEvent
from app.models.schemas import ModelRouteRequest
from app.services.agent_capabilities import (
    agent_supports_specialized,
    get_specialized_task_type,
    is_qa_mode,
    is_experiment_agent,
    is_hypothesis_agent,
    is_knowledge_graph_agent,
    is_literature_agent,
    is_molecular_agent,
    is_report_agent,
    is_target_discovery_agent,
)
from app.services.experiment_service import run_experiment_agent
from app.services.governance_service import create_approval_request
from app.services.hypothesis_service import run_hypothesis_agent
from app.services.knowledge_agent_service import run_knowledge_agent
from app.services.literature_service import run_literature_agent
from app.services.model_router import route_model
from app.services.molecular_service import run_molecular_agent
from app.services.rag_service import agent_supports_rag, run_rag_query
from app.services.report_service import run_report_agent
from app.services.output_style import polish_agent_output
from app.services.target_discovery_service import run_target_discovery_agent


def _resolve_inference_model(routing) -> str:
    if routing.model_type == "slm":
        return settings.slm_model
    selected = routing.selected_model or settings.llm_model
    if selected.startswith("scinova/"):
        return settings.slm_model
    if selected.startswith("gpt-"):
        return settings.llm_model
    return settings.llm_model


def _run_specialized_pipeline(
    db: Session,
    agent: Agent,
    input_data: dict,
    model: str | None,
) -> dict:
    task = get_specialized_task_type(agent)
    if task == "hypothesis" or is_hypothesis_agent(agent):
        return run_hypothesis_agent(db, agent, input_data, model=model)
    if task == "experiment" or is_experiment_agent(agent):
        return run_experiment_agent(db, agent, input_data, model=model)
    if task == "report" or is_report_agent(agent):
        return run_report_agent(db, agent, input_data, model=model)
    if task == "literature" or is_literature_agent(agent):
        return run_literature_agent(db, agent, input_data, model=model)
    if task == "target_discovery" or is_target_discovery_agent(agent):
        return run_target_discovery_agent(db, agent, input_data, model=model)
    if task == "knowledge_graph" or is_knowledge_graph_agent(agent):
        return run_knowledge_agent(db, agent, input_data, model=model)
    if task == "molecular" or is_molecular_agent(agent):
        return run_molecular_agent(db, agent, input_data, model=model)
    raise ValueError(f"No specialized pipeline for agent: {agent.name}")


def execute_agent(
    db: Session,
    agent: Agent,
    input_data: dict,
    context: str | None = None,
    user_id: str | None = None,
    project_id: str | None = None,
) -> AgentRun:
    if user_id:
        input_data = {**input_data, "user_id": user_id}
        if not input_data.get("document_id"):
            from app.services.workspace import document_ids_for_user
            input_data.setdefault("document_ids", document_ids_for_user(db, user_id, project_id))

    route_req = ModelRouteRequest(
        agent_name=agent.name,
        task_type=input_data.get("task_type", "analysis"),
        risk_level=agent.risk_level,
        user_query=input_data.get("query", str(input_data)),
        context=context,
    )
    routing = route_model(route_req)

    run = AgentRun(
        id=str(uuid.uuid4()),
        agent_id=agent.id,
        status="running",
        input_json=input_data,
        model_selected=routing.selected_model,
        routing_reason=routing.reason_for_selection,
        logs_json=[{"timestamp": datetime.utcnow().isoformat(), "message": "Agent execution started"}],
        user_id=user_id,
        project_id=project_id or input_data.get("project_id"),
    )
    db.add(run)
    db.flush()

    for log in input_data.get("_tool_fabric_logs") or []:
        run.logs_json.append({"timestamp": datetime.utcnow().isoformat(), **log})

    model = _resolve_inference_model(routing)
    pipeline = "mock"

    if is_qa_mode(input_data) and agent_supports_rag(agent, input_data):
        doc_id = input_data.get("document_id")
        rag_result = run_rag_query(
            db,
            str(input_data.get("query", "")).strip(),
            document_id=doc_id,
            document_ids=None if doc_id else input_data.get("document_ids"),
            top_k=int(input_data.get("top_k") or 8),
            model=model,
            agent_name=agent.name,
            agent_category=agent.category,
            agent_description=agent.description,
        )
        output = rag_result["output"]
        citations = rag_result["citations"]
        confidence = rag_result["confidence"]
        pipeline = "rag"
        for log in rag_result["logs"]:
            run.logs_json.append({"timestamp": datetime.utcnow().isoformat(), **log})

    elif agent_supports_specialized(agent, input_data):
        spec_result = _run_specialized_pipeline(db, agent, input_data, model)
        output = spec_result["output"]
        output["model_type"] = routing.model_type
        output["human_review_required"] = routing.human_review_required
        citations = spec_result["citations"]
        confidence = spec_result["confidence"]
        pipeline = output.get("mode", "specialized")
        for log in spec_result["logs"]:
            run.logs_json.append({"timestamp": datetime.utcnow().isoformat(), **log})

    elif agent_supports_rag(agent, input_data):
        doc_id = input_data.get("document_id")
        rag_result = run_rag_query(
            db,
            str(input_data.get("query", "")).strip(),
            document_id=doc_id,
            document_ids=None if doc_id else input_data.get("document_ids"),
            top_k=int(input_data.get("top_k") or 8),
            model=model,
            agent_name=agent.name,
            agent_category=agent.category,
            agent_description=agent.description,
        )
        output = rag_result["output"]
        citations = rag_result["citations"]
        confidence = rag_result["confidence"]
        pipeline = "rag"
        for log in rag_result["logs"]:
            run.logs_json.append({"timestamp": datetime.utcnow().isoformat(), **log})

    else:
        output = _generate_mock_output(agent, input_data, routing)
        citations = _generate_citations(db, agent, input_data)
        confidence = round(0.75 + (hash(agent.name) % 20) / 100, 2)
        run.logs_json.append({
            "timestamp": datetime.utcnow().isoformat(),
            "message": (
                "Mock output — provide a query and use Q&A mode, or select a specialized task "
                "(Literature, Target Discovery, Hypothesis, Experiment, Report, ADMET)"
            ),
        })

    run.status = "completed" if (not routing.human_review_required or input_data.get("auto_approve")) else "pending_review"
    run.output_json = polish_agent_output(output)
    run.citations_json = citations
    run.confidence = confidence

    if run.status == "pending_review" and not input_data.get("auto_approve"):
        create_approval_request(
            db,
            title=f"High-risk agent run: {agent.name}",
            request_type="high_risk_agent",
            agent_run_id=run.id,
            details={
                "agent_name": agent.name,
                "query": input_data.get("query"),
                "confidence": confidence,
            },
        )
        run.logs_json.append({
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Queued for human approval in Governance console",
        })

    run.logs_json.append({
        "timestamp": datetime.utcnow().isoformat(),
        "message": "Output generated with evidence trail",
    })
    run.completed_at = datetime.utcnow()

    db.add(AuditEvent(
        event_type="agent_run",
        actor="system",
        resource_type="agent",
        resource_id=agent.id,
        action=f"Agent '{agent.name}' executed",
        details_json={
            "run_id": run.id,
            "model": routing.selected_model,
            "model_type": routing.model_type,
            "human_review": routing.human_review_required,
            "pipeline": pipeline,
            "mode": output.get("mode"),
            "tool_fabric": input_data.get("tool_fabric"),
            "custom_tools_invoked": list((input_data.get("custom_tool_results") or {}).keys()),
        },
    ))

    db.commit()
    db.refresh(run)
    return run


def _generate_mock_output(agent: Agent, input_data: dict, routing) -> dict:
    return {
        "agent": agent.name,
        "mode": "mock",
        "summary": f"Analysis complete for {agent.name}. Processed input with {routing.model_type.upper()} model.",
        "answer": (
            f"Mock analysis output for {agent.name}. "
            "Select Hypothesis Builder, Experiment Planner, Study Report Generator, "
            "or Semantic Q&A Assistant with a query for real LLM pipelines."
        ),
        "findings": [
            f"Primary finding from {agent.category} analysis",
            "Secondary evidence supports hypothesis with moderate confidence",
            "Recommend follow-up validation experiment",
        ],
        "metrics": {
            "confidence": round(0.75 + (hash(agent.name) % 20) / 100, 2),
            "evidence_count": 5 + hash(agent.name) % 10,
            "processing_time_ms": 1200 + hash(agent.name) % 3000,
        },
        "model_used": routing.selected_model,
        "model_type": routing.model_type,
        "human_review_required": routing.human_review_required,
    }


def _generate_citations(db: Session, agent: Agent, input_data: dict) -> list:
    query = input_data.get("query", agent.name)
    try:
        from app.services.ingestion_pipeline import semantic_search
        from app.services.rag_service import _enrich_hits, _build_citations

        hits = semantic_search(str(query), top_k=3)
        chunks = _enrich_hits(db, hits)
        if chunks:
            return _build_citations(chunks)
    except Exception:
        pass
    return [
        {
            "title": "No indexed evidence found",
            "source": "vector_index",
            "relevance": 0.0,
            "excerpt": "Upload documents in Data Fabric to enable citations.",
        },
    ]
