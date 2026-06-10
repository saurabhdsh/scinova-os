"""Full Scientific Data Fabric ingestion pipeline."""

import logging
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.config import settings
from app.models.db_models import (
    AuditEvent,
    Document,
    DocumentChunk,
    GraphNode,
    GraphRelationship,
    IngestionJob,
    ScientificEntity,
)
from app.services.chunker import chunk_text
from app.services.chromadb_client import chromadb_client
from app.services.document_parser import infer_source_type, parse_document
from app.services.embedding_service import embedding_service
from app.services.graph_sync import sync_document_to_neo4j
from app.services.llm_entity_extractor import extract_entities_hybrid, extract_relationships_hybrid
from app.services.entity_extractor import map_ontology

logger = logging.getLogger(__name__)


def _touch_doc_metadata(doc: Document) -> None:
    """SQLAlchemy does not detect in-place JSON mutations; ensure commits persist."""
    if doc.metadata_json is not None:
        flag_modified(doc, "metadata_json")


INGESTION_STAGES = [
    "upload",
    "metadata_extract",
    "text_extract",
    "qc_check",
    "chunk",
    "embed",
    "vector_index",
    "entity_extract",
    "relationship_extract",
    "ontology_map",
    "graph_update",
    "neo4j_sync",
    "complete",
]


