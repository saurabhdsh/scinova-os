"""Sync SQL graph nodes/relationships to Neo4j."""

import logging

from sqlalchemy.orm import Session

from app.models.db_models import GraphNode, GraphRelationship, ScientificEntity
from app.services.neo4j_client import neo4j_client

logger = logging.getLogger(__name__)


def sync_document_to_neo4j(db: Session, document_id: str) -> dict:
    entities = db.query(ScientificEntity).filter(
        ScientificEntity.source_document_id == document_id
    ).all()
    entity_ids = {e.id for e in entities}

    nodes = db.query(GraphNode).filter(GraphNode.entity_id.in_(entity_ids)).all() if entity_ids else []
    node_ids = {n.id for n in nodes}

    rels = db.query(GraphRelationship).filter(
        GraphRelationship.source_node_id.in_(node_ids),
        GraphRelationship.target_node_id.in_(node_ids),
    ).all() if node_ids else []

    neo4j_nodes = []
    for n in nodes:
        ent = next((e for e in entities if e.id == n.entity_id), None)
        neo4j_nodes.append({
            "id": n.id,
            "label": n.label,
            "node_type": n.node_type,
            "entity_id": n.entity_id,
            "document_id": document_id,
            "confidence": ent.confidence if ent else n.properties_json.get("confidence", 0.8),
        })

    neo4j_rels = []
    for r in rels:
        neo4j_rels.append({
            "id": r.id,
            "source_node_id": r.source_node_id,
            "target_node_id": r.target_node_id,
            "relationship_type": r.relationship_type,
            "confidence": r.confidence,
            "document_id": document_id,
        })

    result = neo4j_client.sync_document_graph(neo4j_nodes, neo4j_rels)
    logger.info("Neo4j sync for doc %s: %s", document_id, result)
    return result
