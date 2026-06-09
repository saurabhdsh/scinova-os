"""Experiment design and planning agent pipeline."""

from sqlalchemy.orm import Session

from app.config import settings
from app.services.evidence_service import build_evidence_context, evidence_confidence, gather_evidence
from app.services.llm_output_utils import pick_text
from app.services.llm_service import llm_service

EXPERIMENT_PLAN_SYSTEM = """You are a preclinical experiment design specialist for pharma R&D.
Design rigorous, feasible experiments grounded in the evidence provided.

Return JSON with:
- summary: string
- answer: string (full narrative plan)
- experiment_plan: object with:
  - objective: string
  - study_type: string (in vitro | in vivo | clinical | assay development)
  - model_system: string
  - primary_endpoints: array of strings
  - secondary_endpoints: array of strings
  - sample_size_rationale: string
  - duration_weeks: number
  - controls: array of strings
  - materials: array of strings
  - timeline: array of objects {{phase, duration, activities}}
  - success_criteria: array of strings
- resources: object with personnel, equipment, budget_estimate
- risks: array of strings
- confidence: float 0-1"""

DOE_SYSTEM = """You are a Design of Experiments (DOE) specialist.
Return JSON with:
- summary: string
- answer: string
- doe_design: object with:
  - factors: array of {{name, levels, type}}
  - design_type: string (full factorial | fractional factorial | response surface)
  - runs: array of objects {{run_id, factor_settings, replicates}}
  - response_variables: array of strings
  - statistical_plan: string
  - power_analysis: string
- confidence: float 0-1"""


def run_experiment_agent(
    db: Session,
    agent,
    input_data: dict,
    *,
    model: str | None = None,
) -> dict:
    query = str(input_data.get("query", "")).strip()
    document_id = input_data.get("document_id")
    top_k = int(input_data.get("top_k") or 6)
    agent_name = agent.name or "Experiment Agent"
    is_doe = "doe" in (agent.name or "").lower()
    logs: list[dict] = [{"message": "Starting experiment design pipeline"}]

    evidence = gather_evidence(
        db,
        query,
        tools_used=input_data.get("tools_used") or agent.tools_used or [],
        document_id=document_id,
        document_ids=input_data.get("document_ids"),
        user_id=input_data.get("user_id"),
        project_id=input_data.get("project_id"),
        top_k=top_k,
        include_eln=True,
    )
    logs.extend(evidence["logs"])

    qc_context = ""
    if document_id:
        from app.models.db_models import Document
        doc = db.query(Document).filter(Document.id == document_id).first()
        qc = (doc.metadata_json or {}).get("qc_report") if doc else None
        if qc:
            logs.append({"message": f"Assay QC status: {qc.get('status')} (score {qc.get('score')})"})
            qc_context = f"\n\nAssay dataset QC report:\nStatus: {qc.get('status')}\nSummary: {qc.get('summary')}\nFlags: {', '.join(qc.get('flags') or [])}"

    context = build_evidence_context(evidence) + qc_context
    system = DOE_SYSTEM if is_doe else EXPERIMENT_PLAN_SYSTEM
    user_prompt = f"""Experiment design request:
{query}

Report mode: {"full scientific report" if input_data.get("report_type") == "experiment_plan" else "structured plan"}

Prior context and evidence (documents, PubMed, KEGG, ELN records, knowledge graph):
{context}

Design the experiment following your JSON schema."""

    inference_model = model or settings.llm_model
    structured = None
    mode = "evidence_only"

    if llm_service.is_configured(inference_model):
        logs.append({"message": f"Generating experiment design with {inference_model}"})
        structured = llm_service.chat_json(system, user_prompt, model=inference_model)
        if structured:
            mode = "experiment_design"
            logs.append({"message": "Experiment plan generated"})
    else:
        logs.append({"message": "OPENAI_API_KEY not set — returning evidence summary only"})

    if not structured:
        answer = (
            "**Evidence for experiment planning** (configure OPENAI_API_KEY for full design)\n\n"
            + context[:2000]
        )
        structured = {
            "summary": "Retrieval-only experiment context",
            "answer": answer,
            "experiment_plan": {
                "objective": query[:200],
                "study_type": "to be determined",
                "primary_endpoints": ["Define based on hypothesis"],
            },
            "confidence": 0.35,
        }

    answer = pick_text(structured, "answer", "summary")
    summary = pick_text(structured, "summary", default=answer, max_len=1200)
    plan = structured.get("experiment_plan") or structured.get("doe_design", {})
    findings = []
    if isinstance(plan, dict):
        findings = plan.get("primary_endpoints") or plan.get("response_variables") or []
    if structured.get("risks"):
        findings = findings + structured["risks"][:2]

    output = {
        "mode": mode,
        "agent": agent_name,
        "query": query,
        "answer": answer,
        "summary": summary,
        "experiment_plan": structured.get("experiment_plan"),
        "doe_design": structured.get("doe_design"),
        "resources": structured.get("resources"),
        "risks": structured.get("risks", []),
        "findings": findings[:5],
        "evidence_sources": {
            "vector_chunks": len(evidence["vector_chunks"]),
            "pubmed": len(evidence["pubmed_articles"]),
            "eln_records": len(evidence["eln_records"]),
        },
        "model_used": inference_model if mode == "experiment_design" else None,
        "tools_invoked": ["Protocol DB", "Statistical Planner", "ELN Connector", "PubMed", "KEGG"],
    }

    return {
        "output": output,
        "citations": evidence["citations"],
        "confidence": structured.get("confidence") or evidence_confidence(evidence, mode == "experiment_design"),
        "logs": logs,
    }