def start_ingestion(
    db: Session,
    filename: str,
    file_content: bytes,
    source_type: str | None = None,
    user_id: str | None = None,
    project_id: str | None = None,
) -> IngestionJob:
    doc_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    ext = Path(filename).suffix.upper().lstrip(".") or "TXT"

    doc_dir = Path(settings.upload_dir) / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    file_path = doc_dir / filename

    with open(file_path, "wb") as f:
        f.write(file_content)

    inferred_source = infer_source_type(filename, source_type)

    doc = Document(
        id=doc_id,
        title=filename,
        source_type=inferred_source,
        file_format=ext,
        file_path=str(file_path),
        status="processing",
        metadata_json={
            "uploaded_at": datetime.utcnow().isoformat(),
            "original_filename": filename,
            "file_size_bytes": len(file_content),
        },
        version=1,
        user_id=user_id,
        project_id=project_id,
    )
    job = IngestionJob(
        id=job_id,
        document_id=doc_id,
        status="processing",
        stage="upload",
        progress=0.0,
        stages_completed=[],
        user_id=user_id,
        project_id=project_id,
    )
    db.add(doc)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def run_ingestion_pipeline(db: Session, job_id: str) -> None:
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    if not job:
        logger.error("Job %s not found", job_id)
        return

    doc = db.query(Document).filter(Document.id == job.document_id).first()
    if not doc:
        _fail_job(db, job, "Document not found")
        return

    try:
        parsed = None
        chunks_data: list[dict] = []
        embedding_model = "none"
        extracted_entities = []
        pending_relationships: list[dict] = []
        extraction_method = "pattern_v1"

        for stage in INGESTION_STAGES:
            _advance_stage(db, job, stage)

            if stage == "upload":
                pass  # already saved

            elif stage == "metadata_extract":
                doc.metadata_json.update({
                    "pipeline_version": "2.0",
                    "embedding_provider": embedding_service.provider_label(),
                })

            elif stage == "text_extract":
                parsed = parse_document(doc.file_path, doc.file_format or "TXT")
                doc.metadata_json.update(parsed.metadata)
                doc.title = parsed.metadata.get("title") or doc.title

            elif stage == "qc_check":
                fmt = (doc.file_format or "").upper()
                if fmt in ("CSV", "XLSX") or doc.source_type in (
                    "assay_dataset", "lims_export", "omics_dataset", "csv", "xlsx",
                ):
                    from app.services.experiment_qc_service import run_experiment_qc
                    qc = run_experiment_qc(doc.file_path, doc.file_format or "CSV")
                    doc.metadata_json["qc_report"] = qc
                    doc.metadata_json["qc_status"] = qc.get("status")
                    if qc.get("status") == "fail":
                        doc.metadata_json["qc_warning"] = True

            elif stage == "chunk":
                assert parsed is not None
                text_chunks = chunk_text(
                    parsed.text,
                    chunk_size=settings.chunk_size,
                    chunk_overlap=settings.chunk_overlap,
                    sections=parsed.sections or None,
                )
                chunks_data = [
                    {
                        "chunk_index": tc.index,
                        "content": tc.content,
                        "token_count": tc.token_count,
                        "metadata": tc.metadata,
                        "chroma_id": f"{doc.id}_{tc.index}",
                    }
                    for tc in text_chunks
                ]
                doc.metadata_json["chunk_count"] = len(chunks_data)

            elif stage == "embed":
                if chunks_data:
                    texts = [c["content"] for c in chunks_data]
                    embeddings, embedding_model = embedding_service.embed_texts(texts)
                    for i, emb in enumerate(embeddings):
                        chunks_data[i]["embedding"] = emb
                    doc.metadata_json["embedding_model"] = embedding_model

            elif stage == "vector_index":
                embeddings = [c.get("embedding") for c in chunks_data] if chunks_data else None
                use_embeddings = embeddings if embeddings and embedding_service.remote_available() else None
                index_result = chromadb_client.index_chunks(doc.id, chunks_data, use_embeddings)
                doc.metadata_json["vector_index"] = index_result

                for c in chunks_data:
                    db.add(DocumentChunk(
                        id=str(uuid.uuid4()),
                        document_id=doc.id,
                        chunk_index=c["chunk_index"],
                        content=c["content"],
                        token_count=c["token_count"],
                        chroma_id=c["chroma_id"],
                        metadata_json={**c.get("metadata", {}), "embedding_model": embedding_model},
                    ))

            elif stage == "entity_extract":
                extracted_entities, extraction_method = extract_entities_hybrid(chunks_data)
                doc.metadata_json["entities_extracted"] = len(extracted_entities)
                doc.metadata_json["entity_extraction_method"] = extraction_method
                for ent in extracted_entities:
                    db.add(ScientificEntity(
                        id=str(uuid.uuid4()),
                        name=ent.name,
                        entity_type=ent.entity_type,
                        description=f"Extracted from {doc.title}",
                        ontology_id=map_ontology(ent.name, ent.entity_type),
                        source_document_id=doc.id,
                        confidence=ent.confidence,
                        metadata_json={
                            "chunk_index": ent.source_chunk_index,
                            "context": ent.context[:200],
                            "extracted_by": extraction_method,
                        },
                    ))

            elif stage == "relationship_extract":
                relationships, rel_method = extract_relationships_hybrid(extracted_entities, chunks_data)
                doc.metadata_json["relationships_extracted"] = len(relationships)
                doc.metadata_json["relationship_extraction_method"] = rel_method
                pending_relationships = [
                    {
                        "source_name": r.source_name,
                        "source_type": r.source_type,
                        "target_name": r.target_name,
                        "target_type": r.target_type,
                        "relationship_type": r.relationship_type,
                        "confidence": r.confidence,
                        "evidence": r.evidence,
                        "chunk_index": r.source_chunk_index,
                    }
                    for r in relationships
                ]
                _touch_doc_metadata(doc)

            elif stage == "ontology_map":
                pass  # ontology IDs assigned during entity_extract

            elif stage == "graph_update":
                pending = pending_relationships
                entity_nodes: dict[tuple[str, str], str] = {}

                db_entities = db.query(ScientificEntity).filter(
                    ScientificEntity.source_document_id == doc.id
                ).all()
                for ent in db_entities:
                    key = (ent.name.lower(), ent.entity_type)
                    node = GraphNode(
                        id=str(uuid.uuid4()),
                        label=ent.name,
                        node_type=ent.entity_type,
                        entity_id=ent.id,
                        properties_json={"confidence": ent.confidence},
                        evidence_json=[{
                            "document_id": doc.id,
                            "document_title": doc.title,
                            "chunk_index": ent.metadata_json.get("chunk_index"),
                        }],
                    )
                    db.add(node)
                    db.flush()
                    entity_nodes[key] = node.id

                for rel in pending:
                    src_key = (rel["source_name"].lower(), rel["source_type"])
                    tgt_key = (rel["target_name"].lower(), rel["target_type"])
                    src_id = entity_nodes.get(src_key)
                    tgt_id = entity_nodes.get(tgt_key)
                    if src_id and tgt_id:
                        db.add(GraphRelationship(
                            id=str(uuid.uuid4()),
                            source_node_id=src_id,
                            target_node_id=tgt_id,
                            relationship_type=rel["relationship_type"],
                        properties_json={"extracted_by": doc.metadata_json.get("relationship_extraction_method", "co_occurrence_v1")},
                            evidence_json=[{
                                "document_id": doc.id,
                                "document_title": doc.title,
                                "chunk_index": rel.get("chunk_index"),
                                "excerpt": rel.get("evidence", "")[:300],
                            }],
                            confidence=rel["confidence"],
                        ))

                doc.metadata_json["graph_nodes_created"] = len(entity_nodes)
                doc.metadata_json["graph_relationships_created"] = sum(
                    1 for rel in pending
                    if entity_nodes.get((rel["source_name"].lower(), rel["source_type"]))
                    and entity_nodes.get((rel["target_name"].lower(), rel["target_type"]))
                )
                _touch_doc_metadata(doc)

            elif stage == "neo4j_sync":
                if settings.neo4j_enabled:
                    neo4j_result = sync_document_to_neo4j(db, doc.id)
                    doc.metadata_json["neo4j_sync"] = neo4j_result
                else:
                    doc.metadata_json["neo4j_sync"] = {"synced": False, "mode": "disabled"}

            elif stage == "complete":
                doc.status = "indexed"
                job.status = "completed"
                job.completed_at = datetime.utcnow()

            _touch_doc_metadata(doc)
            db.commit()

        db.add(AuditEvent(
            event_type="document_ingest",
            actor="system",
            resource_type="document",
            resource_id=doc.id,
            action=f"Document '{doc.title}' ingested through SciFabric pipeline v3",
            details_json={
                "job_id": job.id,
                "chunks": doc.metadata_json.get("chunk_count", 0),
                "entities": doc.metadata_json.get("entities_extracted", 0),
                "relationships": doc.metadata_json.get("relationships_extracted", 0),
                "embedding_model": doc.metadata_json.get("embedding_model"),
                "entity_extraction": doc.metadata_json.get("entity_extraction_method"),
                "neo4j_sync": doc.metadata_json.get("neo4j_sync"),
            },
        ))
        db.commit()
        logger.info("Ingestion complete for job %s document %s", job.id, doc.id)

    except Exception as e:
        logger.exception("Ingestion failed for job %s", job_id)
        _fail_job(db, job, str(e))


