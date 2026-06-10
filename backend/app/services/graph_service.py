"""Unified graph query layer — Neo4j when available, SQL fallback, evidence enrichment."""

from sqlalchemy.orm import Session

from app.config import settings
from app.models.db_models import DocumentChunk, GraphNode, GraphRelationship, ScientificEntity
from app.models.schemas import GraphNeighborhoodResponse, GraphNodeResponse, GraphRelationshipResponse, GraphSearchResponse
from app.services.neo4j_client import neo4j_client


from app.services.workspace import document_ids_for_user


def _entity_ids_for_scope(
    db: Session,
    user_id: str,
    document_id: str | None = None,
    project_id: str | None = None,
) -> list[str]:
    doc_ids = document_ids_for_user(db, user_id, project_id)
    if document_id:
        doc_ids = [document_id] if document_id in doc_ids else []
    if not doc_ids:
        return []
    return [
        row[0]
        for row in db.query(ScientificEntity.id).filter(
            ScientificEntity.source_document_id.in_(doc_ids)
        ).all()
    ]


def _user_graph_node_ids(
    db: Session,
    user_id: str,
    document_id: str | None = None,
    project_id: str | None = None,
) -> set[str]:
    entity_ids = _entity_ids_for_scope(db, user_id, document_id, project_id)
    if not entity_ids:
        return set()
    return {
        row[0]
        for row in db.query(GraphNode.id).filter(GraphNode.entity_id.in_(entity_ids)).all()
    }


def _filter_graph_response(
    response: GraphSearchResponse,
    allowed_nodes: set[str] | None,
) -> GraphSearchResponse:
    if allowed_nodes is None:
        return response
    nodes = [n for n in response.nodes if n.id in allowed_nodes]
    node_ids = {n.id for n in nodes}
    rels = [
        r for r in response.relationships
        if r.source_node_id in node_ids and r.target_node_id in node_ids
    ]
    return GraphSearchResponse(
        nodes=nodes,
        relationships=rels,
        graph_source=response.graph_source,
        graph_hint=response.graph_hint,
    )


def resolve_graph_source(requested: str = "auto") -> str:
    mode = (requested or "auto").lower()
    if mode == "sql":
        return "sql"
    if mode == "neo4j":
        return "neo4j" if neo4j_client.connect() else "sql"
    if settings.neo4j_enabled and neo4j_client.connect():
        return "neo4j"
    return "sql"


def _enrich_nodes(db: Session, nodes: list[dict]) -> list[GraphNodeResponse]:
    if not nodes:
        return []
    ids = [n["id"] for n in nodes]
    sql_by_id = {n.id: n for n in db.query(GraphNode).filter(GraphNode.id.in_(ids)).all()}
    enriched = []
    for n in nodes:
        sql_node = sql_by_id.get(n["id"])
        if sql_node:
            enriched.append(GraphNodeResponse.model_validate(sql_node))
        else:
            enriched.append(GraphNodeResponse(
                id=n["id"],
                label=n.get("label") or "Unknown",
                node_type=n.get("node_type") or "Entity",
                entity_id=n.get("entity_id"),
                properties_json=n.get("properties_json") or {},
                evidence_json=n.get("evidence_json") or [],
            ))
    return enriched


def _enrich_relationships(db: Session, rels: list[dict]) -> list[GraphRelationshipResponse]:
    if not rels:
        return []
    ids = [r["id"] for r in rels if r.get("id")]
    sql_by_id = {r.id: r for r in db.query(GraphRelationship).filter(GraphRelationship.id.in_(ids)).all()}
    enriched = []
    for r in rels:
        sql_rel = sql_by_id.get(r.get("id"))
        if sql_rel:
            enriched.append(GraphRelationshipResponse.model_validate(sql_rel))
        else:
            enriched.append(GraphRelationshipResponse(
                id=r["id"],
                source_node_id=r["source_node_id"],
                target_node_id=r["target_node_id"],
                relationship_type=r.get("relationship_type") or "ASSOCIATED_WITH",
                properties_json=r.get("properties_json") or {},
                evidence_json=r.get("evidence_json") or [],
                confidence=float(r.get("confidence") or 0.8),
            ))
    return enriched


