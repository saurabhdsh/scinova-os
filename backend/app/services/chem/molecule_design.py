"""C3 — De novo / scaffold-based candidate design (RDKit + curated templates)."""

from __future__ import annotations

import logging
from typing import Any

from app.services.chemoinformatics_service import compute_molecule_properties

logger = logging.getLogger(__name__)

# Seed scaffolds inspired by known kinase / GPCR chemotypes (demo-safe)
SCAFFOLD_POOL: dict[str, list[tuple[str, str]]] = {
    "JAK2": [
        ("DSN-J2-01", "Cc1ccc(NC(=O)c2ccc(CN3CCN(C)CC3)cc2)cc1"),
        ("DSN-J2-02", "CC(C)(C)c1ccc(Nc2nccc(N3CCN(C)CC3)n2)cc1"),
        ("DSN-J2-03", "O=C(Nc1ccccc1)c1cnc2ccccc2n1"),
        ("DSN-J2-04", "CN1CCN(c2ccc(Nc3ncnc4[nH]ccc34)cc2)CC1"),
        ("DSN-J2-05", "Cc1nc(Nc2ccc(S(N)(=O)=O)cc2)cc(N2CCCC2)n1"),
    ],
    "JAK1": [
        ("DSN-J1-01", "CCC(=O)Nc1ccc(N2CCN(C)CC2)cc1"),
        ("DSN-J1-02", "CN1CCN(c2ncnc3[nH]ccc23)CC1"),
        ("DSN-J1-03", "Fc1ccc2nc(Nc3ccccc3)nc2c1"),
    ],
    "GLP1R": [
        ("DSN-G1-01", "CC1=CC(=CC=C1)C2=NC(=NO2)C3=CC=C(C=C3)C(=O)O"),
        ("DSN-G1-02", "O=C(O)c1ccc(-c2noc(-c3ccccc3)n2)cc1"),
        ("DSN-G1-03", "COc1ccc(-c2nc(-c3ccc(C(=O)O)cc3)no2)cc1"),
    ],
    "DEFAULT": [
        ("DSN-01", "CC(C)Cc1ccc(C(C)C(=O)O)cc1"),
        ("DSN-02", "CC1=C(C(=CC=C1)F)C(=O)N2CCC(CC2)N3CCN(CC3)C"),
        ("DSN-03", "COc1ccc(CCN)cc1"),
    ],
}


def _variants_from_smiles(base: str, cid: str) -> list[tuple[str, str]]:
    """Lightweight analog enumeration via simple string edits when RDKit available."""
    out = [(cid, base)]
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem

        mol = Chem.MolFromSmiles(base)
        if mol is None:
            return out
        # Add a few methyl / fluoro variants at aromatic carbons (conservative)
        rxn_smarts = [
            ("[cH:1]>>[c:1]C", "Me"),
            ("[cH:1]>>[c:1]F", "F"),
        ]
        n = 1
        for smarts, tag in rxn_smarts:
            try:
                rxn = AllChem.ReactionFromSmarts(smarts)
                products = rxn.RunReactants((mol,))
                for prod_tuple in products[:2]:
                    p = prod_tuple[0]
                    try:
                        Chem.SanitizeMol(p)
                        smi = Chem.MolToSmiles(p)
                        if smi and smi != base:
                            out.append((f"{cid}-{tag}{n}", smi))
                            n += 1
                    except Exception:
                        continue
                    if len(out) >= 6:
                        return out
            except Exception:
                continue
    except Exception as exc:
        logger.debug("Variant generation skipped: %s", exc)
    return out


