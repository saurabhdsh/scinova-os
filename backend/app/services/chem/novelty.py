"""C4 — Novelty assessment via Morgan fingerprints + Tanimoto."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _morgan_fp(smiles: str):
    from rdkit import Chem
    from rdkit.Chem import AllChem

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=2048)


def _tanimoto(fp_a, fp_b) -> float:
    from rdkit import DataStructs

    return float(DataStructs.TanimotoSimilarity(fp_a, fp_b))


def _heuristic_similarity(a: str, b: str) -> float:
    """Fallback when RDKit missing — crude token overlap."""
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _canonical(smiles: str, *, isomeric: bool) -> str | None:
    from rdkit import Chem

    mol = Chem.MolFromSmiles(smiles or "")
    if mol is None:
        return None
    try:
        return Chem.MolToSmiles(mol, isomericSmiles=isomeric)
    except Exception:
        return None


def _scaffold(smiles: str) -> str | None:
    from rdkit import Chem
    from rdkit.Chem.Scaffolds import MurckoScaffold

    mol = Chem.MolFromSmiles(smiles or "")
    if mol is None:
        return None
    try:
        scaf = MurckoScaffold.GetScaffoldForMol(mol)
    except Exception:
        return None
    if scaf is None or scaf.GetNumAtoms() == 0:
        return None
    return Chem.MolToSmiles(scaf)


def _is_peptide(smiles: str) -> bool:
    """A long amide chain is a peptide, not a small-molecule neighbor."""
    from rdkit import Chem

    mol = Chem.MolFromSmiles(smiles or "")
    if mol is None:
        return False
    amide = Chem.MolFromSmarts("[NX3][CX3](=[OX1])[#6]")
    amides = len(mol.GetSubstructMatches(amide)) if amide is not None else 0
    return amides >= 6 or mol.GetNumHeavyAtoms() >= 80


def _nearest(candidate_fp, pool: list[tuple[dict[str, Any], Any]]) -> tuple[float, dict[str, Any] | None]:
    best = 0.0
    closest: dict[str, Any] | None = None
    if candidate_fp is None:
        return best, closest
    for row, fingerprint in pool:
        score = _tanimoto(candidate_fp, fingerprint)
        if score > best:
            best = score
            closest = row
    return best, closest


def _mcs_atoms(left: str, right: str) -> int | None:
    from rdkit import Chem
    from rdkit.Chem import rdFMCS

    a = Chem.MolFromSmiles(left or "")
    b = Chem.MolFromSmiles(right or "")
    if a is None or b is None:
        return None
    try:
        result = rdFMCS.FindMCS([a, b], timeout=2)
    except Exception:
        return None
    if result is None or result.canceled or result.numAtoms <= 0:
        return None
    return int(result.numAtoms)


def assess_novelty(
    candidates: list[dict[str, Any]],
    reference_actives: list[dict[str, Any]],
) -> dict[str, Any]:
    references = [row for row in reference_actives if row.get("smiles") and row.get("source") != "demo_curated"]
    ref_smiles = [row.get("smiles") for row in references]
    try:
        from rdkit import Chem  # noqa: F401
        use_rdkit = True
    except ImportError:
        use_rdkit = False
    if not use_rdkit:
        return {
            "capability": "C4",
            "capability_name": "Chemical Novelty Assessment",
            "summary": "Molecular similarity was not calculated.",
            "narrative": (
                "RDKit is not available, so fingerprint Tanimoto, scaffold, and maximum common substructure "
                "comparisons were not run. No similarity score was estimated."
            ),
            "novelty": [],
            "similarity_distribution": [],
            "reference_count": len(ref_smiles),
            "reference_source": "session_actives",
            "tools_used": [],
            "parameters": {"fp": "morgan_r2", "n_bits": 2048, "rdkit": False},
            "provenance": {
                "kind": "similarity",
                "status": "failed",
                "evidence": "not_run",
                "tool": "RDKit",
                "source": "session_reference_ligands",
            },
        }

    small_pool: list[tuple[dict[str, Any], Any]] = []
    peptide_pool: list[tuple[dict[str, Any], Any]] = []
    for row in references:
        fp = _morgan_fp(row.get("smiles") or "")
        if fp is None:
            continue
        if _is_peptide(row.get("smiles") or ""):
            peptide_pool.append((row, fp))
        else:
            small_pool.append((row, fp))

    rows: list[dict[str, Any]] = []
    for cand in candidates:
        smi = cand.get("smiles") or ""
        candidate_fp = _morgan_fp(smi)
        candidate_peptide = _is_peptide(smi)
        like_pool = peptide_pool if candidate_peptide else small_pool
        like_sim, like_row = _nearest(candidate_fp, like_pool)
        other_pool = small_pool if candidate_peptide else peptide_pool
        other_sim, other_row = _nearest(candidate_fp, other_pool)
        if like_row is not None:
            best_sim = like_sim
            closest_row = like_row
            comparable = True
        else:
            best_sim = other_sim
            closest_row = other_row
            comparable = False
        closest = (closest_row or {}).get("smiles")

        exact = False
        stereo_mismatch = False
        scaffold_match = None
        mcs_atoms = None
        if closest:
            query_iso = _canonical(smi, isomeric=True)
            ref_iso = _canonical(closest, isomeric=True)
            query_flat = _canonical(smi, isomeric=False)
            ref_flat = _canonical(closest, isomeric=False)
            exact = bool(query_iso and ref_iso and query_iso == ref_iso)
            stereo_mismatch = bool(query_flat and ref_flat and query_flat == ref_flat and not exact)
            query_scaf = _scaffold(smi)
            ref_scaf = _scaffold(closest)
            if query_scaf and ref_scaf:
                scaffold_match = query_scaf == ref_scaf
            mcs_atoms = _mcs_atoms(smi, closest)

        if not comparable:
            label = "different modality"
        elif exact:
            label = "exact structure match"
        elif best_sim < 0.35:
            label = "structurally distinct"
        elif best_sim < 0.55:
            label = "moderately novel"
        elif best_sim < 0.75:
            label = "analog-like"
        else:
            label = "close analog"

        record_id = (closest_row or {}).get("chembl_id") or (closest_row or {}).get("pref_name") or (closest_row or {}).get("candidate_id")
        rows.append({
            "candidate_id": cand.get("candidate_id"),
            "smiles": smi,
            "max_tanimoto": round(best_sim, 3),
            "closest_analog_smiles": closest,
            "closest_record_id": record_id,
            "closest_name": (closest_row or {}).get("pref_name") or record_id,
            "closest_class": "peptide" if closest and _is_peptide(closest) else "small molecule",
            "comparable": comparable,
            "novelty_label": label,
            "exact_match": exact,
            "stereochemistry_difference": stereo_mismatch,
            "same_bemis_murcko_scaffold": scaffold_match,
            "mcs_atoms": mcs_atoms,
            "fingerprint": "Morgan r=2, 2048 bits",
            "evidence": "calculated",
        })

    rows.sort(key=lambda x: x["max_tanimoto"])
    distribution = [row["max_tanimoto"] for row in rows]
    peptide_refs = len(peptide_pool)
    small_refs = len(small_pool)
    cross = sum(1 for row in rows if not row["comparable"])
    if small_refs == 0 and peptide_refs and cross == len(rows) and rows:
        summary = (
            f"{len(rows)} designed small molecules were compared with {peptide_refs} peptide references. "
            "The low Tanimoto values do not establish small-molecule novelty."
        )
        narrative = (
            f"The stored reference set contains {peptide_refs} peptides and no small molecules. "
            "Morgan fingerprints (radius 2, 2048 bits) give a low Tanimoto between a small molecule and a long peptide "
            "because they are different modalities, not because a small-molecule series was searched. "
            "Nearest records are named in the table. "
            "A like-for-like novelty assessment needs known small-molecule ligands. "
            "This is not a patent novelty or freedom-to-operate determination."
        )
    else:
        summary = (
            f"Compared {len(rows)} candidates with {small_refs} small-molecule and {peptide_refs} peptide references "
            "using Morgan fingerprints and Tanimoto similarity."
        )
        narrative = (
            "Tanimoto similarity uses Morgan fingerprints, radius 2 and 2048 bits. "
            "Nearest neighbors of the same molecular class are used for the label. "
            "A peptide match is reported as a different modality and is not treated as small-molecule novelty. "
            "Exact structure, stereochemistry, Bemis–Murcko scaffold, and maximum common substructure "
            "are included where RDKit could compute them. "
            "This is a database- and fingerprint-dependent observation, not a patent determination."
        )
    return {
        "capability": "C4",
        "capability_name": "Chemical Novelty Assessment",
        "summary": summary,
        "narrative": narrative,
        "novelty": rows,
        "similarity_distribution": distribution,
        "reference_count": len(ref_smiles),
        "reference_source": "session_actives",
        "tools_used": ["RDKit"] if use_rdkit else ["heuristic"],
        "parameters": {"fp": "morgan_r2", "n_bits": 2048, "mcs": bool(use_rdkit)},
        "provenance": {
            "kind": "similarity",
            "status": "completed",
            "evidence": "calculated",
            "tool": "RDKit",
            "source": "session_reference_ligands",
        },
    }
