"""Stop a calculation when the session does not contain its inputs.

Missing molecules, structures, and reference sets stay missing.
Demonstration records are not filled in.
"""

from __future__ import annotations

from typing import Any

from app.services.chem.research_session import (
    designed_molecules,
    molecule_was_requested,
    reference_actives,
    resolve_molecule,
)
from app.services.chem.scientific_turn import explanation_result, novelty_precondition


def _blocked(
    summary: str,
    narrative: str,
    *,
    intent: str,
    missing: str,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "capability": "PRECONDITION",
        "capability_name": "Scientific prerequisite",
        "summary": summary,
        "narrative": narrative,
        "intent_detail": {
            "primaryIntent": intent,
            "requiresExternalTool": False,
            "blocked": True,
            "missing": missing,
        },
        "provenance": {"kind": "precondition", "status": "not_run", "tool": None, "evidence": "not_run"},
        "tools_used": ["Session"],
        "parameters": parameters or {},
    }


def evaluate_preconditions(
    classification: dict[str, Any],
    query: str,
    session: dict[str, Any],
    *,
    selected_molecule_id: str | None = None,
) -> dict[str, Any] | None:
    capability = classification.get("capability")
    primary = classification.get("primaryIntent")
    target = session.get("target") or {}
    has_target = bool(target.get("gene_symbol") or target.get("uniprot_id"))

    if capability == "EXPLAIN" or primary == "SCIENTIFIC_EXPLANATION":
        return None

    if capability == "C4" or primary == "SIMILARITY_ASSESSMENT":
        blocked = novelty_precondition(query, session)
        if blocked:
            return blocked
        if not designed_molecules(session):
            return novelty_precondition(
                "Are these molecules novel versus the known ligands?",
                session,
            )
        if not reference_actives(session):
            return novelty_precondition(
                "Are these molecules novel versus the known ligands?",
                session,
            )
        return None

    if capability == "C3":
        if not has_target:
            return _blocked(
                "Molecular design needs a selected target.",
                "No biological target is selected, so a generation campaign cannot start. "
                "Name the protein you want to design against.",
                intent="MOLECULE_GENERATION",
                missing="target",
            )
        return None

    if capability == "OPT":
        molecule = resolve_molecule(session, query, selected_molecule_id)
        if molecule is None:
            stored = designed_molecules(session)
            if not stored:
                return _blocked(
                    "There is no candidate to optimize.",
                    "No candidate molecules have been generated in this session, so there is nothing to modify. "
                    "A molecule mentioned in the question is not treated as a designed structure.",
                    intent="LEAD_OPTIMIZATION",
                    missing="candidate",
                )
            which = classification.get("moleculeIndex")
            if which:
                return _blocked(
                    "That candidate is not in this session.",
                    f"Molecule {which} is not among the {len(stored)} stored candidates. "
                    "Choose one of the generated structures.",
                    intent="LEAD_OPTIMIZATION",
                    missing="candidate_index",
                    parameters={"requested_index": which, "stored": len(stored)},
                )
            return _blocked(
                "No molecule is selected.",
                "Name the candidate, for example molecule 1, or select it in the workspace. "
                "The wording alone was not treated as a structure.",
                intent="LEAD_OPTIMIZATION",
                missing="selection",
                parameters={"stored": len(stored)},
            )
        return None

    if capability == "TABLE":
        if not designed_molecules(session):
            return _blocked(
                "There are no designed molecules to put in a table.",
                "No designed molecules are stored, so a table of SMILES, bioactivity, and properties was not built. "
                "Generate candidates first. Predicted bioactivity was not invented.",
                intent="ADMET",
                missing="candidates",
            )
        return None

    if capability == "ADMET":
        molecule = resolve_molecule(session, query, selected_molecule_id)
        if molecule is None and not (session.get("last_smiles") or ""):
            return _blocked(
                "ADMET needs a molecular structure.",
                "No valid candidate is selected. Physicochemical descriptors cannot be calculated "
                "until a generated or retrieved structure is in the session.",
                intent="ADMET",
                missing="molecule",
            )
        return None

    if capability == "DOCK":
        molecule = resolve_molecule(session, query, selected_molecule_id)
        smiles = (molecule or {}).get("smiles") or session.get("last_smiles")
        pdb_id = session.get("last_pdb_id")
        missing = []
        if not smiles:
            missing.append("a valid ligand structure")
        if not pdb_id:
            missing.append("a selected protein structure")
        missing.append("a prepared binding region and docking configuration")
        if not smiles or not pdb_id:
            return _blocked(
                "Docking inputs are incomplete.",
                "Docking was not run. It needs " + ", ".join(missing) + ". "
                "No binding score was invented.",
                intent="DOCKING",
                missing="docking_inputs",
                parameters={"has_ligand": bool(smiles), "pdb_id": pdb_id},
            )
        return None

    if capability == "C7":
        molecule = resolve_molecule(session, query, selected_molecule_id) if molecule_was_requested(query) else None
        smiles = (molecule or {}).get("smiles") or session.get("last_smiles")
        if molecule_was_requested(query) and molecule is None:
            smiles = None
        if not smiles:
            return _blocked(
                "Retrosynthesis needs a structure.",
                "No molecular structure is available for a route assessment. "
                "A demonstration structure was not substituted.",
                intent="RETROSYNTHESIS",
                missing="molecule",
            )
        return None

    if capability == "RANK":
        if not designed_molecules(session):
            return _blocked(
                "There are no candidates to rank.",
                "No generated molecules are stored, so a ranking would not refer to real structures. "
                "Generate candidates or select a retrieved series first.",
                intent="SCIENTIFIC_COMPARISON",
                missing="candidates",
            )
        return None

    if capability == "STRUCT":
        if not session.get("docking_results") and not session.get("last_pdb_id"):
            return _blocked(
                "Binding interactions are not in the session.",
                "No docking calculation and no selected structure are stored, so interactions cannot be described. "
                "Nothing was inferred from the model.",
                intent="STRUCTURAL_ANALYSIS",
                missing="structure_or_docking",
            )
        return None

    if capability == "C5":
        if not designed_molecules(session) and not reference_actives(session):
            return _blocked(
                "SAR reasoning needs structures.",
                "No generated molecules and no retrieved ligands are stored. "
                "A motif analysis was not run on invented compounds.",
                intent="SCIENTIFIC_COMPARISON",
                missing="molecules",
            )
        return None

    return None


def explanation_or_none(query: str) -> dict[str, Any] | None:
    return explanation_result(query)
