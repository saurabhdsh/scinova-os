"""Scientific entity and relationship extraction from text."""

import re
import uuid
from dataclasses import dataclass, field


@dataclass
class ExtractedEntity:
    name: str
    entity_type: str
    confidence: float
    source_chunk_index: int
    context: str = ""


@dataclass
class ExtractedRelationship:
    source_name: str
    source_type: str
    target_name: str
    target_type: str
    relationship_type: str
    confidence: float
    source_chunk_index: int
    evidence: str = ""


# Pharma/scientific NER patterns
PATTERNS: list[tuple[str, str, float]] = [
    (r"\b([A-Z]{2,}[0-9][A-Z0-9]*|[A-Z]{4,})\b", "Gene", 0.78),  # JAK1, EGFR, BRAF — not AA/AE
    (r"\b(SN-\d{3,5})\b", "Compound", 0.90),
    (r"\b(LC-\d{3,5})\b", "Compound", 0.90),
    (r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Syndrome|Disease|Disorder|Carcinoma|Arthritis))\b", "Disease", 0.80),
    (r"\b(Rheumatoid Arthritis|NSCLC|Non-Small Cell Lung Cancer|Diabetes Mellitus)\b", "Disease", 0.92),
    (r"\b(PD-L1|PD-1|CRP|IL-6|TNF-alpha|TNF-\u03b1)\b", "Biomarker", 0.88),
    (r"\b(hERG|Kinase|GPCR|Receptor)\b", "Target", 0.70),
    (r"\b(JAK-STAT|EGFR Signaling|MAPK|PI3K-AKT)\b", "Pathway", 0.85),
    (r"\b(LogP|hERG IC50|IC50|EC50|Ki)\b", "ADMET attribute", 0.82),
    (r"\b(Phase [IIV]+(?:/[I]+)?)\b", "Study", 0.78),
    (r"\b(GSE\d{5,8})\b", "Study", 0.90),
    (r"\b(ICH [A-Z]\d+[A-Z]?(?:\([R\d]+\))?)\b", "Regulatory requirement", 0.88),
]

def extract_entities_from_chunks(chunks: list[dict]) -> list[ExtractedEntity]:
    from app.services.entity_quality import GENE_BLOCKLIST, filter_entities
    seen: set[tuple[str, str]] = set()
    entities: list[ExtractedEntity] = []

    for chunk in chunks:
        text = chunk["content"]
        chunk_index = chunk["chunk_index"]

        for pattern, entity_type, base_confidence in PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE if entity_type == "Disease" else 0):
                name = match.group(1) if match.lastindex else match.group(0)
                name = name.strip()
                if len(name) < 2:
                    continue
                if entity_type == "Gene" and name.upper() in GENE_BLOCKLIST:
                    continue
                key = (name.lower(), entity_type)
                if key in seen:
                    continue
                seen.add(key)
                start = max(0, match.start() - 40)
                end = min(len(text), match.end() + 40)
                entities.append(ExtractedEntity(
                    name=name,
                    entity_type=entity_type,
                    confidence=base_confidence,
                    source_chunk_index=chunk_index,
                    context=text[start:end],
                ))

    return filter_entities(entities)


def extract_relationships(
    entities: list[ExtractedEntity],
    chunks: list[dict],
) -> list[ExtractedRelationship]:
    from app.services.entity_quality import MAX_CO_OCCURRENCE_PAIRS_PER_CHUNK, filter_relationships

    relationships: list[ExtractedRelationship] = []
    seen: set[tuple[str, str, str]] = set()

    chunk_entities: dict[int, list[ExtractedEntity]] = {}
    for e in entities:
        chunk_entities.setdefault(e.source_chunk_index, []).append(e)

    type_rel_map = {
        ("Gene", "Disease"): "ASSOCIATED_WITH",
        ("Compound", "Target"): "BINDS_TO",
        ("Compound", "Gene"): "BINDS_TO",
        ("Biomarker", "Disease"): "INDICATES",
        ("Target", "Pathway"): "INVOLVED_IN",
        ("Gene", "Pathway"): "INVOLVED_IN",
        ("Study", "Compound"): "TESTS",
        ("Compound", "ADMET attribute"): "HAS_ADMET_PROPERTY",
    }

    for chunk_index, chunk_ents in chunk_entities.items():
        if len(chunk_ents) < 2:
            continue
        chunk_text = next((c["content"] for c in chunks if c["chunk_index"] == chunk_index), "")
        chunk_ents = sorted(chunk_ents, key=lambda e: e.confidence, reverse=True)[:8]

        pair_count = 0
        for i, src in enumerate(chunk_ents):
            for tgt in chunk_ents[i + 1:]:
                if pair_count >= MAX_CO_OCCURRENCE_PAIRS_PER_CHUNK:
                    break
                rel_type = type_rel_map.get((src.entity_type, tgt.entity_type))
                if not rel_type:
                    rel_type = type_rel_map.get((tgt.entity_type, src.entity_type))
                    if rel_type:
                        src, tgt = tgt, src
                if not rel_type:
                    if src.entity_type == tgt.entity_type == "Gene":
                        continue
                    rel_type = "ASSOCIATED_WITH"

                key = (src.name.lower(), tgt.name.lower(), rel_type)
                if key in seen:
                    continue
                seen.add(key)
                pair_count += 1
                relationships.append(ExtractedRelationship(
                    source_name=src.name,
                    source_type=src.entity_type,
                    target_name=tgt.name,
                    target_type=tgt.entity_type,
                    relationship_type=rel_type,
                    confidence=min(src.confidence, tgt.confidence) * 0.85,
                    source_chunk_index=chunk_index,
                    evidence=chunk_text[:300],
                ))
            if pair_count >= MAX_CO_OCCURRENCE_PAIRS_PER_CHUNK:
                break

    return filter_relationships(relationships)


def map_ontology(entity_name: str, entity_type: str) -> str:
    slug = re.sub(r"[^a-z0-9]", "", entity_name.lower())[:12]
    type_code = entity_type[:3].upper()
    return f"ONT:{type_code}:{slug}:{uuid.uuid4().hex[:6]}"
