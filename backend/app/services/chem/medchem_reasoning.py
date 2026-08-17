"""C5 — Medicinal chemistry motif reasoning."""

from __future__ import annotations

import re
from typing import Any

MOTIF_RULES: list[dict[str, Any]] = [
    {
        "id": "hinge_binder",
        "name": "Hinge-binding heterocycle",
        "smarts_or_pattern": r"n1c|c1ncn|\[nH\]",
        "role": "Kinase hinge H-bond donor/acceptor motif common in JAK inhibitors",
        "selectivity_note": "Azole/aminopyrimidine scaffolds often engage hinge residues",
        "refs": [{"title": "JAK inhibitor hinge binding", "doi": "10.1021/jm401480h", "pubmed": "24180699"}],
    },
    {
        "id": "sulfonamide",
        "name": "Sulfonamide",
        "smarts_or_pattern": r"S\(=O\)\(=O\)N|S\(N\)\(=O\)=O",
        "role": "Polar solubility handle; sometimes water-displacing in pockets",
        "selectivity_note": "Can improve developability; watch efflux",
        "refs": [{"title": "Sulfonamides in medchem", "doi": None, "pubmed": None}],
    },
    {
        "id": "carboxylic_acid",
        "name": "Carboxylic acid",
        "smarts_or_pattern": r"C\(=O\)O(?!C)|C\(=O\)\[O-\]",
        "role": "Ionic / H-bond anchor; common in GPCR agonists",
        "selectivity_note": "May limit CNS exposure; useful for peripheral targets (e.g. GLP1R)",
        "refs": [{"title": "Acid isosteres", "doi": None, "pubmed": None}],
    },
    {
        "id": "piperazine",
        "name": "Piperazine / morpholine",
        "smarts_or_pattern": r"N1CCN|N1CCOCC1",
        "role": "Basic solubilizing group; linker for aryl hinge binders",
        "selectivity_note": "Modulates pKa and PK; check hERG risk with lipophilic bases",
        "refs": [{"title": "Basic groups and hERG", "doi": None, "pubmed": None}],
    },
    {
        "id": "fluorine",
        "name": "Aryl fluoride",
        "smarts_or_pattern": r"Fc1|c\(F\)|F\)",
        "role": "Metabolic blockade / lipophilicity tuning",
        "selectivity_note": "Often improves metabolic stability",
        "refs": [{"title": "Fluorine in drug design", "doi": None, "pubmed": None}],
    },
]


def _detect_motifs(smiles: str) -> list[str]:
    hits = []
    for rule in MOTIF_RULES:
        if re.search(rule["smarts_or_pattern"], smiles, re.I):
            hits.append(rule["id"])
    return hits


def reason_motifs(
    gene_symbol: str | None,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    gene = gene_symbol or "target"
    important = [m for m in MOTIF_RULES if m["id"] in ("hinge_binder", "piperazine", "sulfonamide", "carboxylic_acid")]
    if (gene or "").upper().startswith("GLP"):
        important = [m for m in MOTIF_RULES if m["id"] in ("carboxylic_acid", "fluorine", "piperazine")]

    matrix = []
    for cand in candidates[:15]:
        smi = cand.get("smiles") or ""
        detected = _detect_motifs(smi)
        matrix.append({
            "candidate_id": cand.get("candidate_id"),
            "smiles": smi,
            "motifs": detected,
            "motif_names": [next(m["name"] for m in MOTIF_RULES if m["id"] == mid) for mid in detected],
        })

    rationale = (
        f"For {gene}, key motifs include: "
        + "; ".join(f"{m['name']} — {m['role']}" for m in important[:4])
        + "."
    )
    refs = []
    for m in important:
        for r in m.get("refs") or []:
            if r not in refs:
                refs.append(r)

    return {
        "capability": "C5",
        "capability_name": "Medicinal Chemistry Reasoning",
        "summary": rationale,
        "narrative": rationale,
        "important_motifs": important,
        "motif_matrix": matrix,
        "references": refs,
        "tools_used": ["Literature", "Substructure rules"],
        "parameters": {"gene": gene, "n_candidates": len(candidates)},
    }