def _source_chunks_for_nodes(db: Session, nodes: list[GraphNodeResponse]) -> list:
    document_ids = set()
    for node in nodes:
        for ev in node.evidence_json or []:
            if ev.get("document_id"):
                document_ids.add(ev["document_id"])
    if not document_ids:
        entity_ids = [n.entity_id for n in nodes if n.entity_id]
        if entity_ids:
            for ent in db.query(ScientificEntity).filter(ScientificEntity.id.in_(entity_ids)).all():
                if ent.source_document_id:
                    document_ids.add(ent.source_document_id)
    if not document_ids:
        return []
    return db.query(DocumentChunk).filter(
        DocumentChunk.document_id.in_(list(document_ids))
    ).order_by(DocumentChunk.chunk_index).limit(10).all()


def _live_entity_ids(db: Session) -> set[str]:
    return {
        e.id for e in db.query(ScientificEntity).all()
        if (e.metadata_json or {}).get("extracted_by") not in (None, "Entity Resolver Agent")
    }


def _connected_subgraph_sql(
    db: Session,
    limit: int = 80,
    document_id: str | None = None,
    live_only: bool = False,
    user_id: str | None = None,
    project_id: str | None = None,
) -> GraphSearchResponse:
    """Build a connected subgraph (relationships first) for meaningful visualization."""
    graph_hint = None
    allowed_nodes: set[str] | None = None
    if user_id:
        allowed_nodes = _user_graph_node_ids(db, user_id, document_id, project_id)
        if not allowed_nodes:
            hint = (
                "Upload documents to this project to build its knowledge graph."
                if project_id
                else "Upload documents to build your knowledge graph."
            )
            return GraphSearchResponse(
                nodes=[],
                relationships=[],
                graph_source="sql",
                graph_hint=hint,
            )
    rel_query = db.query(GraphRelationship)

    if document_id:
        entity_ids = [
            e.id for e in db.query(ScientificEntity).filter(
                ScientificEntity.source_document_id == document_id
            ).all()
        ]
        if not entity_ids:
            return GraphSearchResponse(nodes=[], relationships=[], graph_source="sql")
        doc_node_ids = {
            n.id for n in db.query(GraphNode).filter(GraphNode.entity_id.in_(entity_ids)).all()
        }
        rel_query = rel_query.filter(
            GraphRelationship.source_node_id.in_(doc_node_ids),
            GraphRelationship.target_node_id.in_(doc_node_ids),
        )

    rels = rel_query.order_by(GraphRelationship.confidence.desc()).limit(max(limit * 3, 150)).all()

    if live_only and not document_id:
        live_ids = _live_entity_ids(db)
        live_node_ids = {n.id for n in db.query(GraphNode).filter(GraphNode.entity_id.in_(live_ids)).all()}
        live_rels = [
            r for r in rels
            if r.source_node_id in live_node_ids and r.target_node_id in live_node_ids
        ]
        if live_rels:
            rels = live_rels
        else:
            rels = db.query(GraphRelationship).order_by(
                GraphRelationship.confidence.desc()
            ).limit(max(limit * 3, 150)).all()
            graph_hint = (
                "Live-ingested entities have no relationships yet — showing the connected knowledge graph."
            )

    if not rels:
        if document_id:
            fallback = _connected_subgraph_sql(
                db,
                limit=limit,
                document_id=None,
                live_only=False,
                user_id=user_id,
                project_id=project_id,
            )
            if fallback.relationships:
                fallback.graph_hint = (
                    "No relationships within this document — showing the scoped knowledge graph."
                )
                return fallback
            entity_ids = [
                e.id for e in db.query(ScientificEntity).filter(
                    ScientificEntity.source_document_id == document_id
                ).all()
            ]
            doc_nodes = db.query(GraphNode).filter(
                GraphNode.entity_id.in_(entity_ids)
            ).order_by(GraphNode.label).limit(limit).all() if entity_ids else []
            return GraphSearchResponse(
                nodes=[GraphNodeResponse.model_validate(n) for n in doc_nodes],
                relationships=[],
                graph_source="sql",
                graph_hint="No relationships found for this document yet.",
            )

        node_query = db.query(GraphNode).order_by(GraphNode.label)
        if allowed_nodes is not None:
            node_query = node_query.filter(GraphNode.id.in_(allowed_nodes))
        nodes = node_query.limit(limit).all()
        return GraphSearchResponse(
            nodes=[GraphNodeResponse.model_validate(n) for n in nodes],
            relationships=[],
            graph_source="sql",
            graph_hint="No relationships in graph yet — showing extracted entities as nodes. Use Search to explore.",
        )

    node_ids: set[str] = set()
    for r in rels:
        node_ids.add(r.source_node_id)
        node_ids.add(r.target_node_id)

    nodes = db.query(GraphNode).filter(GraphNode.id.in_(node_ids)).order_by(GraphNode.label).limit(limit).all()
    node_id_set = {n.id for n in nodes}
    filtered_rels = [
        r for r in rels
        if r.source_node_id in node_id_set and r.target_node_id in node_id_set
    ]
    if allowed_nodes is not None:
        nodes = [n for n in nodes if n.id in allowed_nodes]
        node_id_set = {n.id for n in nodes}
        filtered_rels = [
            r for r in filtered_rels
            if r.source_node_id in allowed_nodes and r.target_node_id in allowed_nodes
            and r.source_node_id in node_id_set and r.target_node_id in node_id_set
        ]

    return GraphSearchResponse(
        nodes=[GraphNodeResponse.model_validate(n) for n in nodes],
        relationships=[GraphRelationshipResponse.model_validate(r) for r in filtered_rels],
        graph_source="sql",
        graph_hint=graph_hint,
    )


