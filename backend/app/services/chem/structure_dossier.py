"""Per-PDB structure dossier: title, resolution, method, ligands, Mol* assets."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.services.chem.structure_assets import build_visualization_payload

logger = logging.getLogger(__name__)

# Demo dossier matching the AIDD Agent 3UGC example when RCSB is down
DEMO_DOSSIERS: dict[str, dict[str, Any]] = {
    "3UGC": {
        "pdb_id": "3UGC",
        "title": "Structural basis of Jak2 inhibition by the type II inhibitor NVP-BBT594",
        "resolution": 1.34,
        "method": "X-RAY DIFFRACTION",
        "deposition_date": "2011-10-28",
        "release_date": "2012-04-11",
        "ligands": [
            {
                "comp_id": "046",
                "name": (
                    "5-[[6-(acetylamino)pyrimidin-4-yl]oxy]-N-{4-[(4-methylpiperazin-1-yl)"
                    "methyl]-3-(trifluoromethyl)phenyl}-2,3-dihydro-1H-indole-1-carboxamide"
                ),
                "formula_weight": None,
            },
            {"comp_id": "MLI", "name": "Malonate ion", "formula_weight": 104.06},
        ],
        "polymer_count": 1,
        "uniprot_ids": ["O60674"],
    },
}


def extract_pdb_id(query: str) -> str | None:
    m = re.search(r"\b([0-9][A-Za-z0-9]{3})\b", query or "")
    return m.group(1).upper() if m else None


def fetch_entry_core(pdb_id: str) -> dict[str, Any] | None:
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id.upper()}")
            if r.status_code >= 400:
                return None
            return r.json()
    except Exception as exc:
        logger.warning("RCSB entry fetch failed for %s: %s", pdb_id, exc)
        return None


def fetch_ligands(pdb_id: str, entry: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    entry = entry or fetch_entry_core(pdb_id)
    if not entry:
        return []
    ids = (entry.get("rcsb_entry_container_identifiers") or {}).get("non_polymer_entity_ids") or []
    ligands: list[dict[str, Any]] = []
    with httpx.Client(timeout=12.0) as client:
        for eid in ids[:12]:
            try:
                r = client.get(
                    f"https://data.rcsb.org/rest/v1/core/nonpolymer_entity/{pdb_id.upper()}/{eid}"
                )
                if r.status_code >= 400:
                    continue
                ent = r.json()
                chem = ent.get("pdbx_entity_nonpoly") or {}
                comp = (ent.get("rcsb_nonpolymer_entity") or {}).get("comp_id") or chem.get("comp_id")
                name = chem.get("name") or (ent.get("rcsb_nonpolymer_entity") or {}).get("name")
                fw = (ent.get("rcsb_nonpolymer_entity") or {}).get("formula_weight")
                if not comp:
                    continue
                # Skip water / common solvents if they sneak through as named entities
                if str(comp).upper() in {"HOH", "WAT", "DOD"}:
                    continue
                ligands.append({
                    "comp_id": str(comp).upper(),
                    "name": name or str(comp).upper(),
                    "formula_weight": fw,
                    "entity_id": eid,
                })
            except Exception as exc:
                logger.debug("Ligand fetch failed %s/%s: %s", pdb_id, eid, exc)
    return ligands


def build_structure_dossier(pdb_id: str | None, query: str | None = None) -> dict[str, Any]:
    pid = (pdb_id or extract_pdb_id(query or "") or "").upper()
    if not pid:
        return {
            "capability": "C6",
            "capability_name": "Structure Dossier",
            "summary": "No PDB ID found — name an entry such as 3UGC.",
            "narrative": "Provide a four-character PDB identifier to retrieve the structure dossier.",
            "dossier": None,
            "tools_used": ["RCSB PDB"],
            "parameters": {"query": query},
        }

    entry = fetch_entry_core(pid)
    demo = DEMO_DOSSIERS.get(pid)
    ligands: list[dict[str, Any]] = []
    if entry:
        info = entry.get("rcsb_entry_info") or {}
        res_list = info.get("resolution_combined") or []
        resolution = float(res_list[0]) if res_list else None
        methods = info.get("experimental_method") or []
        method = methods[0] if methods else None
        if not method:
            exptl = entry.get("exptl") or []
            if exptl and isinstance(exptl[0], dict):
                method = exptl[0].get("method")
        title = (entry.get("struct") or {}).get("title") or pid
        ligands = fetch_ligands(pid, entry)
        dossier = {
            "pdb_id": pid,
            "title": title,
            "resolution": resolution,
            "method": method or "Unknown",
            "deposition_date": (entry.get("rcsb_accession_info") or {}).get("deposit_date"),
            "release_date": (entry.get("rcsb_accession_info") or {}).get("initial_release_date"),
            "ligands": ligands,
            "polymer_count": info.get("polymer_entity_count"),
            "source": "rcsb",
        }
    elif demo:
        dossier = {**demo, "source": "curated"}
        ligands = demo.get("ligands") or []
    else:
        dossier = {
            "pdb_id": pid,
            "title": pid,
            "resolution": None,
            "method": None,
            "ligands": [],
            "source": "partial",
        }

    viz = build_visualization_payload(pdb_id=pid, label=pid)
    ligand_note = (
        f"{len(ligands)} ligand(s) in the binding site"
        if ligands
        else "No non-polymer ligands annotated"
    )
    summary = (
        f"{pid}: {dossier.get('title')}. "
        f"Resolution {dossier.get('resolution') or 'n/a'} Å · "
        f"{dossier.get('method') or 'method n/a'}. {ligand_note}."
    )

    return {
        "capability": "C6",
        "capability_name": "Structure Dossier",
        "summary": summary,
        "narrative": (
            f"Retrieved PDB entry {pid} with experimental metadata, co-crystal ligands, "
            "and an interactive Mol* view inside SciNova."
        ),
        "dossier": dossier,
        "ligands": ligands or dossier.get("ligands") or [],
        "default_pdb_id": pid,
        "pdb_id": pid,
        "visualization": viz,
        "tools_used": ["RCSB PDB", "Mol*"],
        "parameters": {"pdb_id": pid, "query": query},
    }
