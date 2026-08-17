"""Neural analog design: RNN-sampled R-groups grafted onto real drug scaffolds.

An unconditioned char-RNN invents chemically valid but often un-drug-like strings.
To make generated molecules resemble existing drugs while remaining new, we keep the
neural step (the RNN proposes the substituent chemistry) but assemble it onto Murcko
scaffolds taken from approved drugs, so every candidate lands in the drug-like
similarity window instead of drifting into exotic chemotypes.
"""

from __future__ import annotations

import logging
import random
from typing import Any

logger = logging.getLogger(__name__)


def _drug_scaffolds(gene_symbol: str | None) -> list[dict[str, Any]]:
    """Murcko scaffolds of known drugs for the target family."""
    from rdkit import Chem
    from rdkit.Chem.Scaffolds import MurckoScaffold

    from app.services.chem.drug_similarity import KNOWN_DRUGS, _drug_reference

    generic_names = {d["name"] for d in KNOWN_DRUGS["generic"]}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for drug in _drug_reference(gene_symbol):
        mol = Chem.MolFromSmiles(drug["smiles"])
        if mol is None:
            continue
        try:
            scaf = MurckoScaffold.GetScaffoldForMol(mol)
        except Exception:
            continue
        if scaf is None or scaf.GetNumHeavyAtoms() < 10:
            continue
        smi = Chem.MolToSmiles(scaf)
        if not smi or smi in seen:
            continue
        seen.add(smi)
        out.append({
            "parent": drug["name"],
            "scaffold": smi,
            "target_family": drug["name"] not in generic_names,
        })
    return out


def _attachment_sites(mol) -> list[int]:
    """Aromatic / sp3 carbons and ring nitrogens that still carry a hydrogen."""
    sites: list[int] = []
    for atom in mol.GetAtoms():
        if atom.GetTotalNumHs() < 1:
            continue
        if atom.GetSymbol() not in {"C", "N"}:
            continue
        sites.append(atom.GetIdx())
    return sites


def _graft(scaffold_smiles: str, fragment_smiles: str, rng: random.Random) -> str | None:
    """Bond a fragment to an open position on the scaffold via RDKit."""
    from rdkit import Chem

    scaf = Chem.MolFromSmiles(scaffold_smiles)
    frag = Chem.MolFromSmiles(fragment_smiles)
    if scaf is None or frag is None:
        return None

    sites = _attachment_sites(scaf)
    frag_sites = _attachment_sites(frag)
    if not sites or not frag_sites:
        return None

    combo = Chem.RWMol(Chem.CombineMols(scaf, frag))
    offset = scaf.GetNumAtoms()
    a = rng.choice(sites)
    b = frag_sites[0] + offset
    try:
        combo.AddBond(a, b, Chem.BondType.SINGLE)
        out = combo.GetMol()
        Chem.SanitizeMol(out)
        smi = Chem.MolToSmiles(out)
    except Exception:
        return None

    mol = Chem.MolFromSmiles(smi) if smi else None
    if mol is None:
        return None
    heavy = mol.GetNumHeavyAtoms()
    if heavy < 14 or heavy > 55:
        return None
    return Chem.MolToSmiles(mol)


def design_drug_analogs(
    n: int = 12,
    *,
    gene_symbol: str | None = None,
    extra_actives: list[dict[str, Any]] | None = None,
    sim_low: float | None = None,
    sim_high: float | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Generate n neural analogs that sit inside the drug-similarity window."""
    try:
        from rdkit import Chem  # noqa: F401
    except ImportError:
        return [], {"available": False, "reason": "rdkit_missing"}

    from app.services.chem.drug_similarity import (
        ANALOG_WINDOW_HIGH,
        ANALOG_WINDOW_LOW,
        build_reference_index,
        compare_to_drugs,
    )
    from app.services.chem.smiles_rnn import sample_fragments

    low = ANALOG_WINDOW_LOW if sim_low is None else sim_low
    high = ANALOG_WINDOW_HIGH if sim_high is None else sim_high

    scaffolds = _drug_scaffolds(gene_symbol)
    if not scaffolds:
        return [], {"available": False, "reason": "no_scaffolds"}

    fragments = sample_fragments(max(8, n))
    if not fragments:
        return [], {"available": False, "reason": "no_neural_fragments"}

    index = build_reference_index(gene_symbol, extra_actives)
    rng = random.Random()
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    rejected_duplicate = 0
    rejected_window = 0

    # Prefer scaffolds from drugs that hit this target family; keep a minority of
    # generic drug scaffolds so the output is not one single chemotype.
    family = [s for s in scaffolds if s.get("target_family")] or scaffolds
    attempts = max(60, n * 20)
    for _ in range(attempts):
        if len(out) >= n:
            break
        pool = family if rng.random() < 0.75 else scaffolds
        scaf = rng.choice(pool)
        frag = rng.choice(fragments)
        smi = _graft(scaf["scaffold"], frag, rng)
        if not smi or smi in seen:
            continue
        info = compare_to_drugs(smi, index)
        if info.get("is_duplicate"):
            rejected_duplicate += 1
            continue
        sim = info.get("drug_similarity")
        if sim is None or not (low <= float(sim) <= high):
            rejected_window += 1
            continue
        seen.add(smi)
        entry = {
            "smiles": smi,
            "origin": "neural_analog",
            "scaffold_parent": scaf["parent"],
            "scaffold_smiles": scaf["scaffold"],
            "neural_fragment": frag,
        }
        entry.update(info)
        out.append(entry)

    for i, entry in enumerate(out, start=1):
        entry["candidate_id"] = f"RNN-A{i:02d}"

    stats = {
        "available": True,
        "scaffold_count": len(scaffolds),
        "fragment_count": len(fragments),
        "accepted": len(out),
        "rejected_duplicate": rejected_duplicate,
        "rejected_out_of_window": rejected_window,
        "similarity_window": [low, high],
    }
    return out, stats