def search_graph_sql(
    db: Session,
    q: str = "",
    entity_type: str | None = None,
    document_id: str | None = None,
    live_only: bool = False,
    limit: int = 80,
    user_id: str | None = None,
    project_id: str | None = None,
) -> GraphSearchResponse:
    q = (q or "").strip()
    allowed_nodes: set[str] | None = None
    if user_id:
        allowed_nodes = _user_graph_node_ids(db, user_id, document_id, project_id)
        if not allowed_nodes:
            hint = (
                "Upload documents to this project to build its knowledge graph."
                if project_id
                else "Upload documents to build your knowledge graph."
            )
            return GraphSearchResponse(nodes=[], relationships=[], graph_source="sql", graph_hint=hint)

    if not q and not entity_type:
        return _connected_subgraph_sql(
            db,
            limit=limit,
            document_id=document_id,
            live_only=live_only,
            user_id=user_id,
            project_id=project_id,
        )

    query = db.query(GraphNode)
    query = query.filter(GraphNode.label.ilike(f"%{q}%"))
    if entity_type:
        query = query.filter(GraphNode.node_type == entity_type)
    if document_id:
        entity_ids = [
            e.id for e in db.query(ScientificEntity).filter(
                ScientificEntity.source_document_id == document_id
            ).all()
        ]
        if entity_ids:
            query = query.filter(GraphNode.entity_id.in_(entity_ids))
        else:
            return GraphSearchResponse(nodes=[], relationships=[], graph_source="sql")
    elif live_only:
        entity_ids = list(_live_entity_ids(db))
        if entity_ids:
            query = query.filter(GraphNode.entity_id.in_(entity_ids))
        else:
            return GraphSearchResponse(nodes=[], relationships=[], graph_source="sql")
    elif user_id and allowed_nodes is not None:
        query = query.filter(GraphNode.id.in_(allowed_nodes))

    nodes = query.order_by(GraphNode.label).limit(limit).all()
    if not nodes:
        return GraphSearchResponse(nodes=[], relationships=[], graph_source="sql")

    node_ids = {n.id for n in nodes}
    rels = db.query(GraphRelationship).filter(
        GraphRelationship.source_node_id.in_(node_ids) | GraphRelationship.target_node_id.in_(node_ids)
    ).limit(200).all()

    if not rels:
        fallback = _connected_subgraph_sql(
            db,
            limit=limit,
            document_id=document_id,
            live_only=live_only,
            user_id=user_id,
            project_id=project_id,
        )
        if fallback.relationships:
            fallback.graph_hint = (
                f'No relationships matched "{q or entity_type}" — showing the connected knowledge graph.'
            )
            return fallback
        return GraphSearchResponse(
            nodes=[GraphNodeResponse.model_validate(n) for n in nodes],
            relationships=[],
            graph_source="sql",
            graph_hint="No relationships found for this search.",
        )

    for r in rels:
        node_ids.add(r.source_node_id)
        node_ids.add(r.target_node_id)
    expanded_nodes = db.query(GraphNode).filter(GraphNode.id.in_(node_ids)).order_by(GraphNode.label).limit(limit).all()
    if allowed_nodes is not None:
        expanded_nodes = [n for n in expanded_nodes if n.id in allowed_nodes]
    node_id_set = {n.id for n in expanded_nodes}
    filtered_rels = [
        r for r in rels
        if r.source_node_id in node_id_set and r.target_node_id in node_id_set
    ]

    return GraphSearchResponse(
        nodes=[GraphNodeResponse.model_validate(n) for n in expanded_nodes],
        relationships=[GraphRelationshipResponse.model_validate(r) for r in filtered_rels],
        graph_source="sql",
    )


