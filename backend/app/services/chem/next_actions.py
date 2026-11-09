"""Next steps that follow what the session actually contains."""

from __future__ import annotations

from typing import Any

from app.services.chem.research_session import designed_molecules, reference_actives


def next_actions(session: dict[str, Any]) -> list[dict[str, Any]]:
    target = session.get("target") or {}
    gene = target.get("gene_symbol") or "this target"
    glp = gene.upper().startswith("GLP")
    ligand_word = "agonists" if glp else "ligands"
    actions: list[dict[str, Any]] = []
    actives = reference_actives(session)
    designed = designed_molecules(session)
    structures = session.get("structures") or []

    if not target.get("gene_symbol") and not target.get("uniprot_id"):
        return [{
            "label": "Choose a protein",
            "query": "What are the available crystal structures of GLP1R in the Protein Data Bank?",
            "requires": None,
        }]

    if not structures:
        actions.append({
            "label": "Explore receptor structures",
            "query": f"What are the available crystal structures of {gene} in the Protein Data Bank?",
            "requires": None,
        })
    if not actives:
        actions.append({
            "label": f"Retrieve known {ligand_word}",
            "query": f"Retrieve known {gene} {ligand_word} from ChEMBL.",
            "requires": None,
        })
    elif glp:
        actions.append({
            "label": "Separate peptides from small molecules",
            "query": f"Which of the retrieved {gene} ligands are peptides, and which are small molecules?",
            "requires": None,
        })
    if structures and not session.get("last_pocket"):
        actions.append({
            "label": "Inspect a binding pocket",
            "query": f"Analyze pockets for {session.get('last_pdb_id') or structures[0].get('pdb_id')}.",
            "requires": None,
        })
    if actives and not designed:
        actions.append({
            "label": "Start a design campaign",
            "query": f"Generate 12 candidates for {gene} using the retrieved ligands as context.",
            "requires": None,
        })
    if designed and not actives:
        actions.append({
            "label": "Novelty needs a reference set",
            "query": f"Retrieve known {gene} {ligand_word} from ChEMBL.",
            "requires": "reference ligands are not stored yet",
        })
    if designed and actives and not (session.get("novelty") or []):
        actions.append({
            "label": "Assess structural novelty",
            "query": "Are the designed molecules novel versus the retrieved ligands?",
            "requires": None,
        })
    if designed:
        actions.append({
            "label": "Rank stored candidates",
            "query": "Which five candidates should we investigate first?",
            "requires": None,
        })
    if not designed:
        actions.append({
            "label": "Novelty is not available yet",
            "query": "Are the designed molecules novel versus known ligands?",
            "requires": "no candidates have been generated",
        })
    # Keep the list short and specific.
    seen = set()
    unique = []
    for action in actions:
        if action["label"] in seen:
            continue
        seen.add(action["label"])
        unique.append(action)
    return unique[:4]
