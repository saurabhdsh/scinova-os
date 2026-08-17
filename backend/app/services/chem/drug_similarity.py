"""Drug-likeness benchmarking: match generated molecules against known drugs.

Generated candidates must look like real medicinal chemistry (similar to approved
drugs / known actives) without being duplicates of them. This module reports the
closest known drug, the Tanimoto similarity, and a novelty verdict.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Analog window: drug-like but still novel
DUPLICATE_THRESHOLD = 0.95
CLOSE_ANALOG_THRESHOLD = 0.85
ANALOG_WINDOW_LOW = 0.35
ANALOG_WINDOW_HIGH = 0.70

# Reference set of approved / clinical drugs, grouped by target family.
# "generic" entries are broadly-used drugs so any chemotype has a sane comparator.
KNOWN_DRUGS: dict[str, list[dict[str, str]]] = {
    "JAK": [
        {"name": "Ruxolitinib", "smiles": "C[C@@H]1CCN(C[C@@H]1N(C)C2=NC=NC3=C2C=CN3)C4=CC=CC=C4"},
        {"name": "Fedratinib", "smiles": "CC1=CN=C(N=C1NC2=CC(=CC=C2)S(=O)(=O)NC(C)(C)C)NC3=CC=C(C=C3)N4CCCC4"},
        {"name": "Pacritinib", "smiles": "COC1=CC2=C(C=C1)N=C(N2)NC3=CC=C(C=C3)N4CCN(CC4)C"},
        {"name": "Momelotinib", "smiles": "NC(=O)C1=CC=C(C=C1)C2=NC(=NC=C2)NC3=CC=C(C=C3)N4CCOCC4"},
        {"name": "Abrocitinib", "smiles": "CCC(=O)N[C@@H]1CC[C@H](CC1)N(C)C2=NC=NC3=C2C=CN3"},
        {"name": "Baricitinib", "smiles": "CCS(=O)(=O)N1CC(C1)(CC#N)N2C=C(C=N2)C3=C4C=CNC4=NC=N3"},
        {"name": "Tofacitinib", "smiles": "CC1CCN(CC1N(C)C2=NC=NC3=C2C=CN3)C(=O)CC#N"},
        {"name": "Upadacitinib", "smiles": "CCC1CN2C(=N1)C3=C(C=C(C=C3)F)N=C2N"},
    ],
    "EGFR": [
        {"name": "Gefitinib", "smiles": "COC1=C(C=C2C(=C1)N=CN=C2NC3=CC(=C(C=C3)F)Cl)OCCCN4CCOCC4"},
        {"name": "Erlotinib", "smiles": "COCCOC1=C(C=C2C(=C1)N=CN=C2NC3=CC=CC(=C3)C#C)OCCOC"},
        {"name": "Osimertinib", "smiles": "COC1=C(C=C(C=C1)N(C)CCN(C)C)NC2=NC=CC(=N2)C3=CN(C4=CC=CC=C43)C"},
    ],
    "GLP1R": [
        {"name": "Danuglipron-like acid", "smiles": "O=C(O)c1ccc(-c2noc(-c3ccccc3)n2)cc1"},
        {"name": "Small-mol GLP1R agonist", "smiles": "CC1=CC(=CC=C1)C2=NC(=NO2)C3=CC=C(C=C3)C(=O)O"},
    ],
    "generic": [
        {"name": "Imatinib", "smiles": "CC1=C(C=C(C=C1)NC(=O)C2=CC=C(C=C2)CN3CCN(CC3)C)NC4=NC=CC(=N4)C5=CN=CC=C5"},
        {"name": "Sunitinib", "smiles": "CCN(CC)CCNC(=O)C1=C(NC(=C1C)C=C2C3=C(C=CC(=C3)F)NC2=O)C"},
        {"name": "Sorafenib", "smiles": "CNC(=O)C1=NC=CC(=C1)OC2=CC=C(C=C2)NC(=O)NC3=CC(=C(C=C3)Cl)C(F)(F)F"},
        {"name": "Celecoxib", "smiles": "CC1=CC=C(C=C1)C2=CC(=NN2C3=CC=C(C=C3)S(=O)(=O)N)C(F)(F)F"},
        {"name": "Ibuprofen", "smiles": "CC(C)Cc1ccc(C(C)C(=O)O)cc1"},
        {"name": "Paracetamol", "smiles": "CC(=O)Nc1ccc(O)cc1"},
        {"name": "Aspirin", "smiles": "CC(=O)Oc1ccccc1C(=O)O"},
        {"name": "Metformin", "smiles": "CN(C)C(=N)NC(=N)N"},
        {"name": "Atorvastatin", "smiles": "CC(C)c1c(C(=O)Nc2ccccc2)c(-c2ccccc2)c(-c2ccc(F)cc2)n1CCC(O)CC(O)CC(=O)O"},
        {"name": "Losartan", "smiles": "CCCCc1nc(Cl)c(CO)n1Cc1ccc(-c2ccccc2-c2nn[nH]n2)cc1"},
        {"name": "Omeprazole", "smiles": "COc1ccc2[nH]c(S(=O)Cc3ncc(C)c(OC)c3C)nc2c1"},
        {"name": "Sildenafil", "smiles": "CCCc1nn(C)c2c(=O)[nH]c(-c3cc(S(=O)(=O)N4CCN(C)CC4)ccc3OCC)nc12"},
        {"name": "Diazepam", "smiles": "CN1C(=O)CN=C(c2ccccc2)c2cc(Cl)ccc21"},
        {"name": "Amoxicillin", "smiles": "CC1(C)SC2C(NC(=O)C(N)c3ccc(O)cc3)C(=O)N2C1C(=O)O"},
        {"name": "Ciprofloxacin", "smiles": "O=C(O)c1cn(C2CC2)c2cc(N3CCNCC3)c(F)cc2c1=O"},
        {"name": "Fluoxetine", "smiles": "CNCCC(Oc1ccc(C(F)(F)F)cc1)c1ccccc1"},
        {"name": "Caffeine", "smiles": "Cn1c(=O)c2c(ncn2C)n(C)c1=O"},
        {"name": "Naproxen", "smiles": "COc1ccc2cc(C(C)C(=O)O)ccc2c1"},
        {"name": "Diclofenac", "smiles": "O=C(O)Cc1ccccc1Nc1c(Cl)cccc1Cl"},
        {"name": "Warfarin", "smiles": "CC(=O)CC(c1ccccc1)c1c(O)c2ccccc2oc1=O"},
    ],
}


def _drug_reference(gene_symbol: str | None) -> list[dict[str, str]]:
    """Known drugs for the target family plus a generic approved-drug panel."""
    refs: list[dict[str, str]] = []
    gene = (gene_symbol or "").upper()
    for family, drugs in KNOWN_DRUGS.items():
        if family == "generic":
            continue
        if gene.startswith(family) or family.startswith(gene[:3] or "~"):
            refs.extend(drugs)
    if not refs and gene:
        # Unknown target: still compare against kinase-type drugs for context
        refs.extend(KNOWN_DRUGS["JAK"])
    refs.extend(KNOWN_DRUGS["generic"])
    # Deduplicate by SMILES
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for d in refs:
        if d["smiles"] in seen:
            continue
        seen.add(d["smiles"])
        out.append(d)
    return out


def _morgan_fp(smiles: str):
    from rdkit import Chem
    from rdkit.Chem import AllChem

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=2048)


def _canonical(smiles: str) -> str | None:
    try:
        from rdkit import Chem

        mol = Chem.MolFromSmiles(smiles)
        return Chem.MolToSmiles(mol) if mol else None
    except Exception:
        return None


def build_reference_index(
    gene_symbol: str | None = None,
    extra_actives: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Precompute fingerprints for known drugs (+ session actives)."""
    refs = _drug_reference(gene_symbol)
    for a in extra_actives or []:
        smi = a.get("smiles")
        if not smi:
            continue
        refs.append({
            "name": a.get("pref_name") or a.get("chembl_id") or "known active",
            "smiles": smi,
        })

    entries: list[dict[str, Any]] = []
    canon_set: set[str] = set()
    try:
        from rdkit import Chem  # noqa: F401
    except ImportError:
        logger.warning("RDKit unavailable — drug similarity disabled")
        return {"entries": [], "canonical": set(), "available": False}

    for d in refs:
        fp = _morgan_fp(d["smiles"])
        if fp is None:
            continue
        canon = _canonical(d["smiles"])
        if canon:
            canon_set.add(canon)
        entries.append({"name": d["name"], "smiles": d["smiles"], "fp": fp})
    return {"entries": entries, "canonical": canon_set, "available": True}


