"""Entity resolution — merge duplicates and canonicalize names."""

import re
from dataclasses import replace

from app.services.entity_extractor import ExtractedEntity, ExtractedRelationship


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def resolve_entities(entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
    """Merge entities with same normalized name + type; keep highest confidence."""
    best: dict[tuple[str, str], ExtractedEntity] = {}
    for ent in entities:
        key = (normalize_name(ent.name), ent.entity_type)
        existing = best.get(key)
        if existing is None or ent.confidence > existing.confidence:
            best[key] = ent
        elif existing and ent.confidence == existing.confidence:
            # Prefer shorter, cleaner canonical names
            if len(ent.name) < len(existing.name):
                best[key] = replace(ent, context=existing.context or ent.context)
    return list(best.values())


def resolve_relationships(
    relationships: list[ExtractedRelationship],
    canonical_map: dict[tuple[str, str], ExtractedEntity],
) -> list[ExtractedRelationship]:
    """Remap relationship endpoints to canonical entity names after resolution."""
    resolved: list[ExtractedRelationship] = []
    seen: set[tuple[str, str, str]] = set()

    for rel in relationships:
        src_key = (normalize_name(rel.source_name), rel.source_type)
        tgt_key = (normalize_name(rel.target_name), rel.target_type)
        src = canonical_map.get(src_key)
        tgt = canonical_map.get(tgt_key)
        if not src or not tgt:
            continue
        dedupe = (normalize_name(src.name), normalize_name(tgt.name), rel.relationship_type)
        if dedupe in seen:
            continue
        seen.add(dedupe)
        resolved.append(ExtractedRelationship(
            source_name=src.name,
            source_type=src.entity_type,
            target_name=tgt.name,
            target_type=tgt.entity_type,
            relationship_type=rel.relationship_type,
            confidence=rel.confidence,
            source_chunk_index=rel.source_chunk_index,
            evidence=rel.evidence,
        ))
    return resolved


def build_canonical_map(entities: list[ExtractedEntity]) -> dict[tuple[str, str], ExtractedEntity]:
    return {(normalize_name(e.name), e.entity_type): e for e in entities}