def search_graph(
    db: Session,
    q: str = "",
    entity_type: str | None = None,
    document_id: str | None = None,
    live_only: bool = False,
    source: str = "auto",
    limit: int = 80,
    user_id: str | None = None,
    project_id: str | None = None,
) -> GraphSearchResponse:
    resolved = resolve_graph_source(source)
    allowed_nodes = (
        _user_graph_node_ids(db, user_id, document_id, project_id) if user_id else None
    )

    if resolved == "neo4j":
        if live_only and not document_id:
            pass
        neo_result = neo4j_client.search_graph(
            q=q,
            entity_type=entity_type,
            document_id=document_id,
            limit=limit,
        )
        if neo_result is not None:
            nodes = _enrich_nodes(db, neo_result["nodes"])
            rels = _enrich_relationships(db, neo_result["relationships"])
            if live_only and not document_id:
                live_entity_ids = {
                    e.id for e in db.query(ScientificEntity).all()
                    if (e.metadata_json or {}).get("extracted_by") not in (None, "Entity Resolver Agent")
                }
                nodes = [n for n in nodes if n.entity_id in live_entity_ids]
                node_ids = {n.id for n in nodes}
                rels = [r for r in rels if r.source_node_id in node_ids and r.target_node_id in node_ids]
            response = GraphSearchResponse(nodes=nodes, relationships=rels, graph_source="neo4j")
            return _filter_graph_response(response, allowed_nodes)

    result = search_graph_sql(
        db, q, entity_type, document_id, live_only, limit=limit,
        user_id=user_id, project_id=project_id,
    )
    result.graph_source = "sql"
    return result


