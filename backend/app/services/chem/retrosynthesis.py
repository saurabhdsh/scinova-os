"""C7 — Synthetic feasibility / retrosynthesis (rule-based MVP)."""

from __future__ import annotations

from typing import Any


def assess_synthesis(smiles: str, candidate_id: str | None = None) -> dict[str, Any]:
    smi = (smiles or "").strip()
    complexity = min(1.0, len(smi) / 80)
    # Simple heuristics
    has_amide = "C(=O)N" in smi or "NC(=O)" in smi
    has_biaryl = smi.count("c1") >= 2 or smi.count("C1=") >= 2
    steps = 2 + int(complexity * 4) + (1 if has_biaryl else 0)
    confidence = round(max(0.35, 0.9 - complexity * 0.4), 2)

    if confidence >= 0.7:
        status = "feasible"
    elif confidence >= 0.5:
        status = "challenging"
    else:
        status = "high_complexity"

    # Route tree (simplified)
    intermediates = []
    if has_amide:
        intermediates.append({"id": "I1", "role": "acyl chloride / activated acid", "smiles_hint": "R-COCl"})
        intermediates.append({"id": "I2", "role": "amine coupling partner", "smiles_hint": "R'-NH2"})
    else:
        intermediates.append({"id": "I1", "role": "core scaffold", "smiles_hint": "heterocycle building block"})
        intermediates.append({"id": "I2", "role": "side-chain fragment", "smiles_hint": "aryl halide / amine"})

    route_tree = {
        "root": candidate_id or "product",
        "product_smiles": smi,
        "steps_estimate": steps,
        "children": [
            {
                "id": "step1",
                "reaction": "Amide coupling" if has_amide else "SNAr / cross-coupling",
                "intermediates": intermediates[:1],
            },
            {
                "id": "step2",
                "reaction": "Functional group install / deprotection",
                "intermediates": intermediates[1:] or [{"id": "I2", "role": "protecting group removal"}],
            },
        ],
    }

    summary = (
        f"Synthetic assessment: {status} (~{steps} steps, confidence {confidence}). "
        f"Route highlights {'amide coupling' if has_amide else 'scaffold assembly'} then elaboration."
    )
    return {
        "capability": "C7",
        "capability_name": "Synthetic Feasibility",
        "summary": summary,
        "narrative": summary,
        "route": {
            "status": status,
            "confidence": confidence,
            "steps_estimate": steps,
            "candidate_id": candidate_id,
            "smiles": smi,
            "tree": route_tree,
            "engine": "rule_based_mvp",
        },
        "tools_used": ["Retrosynthesis Engine (MVP)"],
        "parameters": {"smiles": smi},
    }
