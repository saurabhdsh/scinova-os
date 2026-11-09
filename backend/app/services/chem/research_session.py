"""Persistent research facts for one Molecular Discovery Studio session.

Legacy fields (target, actives, candidates, cards, messages) stay in place.
This module adds identity, lineage, workflows, and artifact references
without treating a molecule that was only mentioned as a generated structure.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


ENGINE_ORIGINS = {"neural_analog", "neural_smiles_rnn", "lead_optimization"}

MOLECULE_STATES = (
    "proposed",
    "generated",
    "structure_validated",
    "computationally_evaluated",
    "experimentally_tested",
    "rejected",
    "selected",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def empty_research() -> dict[str, Any]:
    return {
        "design_objectives": [],
        "hypotheses": [],
        "decisions": [],
        "pending_workflows": [],
        "completed_workflows": [],
        "artifacts": [],
        "answered_questions": [],
    }


def empty_selection() -> dict[str, Any]:
    return {"molecule_id": None, "pdb_id": None}


def ensure_research(session: dict[str, Any]) -> dict[str, Any]:
    research = session.get("research")
    if not isinstance(research, dict):
        research = empty_research()
        session["research"] = research
    blank = empty_research()
    for key, value in blank.items():
        research.setdefault(key, list(value) if isinstance(value, list) else value)
    if not isinstance(session.get("selection"), dict):
        session["selection"] = empty_selection()
    else:
        session["selection"].setdefault("molecule_id", None)
        session["selection"].setdefault("pdb_id", None)
    if not isinstance(session.get("workflows"), list):
        session["workflows"] = []
    session.setdefault("messages", [])
    session.setdefault("candidates", [])
    session.setdefault("actives", [])
    session.setdefault("structures", [])
    return session


def identify_structure(smiles: str) -> dict[str, Any]:
    """Canonical identity. Invalid structures stay invalid instead of being repaired."""
    raw = (smiles or "").strip()
    record: dict[str, Any] = {
        "input_smiles": raw,
        "canonical_smiles": None,
        "isomeric_smiles": None,
        "inchi": None,
        "inchikey": None,
        "valid": False,
    }
    if not raw:
        return record
    try:
        from rdkit import Chem
        from rdkit.Chem import inchi as rdkinchi
    except ImportError:
        record["canonical_smiles"] = raw
        record["valid"] = False
        record["identity_note"] = "RDKit is unavailable, so the structure was not validated."
        return record
    mol = Chem.MolFromSmiles(raw)
    if mol is None:
        return record
    try:
        Chem.SanitizeMol(mol)
    except Exception:
        return record
    record["valid"] = True
    record["canonical_smiles"] = Chem.MolToSmiles(mol, isomericSmiles=False)
    record["isomeric_smiles"] = Chem.MolToSmiles(mol, isomericSmiles=True)
    try:
        record["inchi"] = rdkinchi.MolToInchi(mol)
        record["inchikey"] = rdkinchi.MolToInchiKey(mol)
    except Exception:
        record["inchi"] = None
        record["inchikey"] = None
    return record


def stamp_molecule(row: dict[str, Any], *, state: str = "generated") -> dict[str, Any] | None:
    """Attach a real identity. Drop rows the generator did not execute or RDKit rejects."""
    origin = row.get("origin") or ""
    if origin not in ENGINE_ORIGINS:
        return None
    identity = identify_structure(row.get("smiles") or "")
    if not identity.get("valid"):
        return None
    stamped = dict(row)
    stamped["smiles"] = identity["isomeric_smiles"] or identity["canonical_smiles"]
    stamped["canonical_smiles"] = identity["canonical_smiles"]
    stamped["isomeric_smiles"] = identity["isomeric_smiles"]
    stamped["inchi"] = identity.get("inchi")
    stamped["inchikey"] = identity.get("inchikey")
    stamped["input_smiles"] = identity["input_smiles"]
    stamped["state"] = state if state in MOLECULE_STATES else "generated"
    stamped["evidence"] = "generated" if origin != "lead_optimization" else "predicted"
    stamped.setdefault("lineage", [])
    return stamped


def reference_actives(session: dict[str, Any]) -> list[dict[str, Any]]:
    """Live reference ligands only. Placeholder rows are not a reference set."""
    rows = []
    for row in session.get("actives") or []:
        if not row.get("smiles"):
            continue
        if row.get("source") == "demo_curated" or row.get("evidence") == "illustrative":
            continue
        rows.append(row)
    return rows


def designed_molecules(session: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in session.get("candidates") or []:
        if not row.get("smiles"):
            continue
        if row.get("origin") not in ENGINE_ORIGINS and not row.get("inchikey") and not row.get("canonical_smiles"):
            continue
        rows.append(row)
    return rows


def resolve_molecule(session: dict[str, Any], query: str, selected_id: str | None = None) -> dict[str, Any] | None:
    """Resolve 'molecule 3', 'candidate 3', or the clicked selection. Index is 1-based."""
    import re

    candidates = [row for row in (session.get("candidates") or []) if row.get("smiles")]
    by_id = {row.get("candidate_id"): row for row in candidates if row.get("candidate_id")}
    chosen = selected_id or (session.get("selection") or {}).get("molecule_id")
    text = query or ""
    ordinal = re.search(r"\b(?:molecule|candidate|analogue|analog)\s+(\d+)\b", text, re.I)
    if ordinal:
        index = int(ordinal.group(1))
        if 1 <= index <= len(candidates):
            return candidates[index - 1]
        return None
    words = {
        "first": 1,
        "second": 2,
        "third": 3,
        "fourth": 4,
        "fifth": 5,
    }
    named = re.search(r"\bthe (first|second|third|fourth|fifth) (?:candidate|molecule)\b", text, re.I)
    if named:
        index = words[named.group(1).lower()]
        if 1 <= index <= len(candidates):
            return candidates[index - 1]
        return None
    if chosen and chosen in by_id and re.search(r"\b(this|that|the selected|it)\b", text, re.I):
        return by_id[chosen]
    if chosen and chosen in by_id and not ordinal:
        return by_id[chosen] if re.search(r"\b(this molecule|selected molecule)\b", text, re.I) else None
    return None


def molecule_was_requested(query: str) -> bool:
    import re

    return bool(re.search(
        r"\b(?:molecule|candidate|analogue|analog)\s+\d+\b|\bthe (?:first|second|third|fourth|fifth) (?:candidate|molecule)\b|\b(this|selected) molecule\b",
        query or "",
        re.I,
    ))


def add_artifact(session: dict[str, Any], **fields: Any) -> dict[str, Any]:
    ensure_research(session)
    artifact = {
        "artifact_id": str(uuid.uuid4()),
        "created_at": _now(),
        **fields,
    }
    session["research"]["artifacts"].append(artifact)
    return artifact


def add_decision(session: dict[str, Any], statement: str, *, basis: str) -> None:
    ensure_research(session)
    session["research"]["decisions"].append({
        "decision_id": str(uuid.uuid4()),
        "statement": statement,
        "basis": basis,
        "at": _now(),
    })


def record_answer(session: dict[str, Any], query: str, intent: str) -> None:
    ensure_research(session)
    session["research"]["answered_questions"].append({
        "query": query,
        "intent": intent,
        "at": _now(),
    })
