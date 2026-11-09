"""Decide when a scientist's message is an explanation or a blocked calculation.

Tool execution stays downstream. This gate refuses a lookup or a similarity
claim when the question does not ask for one, or when the inputs do not exist.
"""

from __future__ import annotations

import math
import re
from typing import Any


_EXPLAIN = re.compile(
    r"\b(what(?:'s| is| does| do)?|explain|mean(?:s|ing)?|define|definition|corresponds?|tell me about)\b",
    re.I,
)
_PCHEMBL = re.compile(
    r"p\s*-?\s*chembl(?:\s+value)?(?:\s+(?:of|is|=|:))?\s*(\d+(?:\.\d+)?)?",
    re.I,
)
_LIPINSKI = re.compile(r"lipinski|rule of five", re.I)
_NOVELTY = re.compile(r"\b(novel|novelty|tanimoto|similar(?:ity)?)\b", re.I)


def asks_novelty(query: str) -> bool:
    return bool(_NOVELTY.search(query or ""))


def is_scientific_explanation(query: str) -> bool:
    text = query or ""
    if not _EXPLAIN.search(text):
        return False
    return bool(_PCHEMBL.search(text) or _LIPINSKI.search(text))


def _molar_phrase(pchembl: float) -> str:
    molar = 10 ** (-pchembl)
    nanomolar = molar * 1e9
    if nanomolar >= 1000:
        return f"{nanomolar / 1000:.1f} µM"
    if nanomolar >= 1:
        return f"{nanomolar:.1f} nM"
    return f"{nanomolar * 1000:.1f} pM"


def explain_pchembl(value: float) -> str:
    shown = f"{value:.2f}".rstrip("0").rstrip(".")
    concentration = _molar_phrase(value)
    return (
        f"A pChEMBL value of {shown} corresponds to approximately {concentration} "
        "for an eligible standardized activity measurement. "
        "pChEMBL is the negative base-10 logarithm of that concentration in molar units, "
        "so a higher value is a lower concentration and, within a comparable assay, a stronger measured potency or affinity. "
        "Assay type, species, and experimental conditions change how the number should be read. "
        "This explains the scale. No compounds were retrieved."
    )


def explanation_result(query: str) -> dict[str, Any] | None:
    if not is_scientific_explanation(query):
        return None
    text = query or ""
    if _PCHEMBL.search(text):
        match = _PCHEMBL.search(text)
        raw = match.group(1) if match else None
        if raw is None:
            narrative = (
                "pChEMBL is the negative base-10 logarithm of a standardized molar activity, "
                "such as an IC50, EC50, Ki, or Kd. A value of 6 is 1 µM, 7 is about 100 nM, and 9 is 1 nM. "
                "A higher value generally means a stronger measured potency or affinity, and only within a comparable assay. "
                "This explains the scale. No compounds were retrieved."
            )
            summary = "pChEMBL is a logarithmic potency scale."
            value = None
        else:
            value = float(raw)
            if not math.isfinite(value) or value <= 0 or value > 15:
                narrative = (
                    f"{raw} is outside the range used for a pChEMBL activity. "
                    "A usable value is a positive number on the negative-log molar scale, commonly between about 4 and 11. "
                    "No compounds were retrieved."
                )
                summary = "That pChEMBL value is outside the usual activity scale."
            else:
                narrative = explain_pchembl(value)
                summary = f"pChEMBL {value:.2f} is about {_molar_phrase(value)}."
        return {
            "capability": "EXPLAIN",
            "capability_name": "Scientific explanation",
            "summary": summary,
            "narrative": narrative,
            "intent_detail": {
                "primaryIntent": "SCIENTIFIC_EXPLANATION",
                "scientificConcept": "pChEMBL",
                "numericValue": value,
                "requiresExternalTool": False,
                "requiresMoleculeGeneration": False,
                "requiresCompoundRetrieval": False,
            },
            "provenance": {
                "kind": "explanation",
                "status": "derived",
                "source": "pChEMBL definition, negative log10 of a molar concentration",
                "tool": None,
            },
            "tools_used": [],
            "parameters": {"concept": "pChEMBL", "value": value},
        }
    narrative = (
        "Lipinski's rule of five is a guideline for oral small-molecule drug-likeness: "
        "molecular weight under 500, a calculated logP under 5, no more than 5 hydrogen-bond donors, "
        "and no more than 10 hydrogen-bond acceptors. "
        "It is a filter, not a measurement of potency, and many real drugs sit outside it. "
        "No compounds were retrieved."
    )
    return {
        "capability": "EXPLAIN",
        "capability_name": "Scientific explanation",
        "summary": "Lipinski's rule of five is a drug-likeness guideline.",
        "narrative": narrative,
        "intent_detail": {
            "primaryIntent": "SCIENTIFIC_EXPLANATION",
            "scientificConcept": "Lipinski rule of five",
            "requiresExternalTool": False,
            "requiresMoleculeGeneration": False,
            "requiresCompoundRetrieval": False,
        },
        "provenance": {"kind": "explanation", "status": "derived", "source": "medicinal chemistry definition", "tool": None},
        "tools_used": [],
        "parameters": {"concept": "Lipinski"},
    }


def novelty_precondition(query: str, session: dict[str, Any]) -> dict[str, Any] | None:
    """Block a similarity claim until both sides of the comparison exist."""
    if not asks_novelty(query):
        return None
    candidates = [row for row in (session.get("candidates") or []) if row.get("smiles")]
    actives = [row for row in (session.get("actives") or []) if row.get("smiles") and row.get("source") != "demo_curated"]
    target = session.get("target") or {}
    established = bool(target.get("gene_symbol") or target.get("uniprot_id") or session.get("structures"))
    if not candidates:
        if established:
            narrative = (
                "No candidate molecules have been designed in this session. "
                "We have established the target, but molecular novelty cannot yet be evaluated. "
                "Would you like to retrieve known ligands or begin a molecular design campaign?"
            )
        else:
            narrative = (
                "No candidate molecules have been designed in this session, and no target is selected. "
                "Molecular novelty cannot yet be evaluated. "
                "Name the protein first, then retrieve known ligands or begin a design campaign."
            )
        summary = "Novelty cannot be evaluated until candidate molecules exist."
    elif not actives:
        narrative = (
            "Candidate molecules are stored, but this session has no reference ligand set from a live retrieval. "
            "A similarity calculation needs that reference collection. "
            "Would you like to retrieve known ligands for this target?"
        )
        summary = "Novelty cannot be evaluated until a reference ligand set is retrieved."
    else:
        return None
    return {
        "capability": "PRECONDITION",
        "capability_name": "Scientific prerequisite",
        "summary": summary,
        "narrative": narrative,
        "intent_detail": {
            "primaryIntent": "SIMILARITY_ASSESSMENT",
            "requiresExternalTool": False,
            "blocked": True,
            "missing": "candidates" if not candidates else "reference_ligands",
        },
        "provenance": {"kind": "precondition", "status": "not_run", "tool": None},
        "tools_used": ["Session"],
        "parameters": {
            "candidates": len(candidates),
            "reference_ligands": len(actives),
            "target": target.get("gene_symbol"),
        },
    }


def early_scientific_result(query: str, session: dict[str, Any]) -> dict[str, Any] | None:
    explained = explanation_result(query)
    if explained:
        return explained
    return novelty_precondition(query, session)
