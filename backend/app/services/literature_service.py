"""Literature mining and evidence scouting agent pipelines."""

from sqlalchemy.orm import Session

from app.config import settings
from app.services.evidence_service import build_evidence_context, evidence_confidence, gather_evidence
from app.services.llm_output_utils import coerce_text, pick_text
from app.services.llm_service import llm_service

LITERATURE_MINER_SYSTEM = """You are a pharma literature and patent intelligence analyst.
Synthesize evidence from provided sources into structured JSON:
- summary: string (executive brief)
- answer: string (full narrative with [Doc-N]/[PubMed-N] citations)
- key_findings: array of strings (5-8 bullet points)
- papers: array of {{title, source, takeaway, relevance_score}}
- patents_or_ip: array of strings (if any mentioned)
- evidence_gaps: array of strings
- confidence: float 0-1"""

EVIDENCE_SCOUT_SYSTEM = """You are an evidence scout for target discovery.
Return JSON with:
- summary: string
- answer: string (evidence report narrative)
- evidence_items: array of {{claim, strength: high|medium|low, sources, supporting_excerpt}}
- overall_evidence_score: float 0-1
- conflicting_evidence: array of strings
- recommended_next_sources: array of strings
- confidence: float 0-1"""

KNOWLEDGE_SCOUT_SYSTEM = """You are a knowledge graph scout for pharma R&D.
Return JSON with:
- summary: string
- answer: string (knowledge map narrative)
- connections: array of {{entity_a, relationship, entity_b, significance}}
- knowledge_gaps: array of strings
- suggested_graph_queries: array of strings
- confidence: float 0-1"""


def run_literature_agent(
    db: Session,
    agent,
    input_data: dict,
    *,
    model: str | None = None,
) -> dict:
    query = str(input_data.get("query", "")).strip()
    document_id = input_data.get("document_id")
    top_k = int(input_data.get("top_k") or 10)
    agent_name = (agent.name or "").lower()
    logs: list[dict] = [{"message": "Starting literature intelligence pipeline"}]

    evidence = gather_evidence(
        db, query,
        tools_used=input_data.get("tools_used") or agent.tools_used or ["Literature Miner", "PubMed"],
        document_id=document_id,
        document_ids=input_data.get("document_ids"),
        user_id=input_data.get("user_id"),
        project_id=input_data.get("project_id"),
        top_k=top_k,
        include_pubmed=True,
        include_kegg=False,
        include_kg="knowledge scout" in agent_name,
    )
    logs.extend(evidence["logs"])
    context = build_evidence_context(evidence)

    if "evidence scout" in agent_name:
        system = EVIDENCE_SCOUT_SYSTEM
        mode_label = "evidence_scout"
    elif "knowledge scout" in agent_name:
        system = KNOWLEDGE_SCOUT_SYSTEM
        mode_label = "knowledge_scout"
    else:
        system = LITERATURE_MINER_SYSTEM
        mode_label = "literature"

    user_prompt = f"""Research query:
{query}

Evidence bundle (indexed documents + PubMed + knowledge graph):
{context}

Produce structured JSON per your schema."""

    inference_model = model or settings.llm_model
    structured = None
    mode = "evidence_only"

    if llm_service.is_configured(inference_model):
        logs.append({"message": f"Synthesizing literature intelligence with {inference_model}"})
        structured = llm_service.chat_json(system, user_prompt, model=inference_model)
        if structured:
            mode = mode_label
    else:
        logs.append({"message": "OPENAI_API_KEY not set — retrieval summary only"})

    if not structured:
        answer = f"**Literature retrieval** for: {query[:200]}\n\n{context[:2500]}"
        structured = {
            "summary": answer[:400],
            "answer": answer,
            "key_findings": [f"Retrieved {len(evidence['pubmed_articles'])} PubMed articles", f"Retrieved {len(evidence['vector_chunks'])} document chunks"],
            "confidence": 0.35,
        }

    answer = pick_text(structured, "answer", "summary")
    summary = pick_text(structured, "summary", default=answer, max_len=300)
    findings = structured.get("key_findings") or [
        item.get("claim") or item.get("takeaway") or str(item)
        for item in (structured.get("evidence_items") or structured.get("papers") or [])[:5]
        if isinstance(item, (dict, str))
    ]

    output = {
        "mode": mode,
        "agent": agent.name,
        "query": query,
        "answer": answer,
        "summary": summary,
        "key_findings": structured.get("key_findings", findings),
        "papers": structured.get("papers"),
        "evidence_items": structured.get("evidence_items"),
        "connections": structured.get("connections"),
        "evidence_gaps": structured.get("evidence_gaps", []),
        "findings": findings[:6],
        "evidence_sources": {
            "vector_chunks": len(evidence["vector_chunks"]),
            "pubmed": len(evidence["pubmed_articles"]),
            "knowledge_graph": len(evidence["kg_entities"]),
        },
        "model_used": inference_model if mode != "evidence_only" else None,
        "tools_invoked": ["Literature Miner", "PubMed", "Vector Search"],
    }

    return {
        "output": output,
        "citations": evidence["citations"],
        "confidence": structured.get("confidence") or structured.get("overall_evidence_score") or evidence_confidence(evidence, mode != "evidence_only"),
        "logs": logs,
    }
