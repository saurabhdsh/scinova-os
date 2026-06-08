"""Unified evidence gathering for specialized agent pipelines."""

from sqlalchemy.orm import Session

from app.services.external_integrations import fetch_eln_records, search_kegg, search_pubmed
from app.services.graph_service import search_graph
from app.services.ingestion_pipeline import semantic_search
from app.services.rag_service import _build_citations, _enrich_hits


def _should_use_tool(tools: list, *names: str) -> bool:
    tool_set = {t.lower() for t in (tools or [])}
    return any(n.lower() in tool_set for n in names)


def gather_evidence(
    db: Session,
    query: str,
    *,
    tools_used: list | None = None,
    document_id: str | None = None,
    document_ids: list[str] | None = None,
    user_id: str | None = None,
    top_k: int = 8,
    include_pubmed: bool = True,
    include_kegg: bool = True,
    include_kg: bool = True,
    include_eln: bool = False,
) -> dict:
    """Collect evidence from vector index, PubMed, KEGG, knowledge graph, and ELN."""
    tools = tools_used or []
    logs: list[dict] = []
    citations: list[dict] = []
    idx = 1

    hits = semantic_search(
        query,
        top_k=top_k,
        document_id=document_id,
        document_ids=None if document_id else document_ids,
    )
    vector_chunks = _enrich_hits(db, hits)
    for c in vector_chunks:
        c["index"] = idx
        idx += 1
    if vector_chunks:
        logs.append({"message": f"Vector index: {len(vector_chunks)} chunks"})
        citations.extend(_build_citations(vector_chunks))

    pubmed_articles = []
    if include_pubmed and (
        _should_use_tool(tools, "Literature Miner", "PubMed", "Patent DB")
        or not tools
    ):
        pubmed_articles = search_pubmed(query, max_results=5)
        for art in pubmed_articles:
            citations.append({
                "index": idx,
                "title": art["title"],
                "source": "pubmed",
                "document_id": art.get("pmid"),
                "relevance": 0.72,
                "excerpt": art.get("abstract", "")[:400],
                "url": art.get("url"),
                "metadata": {"journal": art.get("journal"), "year": art.get("year")},
            })
            idx += 1
        if pubmed_articles:
            logs.append({"message": f"PubMed: {len(pubmed_articles)} articles"})

    kegg_entries = []
    if include_kegg and (
        _should_use_tool(tools, "KEGG", "Reactome", "KG Builder", "KG Query")
        or not tools
    ):
        kegg_entries = search_kegg(query, max_results=4)
        for entry in kegg_entries:
            citations.append({
                "index": idx,
                "title": f"KEGG {entry['kegg_id']}: {entry['description'][:80]}",
                "source": "kegg",
                "document_id": entry["kegg_id"],
                "relevance": 0.68,
                "excerpt": f"Pathways: {', '.join(entry.get('pathways', [])[:3])}",
                "url": entry.get("url"),
            })
            idx += 1
        if kegg_entries:
            logs.append({"message": f"KEGG: {len(kegg_entries)} gene/pathway hits"})

    kg_entities = []
    if include_kg and (
        _should_use_tool(tools, "KG Query", "KG Builder", "Ontology Mapper")
        or not tools
    ):
        graph = search_graph(
            db, q=query, document_id=document_id, limit=12, user_id=user_id,
        )
        kg_entities = [
            {"id": n.id, "name": n.label, "type": n.node_type, "entity_id": n.entity_id}
            for n in graph.nodes[:8]
        ]
        for ent in kg_entities:
            citations.append({
                "index": idx,
                "title": f"{ent['name']} ({ent['type']})",
                "source": "knowledge_graph",
                "document_id": ent.get("entity_id"),
                "relevance": 0.65,
                "excerpt": f"Graph node in {graph.graph_source or 'sql'} graph",
            })
            idx += 1
        if kg_entities:
            logs.append({"message": f"Knowledge graph: {len(kg_entities)} entities"})

    eln_records = []
    if include_eln or _should_use_tool(tools, "ELN Connector", "ELN/LIMS Copilot", "Data Profiler"):
        eln_records = fetch_eln_records(db, query, limit=5)
        for rec in eln_records:
            citations.append({
                "index": idx,
                "title": rec["title"],
                "source": "eln_lims",
                "document_id": rec["record_id"],
                "relevance": 0.7,
                "excerpt": rec.get("excerpt", "")[:400],
            })
            idx += 1
        if eln_records:
            logs.append({"message": f"ELN/LIMS: {len(eln_records)} experiment records"})

    return {
        "vector_chunks": vector_chunks,
        "pubmed_articles": pubmed_articles,
        "kegg_entries": kegg_entries,
        "kg_entities": kg_entities,
        "eln_records": eln_records,
        "citations": citations,
        "logs": logs,
    }


def build_evidence_context(evidence: dict) -> str:
    """Format gathered evidence for LLM prompts."""
    parts = []

    for c in evidence.get("vector_chunks", []):
        parts.append(
            f"[Doc-{c['index']}] {c['document_title']} (relevance {c['score']:.2f})\n{c['content'][:800]}"
        )

    for i, art in enumerate(evidence.get("pubmed_articles", []), 1):
        parts.append(
            f"[PubMed-{i}] {art['title']} ({art.get('journal', '')} {art.get('year', '')})\n{art.get('abstract', '')[:600]}"
        )

    for i, entry in enumerate(evidence.get("kegg_entries", []), 1):
        parts.append(
            f"[KEGG-{i}] {entry['kegg_id']}: {entry['description']}\nPathways: {', '.join(entry.get('pathways', []))}"
        )

    for i, ent in enumerate(evidence.get("kg_entities", []), 1):
        parts.append(f"[KG-{i}] {ent['name']} ({ent['type']})")

    for i, rec in enumerate(evidence.get("eln_records", []), 1):
        parts.append(f"[ELN-{i}] {rec['title']}\n{rec.get('excerpt', '')[:500]}")

    return "\n\n".join(parts) if parts else "No external or internal evidence retrieved."


def evidence_confidence(evidence: dict, used_llm: bool) -> float:
    scores = []
    for c in evidence.get("vector_chunks", []):
        scores.append(c.get("score", 0.5))
    if evidence.get("pubmed_articles"):
        scores.append(0.7)
    if evidence.get("kegg_entries"):
        scores.append(0.65)
    if evidence.get("kg_entities"):
        scores.append(0.6)
    if not scores:
        return 0.25 if used_llm else 0.15
    avg = sum(scores) / len(scores)
    base = min(0.92, 0.4 + avg * 0.45 + len(scores) * 0.02)
    return round(base if used_llm else base * 0.75, 2)