def get_full_graph(
    db: Session,
    limit: int = 80,
    document_id: str | None = None,
    live_only: bool = False,
    source: str = "auto",
    user_id: str | None = None,
    project_id: str | None = None,
) -> GraphSearchResponse:
    resolved = resolve_graph_source(source)
    allowed_nodes = (
        _user_graph_node_ids(db, user_id, document_id, project_id) if user_id else None
    )

    if resolved == "neo4j":
        neo_result = neo4j_client.search_graph(q="", limit=limit, document_id=document_id)
        if neo_result is not None:
            nodes = _enrich_nodes(db, neo_result["nodes"])[:limit]
            rels = _enrich_relationships(db, neo_result["relationships"])
            node_ids = {n.id for n in nodes}
            rels = [r for r in rels if r.source_node_id in node_ids and r.target_node_id in node_ids]
            if nodes or rels:
                response = GraphSearchResponse(nodes=nodes, relationships=rels, graph_source="neo4j")
                filtered = _filter_graph_response(response, allowed_nodes)
                if filtered.relationships:
                    return filtered
                if filtered.nodes:
                    filtered.graph_hint = (
                        filtered.graph_hint
                        or "Showing project-scoped Neo4j nodes (relationships may be outside this project)."
                    )
                    return filtered
            # fall through to SQL if Neo4j results are empty after project scope

    return _connected_subgraph_sql(
        db,
        limit=limit,
        document_id=document_id,
        live_only=live_only,
        user_id=user_id,
        project_id=project_id,
    )


def get_neighborhood(
    db: Session,
    entity_id: str,
    source: str = "auto",
    depth: int = 2,
    user_id: str | None = None,
    project_id: str | None = None,
) -> GraphNeighborhoodResponse | None:
    resolved = resolve_graph_source(source)
    neo_connected = neo4j_client.connect()
    allowed_nodes = _user_graph_node_ids(db, user_id, project_id=project_id) if user_id else None

    center_sql = db.query(GraphNode).filter(
        (GraphNode.id == entity_id) | (GraphNode.entity_id == entity_id)
    ).first()
    if not center_sql:
        return None
    if allowed_nodes is not None and center_sql.id not in allowed_nodes:
        return None

    center_id = center_sql.id

    if resolved == "neo4j":
        neo_result = neo4j_client.get_neighborhood(center_id, depth=depth)
        if neo_result:
            center = _enrich_nodes(db, [neo_result["center_node"]])[0]
            neighbors = _enrich_nodes(db, neo_result["nodes"])
            rels = _enrich_relationships(db, neo_result["relationships"])
            if allowed_nodes is not None:
                neighbors = [n for n in neighbors if n.id in allowed_nodes]
                rels = [
                    r for r in rels
                    if r.source_node_id in allowed_nodes and r.target_node_id in allowed_nodes
                ]
            chunks = _source_chunks_for_nodes(db, [center, *neighbors])
            return GraphNeighborhoodResponse(
                center_node=center,
                nodes=neighbors,
                relationships=rels,
                source_chunks=chunks,
                neo4j_connected=neo_connected,
                graph_source="neo4j",
                traversal_depth=depth,
            )

    rels = db.query(GraphRelationship).filter(
        (GraphRelationship.source_node_id == center_id) | (GraphRelationship.target_node_id == center_id)
    ).all()
    if allowed_nodes is not None:
        rels = [
            r for r in rels
            if r.source_node_id in allowed_nodes and r.target_node_id in allowed_nodes
        ]
    neighbor_ids = set()
    for r in rels:
        neighbor_ids.add(r.source_node_id)
        neighbor_ids.add(r.target_node_id)
    neighbor_ids.discard(center_id)
    if allowed_nodes is not None:
        neighbor_ids &= allowed_nodes
    neighbors = db.query(GraphNode).filter(GraphNode.id.in_(neighbor_ids)).all() if neighbor_ids else []
    chunks = _source_chunks_for_nodes(db, [GraphNodeResponse.model_validate(center_sql), *[
        GraphNodeResponse.model_validate(n) for n in neighbors
    ]])

    return GraphNeighborhoodResponse(
        center_node=GraphNodeResponse.model_validate(center_sql),
        nodes=[GraphNodeResponse.model_validate(n) for n in neighbors],
        relationships=[GraphRelationshipResponse.model_validate(r) for r in rels],
        source_chunks=chunks,
        neo4j_connected=neo_connected,
        graph_source="sql",
        traversal_depth=1,
    )


def sync_graph_to_neo4j(db: Session) -> dict:
    if not settings.neo4j_enabled:
        return {"synced": False, "mode": "disabled"}
    return neo4j_client.sync_all_from_sql(db)
