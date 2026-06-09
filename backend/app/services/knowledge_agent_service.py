"""Knowledge graph building and ontology mapping agent pipelines."""

from sqlalchemy.orm import Session

from app.config import settings
from app.services.evidence_service import build_evidence_context, evidence_confidence, gather_evidence
from app.services.llm_output_utils import pick_text
from app.services.llm_service import llm_service

ONTOLOGY_SYSTEM = """You are a biomedical ontology mapping specialist.
Return JSON with:
- summary: string
- answer: string
- mapped_entities: array of {{raw_name, standard_name, ontology: UMLS|GO|ChEBI|HGNC, ontology_id, confidence}}
- unmapped_entities: array of strings
- mapping_conflicts: array of strings
- confidence: float 0-1"""

KG_BUILDER_SYSTEM = """You are a knowledge graph builder for scientific R&D.
Return JSON with:
- summary: string
- answer: string
- suggested_nodes: array of {{label, node_type, properties}}
- suggested_relationships: array of {{source, relationship_type, target, evidence, confidence}}
- graph_gaps: array of strings
- confidence: float 0-1"""


def run_knowledge_agent(
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
    logs: list[dict] = [{"message": "Starting knowledge graph agent pipeline"}]

    evidence = gather_evidence(
        db, query,
        tools_used=input_data.get("tools_used") or agent.tools_used or ["KG Query", "Ontology Mapper"],
        document_id=document_id,
        document_ids=input_data.get("document_ids"),
        user_id=input_data.get("user_id"),
        project_id=input_data.get("project_id"),
        top_k=top_k,
        include_kegg=True,
        include_kg=True,
        include_pubmed=False,
    )
    logs.extend(evidence["logs"])
    context = build_evidence_context(evidence)

    system = ONTOLOGY_SYSTEM if "ontology" in agent_name else KG_BUILDER_SYSTEM
    mode_label = "ontology_mapping" if "ontology" in agent_name else "kg_build"

    user_prompt = f"""Task:
{query}

Existing graph entities and document evidence:
{context}

Return structured JSON."""

    inference_model = model or settings.llm_model
    structured = None
    mode = "evidence_only"

    if llm_service.is_configured(inference_model):
        structured = llm_service.chat_json(system, user_prompt, model=inference_model)
        if structured:
            mode = mode_label
            logs.append({"message": f"Knowledge agent output generated ({mode_label})"})
    else:
        logs.append({"message": "OPENAI_API_KEY not set — graph context only"})

    if not structured:
        answer = f"**Graph context** for: {query[:200]}\n\n{context[:2000]}"
        structured = {"summary": answer[:300], "answer": answer, "confidence": 0.3}

    answer = pick_text(structured, "answer", "summary")
    summary = pick_text(structured, "summary", default=answer, max_len=300)
    mapped = structured.get("mapped_entities") or structured.get("suggested_nodes") or []
    findings = [
        (m.get("standard_name") or m.get("label") or str(m))[:80]
        for m in mapped[:5] if isinstance(m, dict)
    ]

    output = {
        "mode": mode,
        "agent": agent.name,
        "query": query,
        "answer": answer,
        "summary": summary,
        "mapped_entities": structured.get("mapped_entities"),
        "suggested_nodes": structured.get("suggested_nodes"),
        "suggested_relationships": structured.get("suggested_relationships"),
        "findings": findings,
        "evidence_sources": {
            "knowledge_graph": len(evidence["kg_entities"]),
            "kegg": len(evidence["kegg_entries"]),
            "vector_chunks": len(evidence["vector_chunks"]),
        },
        "model_used": inference_model if mode != "evidence_only" else None,
        "tools_invoked": ["KG Query", "Ontology Mapper", "KEGG"],
    }

    return {
        "output": output,
        "citations": evidence["citations"],
        "confidence": structured.get("confidence") or evidence_confidence(evidence, mode != "evidence_only"),
        "logs": logs,
    }
