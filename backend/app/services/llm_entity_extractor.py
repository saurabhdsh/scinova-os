"""LLM-based scientific entity and relationship extraction."""

import logging

from app.config import settings
from app.services.entity_extractor import (
    ExtractedEntity,
    ExtractedRelationship,
    extract_entities_from_chunks as pattern_extract_entities,
    extract_relationships as pattern_extract_relationships,
)
from app.services.entity_quality import filter_entities, filter_relationships
from app.services.entity_resolver import resolve_entities, resolve_relationships, build_canonical_map
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

ENTITY_TYPES = [
    "Gene", "Protein", "Disease", "Target", "Biomarker", "Compound", "Molecule",
    "Assay", "Pathway", "Study", "Protocol", "Experiment", "Result",
    "Toxicity signal", "ADMET attribute", "Formulation", "Regulatory requirement",
]

RELATIONSHIP_TYPES = [
    "ASSOCIATED_WITH", "EXPRESSED_IN", "BINDS_TO", "HAS_ADMET_PROPERTY",
    "INVOLVED_IN", "INDICATES", "TESTS", "PRODUCES", "DEFINES", "SUPPORTS",
]


def extract_entities_hybrid(chunks: list[dict]) -> tuple[list[ExtractedEntity], str]:
    pattern_entities = pattern_extract_entities(chunks)
    if not llm_service.available:
        resolved = filter_entities(resolve_entities(pattern_entities))
        return resolved, "pattern_v1"

    llm_entities = _llm_extract(chunks)
    combined = pattern_entities + llm_entities
    resolved = filter_entities(resolve_entities(combined))
    method = "hybrid_llm+pattern" if llm_entities else "pattern_v1"
    return resolved, method


def extract_relationships_hybrid(
    entities: list[ExtractedEntity],
    chunks: list[dict],
) -> tuple[list[ExtractedRelationship], str]:
    canonical = build_canonical_map(entities)
    pattern_rels = pattern_extract_relationships(entities, chunks)

    if not llm_service.available:
        return filter_relationships(resolve_relationships(pattern_rels, canonical)), "co_occurrence_v1"

    llm_rels = _llm_extract_relationships(chunks, entities)
    combined = llm_rels + pattern_rels
    resolved = filter_relationships(resolve_relationships(combined, canonical))
    method = "hybrid_llm+co_occurrence" if llm_rels else "co_occurrence_v1"
    return resolved, method


def _llm_extract(chunks: list[dict]) -> list[ExtractedEntity]:
    text = _sample_text(chunks, max_chars=6000)
    system = (
        "You are a biomedical NER system for pharma R&D. "
        "Extract scientific entities from text. Return JSON: "
        '{"entities":[{"name":"...","entity_type":"Gene|Protein|Disease|Target|Biomarker|Compound|Pathway|Study|ADMET attribute|Regulatory requirement","confidence":0.0-1.0}]}'
    )
    result = llm_service.chat_json(system, f"Extract entities from:\n\n{text}")
    if not result or "entities" not in result:
        return []

    entities: list[ExtractedEntity] = []
    for item in result["entities"][:40]:
        name = str(item.get("name", "")).strip()
        etype = str(item.get("entity_type", "Target")).strip()
        if not name or len(name) < 2:
            continue
        if etype not in ENTITY_TYPES:
            continue
        conf = float(item.get("confidence", 0.85))
        if conf < 0.65:
            continue
        entities.append(ExtractedEntity(
            name=name,
            entity_type=etype,
            confidence=conf,
            source_chunk_index=0,
            context=name,
        ))
    logger.info("LLM extracted %d entities", len(entities))
    return entities


def _llm_extract_relationships(
    chunks: list[dict],
    entities: list[ExtractedEntity],
) -> list[ExtractedRelationship]:
    if len(entities) < 2:
        return []
    text = _sample_text(chunks, max_chars=5000)
    entity_list = ", ".join(f"{e.name} ({e.entity_type})" for e in entities[:25])
    system = (
        "You are a biomedical knowledge graph extractor. "
        "Given text and entities, extract relationships. Return JSON: "
        '{"relationships":[{"source_name":"...","source_type":"...","target_name":"...","target_type":"...",'
        '"relationship_type":"ASSOCIATED_WITH|BINDS_TO|INVOLVED_IN|INDICATES|TESTS|HAS_ADMET_PROPERTY|PRODUCES","confidence":0.0-1.0,"evidence":"short quote"}]}'
    )
    user = f"Entities: {entity_list}\n\nText:\n{text}"
    result = llm_service.chat_json(system, user)
    if not result or "relationships" not in result:
        return []

    rels: list[ExtractedRelationship] = []
    known = {(e.name.lower(), e.entity_type) for e in entities}
    for item in result["relationships"][:30]:
        src = str(item.get("source_name", "")).strip()
        tgt = str(item.get("target_name", "")).strip()
        st = str(item.get("source_type", "Target"))
        tt = str(item.get("target_type", "Target"))
        rtype = str(item.get("relationship_type", "ASSOCIATED_WITH")).upper()
        if rtype not in RELATIONSHIP_TYPES:
            rtype = "ASSOCIATED_WITH"
        if (src.lower(), st) not in known or (tgt.lower(), tt) not in known:
            continue
        rels.append(ExtractedRelationship(
            source_name=src,
            source_type=st,
            target_name=tgt,
            target_type=tt,
            relationship_type=rtype,
            confidence=float(item.get("confidence", 0.8)),
            source_chunk_index=0,
            evidence=str(item.get("evidence", ""))[:300],
        ))
    logger.info("LLM extracted %d relationships", len(rels))
    return rels


def _sample_text(chunks: list[dict], max_chars: int = 6000) -> str:
    parts = []
    total = 0
    for c in chunks[:12]:
        content = c.get("content", "")
        if total + len(content) > max_chars:
            parts.append(content[: max_chars - total])
            break
        parts.append(content)
        total += len(content)
    return "\n\n".join(parts)
