"""Enriched PDB catalog: resolution, ligands, filtered counts for a UniProt target."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Curated high-resolution JAK2 entries used when RCSB is unreachable
DEMO_STRUCTURES: dict[str, list[dict[str, Any]]] = {
    "O60674": [
        {"pdb_id": "8BXH", "resolution": 1.30, "method": "X-RAY DIFFRACTION", "has_ligand": True, "title": "JAK2 JH1 complex"},
        {"pdb_id": "7LL4", "resolution": 1.31, "method": "X-RAY DIFFRACTION", "has_ligand": True, "title": "JAK2 kinase domain"},
        {"pdb_id": "3UGC", "resolution": 1.34, "method": "X-RAY DIFFRACTION", "has_ligand": True, "title": "Structural basis of Jak2 inhibition by NVP-BBT594"},
        {"pdb_id": "7REE", "resolution": 1.38, "method": "X-RAY DIFFRACTION", "has_ligand": True, "title": "JAK2 with type I inhibitor"},
        {"pdb_id": "8BA3", "resolution": 1.40, "method": "X-RAY DIFFRACTION", "has_ligand": True, "title": "JAK2 JH1"},
        {"pdb_id": "8BX9", "resolution": 1.40, "method": "X-RAY DIFFRACTION", "has_ligand": True, "title": "JAK2 inhibitor complex"},
        {"pdb_id": "7TEU", "resolution": 1.45, "method": "X-RAY DIFFRACTION", "has_ligand": True, "title": "JAK2 kinase"},
        {"pdb_id": "4IVA", "resolution": 1.50, "method": "X-RAY DIFFRACTION", "has_ligand": True, "title": "JAK2 JH1 domain"},
        {"pdb_id": "5UT3", "resolution": 1.50, "method": "X-RAY DIFFRACTION", "has_ligand": True, "title": "JAK2 with ligand"},
        {"pdb_id": "7LL5", "resolution": 1.50, "method": "X-RAY DIFFRACTION", "has_ligand": True, "title": "JAK2 kinase domain"},
    ],
}


def _rcsb_search(body: dict) -> dict[str, Any]:
    url = "https://search.rcsb.org/rcsbsearch/v2/query"
    with httpx.Client(timeout=20.0) as client:
        r = client.post(url, json=body)
        if r.status_code >= 400:
            return {}
        return r.json() or {}


def count_structures(
    uniprot_id: str,
    *,
    max_resolution: float | None = 2.5,
    require_ligand: bool = True,
) -> int:
    """Count PDB entries for a UniProt ID with optional resolution / ligand filters."""
    nodes: list[dict] = [
        {
            "type": "terminal",
            "service": "text",
            "parameters": {
                "attribute": "rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_accession",
                "operator": "exact_match",
                "value": uniprot_id,
            },
        }
    ]
    if max_resolution is not None:
        nodes.append({
            "type": "terminal",
            "service": "text",
            "parameters": {
                "attribute": "rcsb_entry_info.resolution_combined",
                "operator": "less_or_equal",
                "value": max_resolution,
            },
        })
    if require_ligand:
        nodes.append({
            "type": "terminal",
            "service": "text",
            "parameters": {
                "attribute": "rcsb_entry_info.nonpolymer_entity_count",
                "operator": "greater",
                "value": 0,
            },
        })
    body = {
        "query": {"type": "group", "logical_operator": "and", "nodes": nodes},
        "return_type": "entry",
        "request_options": {
            "paginate": {"start": 0, "rows": 0},
            "return_counts": True,
        },
    }
    try:
        data = _rcsb_search(body)
        total = data.get("total_count")
        if total is not None:
            return int(total)
    except Exception as exc:
        logger.warning("RCSB count failed for %s: %s", uniprot_id, exc)
    demo = DEMO_STRUCTURES.get(uniprot_id) or []
    return len(demo)


def fetch_structure_catalog(
    uniprot_id: str,
    *,
    limit: int = 10,
    max_resolution: float | None = 2.5,
    require_ligand: bool = True,
) -> dict[str, Any]:
    """
    Return filtered PDB structures sorted by resolution (best first),
    plus total matching count.
    """
    total = count_structures(
        uniprot_id, max_resolution=max_resolution, require_ligand=require_ligand
    )
    nodes: list[dict] = [
        {
            "type": "terminal",
            "service": "text",
            "parameters": {
                "attribute": "rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_accession",
                "operator": "exact_match",
                "value": uniprot_id,
            },
        }
    ]
    if max_resolution is not None:
        nodes.append({
            "type": "terminal",
            "service": "text",
            "parameters": {
                "attribute": "rcsb_entry_info.resolution_combined",
                "operator": "less_or_equal",
                "value": max_resolution,
            },
        })
    if require_ligand:
        nodes.append({
            "type": "terminal",
            "service": "text",
            "parameters": {
                "attribute": "rcsb_entry_info.nonpolymer_entity_count",
                "operator": "greater",
                "value": 0,
            },
        })

    body = {
        "query": {"type": "group", "logical_operator": "and", "nodes": nodes},
        "return_type": "entry",
        "request_options": {
            "paginate": {"start": 0, "rows": limit},
            "sort": [{
                "sort_by": "rcsb_entry_info.resolution_combined",
                "direction": "asc",
            }],
        },
    }

    ids: list[str] = []
    try:
        data = _rcsb_search(body)
        ids = [hit["identifier"] for hit in data.get("result_set") or []]
        if data.get("total_count") is not None:
            total = int(data["total_count"])
    except Exception as exc:
        logger.warning("RCSB catalog search failed for %s: %s", uniprot_id, exc)

    structures: list[dict[str, Any]] = []
    if ids:
        structures = enrich_entries(ids)
    if not structures:
        demo = list(DEMO_STRUCTURES.get(uniprot_id) or [])
        structures = [
            {
                **row,
                "label": row["pdb_id"],
                "mmcif_url": f"https://files.rcsb.org/download/{row['pdb_id']}.cif",
                "rcsb_url": f"https://www.rcsb.org/structure/{row['pdb_id']}",
                "source": "curated",
            }
            for row in demo[:limit]
        ]
        total = max(total, len(demo))

    return {
        "structures": structures,
        "total_count": total or len(structures),
        "filters": {
            "max_resolution_A": max_resolution,
            "require_co_crystal_ligand": require_ligand,
        },
        "source": "rcsb" if ids else "curated",
    }


def enrich_entries(pdb_ids: list[str]) -> list[dict[str, Any]]:
    """Pull resolution / title / method for a list of PDB IDs."""
    out: list[dict[str, Any]] = []
    with httpx.Client(timeout=12.0) as client:
        for pid in pdb_ids:
            try:
                r = client.get(f"https://data.rcsb.org/rest/v1/core/entry/{pid}")
                if r.status_code >= 400:
                    out.append(_bare(pid))
                    continue
                entry = r.json()
                info = entry.get("rcsb_entry_info") or {}
                res_list = info.get("resolution_combined") or []
                resolution = float(res_list[0]) if res_list else None
                methods = info.get("experimental_method") or entry.get("exptl") or []
                if isinstance(methods, list) and methods and isinstance(methods[0], dict):
                    method = methods[0].get("method")
                elif isinstance(methods, list) and methods:
                    method = methods[0]
                else:
                    method = None
                title = (entry.get("struct") or {}).get("title") or pid
                ligand_count = int(info.get("nonpolymer_entity_count") or 0)
                out.append({
                    "pdb_id": pid.upper(),
                    "label": pid.upper(),
                    "title": title,
                    "resolution": resolution,
                    "method": method,
                    "has_ligand": ligand_count > 0,
                    "ligand_entity_count": ligand_count,
                    "mmcif_url": f"https://files.rcsb.org/download/{pid.upper()}.cif",
                    "rcsb_url": f"https://www.rcsb.org/structure/{pid.upper()}",
                    "source": "rcsb",
                })
            except Exception as exc:
                logger.debug("Entry enrich failed for %s: %s", pid, exc)
                out.append(_bare(pid))
    return out


def _bare(pid: str) -> dict[str, Any]:
    return {
        "pdb_id": pid.upper(),
        "label": pid.upper(),
        "title": pid.upper(),
        "resolution": None,
        "method": None,
        "has_ligand": None,
        "mmcif_url": f"https://files.rcsb.org/download/{pid.upper()}.cif",
        "rcsb_url": f"https://www.rcsb.org/structure/{pid.upper()}",
        "source": "partial",
    }