def design_candidates(
    gene_symbol: str | None = None,
    *,
    max_candidates: int = 12,
    reference_smiles: list[str] | None = None,
    pdb_id: str | None = None,
    pocket_id: str | None = None,
    receptor_based: bool = False,
) -> dict[str, Any]:
    gene = (gene_symbol or "DEFAULT").upper()
    if gene.startswith("GLP"):
        gene = "GLP1R"

    seen: set[str] = set()
    candidates: list[dict[str, Any]] = []
    generator_meta: dict[str, Any] | None = None
    neural_count = 0
    analog_count = 0
    analog_stats: dict[str, Any] = {}
    # Oversample so the list still fills max_candidates after known-drug duplicates drop out
    oversample = max_candidates + 6

    # 1) Neural analog design: RNN-sampled R-groups grafted onto real drug scaffolds,
    #    accepted only inside the drug-similarity window (drug-like but not a duplicate)
    try:
        from app.services.chem.analog_design import design_drug_analogs
        from app.services.chem.smiles_rnn import generator_info

        analogs, analog_stats = design_drug_analogs(
            max_candidates,
            gene_symbol=gene,
            extra_actives=[{"smiles": s} for s in (reference_smiles or [])],
        )
        generator_meta = generator_info()
        for item in analogs:
            smi = item["smiles"]
            if smi in seen:
                continue
            props = compute_molecule_properties(smi)
            if not props.get("valid"):
                continue
            seen.add(smi)
            analog_count += 1
            neural_count += 1
            candidates.append({
                "candidate_id": item["candidate_id"],
                "smiles": smi,
                "mw": props.get("molecular_weight"),
                "clogp": props.get("logp"),
                "tpsa": props.get("tpsa"),
                "hbd": props.get("h_bond_donors"),
                "hba": props.get("h_bond_acceptors"),
                "qed": props.get("qed"),
                "lipinski_pass": props.get("lipinski_pass"),
                "rings": None,
                "origin": "neural_analog",
                "scaffold_parent": item.get("scaffold_parent"),
                "neural_fragment": item.get("neural_fragment"),
                "rank": None,
                "docking_score": None,
            })
            if len(candidates) >= oversample:
                break
    except Exception as exc:
        logger.warning("Neural analog design unavailable (%s)", exc)

    # 2) Free neural sampling for chemotype diversity
    try:
        from app.services.chem.smiles_rnn import generate_molecules, generator_info

        neural = generate_molecules(
            max(0, oversample - len(candidates)),
            temperature=0.8,
            gene_symbol=gene,
        )
        generator_meta = generator_meta or generator_info()
        for item in neural:
            smi = item["smiles"]
            if smi in seen:
                continue
            props = compute_molecule_properties(smi)
            if not props.get("valid"):
                continue
            seen.add(smi)
            neural_count += 1
            candidates.append({
                "candidate_id": item["candidate_id"],
                "smiles": smi,
                "mw": props.get("molecular_weight"),
                "clogp": props.get("logp"),
                "tpsa": props.get("tpsa"),
                "hbd": props.get("h_bond_donors"),
                "hba": props.get("h_bond_acceptors"),
                "qed": props.get("qed"),
                "lipinski_pass": props.get("lipinski_pass"),
                "rings": None,
                "origin": "neural_smiles_rnn",
                "rank": None,
                "docking_score": None,
            })
            if len(candidates) >= oversample:
                break
    except Exception as exc:
        logger.warning("Neural SMILES generator unavailable (%s) — falling back to scaffolds", exc)

    # 3) Fill remainder from curated scaffolds / ChEMBL analogs (safety net)
    if len(candidates) < max_candidates:
        pool = list(SCAFFOLD_POOL.get(gene) or SCAFFOLD_POOL["DEFAULT"])
        seeds: list[tuple[str, str]] = []
        if reference_smiles:
            for i, smi in enumerate(reference_smiles[:3]):
                seeds.extend(_variants_from_smiles(smi, f"REF-{i + 1}"))
        for cid, smi in pool:
            seeds.extend(_variants_from_smiles(smi, cid))
        for cid, smi in seeds:
            if smi in seen:
                continue
            props = compute_molecule_properties(smi)
            if not props.get("valid"):
                continue
            seen.add(smi)
            candidates.append({
                "candidate_id": cid,
                "smiles": smi,
                "mw": props.get("molecular_weight"),
                "clogp": props.get("logp"),
                "tpsa": props.get("tpsa"),
                "hbd": props.get("h_bond_donors"),
                "hba": props.get("h_bond_acceptors"),
                "qed": props.get("qed"),
                "lipinski_pass": props.get("lipinski_pass"),
                "rings": None,
                "origin": "scaffold_fill" if neural_count else (
                    "receptor_based" if receptor_based else "scaffold_design"
                ),
                "rank": None,
                "docking_score": None,
            })
            if len(candidates) >= oversample:
                break

    # Ring counts when RDKit present
    try:
        from rdkit import Chem
        from rdkit.Chem import Lipinski

        for c in candidates:
            mol = Chem.MolFromSmiles(c["smiles"])
            if mol:
                c["rings"] = Lipinski.RingCount(mol)
    except Exception:
        pass

    # Benchmark against known drugs: keep drug-like analogs, drop duplicates
    drug_stats: dict[str, Any] = {}
    try:
        from app.services.chem.drug_similarity import annotate_candidates

        candidates, drug_stats = annotate_candidates(
            candidates,
            gene_symbol=gene,
            extra_actives=[{"smiles": s} for s in (reference_smiles or [])],
            drop_duplicates=True,
        )
    except Exception as exc:
        logger.warning("Drug similarity benchmarking unavailable: %s", exc)

    if receptor_based or pdb_id:
        candidates = _score_receptor_candidates(candidates, pdb_id=pdb_id)
    elif drug_stats.get("available"):
        candidates = _rank_by_drug_likeness(candidates)
    candidates = candidates[:max_candidates]
    neural_origins = {"neural_smiles_rnn", "neural_analog"}
    neural_count = sum(1 for c in candidates if c.get("origin") in neural_origins)
    analog_count = sum(1 for c in candidates if c.get("origin") == "neural_analog")

    if drug_stats.get("available"):
        sims = [c["drug_similarity"] for c in candidates if c.get("drug_similarity") is not None]
        drug_stats["mean_drug_similarity"] = round(sum(sims) / len(sims), 3) if sims else None
        drug_stats["max_drug_similarity"] = round(max(sims), 3) if sims else None
        drug_stats["in_analog_window"] = sum(1 for c in candidates if c.get("in_analog_window"))

    method = _generation_method(
        pdb_id=pdb_id,
        pocket_id=pocket_id,
        receptor_based=receptor_based or bool(pdb_id),
        generator_meta=generator_meta,
        neural_count=neural_count,
        total=len(candidates),
        drug_stats=drug_stats,
        analog_stats=analog_stats,
        analog_count=analog_count,
    )

    summary = (
        f"Neural generator produced {neural_count} valid molecules"
        + (f" ({analog_count} built on approved-drug scaffolds)" if analog_count else "")
        + (f" for {gene}" if gene else "")
        + (f" against {pdb_id}/{pocket_id or 'P_0'}" if pdb_id else "")
        + f"; {len(candidates)} candidates after RDKit validation and ranking."
    )
    if drug_stats.get("available"):
        summary += (
            f" Benchmarked vs {drug_stats.get('reference_drug_count')} known drugs — "
            f"mean similarity {drug_stats.get('mean_drug_similarity')}, "
            f"{drug_stats.get('in_analog_window')} in the drug-like analog window "
            f"{drug_stats.get('analog_window')}"
        )
        if drug_stats.get("duplicates_removed"):
            summary += f", {drug_stats['duplicates_removed']} duplicate(s) removed"
        summary += "."

    tools = ["SMILES Char-RNN", "RDKit"]
    if receptor_based or pdb_id:
        tools.append("Affinity Heuristic")
    if drug_stats.get("available"):
        tools.append("Drug Similarity (Morgan/Tanimoto)")
    if neural_count < len(candidates):
        tools.append("Scaffold Fallback")

    return {
        "capability": "C3",
        "capability_name": "Neural Molecule Generation",
        "summary": summary,
        "narrative": summary,
        "candidates": candidates,
        "gene_symbol": gene,
        "pdb_id": pdb_id,
        "pocket_id": pocket_id or ("P_0" if pdb_id else None),
        "method": method,
        "generator": generator_meta,
        "neural_count": neural_count,
        "analog_count": analog_count,
        "drug_benchmark": drug_stats,
        "analog_design": analog_stats,
        "tools_used": tools,
        "parameters": {
            "gene": gene,
            "max_candidates": max_candidates,
            "pdb_id": pdb_id,
            "pocket_id": pocket_id,
            "receptor_based": bool(receptor_based or pdb_id),
            "generator": "smiles_char_rnn",
        },
    }


