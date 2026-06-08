"""RDKit-backed molecular property calculation and virtual screening."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

SMILES_PATTERN = re.compile(r"^[A-Za-z0-9@+\-\[\]\(\)=#/\\%.]+$")


def rdkit_available() -> bool:
    try:
        from rdkit import Chem  # noqa: F401
        return True
    except ImportError:
        return False


def _normalize_smiles(value: str) -> str | None:
    s = (value or "").strip()
    if not s or len(s) < 2:
        return None
    if SMILES_PATTERN.match(s):
        return s
    return None


def extract_compounds(input_data: dict) -> list[dict[str, str]]:
    """Parse compound list from agent input (SMILES lines, CSV-like text, or structured list)."""
    compounds: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(cid: str, smiles: str) -> None:
        smi = _normalize_smiles(smiles)
        if not smi or smi in seen:
            return
        seen.add(smi)
        compounds.append({"compound_id": cid or f"CMP-{len(compounds) + 1}", "smiles": smi})

    raw_list = input_data.get("compound_list") or input_data.get("compounds") or []
    if isinstance(raw_list, list):
        for i, item in enumerate(raw_list):
            if isinstance(item, dict):
                add(str(item.get("id") or item.get("compound_id") or f"CMP-{i + 1}"), str(item.get("smiles") or item.get("SMILES") or ""))
            else:
                add(f"CMP-{i + 1}", str(item))

    for line in str(input_data.get("smiles") or "").splitlines():
        line = line.strip()
        if not line or line.lower().startswith("smiles"):
            continue
        if "," in line:
            parts = line.split(",")
            add(parts[0].strip(), parts[-1].strip())
        else:
            add(f"CMP-{len(compounds) + 1}", line)

    query = str(input_data.get("query") or "")
    for line in query.splitlines():
        line = line.strip()
        if not line:
            continue
        if "," in line and len(line.split(",")) >= 2:
            parts = [p.strip() for p in line.split(",")]
            add(parts[0], parts[-1])
        elif _normalize_smiles(line):
            add(f"CMP-{len(compounds) + 1}", line)

    if not compounds:
        # Demo compounds for empty input (educational fallback)
        demos = [
            ("SN-2847", "CC(C)Cc1ccc(C(C)C(=O)O)cc1"),
            ("ABT-494", "CC1=C(C(=CC=C1)F)C(=O)N2CCC(CC2)N3CCN(CC3)C"),
        ]
        for cid, smi in demos:
            add(cid, smi)

    return compounds[:200]


def compute_molecule_properties(smiles: str) -> dict[str, Any]:
    """Compute ADMET-relevant descriptors with RDKit; heuristic fallback if unavailable."""
    if rdkit_available():
        from rdkit import Chem
        from rdkit.Chem import Crippen, Descriptors, Lipinski, QED

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return {"smiles": smiles, "valid": False, "error": "Invalid SMILES"}

        mw = Descriptors.MolWt(mol)
        logp = Crippen.MolLogP(mol)
        tpsa = Descriptors.TPSA(mol)
        hbd = Lipinski.NumHDonors(mol)
        hba = Lipinski.NumHAcceptors(mol)
        rotatable = Lipinski.NumRotatableBonds(mol)
        qed = QED.qed(mol)

        lipinski_violations = sum([
            mw > 500,
            logp > 5,
            hbd > 5,
            hba > 10,
        ])
        return {
            "smiles": smiles,
            "valid": True,
            "engine": "rdkit",
            "molecular_weight": round(mw, 2),
            "logp": round(logp, 2),
            "tpsa": round(tpsa, 2),
            "h_bond_donors": hbd,
            "h_bond_acceptors": hba,
            "rotatable_bonds": rotatable,
            "qed": round(qed, 3),
            "lipinski_violations": lipinski_violations,
            "lipinski_pass": lipinski_violations == 0,
            "solubility_class": "high" if logp < 1 and tpsa > 60 else "moderate" if logp < 3 else "low",
            "bbb_permeability": "likely" if tpsa < 90 and mw < 450 and hbd <= 3 else "unlikely",
            "herg_risk": "elevated" if logp > 4 and mw > 400 else "moderate" if logp > 3 else "low",
        }

    # Heuristic fallback without RDKit
    length = len(smiles)
    return {
        "smiles": smiles,
        "valid": True,
        "engine": "heuristic",
        "molecular_weight": min(900, 150 + length * 8),
        "logp": round(min(6.0, length / 18), 2),
        "tpsa": min(180, 40 + length * 2),
        "h_bond_donors": smiles.count("O") // 3,
        "h_bond_acceptors": smiles.count("N") + smiles.count("O"),
        "rotatable_bonds": smiles.count("C-C"),
        "qed": round(max(0.2, 0.9 - length / 120), 3),
        "lipinski_violations": 1 if length > 80 else 0,
        "lipinski_pass": length <= 80,
        "solubility_class": "moderate",
        "bbb_permeability": "unknown",
        "herg_risk": "moderate",
        "note": "Install RDKit for physics-based descriptors",
    }


def virtual_screen_compounds(
    compounds: list[dict[str, str]],
    *,
    max_hits: int = 25,
    lipinski_only: bool = True,
) -> list[dict[str, Any]]:
    """Rank compounds by drug-likeness (QED) with optional Lipinski filter."""
    scored: list[dict[str, Any]] = []
    for item in compounds:
        props = compute_molecule_properties(item["smiles"])
        if not props.get("valid"):
            continue
        if lipinski_only and not props.get("lipinski_pass"):
            continue
        scored.append({
            "compound_id": item["compound_id"],
            **props,
            "screening_score": props.get("qed", 0),
            "status": "hit" if props.get("qed", 0) >= 0.5 else "candidate",
        })

    scored.sort(key=lambda x: x.get("screening_score", 0), reverse=True)
    for i, row in enumerate(scored[:max_hits]):
        row["rank"] = i + 1
    return scored[:max_hits]
