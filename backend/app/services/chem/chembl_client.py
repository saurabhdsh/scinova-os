"""C2 — Known bioactive discovery via ChEMBL."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# TEMP DEMO: delete these files and _snapshot_rows after the demo.
_SNAPSHOTS = {
    "P43220": Path(__file__).with_name("glp1r_chembl_snapshot.json"),
    "P00533": Path(__file__).with_name("egfr_chembl_snapshot.json"),
}
_SNAPSHOT_GENES = {"GLP1R": "P43220", "EGFR": "P00533"}

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


def _row_from_activity(act: dict[str, Any], *, target_chembl_id: str) -> dict[str, Any] | None:
    cid = act.get("molecule_chembl_id")
    smiles = act.get("canonical_smiles")
    if not cid or not smiles:
        return None
    pchembl = act.get("pchembl_value")
    try:
        pchembl_f = float(pchembl) if pchembl is not None else None
    except (TypeError, ValueError):
        pchembl_f = None
    assay_type = act.get("assay_type")
    standard_type = act.get("standard_type")
    description = act.get("assay_description") or ""
    return {
        "chembl_id": cid,
        "activity_id": act.get("activity_id"),
        "target_chembl_id": target_chembl_id,
        "pref_name": act.get("molecule_pref_name") or cid,
        "pchembl": pchembl_f,
        "smiles": smiles,
        "assay": description or standard_type or "bioactivity",
        "assay_type": assay_type,
        "standard_type": standard_type,
        "standard_relation": act.get("standard_relation"),
        "standard_value": act.get("standard_value"),
        "standard_units": act.get("standard_units"),
        "target_organism": act.get("target_organism"),
        "modality": _infer_modality(description, standard_type),
    }


def _infer_modality(description: str, standard_type: str | None) -> str | None:
    text = f"{description} {standard_type or ''}".lower()
    if "agonist" in text and "antagonist" not in text:
        return "agonist"
    if "antagonist" in text:
        return "antagonist"
    if "inhibitor" in text or (standard_type or "").upper() in {"IC50", "KI", "KD"}:
        return None
    return None


_CELLULAR = re.compile(r"\b(cells?|cellular)\b", re.I)
_PATHWAY_READOUT = re.compile(
    r"erk|phosphorylation|proliferation|celltiter|viability|reporter",
    re.I,
)
_PURINE = None


def activity_relation(row: dict[str, Any]) -> str:
    """Separate a direct measurement from a probe, a peptide, or a cell-pathway readout."""
    smiles = row.get("smiles") or ""
    if _is_nucleotide(smiles):
        return "nucleotide probe"
    try:
        from app.services.chem.novelty import _is_peptide

        if _is_peptide(smiles):
            return "peptide"
    except Exception:
        pass
    assay = f"{row.get('assay') or ''} {row.get('standard_type') or ''}"
    if _CELLULAR.search(assay) and _PATHWAY_READOUT.search(assay):
        return "cellular pathway readout"
    return "biochemical"


def _is_nucleotide(smiles: str) -> bool:
    """A nucleobase plus a phosphate is a nucleotide probe, not a designed ligand."""
    try:
        from rdkit import Chem

        mol = Chem.MolFromSmiles(smiles or "")
        if mol is None or not any(atom.GetAtomicNum() == 15 for atom in mol.GetAtoms()):
            return False
        global _PURINE
        if _PURINE is None:
            _PURINE = Chem.MolFromSmarts("[#7]1:[#6]:[#7]:[#6]2:[#7]:[#6]:[#7]:[#6]:[#6]:1:2")
        return bool(_PURINE is not None and mol.HasSubstructMatch(_PURINE))
    except Exception:
        return False


def _matches_modality(row: dict[str, Any], modality: str | None) -> bool:
    if not modality:
        return True
    text = f"{row.get('assay') or ''} {row.get('standard_type') or ''}".lower()
    label = row.get("modality")
    if modality == "agonist":
        return label == "agonist" or ("agonist" in text and "antagonist" not in text)
    if modality == "antagonist":
        return label == "antagonist" or "antagonist" in text
    if modality == "inhibitor":
        return "antagonist" in text or "inhibitor" in text or (row.get("standard_type") or "").upper() in {"IC50", "KI"}
    return True


def fetch_actives_status(
    uniprot_id: str,
    limit: int = 25,
    *,
    modality: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Return activities and a status: ok, empty, no_target, or unavailable."""
    tid = _target_chembl_id(uniprot_id)
    if not tid:
        return [], "no_target"
    assay_types = ("F", "B") if modality == "agonist" else ("B", "F")
    try:
        activities: list[dict[str, Any]] = []
        with httpx.Client(timeout=20.0) as client:
            for assay_type in assay_types:
                params = {
                    "target_chembl_id": tid,
                    "pchembl_value__gte": 6,
                    "limit": min(limit * 2, 50),
                    "assay_type": assay_type,
                }
                response = client.get("https://www.ebi.ac.uk/chembl/api/data/activity.json", params=params)
                response.raise_for_status()
                activities.extend(response.json().get("activities") or [])
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for act in activities:
            parsed = _row_from_activity(act, target_chembl_id=tid)
            if not parsed or parsed["chembl_id"] in seen:
                continue
            seen.add(parsed["chembl_id"])
            parsed["relation"] = activity_relation(parsed)
            rows.append(parsed)
        matched = [row for row in rows if _matches_modality(row, modality)] if modality else rows
        if modality and matched:
            chosen = matched
        elif modality:
            functional = [row for row in rows if row.get("assay_type") == "F"]
            chosen = functional or rows
            for row in chosen:
                row["modality_supported"] = False
        else:
            chosen = rows
        order = {"biochemical": 0, "cellular pathway readout": 1, "peptide": 2, "nucleotide probe": 3}
        chosen.sort(key=lambda x: (order.get(x.get("relation"), 9), -(x.get("pchembl") or 0)))
        ligands = [row for row in chosen if row.get("relation") != "nucleotide probe"]
        return chosen, ("ok" if ligands else "empty")
    except Exception as exc:
        logger.warning("ChEMBL activity fetch failed: %s", exc)
        return [], "unavailable"


