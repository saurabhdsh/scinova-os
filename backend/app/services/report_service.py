"""Scientific report generation agent pipeline."""

import json
import uuid

from sqlalchemy.orm import Session

from app.config import settings
from app.models.db_models import Agent, AuditEvent, ScientificReport
from app.services.evidence_service import build_evidence_context, evidence_confidence, gather_evidence
from app.services.llm_output_utils import pick_text
from app.services.llm_service import llm_service
from app.services.report_content_builder import enrich_report_content

REPORT_SYSTEM = """You are a GxP-aware scientific report writer for pharma R&D.
Write traceable, publication-quality scientific reports grounded ONLY in the provided evidence.

Return JSON with:
- title: string
- summary: string (executive summary, 150-250 words)
- answer: string (full report narrative, 800-1500 words minimum — multiple paragraphs, cite evidence inline)
- sections: array of objects {{name, content}} — REQUIRED detailed sections:
  Executive Summary, Background, Evidence Review, Analysis, Conclusions, Recommendations
  Each section content must be at least 2-3 substantive paragraphs.
- figures: array of strings (suggested figure descriptions)
- limitations: array of strings (4-6 items)
- recommendations: array of strings (4-6 actionable next steps)
- word_count: integer estimate
- confidence: float 0-1"""

CAPTURE_SYSTEM = """You are an ELN/LIMS result capture specialist.
Summarize captured experimental records into structured results.

Return JSON with:
- summary: string
- answer: string
- captured_results: array of objects {{source, assay, outcome, date, notes}}
- data_quality_flags: array of strings
- sections: array of {{name, content}}
- confidence: float 0-1"""


def run_report_agent(
    db: Session,
    agent,
    input_data: dict,
    *,
    model: str | None = None,
) -> dict:
    query = str(input_data.get("query", "")).strip()
    document_id = input_data.get("document_id")
    report_type = input_data.get("report_type", "study_report")
    top_k = int(input_data.get("top_k") or 8)
    agent_name = agent.name or "Report Agent"
    is_capture = "result capture" in (agent.name or "").lower()
    logs: list[dict] = [{"message": "Starting report generation pipeline"}]

    evidence = gather_evidence(
        db,
        query,
        tools_used=input_data.get("tools_used") or agent.tools_used or [],
        document_id=document_id,
        document_ids=input_data.get("document_ids"),
        user_id=input_data.get("user_id"),
        top_k=top_k,
        include_eln=True,
    )
    logs.extend(evidence["logs"])

    prior_context = input_data.get("prior_context") or input_data.get("source_data") or {}
    context = build_evidence_context(evidence)
    system = CAPTURE_SYSTEM if is_capture else REPORT_SYSTEM

    user_prompt = f"""Report request ({report_type}):
{query}

Additional source data:
{prior_context}

Evidence bundle:
{context}

Generate the JSON report following your schema. Cite evidence inline as [Doc-N], [PubMed-N], [ELN-N]."""

    inference_model = model or settings.llm_model
    structured = None
    mode = "evidence_only"

    if llm_service.is_configured(inference_model):
        logs.append({"message": f"Generating report with {inference_model}"})
        structured = llm_service.chat_json(system, user_prompt, model=inference_model)
        if structured:
            mode = "report"
            logs.append({"message": "Scientific report generated"})
    else:
        logs.append({"message": "OPENAI_API_KEY not set — returning evidence summary only"})

    if not structured:
        answer = (
            "**Report evidence bundle** (configure OPENAI_API_KEY for full report generation)\n\n"
            + context[:2500]
        )
        structured = {
            "title": query[:120],
            "summary": answer[:400],
            "answer": answer,
            "sections": [
                {"name": "Executive Summary", "content": answer[:500]},
                {"name": "Evidence Index", "content": context[:1000]},
            ],
            "word_count": len(answer.split()),
            "confidence": 0.35,
        }

    answer = pick_text(structured, "answer", "summary")
    summary = pick_text(structured, "summary", default=answer, max_len=1200)
    sections = structured.get("sections", [])
    section_names = [s.get("name") if isinstance(s, dict) else s for s in sections]

    output = {
        "mode": mode,
        "agent": agent_name,
        "query": query,
        "report_type": report_type,
        "answer": answer,
        "summary": summary,
        "title": structured.get("title", query[:120]),
        "sections": sections,
        "section_names": section_names,
        "figures": structured.get("figures", []),
        "limitations": structured.get("limitations", []),
        "recommendations": structured.get("recommendations", []),
        "captured_results": structured.get("captured_results"),
        "word_count": structured.get("word_count", len(answer.split())),
        "findings": structured.get("recommendations", [])[:3],
        "model_used": inference_model if mode == "report" else None,
        "tools_invoked": ["Report Generator", "ELN Connector", "Literature Miner", "Vector Search"],
    }

    return {
        "output": output,
        "citations": evidence["citations"],
        "confidence": structured.get("confidence") or evidence_confidence(evidence, mode == "report"),
        "logs": logs,
    }


