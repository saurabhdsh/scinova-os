"""Target discovery, pathway, and validation agent pipelines."""

from sqlalchemy.orm import Session

from app.config import settings
from app.services.evidence_service import build_evidence_context, evidence_confidence, gather_evidence
from app.services.llm_output_utils import pick_text
from app.services.llm_service import llm_service

PATHWAY_SYSTEM = """You are a pathway analysis expert for drug discovery.
Return JSON with:
- summary: string
- answer: string (pathway analysis narrative)
- pathways: array of {{name, role, druggable_nodes, evidence}}
- druggable_targets: array of {{target, mechanism, rationale, score: 0-1}}
- cascade_effects: array of strings
- confidence: float 0-1"""

TARGET_VALIDATION_SYSTEM = """You are a target validation scientist.
Return JSON with:
- summary: string
- answer: string (validation report)
- validation_score: float 0-1
- evidence_for: array of strings
- evidence_against: array of strings
- gap_analysis: array of strings
- recommendation: "proceed" | "conditional" | "deprioritize"
- suggested_validation_assays: array of strings
- confidence: float 0-1"""

BIOMARKER_SYSTEM = """You are a biomarker discovery analyst.
Return JSON with:
- summary: string
- answer: string
- biomarker_candidates: array of {{name, type, disease_link, evidence_strength, assay_suggestion}}
- panel_recommendation: array of strings
- confidence: float 0-1"""

DRUGGABILITY_SYSTEM = """You are a druggability assessment specialist.
Return JSON with:
- summary: string
- answer: string
- druggability_score: float 0-1
- structural_assessment: string
- modality_recommendations: array of strings (small molecule, biologic, etc.)
- known_tool_compounds: array of strings
- risks: array of strings
- confidence: float 0-1"""


def run_target_discovery_agent(
    db: Session,
    agent,
    input_data: dict,
    *,
    model: str | None = None,
) -> dict:
    query = str(input_data.get("query", "")).strip()
    document_id = input_data.get("document_id")
    top_k = int(input_data.get("top_k") or 8)
    agent_name = (agent.name or "").lower()
    logs: list[dict] = [{"message": "Starting target discovery pipeline"}]

    evidence = gather_evidence(
        db, query,
        tools_used=input_data.get("tools_used") or agent.tools_used or ["KG Query", "KEGG", "Literature Miner"],
        document_id=document_id,
        document_ids=input_data.get("document_ids"),
        user_id=input_data.get("user_id"),
        top_k=top_k,
        include_kegg=True,
        include_kg=True,
    )
    logs.extend(evidence["logs"])
    context = build_evidence_context(evidence)

    if "pathway" in agent_name:
        system, mode_label = PATHWAY_SYSTEM, "pathway_analysis"
    elif "validation" in agent_name:
        system, mode_label = TARGET_VALIDATION_SYSTEM, "target_validation"
    elif "biomarker" in agent_name:
        system, mode_label = BIOMARKER_SYSTEM, "biomarker_discovery"
    elif "druggability" in agent_name:
        system, mode_label = DRUGGABILITY_SYSTEM, "druggability"
    else:
        system, mode_label = TARGET_VALIDATION_SYSTEM, "target_discovery"

    user_prompt = f"""Analysis request:
{query}

Evidence (documents, PubMed, KEGG pathways, knowledge graph):
{context}

Return structured JSON."""

    inference_model = model or settings.llm_model
    structured = None
    mode = "evidence_only"

    if llm_service.is_configured(inference_model):
        logs.append({"message": f"Running target discovery analysis with {inference_model}"})
        structured = llm_service.chat_json(system, user_prompt, model=inference_model)
        if structured:
            mode = mode_label
    else:
        logs.append({"message": "OPENAI_API_KEY not set — retrieval summary only"})

    if not structured:
        answer = f"**Target discovery evidence** for: {query[:200]}\n\n{context[:2500]}"
        structured = {"summary": answer[:400], "answer": answer, "confidence": 0.35}

    answer = pick_text(structured, "answer", "summary")
    summary = pick_text(structured, "summary", default=answer, max_len=300)
    findings = []
    for key in ("druggable_targets", "biomarker_candidates", "pathways", "evidence_for"):
        items = structured.get(key) or []
        for item in items[:3]:
            if isinstance(item, dict):
                findings.append(item.get("name") or item.get("target") or item.get("role") or str(item)[:80])
            else:
                findings.append(str(item)[:80])

    output = {
        "mode": mode,
        "agent": agent.name,
        "query": query,
        "answer": answer,
        "summary": summary,
        "pathways": structured.get("pathways"),
        "druggable_targets": structured.get("druggable_targets"),
        "validation_score": structured.get("validation_score"),
        "recommendation": structured.get("recommendation"),
        "biomarker_candidates": structured.get("biomarker_candidates"),
        "druggability_score": structured.get("druggability_score"),
        "findings": findings[:5],
        "evidence_sources": {
            "vector_chunks": len(evidence["vector_chunks"]),
            "pubmed": len(evidence["pubmed_articles"]),
            "kegg": len(evidence["kegg_entries"]),
            "knowledge_graph": len(evidence["kg_entities"]),
        },
        "model_used": inference_model if mode != "evidence_only" else None,
        "tools_invoked": ["KEGG", "KG Query", "Literature Miner", "Reactome"],
    }

    return {
        "output": output,
        "citations": evidence["citations"],
        "confidence": structured.get("confidence") or structured.get("validation_score") or structured.get("druggability_score") or evidence_confidence(evidence, mode != "evidence_only"),
        "logs": logs,
    }