def _snapshot_path(uniprot_id: str | None, gene_symbol: str | None) -> Path | None:
    uid = (uniprot_id or "").upper()
    gene = re.sub(r"[\s\-]", "", gene_symbol or "").upper()
    path = _SNAPSHOTS.get(uid) or _SNAPSHOTS.get(_SNAPSHOT_GENES.get(gene, ""))
    if path and path.is_file():
        return path
    return None


def _snapshot_rows(path: Path, limit: int, modality: str | None) -> tuple[list[dict[str, Any]], str | None, str]:
    """Saved activities for one demo target. Used only when the live ChEMBL call does not respond."""
    payload = json.loads(path.read_text())
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in payload.get("rows") or []:
        cid = raw.get("chembl_id")
        if not cid or not raw.get("smiles") or cid in seen:
            continue
        row = dict(raw)
        row["modality"] = _infer_modality(row.get("assay") or "", row.get("standard_type"))
        row["relation"] = activity_relation(row)
        seen.add(cid)
        rows.append(row)
    matched = [row for row in rows if _matches_modality(row, modality)] if modality else rows
    if modality and matched:
        chosen = matched
    elif modality:
        functional = [row for row in rows if row.get("assay_type") == "F"]
        chosen = functional or rows
    else:
        chosen = rows
    order = {"biochemical": 0, "cellular pathway readout": 1, "peptide": 2, "nucleotide probe": 3}
    chosen.sort(key=lambda x: (order.get(x.get("relation"), 9), -(x.get("pchembl") or 0)))
    ligands = [row for row in chosen if row.get("relation") != "nucleotide probe"]
    label = payload.get("gene_symbol") or payload.get("uniprot_id") or "this protein"
    return ligands[:limit], payload.get("saved_at"), label


def fetch_actives(uniprot_id: str, limit: int = 25) -> list[dict[str, Any]]:
    rows, _status = fetch_actives_status(uniprot_id, limit=limit)
    ligands = [row for row in rows if row.get("relation") != "nucleotide probe"]
    return ligands[:limit]