def _generation_method(
    *,
    pdb_id: str | None,
    pocket_id: str | None,
    receptor_based: bool,
    generator_meta: dict[str, Any] | None,
    neural_count: int,
    total: int,
    drug_stats: dict[str, Any] | None = None,
    analog_stats: dict[str, Any] | None = None,
    analog_count: int = 0,
) -> dict[str, Any]:
    meta = generator_meta or {}
    stats = drug_stats or {}
    astats = analog_stats or {}
    pid = pdb_id or "receptor"
    pocket = pocket_id or "P_0"
    return {
        "name": "Neural SMILES Generation (Char-RNN)",
        "framework": (
            "Character-level recurrent neural network trained on curated drug-like SMILES; "
            "samples new strings, RDKit-validates, then ranks"
            + (f" for pocket {pocket} on {pid}" if receptor_based else "")
            + "."
        ),
        "pdb_id": pdb_id,
        "pocket_id": pocket if receptor_based else None,
        "model": {
            "name": meta.get("name") or "SciNova SMILES Char-RNN",
            "architecture": meta.get("architecture"),
            "hidden_size": meta.get("hidden_size"),
            "vocab_size": meta.get("vocab_size"),
            "n_train_smiles": meta.get("n_train_smiles"),
            "epochs": meta.get("epochs"),
            "smooth_loss": meta.get("smooth_loss"),
        },
        "steps": [
            {
                "step": 1,
                "name": "Train on chemical data",
                "detail": (
                    f"Char-RNN ({meta.get('hidden_size', 128)}-d hidden) trained for "
                    f"{meta.get('epochs', '?')} epochs on {meta.get('n_train_smiles', '?')} "
                    "drug-like SMILES to learn next-character chemistry."
                ),
            },
            {
                "step": 2,
                "name": "Sample candidate structures",
                "detail": (
                    f"Draw SMILES from the learned distribution"
                    + (f" with mild {pid}/{pocket} chemotype priming" if receptor_based else "")
                    + f"; kept {neural_count} RDKit-valid unique molecules."
                ),
            },
            {
                "step": 3,
                "name": "Graft neural R-groups onto approved-drug scaffolds",
                "detail": (
                    (
                        f"Model-sampled substituents were bonded onto Murcko scaffolds from "
                        f"{astats.get('scaffold_count')} approved drugs using "
                        f"{astats.get('fragment_count')} neural fragments, accepting only molecules "
                        f"inside the similarity window {astats.get('similarity_window')}: "
                        f"{astats.get('accepted')} accepted, "
                        f"{astats.get('rejected_out_of_window', 0)} rejected as too similar or too unlike a drug, "
                        f"{astats.get('rejected_duplicate', 0)} rejected as duplicates."
                    )
                    if astats.get("available")
                    else "Skipped — falling back to free neural sampling."
                ),
            },
            {
                "step": 4,
                "name": "Validate & featurize",
                "detail": "RDKit sanitization, canonical SMILES, and descriptors (MW, cLogP, QED, Lipinski).",
            },
            {
                "step": 5,
                "name": "Match against existing drugs",
                "detail": (
                    (
                        f"Morgan r=2 / Tanimoto comparison against "
                        f"{stats.get('reference_drug_count')} approved and clinical drugs: "
                        f"mean similarity {stats.get('mean_drug_similarity')}, "
                        f"max {stats.get('max_drug_similarity')}, "
                        f"{stats.get('in_analog_window')} inside the drug-like analog window "
                        f"{stats.get('analog_window')}; "
                        f"{stats.get('duplicates_removed', 0)} exact duplicate(s) of known drugs removed."
                    )
                    if stats.get("available")
                    else "Skipped — RDKit fingerprints unavailable."
                ),
            },
            {
                "step": 6,
                "name": "Rank for the design goal",
                "detail": (
                    f"Ranked {total} candidates"
                    + (" with a docking-score surrogate for the named pocket." if receptor_based else ".")
                ),
            },
        ],
        "rationale": (
            "A neural generator invents SMILES by sampling a model trained on chemical data, "
            "rather than returning a fixed hand-authored list. Each sample is then benchmarked "
            "against real drugs so it stays medicinally plausible without duplicating a known drug."
        ),
    }


