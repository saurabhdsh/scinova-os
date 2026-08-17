"""Binding-pocket / druggability analysis for a PDB entry (MVP + curated fallbacks)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.chem.structure_assets import build_visualization_payload
from app.services.chem.structure_dossier import extract_pdb_id, fetch_entry_core, fetch_ligands

logger = logging.getLogger(__name__)

# Curated pocket results aligned with the AIDD Agent 3UGC example
DEMO_POCKETS: dict[str, dict[str, Any]] = {
    "3UGC": {
        "pdb_id": "3UGC",
        "pockets": [
            {
                "pocket_id": "P_0",
                "label": "Primary ATP / type-II inhibitor site",
                "druggability_score": 0.88,
                "volume_A3": 620,
                "surface_A2": 980,
                "hydrophobicity": 0.62,
                "residues": ["Leu855", "Met929", "Glu930", "Leu932", "Asp994"],
                "note": (
                    "Consistent with the co-crystallized type II inhibitor NVP-BBT594 "
                    "(ligand 046) in 3UGC."
                ),
            },
            {
                "pocket_id": "P_1",
                "label": "Secondary shallow site",
                "druggability_score": 0.41,
                "volume_A3": 210,
                "surface_A2": 340,
                "hydrophobicity": 0.38,
                "residues": [],
                "note": "Lower priority cavity; typically not pursued for JAK2 JH1.",
            },
        ],
        "top_pocket_id": "P_0",
    },
}


def _score_from_ligand_context(ligands: list[dict], resolution: float | None) -> float:
    """Heuristic druggability when a real pocket detector is unavailable."""
    score = 0.45
    druglike = [lg for lg in ligands if lg.get("comp_id") not in {"MLI", "SO4", "GOL", "EDO", "PEG", "DMS", "ACT"}]
    if druglike:
        score += 0.28
    if resolution is not None:
        if resolution <= 1.5:
            score += 0.12
        elif resolution <= 2.5:
            score += 0.06
    return round(min(0.95, score), 2)


def analyze_pockets(pdb_id: str | None, query: str | None = None) -> dict[str, Any]:
    pid = (pdb_id or extract_pdb_id(query or "") or "").upper()
    if not pid:
        return {
            "capability": "C6P",
            "capability_name": "Pocket / Druggability",
            "summary": "Name a PDB entry (e.g. 3UGC) to run pocket / druggability analysis.",
            "narrative": "Pocket analysis requires a structure identifier.",
            "pockets": [],
            "tools_used": ["RCSB PDB"],
            "parameters": {"query": query},
        }

    demo = DEMO_POCKETS.get(pid)
    entry = fetch_entry_core(pid)
    ligands = fetch_ligands(pid, entry) if entry else (demo.get("ligands") if demo else [])
    if entry:
        info = entry.get("rcsb_entry_info") or {}
        res_list = info.get("resolution_combined") or []
        resolution = float(res_list[0]) if res_list else None
        title = (entry.get("struct") or {}).get("title") or pid
    else:
        resolution = None
        title = pid

    if demo:
        pockets = list(demo["pockets"])
        top_id = demo["top_pocket_id"]
        source = "curated" if not entry else "hybrid"
    else:
        score = _score_from_ligand_context(ligands or [], resolution)
        pockets = [
            {
                "pocket_id": "P_0",
                "label": "Primary ligand-associated site",
                "druggability_score": score,
                "volume_A3": None,
                "surface_A2": None,
                "hydrophobicity": None,
                "residues": [],
                "note": (
                    "Heuristic score from co-crystal ligand presence and resolution. "
                    "A full geometric pocket detector (fpocket / SiteMap) can replace this MVP."
                ),
            }
        ]
        top_id = "P_0"
        source = "heuristic"

    top = next((p for p in pockets if p["pocket_id"] == top_id), pockets[0] if pockets else None)
    score = top["druggability_score"] if top else None
    label = (
        "highly druggable" if (score or 0) >= 0.75
        else "moderately druggable" if (score or 0) >= 0.5
        else "challenging"
    )
    summary = (
        f"{pid} ({title[:80]}{'…' if len(title) > 80 else ''}): "
        f"top pocket {top_id} scores {score} — {label}."
    )
    if top and top.get("note"):
        summary += f" {top['note']}"

    viz = build_visualization_payload(pdb_id=pid, label=f"{pid} pocket")

    return {
        "capability": "C6P",
        "capability_name": "Pocket / Druggability",
        "summary": summary,
        "narrative": (
            f"Druggability analysis for {pid} identified {len(pockets)} candidate binding site(s). "
            f"Top site {top_id} is {label} (score {score})."
        ),
        "pdb_id": pid,
        "default_pdb_id": pid,
        "title": title,
        "resolution": resolution,
        "ligands": ligands or [],
        "pockets": pockets,
        "top_pocket": top,
        "source": source,
        "visualization": viz,
        "tools_used": ["RCSB PDB", "Pocket Heuristics", "Mol*"],
        "parameters": {"pdb_id": pid, "query": query},
        "method_note": (
            "MVP: curated pocket map for known demo entries; otherwise ligand+resolution heuristic. "
            "Geometric descriptors (volume, surface, hydrophobicity) shown when curated."
        ),
    }
