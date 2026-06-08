"""Hypothesis generation and validation agent pipeline."""

from sqlalchemy.orm import Session

from app.config import settings
from app.services.agent_capabilities import is_hypothesis_agent
from app.services.evidence_service import build_evidence_context, evidence_confidence, gather_evidence
from app.services.llm_output_utils import pick_text
from app.services.llm_service import llm_service

HYPOTHESIS_BUILD_SYSTEM = """You are a pharma target discovery scientist.
Generate structured, evidence-backed scientific hypotheses as JSON.

Return JSON with keys:
- summary: string (2-3 sentences)
- hypotheses: array of objects with:
  - title: string
  - statement: string (testable hypothesis)
  - target_or_mechanism: string
  - disease_context: string
  - rationale: string
  - evidence_strength: "high" | "medium" | "low"
  - suggested_experiments: array of strings (2-3 items)
  - confidence: float 0-1
- gaps: array of strings (knowledge gaps)
- answer: string (detailed report narrative for scientists, 600-1200 words covering background, evidence synthesis, ranked hypotheses, and recommended next experiments)"""

HYPOTHESIS_VALIDATE_SYSTEM = """You are a scientific hypothesis validator for pharma R&D.
Evaluate the hypothesis against provided evidence. Return JSON with:
- summary: string
- hypothesis_statement: string (restated)
- verdict: "supported" | "partially_supported" | "insufficient_evidence" | "contradicted"
- evidence_for: array of strings
- evidence_against: array of strings
- confidence: float 0-1
- recommended_validation_experiments: array of strings
- answer: string (detailed validation narrative)"""


def run_hypothesis_agent(
    db: Session,
    agent,
    input_data: dict,
    *,
    model: str | None = None,
) -> dict:
    query = str(input_data.get("query", "")).strip()
    document_id = input_data.get("document_id")
    top_k = int(input_data.get("top_k") or 8)
    agent_name = agent.name or "Hypothesis Agent"
    logs: list[dict] = [{"message": "Starting hypothesis pipeline"}]

    evidence = gather_evidence(
        db,
        query,
        tools_used=input_data.get("tools_used") or agent.tools_used or [],
        document_id=document_id,
        document_ids=input_data.get("document_ids"),
        user_id=input_data.get("user_id"),
        top_k=top_k,
    )
    logs.extend(evidence["logs"])

    context = build_evidence_context(evidence)
    is_validation = "validation" in (agent.name or "").lower()

    system = HYPOTHESIS_VALIDATE_SYSTEM if is_validation else HYPOTHESIS_BUILD_SYSTEM
    user_prompt = f"""Research question / hypothesis:
{query}

Report mode: {"full scientific report" if input_data.get("report_type") in ("hypothesis_report", "target_discovery") else "structured analysis"}

Evidence bundle (internal documents, PubMed, KEGG, knowledge graph):
{context}

Produce the JSON output specified in your instructions. Be comprehensive and evidence-led."""

    inference_model = model or settings.llm_model
    structured = None
    mode = "evidence_only"

    if llm_service.is_configured(inference_model):
        logs.append({"message": f"Synthesizing hypotheses with {inference_model}"})
        structured = llm_service.chat_json(system, user_prompt, model=inference_model)
        if structured:
            mode = "hypothesis"
            logs.append({"message": "Structured hypothesis output generated"})
    else:
        logs.append({"message": "OPENAI_API_KEY not set — returning evidence summary only"})

    if not structured:
        hypotheses = [{
            "title": "Evidence-based lead hypothesis (retrieval only)",
            "statement": f"Further analysis needed for: {query[:200]}",
            "evidence_strength": "medium",
            "suggested_experiments": ["Literature review", "In vitro validation assay"],
            "confidence": 0.4,
        }]
        answer = (
            "**Evidence retrieved** (configure OPENAI_API_KEY for full hypothesis generation)\n\n"
            + context[:2000]
        )
        structured = {"summary": answer[:300], "hypotheses": hypotheses, "gaps": [], "answer": answer}

    answer = pick_text(structured, "answer", "summary")
    summary = pick_text(structured, "summary", default=answer, max_len=1200)
    hypotheses = structured.get("hypotheses", [])
    findings = [h.get("statement", h.get("title", "")) for h in hypotheses[:5] if isinstance(h, dict)]

    output = {
        "mode": mode,
        "agent": agent_name,
        "query": query,
        "answer": answer,
        "summary": summary,
        "hypotheses": hypotheses,
        "gaps": structured.get("gaps", []),
        "verdict": structured.get("verdict"),
        "evidence_for": structured.get("evidence_for", []),
        "evidence_against": structured.get("evidence_against", []),
        "findings": findings,
        "evidence_sources": {
            "vector_chunks": len(evidence["vector_chunks"]),
            "pubmed": len(evidence["pubmed_articles"]),
            "kegg": len(evidence["kegg_entries"]),
            "knowledge_graph": len(evidence["kg_entities"]),
        },
        "model_used": inference_model if mode == "hypothesis" else None,
        "tools_invoked": ["Vector Search", "PubMed", "KEGG", "KG Query"],
    }

    return {
        "output": output,
        "citations": evidence["citations"],
        "confidence": structured.get("confidence") or evidence_confidence(evidence, mode == "hypothesis"),
        "logs": logs,
    }


def agent_is_hypothesis(agent) -> bool:
    return is_hypothesis_agent(agent)
