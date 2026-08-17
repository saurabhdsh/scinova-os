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


def assess_novelty(
    candidates: list[dict[str, Any]],
    reference_actives: list[dict[str, Any]],
) -> dict[str, Any]:
    ref_smiles = [r.get("smiles") for r in reference_actives if r.get("smiles")]
    use_rdkit = True
    try:
        from rdkit import Chem  # noqa: F401
    except ImportError:
        use_rdkit = False

    ref_fps = []
    if use_rdkit:
        for smi in ref_smiles:
            fp = _morgan_fp(smi)
            if fp is not None:
                ref_fps.append((smi, fp))

    rows: list[dict[str, Any]] = []
    for cand in candidates:
        smi = cand.get("smiles") or ""
        best_sim = 0.0
        closest = None
        if use_rdkit and ref_fps:
            cfp = _morgan_fp(smi)
            if cfp is not None:
                for rsmi, rfp in ref_fps:
                    sim = _tanimoto(cfp, rfp)
                    if sim > best_sim:
                        best_sim = sim
                        closest = rsmi
        else:
            for rsmi in ref_smiles:
                sim = _heuristic_similarity(smi, rsmi)
                if sim > best_sim:
                    best_sim = sim
                    closest = rsmi

        if best_sim < 0.35:
            label = "structurally distinct"
        elif best_sim < 0.55:
            label = "moderately novel"
        elif best_sim < 0.75:
            label = "analog-like"
        else:
            label = "close analog"

        rows.append({
            "candidate_id": cand.get("candidate_id"),
            "smiles": smi,
            "max_tanimoto": round(best_sim, 3),
            "closest_analog_smiles": closest,
            "novelty_label": label,
            "fingerprint": "Morgan r=2, 2048 bits" if use_rdkit else "heuristic",
        })

    rows.sort(key=lambda x: x["max_tanimoto"])
    summary = (
        f"Assessed novelty for {len(rows)} candidates vs {len(ref_smiles)} reference actives "
        f"(Morgan FP r=2 / Tanimoto)."
    )
    return {
        "capability": "C4",
        "capability_name": "Chemical Novelty Assessment",
        "summary": summary,
        "narrative": summary,
        "novelty": rows,
        "reference_count": len(ref_smiles),
        "reference_source": "session_actives",
        "tools_used": ["RDKit"] if use_rdkit else ["heuristic"],
        "parameters": {"fp": "morgan_r2", "n_bits": 2048},
    }
