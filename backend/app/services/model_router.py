"""Model Router - routes tasks to SLM (Ministral 8B) or frontier LLM."""

from app.config import settings
from app.models.schemas import ModelRouteRequest, ModelRoutingDecision
from app.services.llm_service import is_bedrock_llm_model

# Logical SLM profile names → resolved at inference to settings.slm_model (Ministral 8B)
SLM_MODELS = {
    "literature-intelligence-slm": settings.slm_model,
    "ontology-mapping-slm": settings.slm_model,
    "scientific-writing-slm": settings.slm_model,
    "compliance-gxp-slm": settings.slm_model,
    "bioinformatics-slm": settings.slm_model,
    "molecular-intelligence-slm": settings.slm_model,
}

def _frontier_model() -> str:
    return settings.llm_model


def _frontier_fallback() -> str:
    if settings.llm_fallback_model:
        return settings.llm_fallback_model
    if is_bedrock_llm_model(settings.llm_model):
        return settings.bedrock_llm_model or settings.llm_model
    return "gpt-4o-mini"

LOW_RISK_TASKS = {
    "summarization", "extraction", "classification", "mapping",
    "profiling", "parsing", "indexing", "query", "search",
}

HIGH_RISK_LEVELS = {"high"}


def route_model(request: ModelRouteRequest) -> ModelRoutingDecision:
    task_lower = request.task_type.lower()
    risk = request.risk_level.lower()
    agent_lower = request.agent_name.lower()

    human_review = risk in HIGH_RISK_LEVELS

    # High risk always uses frontier + human review
    if risk == "high":
        return ModelRoutingDecision(
            selected_model=_frontier_model(),
            reason_for_selection="High-risk task requires frontier LLM with human review checkpoint.",
            fallback_model=_frontier_fallback(),
            human_review_required=True,
            model_type="frontier",
        )

    # Complex reasoning tasks use frontier
    complex_keywords = ["hypothesis", "validation", "decision", "design", "generation", "review", "assessment"]
    if any(kw in task_lower or kw in agent_lower for kw in complex_keywords):
        return ModelRoutingDecision(
            selected_model=_frontier_model(),
            reason_for_selection="Complex reasoning or scientific decision task routed to frontier LLM.",
            fallback_model=_frontier_fallback(),
            human_review_required=human_review,
            model_type="frontier",
        )

    # Repetitive low-risk tasks use SLM
    if task_lower in LOW_RISK_TASKS or risk == "low":
        slm = _match_slm(agent_lower)
        return ModelRoutingDecision(
            selected_model=slm,
            reason_for_selection="Repetitive, domain-specific, low-risk task routed to specialized SLM.",
            fallback_model=_frontier_fallback(),
            human_review_required=False,
            model_type="slm",
        )

    # Medium risk default
    return ModelRoutingDecision(
        selected_model=_frontier_model(),
        reason_for_selection="Medium-risk task with mixed complexity routed to frontier LLM.",
        fallback_model=_frontier_fallback(),
        human_review_required=human_review,
        model_type="frontier",
    )


def _match_slm(agent_name: str) -> str:
    if any(k in agent_name for k in ["literature", "paper", "patent", "evidence", "scout"]):
        return SLM_MODELS["literature-intelligence-slm"]
    if any(k in agent_name for k in ["ontology", "entity", "relationship", "kg", "knowledge graph"]):
        return SLM_MODELS["ontology-mapping-slm"]
    if any(k in agent_name for k in ["writer", "report", "capture", "document"]):
        return SLM_MODELS["scientific-writing-slm"]
    if any(k in agent_name for k in ["gxp", "compliance", "privacy", "governance", "traceability"]):
        return SLM_MODELS["compliance-gxp-slm"]
    if any(k in agent_name for k in ["bioinfo", "omics", "ngs", "efficacy", "pk/pd"]):
        return SLM_MODELS["bioinformatics-slm"]
    if any(k in agent_name for k in ["admet", "molecule", "compound", "screening", "mpo", "druggability"]):
        return SLM_MODELS["molecular-intelligence-slm"]
    return SLM_MODELS["literature-intelligence-slm"]
