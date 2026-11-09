"""Choose the Research Value Chain agent that owns a studio question.

The studio tools still produce the evidence. This bridge only names the
agent from the existing catalog whose stage matches the question.
"""

from __future__ import annotations

import re
from typing import Any

_PATHWAY = re.compile(r"\bpathway\b|biological role|signaling cascade", re.I)
_WHY_ADMET = re.compile(r"\bwhy\b|explainable|structural alert", re.I)
_PKPD = re.compile(r"\bpk\s*/?\s*pd\b|pharmacokinetic|pharmacodynamic", re.I)
_INVIVO = re.compile(r"in[- ]vivo|animal study", re.I)
_TOX = re.compile(r"\btoxicit", re.I)
_SCALE = re.compile(r"scale-?up|process design", re.I)
_STABILITY = re.compile(r"\bstabilit", re.I)
_QBD = re.compile(r"quality by design|\bqbd\b", re.I)
_ADMET = re.compile(r"\badmet\b", re.I)


def select_triggered_agents(
    query: str,
    capability: str | None,
    classification: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """At most two agents. A greeting selects none."""
    text = query or ""
    cap = (capability or "").upper()
    concept = str((classification or {}).get("scientificConcept") or "")
    chosen: list[dict[str, str]] = []

    def add(stage: str, name: str) -> None:
        if len(chosen) >= 2 or any(row["name"] == name for row in chosen):
            return
        chosen.append({"stage": stage, "name": name, "status": "triggered"})

    if _PKPD.search(text):
        add("Preclinical Studies", "PK/PD Modelling Agent")
        return chosen
    if _INVIVO.search(text):
        add("Preclinical Studies", "In-vivo Study Design Agent")
        return chosen
    if _TOX.search(text) and not _ADMET.search(text):
        add("Preclinical Studies", "Toxicity Prediction Agent")
        return chosen
    if _SCALE.search(text):
        add("Early Development & CMC", "Process Design and Scale-up Agent")
        return chosen
    if _STABILITY.search(text) and not _ADMET.search(text):
        add("Early Development & CMC", "Stability Prediction Agent")
        return chosen
    if _QBD.search(text):
        add("Early Development & CMC", "Quality by Design Agent")
        return chosen

    if cap == "ROLE" or (_PATHWAY.search(text) and cap not in {"C1", "C6", "C6D", "C6P"}):
        add("Target Discovery", "Pathway Insight Agent")
        return chosen

    if cap in {"CHAT", "CONTEXT", "CX"}:
        return []
    if cap in {"EXPLAIN", "PRECONDITION"} and "admet" not in concept.lower() and not _ADMET.search(text):
        return []

    if cap in {"C1", "C6", "C6D", "C6P"}:
        add("Target Discovery", "Druggability Finder Agent")
        if _PATHWAY.search(text):
            add("Target Discovery", "Pathway Insight Agent")
    elif cap == "C2":
        add("Target Discovery", "Evidence Scout Agent")
    elif cap in {"C3", "OPT"}:
        add("Lead Identification", "Molecule Generation Agent")
    elif cap == "RANK":
        add("Lead Identification", "Deduplication, Filtering & Hit-Ranking Agent")
    elif cap == "DOCK":
        add("Lead Identification", "Virtual Screening Agent")
    elif cap in {"ADMET", "TABLE"} or "admet" in concept.lower():
        add("Lead Optimization", "ADMET Prediction Agent")
        if _WHY_ADMET.search(text):
            add("Lead Optimization", "Explainable ADMET Agent")
    return chosen