REPORT_TYPE_AGENTS = {
    "hypothesis_report": "Hypothesis Builder Assistant",
    "experiment_plan": "Experiment Planner Assistant",
    "study_report": "Study Report Generator",
    "target_discovery": "Target Hypothesis Generation Agent",
    "cmc_readiness": "Study Report Generator",
}

STRUCTURED_REPORT_TYPES = frozenset({"hypothesis_report", "target_discovery", "experiment_plan"})


def expand_report_narrative(
    report_type: str,
    query: str,
    structured_output: dict,
    citations: list | None = None,
    *,
    model: str | None = None,
) -> dict:
    """Second LLM pass: turn structured agent output into a full GxP report narrative."""
    inference_model = model or settings.llm_model
    if not llm_service.is_configured(inference_model):
        return {}

    payload = {
        k: structured_output[k]
        for k in (
            "summary", "hypotheses", "gaps", "experiment_plan", "doe_design",
            "verdict", "evidence_for", "evidence_against", "findings",
            "captured_results", "resources", "risks",
        )
        if structured_output.get(k)
    }
    structured_json = json.dumps(payload, indent=2, default=str)[:8000]

    cite_lines = []
    for cite in (citations or [])[:15]:
        excerpt = (cite.get("excerpt") or "")[:220]
        cite_lines.append(
            f"[{cite.get('index', '?')}] {cite.get('title', 'Source')} "
            f"({cite.get('source', '')}): {excerpt}"
        )

    user_prompt = f"""Report type: {report_type}
Research question / scope:
{query}

Structured findings from specialized analysis (preserve all hypotheses, plans, and gaps — expand with narrative):
{structured_json}

Evidence references (cite inline as [N]):
{chr(10).join(cite_lines) or 'See structured findings above.'}

Write the complete JSON report. The answer field MUST be 800-1500 words minimum.
Each section object MUST contain 2-3 substantive paragraphs."""

    expanded = llm_service.chat_json(REPORT_SYSTEM, user_prompt, model=inference_model)
    if not expanded:
        return {}

    answer = pick_text(expanded, "answer", "summary")
    return {
        "answer": answer,
        "summary": pick_text(expanded, "summary", default=answer, max_len=1200),
        "sections": expanded.get("sections") or [],
        "limitations": expanded.get("limitations") or [],
        "recommendations": expanded.get("recommendations") or [],
        "figures": expanded.get("figures") or [],
        "word_count": expanded.get("word_count") or len(answer.split()),
        "title": expanded.get("title"),
        "confidence": expanded.get("confidence"),
    }


def _merge_structured_with_narrative(structured: dict, narrative: dict) -> dict:
    """Keep structured fields; overlay full narrative from expansion pass."""
    merged = dict(structured)
    for key in (
        "answer", "summary", "sections", "limitations",
        "recommendations", "figures", "word_count",
    ):
        if narrative.get(key):
            merged[key] = narrative[key]
    if narrative.get("title") and not merged.get("title"):
        merged["title"] = narrative["title"]
    return merged


