"""Neo4j graph database client with graceful fallback."""

import logging
import re

from app.config import settings

logger = logging.getLogger(__name__)


def _safe_label(label: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", label.replace(" ", "_"))
    return cleaned or "Entity"


class Neo4jClient:
    def __init__(self):
        self._driver = None
        self._connected = False
        self._error: str | None = None
        self._connect_attempted = False

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self) -> bool:
        if self._driver is not None:
            return self._connected
        if self._connect_attempted and not self._connected:
            return False
        self._connect_attempted = True
        try:
            from neo4j import GraphDatabase

            self._driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
            self._driver.verify_connectivity()
            self._ensure_constraints()
            self._connected = True
            self._error = None
            logger.info("Neo4j connected at %s", settings.neo4j_uri)
            return True
        except Exception as e:
            self._connected = False
            self._error = str(e)
            self._driver = None
            logger.warning("Neo4j unavailable (%s); graph sync will be skipped", e)
            return False

    def _ensure_constraints(self):
        with self._driver.session() as session:
            session.run(
                "CREATE CONSTRAINT scinova_node_id IF NOT EXISTS "
                "FOR (n:SciNovaEntity) REQUIRE n.sql_id IS UNIQUE"
            )

    def stats(self) -> dict:
        if not self.connect():
            return {"connected": False, "nodes": 0, "relationships": 0, "error": self._error}
        with self._driver.session() as session:
            nodes = session.run("MATCH (n:SciNovaEntity) RETURN count(n) AS c").single()["c"]
            rels = session.run("MATCH ()-[r:SCINOVA_REL]->() RETURN count(r) AS c").single()["c"]
            return {"connected": True, "nodes": nodes, "relationships": rels, "error": None}

    def upsert_node(self, node: dict) -> bool:
        if not self.connect():
            return False
        label = _safe_label(node["node_type"])
        query = f"""
        MERGE (n:SciNovaEntity {{sql_id: $sql_id}})
        SET n:{label}
        SET n.label = $label,
            n.node_type = $node_type,
            n.entity_id = $entity_id,
            n.document_id = $document_id,
            n.confidence = $confidence,
            n.updated_at = datetime()
        """
        with self._driver.session() as session:
            session.run(
                query,
                sql_id=node["id"],
                label=node["label"],
                node_type=node["node_type"],
                entity_id=node.get("entity_id"),
                document_id=node.get("document_id"),
                confidence=node.get("confidence", 0.8),
            )
        return True

    def upsert_relationship(self, rel: dict, source_label: str, target_label: str) -> bool:
        if not self.connect():
            return False
        rel_type = _safe_label(rel["relationship_type"]).upper()
        query = f"""
        MATCH (a:SciNovaEntity {{sql_id: $source_id}})
        MATCH (b:SciNovaEntity {{sql_id: $target_id}})
        MERGE (a)-[r:SCINOVA_REL {{sql_id: $sql_id}}]->(b)
        SET r.type = $rel_type,
            r.raw_type = $raw_type,
            r.confidence = $confidence,
            r.document_id = $document_id
        """
        with self._driver.session() as session:
            session.run(
                query,
                source_id=rel["source_node_id"],
                target_id=rel["target_node_id"],
                sql_id=rel["id"],
                rel_type=rel_type,
                raw_type=rel["relationship_type"],
                confidence=rel.get("confidence", 0.8),
                document_id=rel.get("document_id"),
            )
        return True

    def sync_document_graph(self, nodes: list[dict], relationships: list[dict]) -> dict:
        if not self.connect():
            return {"synced": False, "nodes": 0, "relationships": 0, "mode": "unavailable"}
        synced_nodes = 0
        synced_rels = 0
        for n in nodes:
            if self.upsert_node(n):
                synced_nodes += 1
        for r in relationships:
            if self.upsert_relationship(r, "", ""):
                synced_rels += 1
        return {"synced": True, "nodes": synced_nodes, "relationships": synced_rels, "mode": "neo4j"}

    def search_graph(
        self,
        q: str = "",
        entity_type: str | None = None,
        document_id: str | None = None,
        limit: int = 80,
    ) -> dict | None:
        """Return {nodes, relationships} from Neo4j or None if unavailable."""
        if not self.connect():
            return None

        cypher = """
        MATCH (n:SciNovaEntity)
        WHERE ($q = '' OR toLower(n.label) CONTAINS toLower($q))
          AND ($entity_type IS NULL OR n.node_type = $entity_type)
          AND ($document_id IS NULL OR n.document_id = $document_id)
        RETURN n.sql_id AS id, n.label AS label, n.node_type AS node_type,
               n.entity_id AS entity_id, n.confidence AS confidence,
               n.document_id AS document_id
        ORDER BY n.label
        LIMIT $limit
        """
        with self._driver.session() as session:
            rows = session.run(
                cypher,
                q=q or "",
                entity_type=entity_type,
                document_id=document_id,
                limit=limit,
            ).data()

        if not rows:
            return {"nodes": [], "relationships": []}

        node_ids = [r["id"] for r in rows if r.get("id")]
        nodes = [
            {
                "id": r["id"],
                "label": r.get("label") or "Unknown",
                "node_type": r.get("node_type") or "Entity",
                "entity_id": r.get("entity_id"),
                "properties_json": {"confidence": r.get("confidence", 0.8)},
                "evidence_json": [],
                "document_id": r.get("document_id"),
            }
            for r in rows
            if r.get("id")
        ]

        rel_cypher = """
        MATCH (a:SciNovaEntity)-[r:SCINOVA_REL]->(b:SciNovaEntity)
        WHERE a.sql_id IN $node_ids AND b.sql_id IN $node_ids
        RETURN r.sql_id AS id, a.sql_id AS source_node_id, b.sql_id AS target_node_id,
               coalesce(r.raw_type, r.type, 'ASSOCIATED_WITH') AS relationship_type,
               coalesce(r.confidence, 0.8) AS confidence
        LIMIT 200
        """
        with self._driver.session() as session:
            rel_rows = session.run(rel_cypher, node_ids=node_ids).data()

        relationships = [
            {
                "id": r["id"] or f"{r['source_node_id']}-{r['target_node_id']}",
                "source_node_id": r["source_node_id"],
                "target_node_id": r["target_node_id"],
                "relationship_type": (r.get("relationship_type") or "ASSOCIATED_WITH").replace(" ", "_"),
                "properties_json": {},
                "evidence_json": [],
                "confidence": float(r.get("confidence") or 0.8),
            }
            for r in rel_rows
            if r.get("source_node_id") and r.get("target_node_id")
        ]
        return {"nodes": nodes, "relationships": relationships}

    def get_neighborhood(self, node_id: str, depth: int = 2) -> dict | None:
        """Multi-hop neighborhood from Neo4j."""
        if not self.connect():
            return None

        depth = max(1, min(depth, 2))
        cypher = f"""
        MATCH (center:SciNovaEntity {{sql_id: $node_id}})
        OPTIONAL MATCH (center)-[:SCINOVA_REL*1..{depth}]-(n:SciNovaEntity)
        WHERE n IS NULL OR n <> center
        WITH center, collect(DISTINCT n) AS neighbors
        RETURN center, neighbors
        """
        with self._driver.session() as session:
            record = session.run(cypher, node_id=node_id).single()
            if not record or not record.get("center"):
                return None
            center = record["center"]
            neighbors = [n for n in (record.get("neighbors") or []) if n is not None]

        center_node = {
            "id": center["sql_id"],
            "label": center.get("label") or "Unknown",
            "node_type": center.get("node_type") or "Entity",
            "entity_id": center.get("entity_id"),
            "properties_json": {"confidence": center.get("confidence", 0.8)},
            "evidence_json": [],
        }

        neighbor_nodes = []
        seen_ids = {center_node["id"]}
        for n in neighbors:
            nid = n.get("sql_id")
            if not nid or nid in seen_ids:
                continue
            seen_ids.add(nid)
            neighbor_nodes.append({
                "id": nid,
                "label": n.get("label") or "Unknown",
                "node_type": n.get("node_type") or "Entity",
                "entity_id": n.get("entity_id"),
                "properties_json": {"confidence": n.get("confidence", 0.8)},
                "evidence_json": [],
            })

        all_node_ids = list(seen_ids)
        rel_cypher = """
        MATCH (a:SciNovaEntity)-[r:SCINOVA_REL]->(b:SciNovaEntity)
        WHERE a.sql_id IN $node_ids AND b.sql_id IN $node_ids
        RETURN r.sql_id AS id, a.sql_id AS source_node_id, b.sql_id AS target_node_id,
               coalesce(r.raw_type, r.type, 'ASSOCIATED_WITH') AS relationship_type,
               coalesce(r.confidence, 0.8) AS confidence
        """
        with self._driver.session() as session:
            rel_rows = session.run(rel_cypher, node_ids=all_node_ids).data()

        relationships = [
            {
                "id": r["id"] or f"{r['source_node_id']}-{r['target_node_id']}",
                "source_node_id": r["source_node_id"],
                "target_node_id": r["target_node_id"],
                "relationship_type": (r.get("relationship_type") or "ASSOCIATED_WITH").replace(" ", "_"),
                "properties_json": {},
                "evidence_json": [],
                "confidence": float(r.get("confidence") or 0.8),
            }
            for r in rel_rows
        ]

        return {
            "center_node": center_node,
            "nodes": neighbor_nodes,
            "relationships": relationships,
        }

    def sync_all_from_sql(self, db) -> dict:
        """Bulk sync all SQL graph nodes/relationships into Neo4j."""
        from app.models.db_models import GraphNode, GraphRelationship, ScientificEntity

        if not self.connect():
            return {"synced": False, "nodes": 0, "relationships": 0, "error": self._error}

        nodes = db.query(GraphNode).all()
        rels = db.query(GraphRelationship).all()
        entity_map = {
            e.id: e for e in db.query(ScientificEntity).filter(
                ScientificEntity.id.in_([n.entity_id for n in nodes if n.entity_id])
            ).all()
        }

        neo4j_nodes = []
        for n in nodes:
            ent = entity_map.get(n.entity_id)
            doc_id = None
            if ent and ent.source_document_id:
                doc_id = ent.source_document_id
            elif n.evidence_json:
                doc_id = (n.evidence_json[0] or {}).get("document_id")
            neo4j_nodes.append({
                "id": n.id,
                "label": n.label,
                "node_type": n.node_type,
                "entity_id": n.entity_id,
                "document_id": doc_id,
                "confidence": ent.confidence if ent else n.properties_json.get("confidence", 0.8),
            })

        neo4j_rels = []
        for r in rels:
            doc_id = None
            if r.evidence_json:
                doc_id = (r.evidence_json[0] or {}).get("document_id")
            neo4j_rels.append({
                "id": r.id,
                "source_node_id": r.source_node_id,
                "target_node_id": r.target_node_id,
                "relationship_type": r.relationship_type,
                "confidence": r.confidence,
                "document_id": doc_id,
            })

        return self.sync_document_graph(neo4j_nodes, neo4j_rels)


neo4j_client = Neo4jClient()
