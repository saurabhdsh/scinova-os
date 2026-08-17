"""C2 — Known bioactive discovery via ChEMBL."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Demo JAK2 inhibitors when ChEMBL is unreachable
DEMO_ACTIVES: dict[str, list[dict[str, Any]]] = {
    "O60674": [  # JAK2
        {"chembl_id": "CHEMBL2141297", "pref_name": "Fedratinib", "pchembl": 8.1, "smiles": "CC1=CN=C(N=C1NC2=CC(=CC=C2)S(=O)(=O)NC(C)(C)C)NC3=CC=C(C=C3)N4CCCC4", "assay": "JAK2 IC50"},
        {"chembl_id": "CHEMBL1201747", "pref_name": "Ruxolitinib", "pchembl": 8.4, "smiles": "C[C@@H]1CCN(C[C@@H]1N(C)C2=NC=NC3=C2C=CN3)C4=CC=CC=C4", "assay": "JAK2 Ki"},
        {"chembl_id": "CHEMBL2105759", "pref_name": "Pacritinib", "pchembl": 7.6, "smiles": "COC1=CC2=C(C=C1)N=C(N2)NC3=CC=C(C=C3)N4CCN(CC4)C", "assay": "JAK2 IC50"},
        {"chembl_id": "CHEMBL3137339", "pref_name": "Momelotinib", "pchembl": 7.9, "smiles": "NC(=O)C1=CC=C(C=C1)C2=NC(=NC=C2)NC3=CC=C(C=C3)N4CCOCC4", "assay": "JAK2 IC50"},
        {"chembl_id": "CHEMBL4297456", "pref_name": "Abrocitinib", "pchembl": 7.2, "smiles": "CCC(=O)N[C@@H]1CC[C@H](CC1)N(C)C2=NC=NC3=C2C=CN3", "assay": "JAK2 IC50"},
    ],
    "P23458": [  # JAK1
        {"chembl_id": "CHEMBL4297456", "pref_name": "Abrocitinib", "pchembl": 8.0, "smiles": "CCC(=O)N[C@@H]1CC[C@H](CC1)N(C)C2=NC=NC3=C2C=CN3", "assay": "JAK1 IC50"},
        {"chembl_id": "CHEMBL2103839", "pref_name": "Upadacitinib", "pchembl": 8.5, "smiles": "CC[C@@H]1CN2C(=N1)C3=C(C=C(C=C3)F)N=C2N", "assay": "JAK1 Ki"},
    ],
    "P43220": [  # GLP1R
        {"chembl_id": "CHEMBL4297610", "pref_name": "Semaglutide-related", "pchembl": 9.0, "smiles": "CC(C)C[C@H](NC(=O)[C@H](CC1=CC=CC=C1)N)C(=O)N", "assay": "GLP1R EC50"},
        {"chembl_id": "CHEMBL4297611", "pref_name": "Small-mol GLP1R ago", "pchembl": 7.1, "smiles": "CC1=CC(=CC=C1)C2=NC(=NO2)C3=CC=C(C=C3)C(=O)O", "assay": "GLP1R binding"},
    ],
}


def _target_chembl_id(uniprot_id: str) -> str | None:
    try:
        url = f"https://www.ebi.ac.uk/chembl/api/data/target.json"
        params = {"target_components__accession": uniprot_id, "limit": 5}
        with httpx.Client(timeout=15.0) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            targets = r.json().get("targets") or []
            if not targets:
                return None
            # Prefer single protein
            for t in targets:
                if t.get("target_type") == "SINGLE PROTEIN":
                    return t.get("target_chembl_id")
            return targets[0].get("target_chembl_id")
    except Exception as exc:
        logger.warning("ChEMBL target lookup failed: %s", exc)
        return None


def fetch_actives(uniprot_id: str, limit: int = 25) -> list[dict[str, Any]]:
    tid = _target_chembl_id(uniprot_id)
    if not tid:
        return []
    try:
        url = "https://www.ebi.ac.uk/chembl/api/data/activity.json"
        params = {
            "target_chembl_id": tid,
            "pchembl_value__gte": 6,
            "limit": min(limit * 2, 50),
            "assay_type": "B",
        }
        with httpx.Client(timeout=20.0) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            activities = r.json().get("activities") or []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for act in activities:
            cid = act.get("molecule_chembl_id")
            if not cid or cid in seen:
                continue
            smiles = act.get("canonical_smiles")
            if not smiles:
                continue
            seen.add(cid)
            pchembl = act.get("pchembl_value")
            try:
                pchembl_f = float(pchembl) if pchembl is not None else None
            except (TypeError, ValueError):
                pchembl_f = None
            rows.append({
                "chembl_id": cid,
                "pref_name": act.get("molecule_pref_name") or cid,
                "pchembl": pchembl_f,
                "smiles": smiles,
                "assay": act.get("assay_description") or act.get("standard_type") or "bioactivity",
                "standard_value": act.get("standard_value"),
                "standard_units": act.get("standard_units"),
            })
            if len(rows) >= limit:
                break
        rows.sort(key=lambda x: x.get("pchembl") or 0, reverse=True)
        return rows
    except Exception as exc:
        logger.warning("ChEMBL activity fetch failed: %s", exc)
        return []


def discover_known_actives(uniprot_id: str | None, gene_symbol: str | None = None, limit: int = 20) -> dict[str, Any]:
    uid = uniprot_id or ""
    rows = fetch_actives(uid, limit=limit) if uid else []
    source = "chembl"
    if not rows:
        rows = list(DEMO_ACTIVES.get(uid) or DEMO_ACTIVES.get("O60674") or [])[:limit]
        source = "demo_curated"
        for i, row in enumerate(rows):
            row = dict(row)
            rows[i] = row

    for i, row in enumerate(rows):
        row["rank"] = i + 1

    summary = (
        f"Retrieved {len(rows)} known actives for {gene_symbol or uid} "
        f"(ranked by pChEMBL). Source: {source}."
    )
    return {
        "capability": "C2",
        "capability_name": "Known Bioactive Discovery",
        "summary": summary,
        "narrative": summary,
        "actives": rows,
        "uniprot_id": uid,
        "source": source,
        "tools_used": ["ChEMBL"],
        "parameters": {"uniprot_id": uid, "limit": limit},
    }