def compare_to_drugs(smiles: str, index: dict[str, Any]) -> dict[str, Any]:
    """Closest known drug + similarity + verdict for one molecule."""
    result: dict[str, Any] = {
        "closest_drug": None,
        "closest_drug_smiles": None,
        "drug_similarity": None,
        "drug_likeness_verdict": "not assessed",
        "is_duplicate": False,
        "in_analog_window": False,
    }
    if not index.get("available") or not index.get("entries"):
        return result

    from rdkit import DataStructs

    fp = _morgan_fp(smiles)
    if fp is None:
        return result

    canon = _canonical(smiles)
    if canon and canon in index["canonical"]:
        result.update({
            "is_duplicate": True,
            "drug_similarity": 1.0,
            "drug_likeness_verdict": "duplicate of known drug",
        })

    best_sim = 0.0
    best = None
    for entry in index["entries"]:
        sim = float(DataStructs.TanimotoSimilarity(fp, entry["fp"]))
        if sim > best_sim:
            best_sim = sim
            best = entry

    if best is not None:
        result["closest_drug"] = best["name"]
        result["closest_drug_smiles"] = best["smiles"]
        result["drug_similarity"] = round(best_sim, 3)

    if result["is_duplicate"] or best_sim >= DUPLICATE_THRESHOLD:
        result["is_duplicate"] = True
        result["drug_likeness_verdict"] = "duplicate of known drug"
    elif best_sim >= CLOSE_ANALOG_THRESHOLD:
        result["drug_likeness_verdict"] = "very close analog"
    elif best_sim >= ANALOG_WINDOW_LOW:
        result["drug_likeness_verdict"] = (
            "drug-like analog" if best_sim <= ANALOG_WINDOW_HIGH else "close analog"
        )
        result["in_analog_window"] = ANALOG_WINDOW_LOW <= best_sim <= ANALOG_WINDOW_HIGH
    else:
        result["drug_likeness_verdict"] = "novel chemotype (low drug similarity)"

    return result


