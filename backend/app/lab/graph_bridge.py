"""Publish lab entities into the existing SQL knowledge graph."""

from __future__ import annotations

from collections import deque

from sqlalchemy.orm import Session

from app.lab.models import (
    ENTITY_MODELS,
    LabExperiment,
    LabExperimentPlan,
    LabInstrument,
    LabMeasurement,
    LabProtocol,
    LabProtocolVersion,
    LabRawDataFile,
    LabRun,
    LabSample,
)
from app.models.db_models import GraphNode, GraphRelationship, ScientificEntity


def publish(db: Session, row, *, entity_type: str, label: str, document_id: str | None, ontology_id: str | None = None, confidence: float = 1.0, extra: dict | None = None) -> GraphNode:
    props = {"lab_id": row.id, "lab_entity_type": entity_type, "data_origin": getattr(row, "data_origin", None)}
    if extra:
        props.update(extra)
    if row.graph_node_id:
        node = db.get(GraphNode, row.graph_node_id)
        if node is not None:
            node.label = label[:512]
            node.properties_json = props
            node.node_type = entity_type
            return node
    entity = ScientificEntity(
        name=label[:512],
        entity_type=entity_type,
        description=label[:512],
        ontology_id=ontology_id,
        source_document_id=document_id,
        confidence=confidence,
        metadata_json=props,
    )
    db.add(entity)
    db.flush()
    node = GraphNode(
        label=label[:512],
        node_type=entity_type,
        entity_id=entity.id,
        properties_json=props,
        evidence_json=[{"kind": "lab_fabric", "lab_id": row.id, "entity_type": entity_type}],
    )
    db.add(node)
    db.flush()
    row.graph_node_id = node.id
    return node


def link(db: Session, source: GraphNode | None, target: GraphNode | None, relationship_type: str, properties: dict | None = None) -> GraphRelationship | None:
    if source is None or target is None:
        return None
    existing = (
        db.query(GraphRelationship)
        .filter(
            GraphRelationship.source_node_id == source.id,
            GraphRelationship.target_node_id == target.id,
            GraphRelationship.relationship_type == relationship_type,
        )
        .first()
    )
    if existing:
        return existing
    rel = GraphRelationship(
        source_node_id=source.id,
        target_node_id=target.id,
        relationship_type=relationship_type,
        properties_json=properties or {},
        evidence_json=[{"kind": "lab_fabric"}],
        confidence=1.0,
    )
    db.add(rel)
    db.flush()
    return rel


def node_for(row) -> str | None:
    return getattr(row, "graph_node_id", None)


def find_entity(db: Session, entity_ref: str):
    token = entity_ref.split(":")[-1]
    hinted = entity_ref.split(":")[0] if ":" in entity_ref else None
    if hinted and hinted in ENTITY_MODELS:
        row = db.get(ENTITY_MODELS[hinted], token)
        if row is not None:
            return hinted, row
    for name, model in ENTITY_MODELS.items():
        row = db.get(model, token)
        if row is not None:
            return name, row
    return None, None


def lineage(db: Session, entity_ref: str) -> dict:
    kind, row = find_entity(db, entity_ref)
    if row is None:
        return {}
    measurement = row if kind == "measurement" else None
    if kind == "result":
        ids = row.measurement_ids_json or []
        if ids:
            measurement = db.get(LabMeasurement, ids[0])
    if measurement is None and kind == "experiment":
        measurement = (
            db.query(LabMeasurement)
            .filter(LabMeasurement.experiment_id == row.id, LabMeasurement.status == "active", LabMeasurement.sample_id.isnot(None))
            .first()
        )
    if measurement is None:
        return {"entity_ref": entity_ref, "entity_type": kind, "chain": [_brief(kind, row)], "resolvable": False}

    run = db.get(LabRun, measurement.run_id)
    instrument = db.get(LabInstrument, run.instrument_id) if run and run.instrument_id else None
    sample = db.get(LabSample, measurement.sample_id) if measurement.sample_id else None
    experiment = db.get(LabExperiment, measurement.experiment_id)
    plan = db.get(LabExperimentPlan, experiment.plan_id) if experiment else None
    version = db.get(LabProtocolVersion, plan.protocol_version_id) if plan else None
    protocol = db.get(LabProtocol, version.protocol_id) if version else None
    raw = db.get(LabRawDataFile, measurement.raw_file_id) if measurement.raw_file_id else None
    ordered = [
        ("Measurement", measurement),
        ("Run", run),
        ("Instrument", instrument),
        ("Sample", sample),
        ("Experiment", experiment),
        ("ExperimentPlan", plan),
        ("ProtocolVersion", version),
        ("Protocol", protocol),
    ]
    chain = [_brief(name, item) for name, item in ordered]
    resolvable = all(item is not None for _, item in ordered)
    return {
        "entity_ref": measurement.id,
        "entity_type": "measurement",
        "resolvable": resolvable,
        "chain": chain,
        "raw_data_file": _brief("RawDataFile", raw) if raw else None,
        "graph_node_ids": [item.graph_node_id for _, item in ordered if item is not None and item.graph_node_id],
        "checksum": raw.sha256 if raw else None,
    }


def _brief(entity_type: str, row) -> dict | None:
    if row is None:
        return None
    payload = {"entity_type": entity_type, "id": row.id, "graph_node_id": getattr(row, "graph_node_id", None)}
    for attr in ("sample_code", "run_code", "serial_number", "title", "code", "version_label", "readout_key", "sha256", "filename"):
        if hasattr(row, attr):
            payload[attr] = getattr(row, attr)
    return payload


def query_relationships(db: Session, start_id: str, relationship: str | None = None, depth: int = 2) -> dict:
    kind, row = find_entity(db, start_id)
    if row is None or not getattr(row, "graph_node_id", None):
        return {"nodes": [], "relationships": [], "start": start_id}
    seen = {row.graph_node_id}
    found_rels = []
    queue = deque([(row.graph_node_id, 0)])
    while queue:
        node_id, dist = queue.popleft()
        if dist >= depth:
            continue
        rels = (
            db.query(GraphRelationship)
            .filter((GraphRelationship.source_node_id == node_id) | (GraphRelationship.target_node_id == node_id))
            .all()
        )
        for rel in rels:
            if relationship and rel.relationship_type != relationship:
                continue
            found_rels.append(rel)
            other = rel.target_node_id if rel.source_node_id == node_id else rel.source_node_id
            if other not in seen:
                seen.add(other)
                queue.append((other, dist + 1))
    nodes = db.query(GraphNode).filter(GraphNode.id.in_(seen)).all() if seen else []
    unique_rels = {rel.id: rel for rel in found_rels}
    return {
        "start": {"entity_type": kind, "id": row.id, "graph_node_id": row.graph_node_id},
        "nodes": [
            {"id": node.id, "label": node.label, "node_type": node.node_type, "properties": node.properties_json}
            for node in nodes
        ],
        "relationships": [
            {
                "id": rel.id,
                "source_node_id": rel.source_node_id,
                "target_node_id": rel.target_node_id,
                "relationship_type": rel.relationship_type,
            }
            for rel in unique_rels.values()
        ],
    }