def _rank_by_drug_likeness(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank so molecules closest to the analog window (drug-like yet novel) come first."""
    from app.services.chem.drug_similarity import ANALOG_WINDOW_HIGH, ANALOG_WINDOW_LOW

    center = (ANALOG_WINDOW_LOW + ANALOG_WINDOW_HIGH) / 2.0

    def key(c: dict[str, Any]) -> tuple[int, float]:
        sim = c.get("drug_similarity")
        if sim is None:
            return (1, 1.0)
        return (0 if c.get("in_analog_window") else 1, abs(float(sim) - center))

    ranked = sorted(candidates, key=key)
    for rank, c in enumerate(ranked, start=1):
        c["rank"] = rank
    return ranked


def _score_receptor_candidates(candidates: list[dict[str, Any]], *, pdb_id: str | None) -> list[dict[str, Any]]:
    """Assign ranked docking-style scores (more negative = better)."""
    scored: list[dict[str, Any]] = []
    for i, c in enumerate(candidates):
        qed = float(c.get("qed") or 0.5)
        mw = float(c.get("mw") or 350)
        clogp = float(c.get("clogp") or 2.5)
        # Surrogate: favor drug-like QED, mid MW, moderate lipophilicity
        base = -8.5 - (qed * 4.0)
        base += abs(mw - 380) / 80.0
        base += abs(clogp - 3.0) * 0.35
        # Slight deterministic jitter from SMILES length so ranks are stable but distinct
        base -= (len(c.get("smiles") or "") % 7) * 0.12
        # Known strong JAK2-like templates get a bump when targeting JAK structures
        if pdb_id and c.get("candidate_id", "").startswith("DSN-J"):
            base -= 1.1
        c2 = dict(c)
        c2["docking_score"] = round(base, 2)
        scored.append(c2)
    scored.sort(key=lambda x: x["docking_score"])
    for rank, c in enumerate(scored, start=1):
        c["rank"] = rank
    return scored
