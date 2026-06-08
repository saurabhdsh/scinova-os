"""RAG pipeline: retrieve chunks from ChromaDB and generate grounded answers with citations."""

import html
import logging
import re

from sqlalchemy.orm import Session

from app.config import settings
from app.models.db_models import Document
from app.services.ingestion_pipeline import semantic_search
from app.services.llm_service import llm_service

from app.services.agent_capabilities import is_qa_mode

logger = logging.getLogger(__name__)

RAG_SYSTEM = """You are a scientific research assistant for a pharma R&D platform.
Answer the user's question using ONLY the provided context excerpts from ingested documents.

Rules:
- If the context does not contain enough information, say so clearly.
- Reference sources using [1], [2], etc. matching the source numbers in the context.
- Be precise with scientific terms, study phases, endpoints, and compound names.
- Do not invent facts not supported by the context.
- Write polished professional prose — no markdown headings (#), no ** bold, no bullet markdown.
- Use 2-4 short paragraphs of complete sentences for complex questions."""


def _decode_title(title: str) -> str:
    if not title:
        return "Untitled document"
    try:
        return html.unescape(re.sub(r"<[^>]+>", "", title))
    except Exception:
        return title


def _enrich_hits(db: Session | None, hits: list[dict]) -> list[dict]:
    if not hits:
        return []

    doc_titles: dict[str, str] = {}
    if db:
        doc_ids = list({h["document_id"] for h in hits if h.get("document_id")})
        if doc_ids:
            docs = db.query(Document).filter(Document.id.in_(doc_ids)).all()
            doc_titles = {d.id: _decode_title(d.title) for d in docs}

    enriched = []
    for i, h in enumerate(hits, start=1):
        doc_id = h.get("document_id", "")
        content = h.get("content") or ""
        enriched.append({
            "index": i,
            "chunk_id": h.get("chunk_id"),
            "document_id": doc_id,
            "document_title": doc_titles.get(doc_id, f"Document {doc_id[:8]}"),
            "chunk_index": h.get("chunk_index"),
            "score": float(h.get("score") or 0),
            "content": content,
            "excerpt": content[:400],
        })
    return enriched


def _build_context(chunks: list[dict]) -> str:
    parts = []
    for c in chunks:
        parts.append(
            f"[{c['index']}] {c['document_title']} "
            f"(chunk {c['chunk_index']}, relevance {c['score']:.2f})\n{c['content']}"
        )
    return "\n\n".join(parts)


def _build_citations(chunks: list[dict]) -> list[dict]:
    return [
        {
            "index": c["index"],
            "title": c["document_title"],
            "source": "vector_index",
            "document_id": c["document_id"],
            "chunk_id": c.get("chunk_id"),
            "chunk_index": c.get("chunk_index"),
            "relevance": c["score"],
            "excerpt": c["excerpt"],
        }
        for c in chunks
    ]


def _confidence_from_hits(chunks: list[dict], used_llm: bool) -> float:
    if not chunks:
        return 0.2
    avg_score = sum(c["score"] for c in chunks) / len(chunks)
    base = min(0.95, 0.45 + avg_score * 0.5)
    return round(base if used_llm else base * 0.7, 2)


def _extract_findings(answer: str) -> list[str]:
    lines = [line.strip() for line in answer.split("\n") if line.strip().startswith(("-", "•", "*"))]
    if lines:
        return [re.sub(r"^[-•*]\s*", "", line) for line in lines[:5]]
    sentences = re.split(r"(?<=[.!?])\s+", answer)
    return [s.strip() for s in sentences if len(s.strip()) > 40][:3]


def agent_supports_rag(agent, input_data: dict) -> bool:
    query = str(input_data.get("query", "")).strip()
    if not query:
        return False

    if is_qa_mode(input_data):
        return True

    tools = agent.tools_used or []
    if "Vector Search" in tools or "KG Query" in tools:
        return True

    name = (agent.name or "").lower()
    return "q&a" in name or "semantic q" in name or "knowledge scout" in name


def run_rag_query(
    db: Session,
    query: str,
    *,
    document_id: str | None = None,
    document_ids: list[str] | None = None,
    top_k: int = 8,
    model: str | None = None,
    agent_name: str = "Agent",
    agent_category: str | None = None,
    agent_description: str | None = None,
) -> dict:
    logs: list[dict] = []
    query = (query or "").strip()
    if not query:
        return {
            "output": {
                "answer": "Please provide a question to search the knowledge base.",
                "mode": "error",
                "agent": agent_name,
            },
            "citations": [],
            "confidence": 0.0,
            "logs": logs,
        }

    logs.append({"message": f"Retrieving top {top_k} chunks for query"})
    hits = semantic_search(
        query,
        top_k=top_k,
        document_id=document_id,
        document_ids=document_ids,
    )
    chunks = _enrich_hits(db, hits)
    logs.append({"message": f"Retrieved {len(chunks)} relevant chunks from vector index"})

    if not chunks:
        return {
            "output": {
                "answer": (
                    "No relevant documents were found in the knowledge base. "
                    "Upload scientific PDFs in Data Fabric first, then try again."
                ),
                "mode": "retrieval_empty",
                "agent": agent_name,
                "query": query,
                "chunks_used": 0,
            },
            "citations": [],
            "confidence": 0.15,
            "logs": logs,
        }

    context = _build_context(chunks)
    persona = agent_name
    if agent_category:
        persona += f" ({agent_category})"
    scope_hint = ""
    if agent_description:
        scope_hint = f"\nAgent scope: {agent_description[:400]}"
    system = (
        f"{RAG_SYSTEM}\n\nYou are responding as **{persona}** — frame answers from that agent's domain perspective."
        f"{scope_hint}"
    )
    user_prompt = f"""Context excerpts from indexed documents:

{context}

---

Question: {query}

Answer the question using the context above. Cite sources as [1], [2], etc."""

    inference_model = model or settings.llm_model
    answer = None
    mode = "retrieval_only"

    if llm_service.is_configured(inference_model):
        logs.append({"message": f"Generating grounded answer with {inference_model} as {agent_name}"})
        answer = llm_service.chat(system, user_prompt, model=inference_model)
        if answer:
            mode = "rag"
            logs.append({"message": "LLM answer generated with citation grounding"})
        else:
            logs.append({"message": "LLM call failed; falling back to retrieval summary"})
    else:
        logs.append({"message": "OPENAI_API_KEY not set; returning retrieval summary only"})

    if not answer:
        answer = (
            "**Retrieval results** (set OPENAI_API_KEY for full synthesized answers)\n\n"
            + "\n\n".join(
                f"**[{c['index']}] {c['document_title']}** ({c['score'] * 100:.0f}% match)\n{c['excerpt']}..."
                for c in chunks[:3]
            )
        )

    citations = _build_citations(chunks)
    confidence = _confidence_from_hits(chunks, mode == "rag")

    output = {
        "answer": answer,
        "mode": mode,
        "agent": agent_name,
        "query": query,
        "chunks_used": len(chunks),
        "model_used": inference_model if mode == "rag" else None,
        "summary": answer[:240] + "..." if len(answer) > 240 else answer,
        "findings": _extract_findings(answer) if mode == "rag" else [],
        "task_type": "qa",
    }

    return {
        "output": output,
        "citations": citations,
        "confidence": confidence,
        "logs": logs,
    }