def annotate_candidates(
    candidates: list[dict[str, Any]],
    *,
    gene_symbol: str | None = None,
    extra_actives: list[dict[str, Any]] | None = None,
    drop_duplicates: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Attach closest-drug similarity to each candidate; optionally drop duplicates."""
    index = build_reference_index(gene_symbol, extra_actives)
    kept: list[dict[str, Any]] = []
    dropped = 0
    for cand in candidates:
        info = compare_to_drugs(cand.get("smiles") or "", index)
        if drop_duplicates and info.get("is_duplicate"):
            dropped += 1
            continue
        merged = dict(cand)
        merged.update(info)
        kept.append(merged)

    sims = [c["drug_similarity"] for c in kept if c.get("drug_similarity") is not None]
    in_window = sum(1 for c in kept if c.get("in_analog_window"))
    stats = {
        "reference_drug_count": len(index.get("entries") or []),
        "duplicates_removed": dropped,
        "mean_drug_similarity": round(sum(sims) / len(sims), 3) if sims else None,
        "max_drug_similarity": round(max(sims), 3) if sims else None,
        "in_analog_window": in_window,
        "analog_window": [ANALOG_WINDOW_LOW, ANALOG_WINDOW_HIGH],
        "fingerprint": "Morgan r=2, 2048 bits",
        "available": bool(index.get("available")),
    }
    return kept, stats