def _advance_stage(db: Session, job: IngestionJob, stage: str) -> None:
    completed = list(job.stages_completed or [])
    if stage not in completed:
        completed.append(stage)
    job.stage = stage
    job.stages_completed = completed
    job.progress = round(len(completed) / len(INGESTION_STAGES) * 100, 1)
    db.commit()


def _fail_job(db: Session, job: IngestionJob, error: str) -> None:
    job.status = "failed"
    job.error_message = error
    job.completed_at = datetime.utcnow()
    if job.document_id:
        doc = db.query(Document).filter(Document.id == job.document_id).first()
        if doc:
            doc.status = "failed"
    db.commit()


def backfill_graph_relationships(db: Session, document_id: str) -> dict:
    """Create SQL graph edges for a document that already has entities/nodes but no rels."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise ValueError("Document not found")

    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
        .all()
    )
    if not chunks:
        return {"document_id": document_id, "created": 0, "reason": "no_chunks"}

    chunks_data = [
        {"chunk_index": c.chunk_index, "content": c.content, "token_count": c.token_count}
        for c in chunks
    ]
    entities, _ = extract_entities_hybrid(chunks_data)
    relationships, rel_method = extract_relationships_hybrid(entities, chunks_data)

    db_entities = db.query(ScientificEntity).filter(
        ScientificEntity.source_document_id == document_id
    ).all()
    entity_nodes: dict[tuple[str, str], str] = {}
    for ent in db_entities:
        node = (
            db.query(GraphNode)
            .filter(GraphNode.entity_id == ent.id)
            .order_by(GraphNode.label)
            .first()
        )
        if node:
            entity_nodes[(ent.name.lower(), ent.entity_type)] = node.id

    created = 0
    seen: set[tuple[str, str, str]] = set()
    for rel in relationships:
        src_key = (rel.source_name.lower(), rel.source_type)
        tgt_key = (rel.target_name.lower(), rel.target_type)
        src_id = entity_nodes.get(src_key)
        tgt_id = entity_nodes.get(tgt_key)
        if not src_id or not tgt_id:
            continue
        dedupe = (src_id, tgt_id, rel.relationship_type)
        if dedupe in seen:
            continue
        seen.add(dedupe)
        db.add(GraphRelationship(
            id=str(uuid.uuid4()),
            source_node_id=src_id,
            target_node_id=tgt_id,
            relationship_type=rel.relationship_type,
            properties_json={"extracted_by": rel_method, "backfill": True},
            evidence_json=[{
                "document_id": doc.id,
                "document_title": doc.title,
                "chunk_index": rel.source_chunk_index,
                "excerpt": rel.evidence[:300],
            }],
            confidence=rel.confidence,
        ))
        created += 1

    doc.metadata_json = {
        **(doc.metadata_json or {}),
        "relationships_extracted": len(relationships),
        "relationship_extraction_method": rel_method,
        "graph_relationships_created": created,
        "relationship_backfill_at": datetime.utcnow().isoformat(),
    }
    _touch_doc_metadata(doc)
    db.commit()

    if settings.neo4j_enabled:
        sync_document_to_neo4j(db, document_id)

    return {
        "document_id": document_id,
        "relationships_found": len(relationships),
        "relationships_created": created,
        "method": rel_method,
    }


def semantic_search(
    query: str,
    top_k: int = 10,
    document_id: str | None = None,
    document_ids: list[str] | None = None,
) -> list[dict]:
    query_embedding = None
    if embedding_service.remote_available():
        query_embedding, _ = embedding_service.embed_query(query)
    return chromadb_client.search(
        query,
        top_k=top_k,
        document_id=document_id,
        document_ids=document_ids,
        query_embedding=query_embedding,
    )