def discover_known_actives(
    uniprot_id: str | None,
    gene_symbol: str | None = None,
    limit: int = 20,
    *,
    modality: str | None = None,
) -> dict[str, Any]:
    from datetime import datetime, timezone

    from app.config import settings

    uid = uniprot_id or ""
    retrieved_at = datetime.now(timezone.utc).isoformat()
    if uid:
        rows, status = fetch_actives_status(uid, limit=limit, modality=modality)
    else:
        rows, status = [], "no_target"
    nucleotide_count = sum(1 for row in rows if row.get("relation") == "nucleotide probe")
    rows = [row for row in rows if row.get("relation") != "nucleotide probe"][:limit]
    source = "chembl"
    snapshot_saved_at = None
    snapshot_label = None
    # TEMP DEMO: GLP1R and EGFR only, and only after the live call fails. Delete with the snapshot files.
    snapshot = _snapshot_path(uid, gene_symbol)
    if not rows and snapshot and status in {"unavailable", "no_target"}:
        snapshot_rows, snapshot_saved_at, snapshot_label = _snapshot_rows(snapshot, limit, modality)
        if snapshot_rows:
            rows = snapshot_rows
            source = "chembl_snapshot"
            status = "snapshot"
    if not rows and settings.chem_allow_demo_actives:
        rows = [dict(row) for row in (DEMO_ACTIVES.get(uid) or DEMO_ACTIVES.get("O60674") or [])[:limit]]
        source = "demo_curated"
        status = "demo"
    for i, row in enumerate(rows):
        row["rank"] = i + 1
        row["source"] = source
        row["retrieved_at"] = retrieved_at
        row["evidence"] = "measured" if source in {"chembl", "chembl_snapshot"} else "illustrative"

    label = gene_symbol or uid or "this protein"
    if rows and source == "chembl":
        asked = f" {modality} " if modality else " "
        summary = (
            f"Retrieved {len(rows)} known{asked}actives for {label} from ChEMBL, "
            "with biochemical measurements before cellular pathway readouts and peptides."
        )
        counts: dict[str, int] = {}
        for row in rows:
            kind = row.get("relation") or "biochemical"
            counts[kind] = counts.get(kind, 0) + 1
        narrative = (
            summary
            + " Each row keeps its assay type, standard type, and source activity id. "
            "A pChEMBL value is a standardized activity, not by itself proof of agonism or inhibition. "
            f"{counts.get('biochemical', 0)} biochemical measurement(s), "
            f"{counts.get('cellular pathway readout', 0)} cellular pathway readout(s), and "
            f"{counts.get('peptide', 0)} peptide(s) are in this table. "
            "A cellular readout such as ERK phosphorylation or proliferation in cells "
            "can come from an upstream protein and is not direct binding to this target. "
            f"{nucleotide_count} nucleotide probe(s) were left out of the table."
        )
        if (gene_symbol or "").upper().startswith("GLP"):
            narrative += (
                " GLP1R is a class B GPCR. Peptide and small-molecule ligands, agonists and antagonists, "
                "and binding affinity versus functional potency are different observations and are not collapsed here."
            )
        if modality == "agonist" and any(row.get("modality") == "agonist" for row in rows):
            narrative += " Rows were kept when the assay text indicated agonism. They are not labeled as inhibitors."
        elif modality == "agonist":
            narrative += (
                " No assay description explicitly marked these rows as agonists. "
                "They remain unlabeled activities and are not called inhibitors."
            )
        elif modality == "inhibitor":
            narrative += " Inhibitor here means the assay text or standard type supports inhibition or binding, not agonism."
    elif rows and source == "chembl_snapshot":
        saved = snapshot_saved_at or "an earlier download"
        shown = snapshot_label or label
        summary = (
            f"ChEMBL did not respond for {shown}. "
            f"Showing {len(rows)} {shown} activities saved from ChEMBL on {saved}."
        )
        narrative = (
            summary
            + f" These rows are the temporary {shown} extract, not a live call. "
            "A pChEMBL value is a standardized activity, not by itself proof of agonism or inhibition."
        )
        if modality == "agonist" and any(row.get("modality") == "agonist" for row in rows):
            narrative += " Rows were kept when the assay text indicated agonism."
        elif modality == "agonist":
            narrative += " No saved assay description explicitly marked these rows as agonists."
        elif modality == "inhibitor":
            narrative += " Inhibitor here means the assay text or standard type supports inhibition or binding, not agonism."
    elif rows and source == "demo_curated":
        summary = f"Demo mode returned {len(rows)} placeholder actives for {label}. These are not a live ChEMBL result."
        narrative = summary
    elif status == "unavailable":
        summary = f"ChEMBL could not be reached for {label}. No substitute compounds were added."
        narrative = summary
    elif status == "no_target":
        summary = f"ChEMBL has no target mapping for {label}. No substitute compounds were added."
        narrative = summary
    else:
        summary = f"ChEMBL returned no activities at the requested cutoff for {label}. No substitute compounds were added."
        narrative = summary
    return {
        "capability": "C2",
        "capability_name": "Known Bioactive Discovery",
        "summary": summary,
        "narrative": narrative,
        "actives": rows,
        "uniprot_id": uid,
        "source": source,
        "retrieval_status": status,
        "retrieved_at": retrieved_at,
        "provenance": {
            "source": source,
            "status": status,
            "retrieved_at": retrieved_at,
            "tool": "ChEMBL",
            "kind": "measured" if source in {"chembl", "chembl_snapshot"} and rows else "unavailable",
            "saved_at": snapshot_saved_at,
        },
        "tools_used": ["ChEMBL"],
        "parameters": {"uniprot_id": uid, "limit": limit, "pchembl_gte": 6, "assay_types": ["B", "F"], "modality": modality},
    }