def generate_scientific_report(
    db: Session,
    report_type: str,
    title: str,
    source_data: dict,
    user_id: str | None = None,
    project_id: str | None = None,
) -> ScientificReport:
    """Generate a report by invoking the appropriate specialized agent."""
    agent_name = REPORT_TYPE_AGENTS.get(report_type, "Study Report Generator")
    agent = db.query(Agent).filter(Agent.name == agent_name).first()
    if not agent:
        agent = db.query(Agent).filter(Agent.name == "Study Report Generator").first()

    query = source_data.get("query") or source_data.get("project") or title
    input_data = {
        "query": str(query),
        "task_type": "report",
        "report_type": report_type,
        "source_data": source_data,
        "document_id": source_data.get("document_id"),
        "document_ids": source_data.get("document_ids"),
        "user_id": user_id or source_data.get("user_id"),
        "top_k": int(source_data.get("top_k") or 12),
    }

    if report_type in ("hypothesis_report", "target_discovery"):
        from app.services.hypothesis_service import run_hypothesis_agent
        result = run_hypothesis_agent(db, agent, input_data)
    elif report_type == "experiment_plan":
        from app.services.experiment_service import run_experiment_agent
        result = run_experiment_agent(db, agent, input_data)
    else:
        result = run_report_agent(db, agent, input_data)

    if report_type in STRUCTURED_REPORT_TYPES:
        expansion = expand_report_narrative(
            report_type,
            str(query),
            result["output"],
            result.get("citations") or [],
        )
        if expansion:
            result["output"] = _merge_structured_with_narrative(result["output"], expansion)
            if expansion.get("confidence") is not None:
                result["confidence"] = expansion["confidence"]
            result["logs"] = (result.get("logs") or []) + [
                {"message": "Expanded structured output into full scientific report narrative"},
            ]

    output = enrich_report_content(
        report_type,
        result["output"],
        query=str(query),
        citations=result.get("citations") or [],
    )
    citations = result.get("citations") or []
    sections = output.get("sections") or []
    section_content = output.get("section_content") or []

    figures_raw = output.get("figures") or []
    figures_list = figures_raw if isinstance(figures_raw, list) else []

    report = ScientificReport(
        id=str(uuid.uuid4()),
        title=title or output.get("title", "Generated Report"),
        report_type=report_type,
        user_id=user_id or source_data.get("user_id"),
        project_id=project_id or source_data.get("project_id"),
        content_json={
            "sections": sections,
            "section_content": section_content,
            "body": output.get("body") or output.get("answer"),
            "summary": output.get("summary"),
            "answer": output.get("answer"),
            "hypotheses": output.get("hypotheses"),
            "experiment_plan": output.get("experiment_plan"),
            "doe_design": output.get("doe_design"),
            "gaps": output.get("gaps") or [],
            "verdict": output.get("verdict"),
            "evidence_for": output.get("evidence_for") or [],
            "evidence_against": output.get("evidence_against") or [],
            "findings": output.get("findings") or [],
            "word_count": output.get("word_count", 0),
            "figures": len(figures_list),
            "figures_list": figures_list,
            "citations": len(citations),
            "citations_list": citations,
            "limitations": output.get("limitations") or [],
            "recommendations": output.get("recommendations") or [],
            "evidence_sources": output.get("evidence_sources"),
            "mode": output.get("mode"),
            "model_used": output.get("model_used"),
            "confidence": result.get("confidence"),
            "agent_name": agent_name,
            "generated_from": {
                k: v for k, v in source_data.items() if k != "document_ids"
            },
            "logs": (result.get("logs") or [])[-8:],
        },
        status="draft",
    )
    db.add(report)

    db.add(AuditEvent(
        event_type="report_generated",
        actor=source_data.get("initiated_by", "system"),
        resource_type="report",
        resource_id=report.id,
        action=f"Report '{report.title}' generated via {agent_name}",
        details_json={
            "report_type": report_type,
            "agent": agent_name,
            "citations": len(citations),
            "confidence": result.get("confidence"),
            "mode": output.get("mode"),
        },
    ))
    db.commit()
    db.refresh(report)
    return report


ALLOWED_STATUS_TRANSITIONS = {
    "draft": {"under_review", "approved", "published"},
    "under_review": {"draft", "approved", "published"},
    "approved": {"draft", "under_review", "published"},
    "published": {"draft", "under_review", "approved"},
}


def update_report_status(db: Session, report: ScientificReport, new_status: str, *, actor: str) -> ScientificReport:
    new_status = new_status.lower().strip()
    allowed = ALLOWED_STATUS_TRANSITIONS.get(report.status, set())
    if new_status not in allowed and new_status != report.status:
        raise ValueError(
            f"Cannot transition report from '{report.status}' to '{new_status}'. "
            f"Allowed: {', '.join(sorted(allowed)) or 'none'}"
        )
    old = report.status
    report.status = new_status
    db.add(AuditEvent(
        event_type="report_status_changed",
        actor=actor,
        resource_type="report",
        resource_id=report.id,
        action=f"Report status: {old} → {new_status}",
        details_json={"from": old, "to": new_status},
    ))
    db.commit()
    db.refresh(report)
    return report
