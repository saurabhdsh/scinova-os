"""Scientific conversation orchestrator.

Every turn is classified, checked against the session, and only then
handed to a specialist. A halted turn is an explanation or a refusal
to calculate. It is not a completed experiment.
"""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.services.chem.intent_engine import classify_scientific_intent
from app.services.chem.lead_optimization import optimize_solubility
from app.services.chem.next_actions import next_actions
from app.services.chem.precondition_engine import evaluate_preconditions, explanation_or_none
from app.services.chem.research_session import (
    add_artifact,
    add_decision,
    designed_molecules,
    ensure_research,
    identify_structure,
    record_answer,
    resolve_molecule,
    stamp_molecule,
)
from app.services.chem.scientific_turn import explanation_result
from app.services.chem.workflow_engine import open_workflow, pending_generation, transition
from app.services.chemoinformatics_service import compute_molecule_properties


def _rankable(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[tuple[dict[str, Any], str]]]:
    from app.services.chem.smiles_rnn import rejection_reason

    usable: list[dict[str, Any]] = []
    held: list[tuple[dict[str, Any], str]] = []
    for row in rows:
        reason = rejection_reason(row.get("smiles") or "")
        if reason:
            held.append((row, reason))
        else:
            usable.append(row)
    return usable, held


def _reference_fingerprints(session: dict[str, Any]):
    from app.services.chem.novelty import _is_peptide, _morgan_fp

    prints = []
    for active in session.get("actives") or []:
        if active.get("relation") in {"nucleotide probe", "peptide"}:
            continue
        smiles = active.get("smiles") or ""
        if not smiles or _is_peptide(smiles):
            continue
        fingerprint = _morgan_fp(smiles)
        if fingerprint is not None:
            prints.append(fingerprint)
    return prints


def _rank_key(row: dict[str, Any], references) -> tuple[float, float]:
    from app.services.chem.novelty import _morgan_fp, _tanimoto

    qed = row.get("qed")
    qed_value = float(qed) if isinstance(qed, (int, float)) else -1.0
    if not references:
        return (0.0, qed_value)
    fingerprint = _morgan_fp(row.get("smiles") or "")
    if fingerprint is None:
        row["_ligand_similarity"] = 0.0
        return (0.0, qed_value)
    similarity = max(_tanimoto(fingerprint, ref) for ref in references)
    row["_ligand_similarity"] = similarity
    return (similarity, qed_value)


class ScientificConversationOrchestrator:
    """Coordinates one scientist turn. Tool execution stays in the caller."""

    def plan(
        self,
        query: str,
        session: dict[str, Any],
        *,
        selected_molecule_id: str | None = None,
    ) -> dict[str, Any]:
        ensure_research(session)
        if selected_molecule_id:
            session.setdefault("selection", {})["molecule_id"] = selected_molecule_id
        classification = classify_scientific_intent(query, session)
        blocked = evaluate_preconditions(
            classification,
            query,
            session,
            selected_molecule_id=selected_molecule_id,
        )
        if blocked:
            blocked["intent_detail"] = {**classification, **(blocked.get("intent_detail") or {})}
            return {"classification": classification, "capability": "PRECONDITION", "halt": blocked}

        capability = classification.get("capability")
        if capability == "EXPLAIN":
            explained = self._explain(query, classification)
            return {"classification": classification, "capability": "EXPLAIN", "halt": explained}
        if capability == "OPT":
            return {
                "classification": classification,
                "capability": "OPT",
                "halt": optimize_solubility(session, query, selected_molecule_id=selected_molecule_id),
            }
        if capability == "TABLE":
            return {
                "classification": classification,
                "capability": "TABLE",
                "halt": self._design_table(session),
            }
        if capability == "ADMET":
            return {
                "classification": classification,
                "capability": "ADMET",
                "halt": self._admet(query, session, selected_molecule_id),
            }
        if capability == "DOCK":
            return {
                "classification": classification,
                "capability": "DOCK",
                "halt": self._dock(query, session, selected_molecule_id),
            }
        if capability == "RANK":
            return {
                "classification": classification,
                "capability": "RANK",
                "halt": self._rank(query, session, classification.get("count")),
            }
        if capability == "STRUCT":
            return {
                "classification": classification,
                "capability": "STRUCT",
                "halt": self._interactions(session),
            }
        if capability == "C3":
            count = int(classification.get("count") or 12)
            threshold = int(getattr(settings, "chem_campaign_approval_above", 24))
            if count > threshold and not self._is_approval(query, session):
                proposal = self._proposal(session, count)
                return {"classification": classification, "capability": "APPROVAL", "halt": proposal}
        if capability == "APPROVE":
            waiting = pending_generation(session)
            count = int((waiting or {}).get("parameters", {}).get("count") or 12)
            return {
                "classification": classification,
                "capability": "C3",
                "halt": None,
                "approved": True,
                "generation_count": count,
                "workflow_id": (waiting or {}).get("workflow_id"),
            }
        return {
            "classification": classification,
            "capability": capability,
            "halt": None,
            "modality": classification.get("modality"),
            "generation_count": classification.get("count"),
        }

    def _is_approval(self, query: str, session: dict[str, Any]) -> bool:
        import re

        return bool(pending_generation(session) and re.search(r"\b(approve|proceed|yes,? run)\b", query or "", re.I))

    def _explain(self, query: str, classification: dict[str, Any]) -> dict[str, Any]:
        explained = explanation_or_none(query) or explanation_result(query)
        if explained:
            explained["intent_detail"] = classification
            return explained
        concept = classification.get("scientificConcept") or "that concept"
        narrative = _concept_narrative(concept)
        return {
            "capability": "EXPLAIN",
            "capability_name": "Scientific explanation",
            "summary": f"Explanation of {concept}.",
            "narrative": narrative,
            "intent_detail": classification,
            "provenance": {"kind": "explanation", "status": "derived", "evidence": "derived", "tool": None},
            "tools_used": [],
            "parameters": {"concept": concept},
        }

    def _proposal(self, session: dict[str, Any], count: int) -> dict[str, Any]:
        target = session.get("target") or {}
        workflow = open_workflow(
            session,
            kind="molecule_generation",
            parameters={"count": count, "gene": target.get("gene_symbol")},
            status="READY",
        )
        add_decision(
            session,
            f"Generation of {count} molecules is waiting for approval.",
            basis="count exceeds the configured campaign threshold",
        )
        gene = target.get("gene_symbol") or "the selected target"
        return {
            "capability": "APPROVAL",
            "capability_name": "Workflow approval",
            "summary": f"Generation of {count} molecules is ready and has not been run.",
            "narrative": (
                f"A campaign of {count} candidates for {gene} is above the approval threshold. "
                "No molecules were generated. Reply that you approve the generation campaign to run the engine."
            ),
            "workflow": workflow,
            "intent_detail": {"primaryIntent": "MOLECULE_GENERATION", "blocked": False, "awaitingApproval": True},
            "provenance": {"kind": "workflow", "status": "ready", "evidence": "not_run", "tool": None},
            "tools_used": ["Workflow"],
            "parameters": workflow.get("parameters"),
        }

    def _design_table(self, session: dict[str, Any]) -> dict[str, Any]:
        rows = []
        for molecule in designed_molecules(session):
            props = compute_molecule_properties(molecule.get("smiles") or "")
            bioactivity = molecule.get("predicted_bioactivity")
            rows.append({
                "candidate_id": molecule.get("candidate_id"),
                "smiles": molecule.get("smiles"),
                "predicted_bioactivity": bioactivity if bioactivity not in (None, "") else "not predicted",
                "molecular_weight": props.get("molecular_weight"),
                "logp": props.get("logp"),
                "tpsa": props.get("tpsa"),
                "h_bond_donors": props.get("h_bond_donors"),
                "h_bond_acceptors": props.get("h_bond_acceptors"),
                "rotatable_bonds": props.get("rotatable_bonds"),
                "qed": props.get("qed"),
                "lipinski_violations": props.get("lipinski_violations"),
            })
        narrative = (
            f"The table has {len(rows)} designed molecules. "
            "Each row shows the SMILES string and eight calculated physicochemical properties: "
            "molecular weight, logP, TPSA, hydrogen-bond donors, hydrogen-bond acceptors, "
            "rotatable bonds, QED, and Lipinski violations. "
            "Predicted bioactivity is marked not predicted because no bioactivity model was run."
        )
        return {
            "capability": "TABLE",
            "capability_name": "Designed molecule table",
            "summary": f"Table of {len(rows)} designed molecules. Predicted bioactivity was not calculated.",
            "narrative": narrative,
            "property_table": rows,
            "tools_used": ["RDKit"],
            "provenance": {
                "kind": "calculation",
                "status": "completed",
                "evidence": "calculated",
                "tool": "RDKit",
                "model": None,
            },
            "parameters": {"rows": len(rows), "bioactivity_model": None},
        }

    def _admet(self, query: str, session: dict[str, Any], selected_molecule_id: str | None) -> dict[str, Any]:
        molecule = resolve_molecule(session, query, selected_molecule_id)
        smiles = (molecule or {}).get("smiles") or session.get("last_smiles")
        props = compute_molecule_properties(smiles or "")
        if not props.get("valid"):
            return {
                "capability": "ADMET",
                "capability_name": "ADMET descriptors",
                "summary": "The structure could not be evaluated.",
                "narrative": "RDKit did not accept the structure, so no properties were reported.",
                "tools_used": ["RDKit"],
                "provenance": {"kind": "calculation", "status": "failed", "evidence": "calculated", "tool": "RDKit"},
            }
        values = [
            ("molecular weight", props.get("molecular_weight")),
            ("logP", props.get("logp")),
            ("TPSA", props.get("tpsa")),
            ("hydrogen-bond donors", props.get("h_bond_donors")),
            ("hydrogen-bond acceptors", props.get("h_bond_acceptors")),
            ("rotatable bonds", props.get("rotatable_bonds")),
            ("QED", props.get("qed")),
            ("Lipinski violations", props.get("lipinski_violations")),
        ]
        listed = [f"{name} {value}" for name, value in values if value is not None]
        who = molecule.get("candidate_id") if molecule else "the selected structure"
        narrative = (
            f"{len(listed)} physicochemical properties were calculated for {who}: "
            + ", ".join(listed)
            + ". These are calculated from the structure. "
            "They are not measured ADMET endpoints, and no separate predictive ADMET model was executed."
        )
        return {
            "capability": "ADMET",
            "capability_name": "ADMET descriptors",
            "summary": f"{len(listed)} physicochemical properties were calculated. No predictive ADMET model was run.",
            "narrative": narrative,
            "properties": props,
            "tools_used": ["RDKit"],
            "provenance": {
                "kind": "calculation",
                "status": "completed",
                "evidence": "calculated",
                "tool": "RDKit",
                "model": None,
            },
            "parameters": {"smiles": smiles},
        }

    def _dock(self, query: str, session: dict[str, Any], selected_molecule_id: str | None) -> dict[str, Any]:
        """Do not report an affinity unless Vina actually finishes on a prepared ligand."""
        from app.services.docking_service import vina_available

        molecule = resolve_molecule(session, query, selected_molecule_id)
        smiles = (molecule or {}).get("smiles") or session.get("last_smiles")
        pdb_id = session.get("last_pdb_id")
        if not vina_available() or not settings.vina_receptor_pdbqt:
            return {
                "capability": "DOCK",
                "capability_name": "Docking",
                "summary": "Docking was not run.",
                "narrative": (
                    "A docking score was not produced. AutoDock Vina is not configured with a prepared receptor, "
                    f"and ligand preparation for {pdb_id or 'a selected structure'} is not available. "
                    "Shape similarity was not substituted for a docking result."
                ),
                "tools_used": ["Docking configuration"],
                "provenance": {"kind": "docking", "status": "not_run", "evidence": "not_run", "tool": "AutoDock Vina"},
                "parameters": {"pdb_id": pdb_id, "has_ligand": bool(smiles)},
            }
        from app.services.docking_service import run_vina_docking

        outcome = run_vina_docking(smiles)
        if outcome.get("status") != "completed" or outcome.get("binding_affinity_kcal_mol") is None:
            return {
                "capability": "DOCK",
                "capability_name": "Docking",
                "summary": "The docking engine did not return a score.",
                "narrative": (
                    "Vina was invoked and did not return a completed affinity. "
                    "No score was filled in. "
                    + str(outcome.get("reason") or outcome.get("note") or outcome.get("status") or "")
                ).strip(),
                "docking": outcome,
                "tools_used": ["AutoDock Vina"],
                "provenance": {"kind": "docking", "status": "failed", "evidence": "not_run", "tool": "AutoDock Vina"},
            }
        return {
            "capability": "DOCK",
            "capability_name": "Docking",
            "summary": f"Vina reported {outcome.get('binding_affinity_kcal_mol')} kcal/mol. This is a predicted score.",
            "narrative": (
                "AutoDock Vina completed. The affinity is a predicted docking score, not a measured potency."
            ),
            "docking": outcome,
            "tools_used": ["AutoDock Vina"],
            "provenance": {"kind": "docking", "status": "completed", "evidence": "predicted", "tool": "AutoDock Vina"},
        }

    def _rank(self, query: str, session: dict[str, Any], count: int | None) -> dict[str, Any]:
        import re

        limit = count or 5
        match = re.search(r"\btop\s+(\d+)\b", query or "", re.I)
        if match:
            limit = int(match.group(1))
        limit = max(1, min(limit, 20))
        rows = designed_molecules(session)
        usable, held = _rankable(rows)
        references = _reference_fingerprints(session)
        ranked = sorted(usable, key=lambda row: _rank_key(row, references), reverse=True)[:limit]
        lines = []
        for index, row in enumerate(ranked, start=1):
            qed = row.get("qed")
            shown = f"{qed:.2f}" if isinstance(qed, (int, float)) else "not calculated"
            similarity = row.get("_ligand_similarity")
            if isinstance(similarity, float):
                lines.append(
                    f"{index}. {row.get('candidate_id')} — Tanimoto {similarity:.3f} "
                    f"to the nearest stored small-molecule activity, calculated QED {shown}."
                )
            else:
                lines.append(f"{index}. {row.get('candidate_id')} — calculated QED {shown}.")
        if references:
            basis = (
                "Ranking uses Morgan fingerprint similarity (radius 2, 2048 bits) to the stored "
                "small-molecule activities, then calculated QED as a tie-break. "
                "Similarity is not potency, and QED is not a measured activity on this target."
            )
            criterion = "ligand_similarity_then_qed"
            tool = "RDKit Morgan/Tanimoto, RDKit QED"
        else:
            basis = (
                "No small-molecule activities are stored, so ranking uses calculated QED only. "
                "QED is a drug-likeness score, not measured potency."
            )
            criterion = "qed"
            tool = "RDKit QED"
        held_note = ""
        if held:
            held_note = (
                f" {len(held)} stored structure(s) were set aside because they contain a radical "
                "or a ring with five or more nitrogens: "
                + ", ".join(f"{row.get('candidate_id')} ({reason})" for row, reason in held[:8])
                + "."
            )
        narrative = basis + held_note + "\n" + "\n".join(lines)
        for row in ranked:
            row.pop("_ligand_similarity", None)
        return {
            "capability": "RANK",
            "capability_name": "Candidate ranking",
            "summary": f"Top {len(ranked)} candidates by {criterion.replace('_', ' ')}.",
            "narrative": narrative,
            "candidates": ranked,
            "tools_used": ["Session", tool],
            "provenance": {"kind": "ranking", "status": "derived", "evidence": "calculated", "tool": tool},
            "parameters": {"limit": limit, "criterion": criterion, "set_aside": len(held)},
        }

    def _interactions(self, session: dict[str, Any]) -> dict[str, Any]:
        pdb_id = session.get("last_pdb_id")
        if session.get("docking_results"):
            narrative = (
                f"Stored docking records exist for {pdb_id or 'the selected structure'}. "
                "Open those records for the poses that were actually calculated. "
                "Interactions that were not in the output are not described here."
            )
        else:
            narrative = (
                f"Structure {pdb_id} is selected, but no docking or interaction calculation has been stored. "
                "Binding interactions were not inferred."
            )
        return {
            "capability": "STRUCT",
            "capability_name": "Structural analysis",
            "summary": "No interaction list was invented.",
            "narrative": narrative,
            "tools_used": ["Session"],
            "provenance": {"kind": "structural", "status": "not_run", "evidence": "not_run", "tool": None},
            "parameters": {"pdb_id": pdb_id},
        }

    def remember(
        self,
        session: dict[str, Any],
        *,
        query: str,
        capability: str,
        result: dict[str, Any],
    ) -> None:
        ensure_research(session)
        record_answer(session, query, capability)
        provenance = result.get("provenance") or {}
        status = provenance.get("status") or "completed"
        if capability in {"C2", "C3", "C4", "OPT", "ADMET", "DOCK", "C7"} and status not in {"not_run", "ready"}:
            kind = {
                "C2": "known_ligands",
                "C3": "molecule_generation",
                "C4": "similarity",
                "OPT": "lead_optimization",
                "ADMET": "admet",
                "DOCK": "docking",
                "C7": "retrosynthesis",
            }[capability]
            workflow = open_workflow(session, kind=kind, parameters=result.get("parameters") or {}, status="RUNNING")
            final = "COMPLETED" if status in {"completed", "ok", "derived", "predicted", "calculated"} or provenance.get("evidence") not in {None, "not_run"} else "FAILED"
            if status in {"failed", "unavailable", "empty"}:
                final = "FAILED" if status == "failed" else "COMPLETED"
            transition(session, workflow["workflow_id"], "COMPLETED" if final != "FAILED" else "FAILED", note=result.get("summary"))
            add_artifact(
                session,
                kind=kind,
                source=(provenance.get("source") or provenance.get("tool")),
                status=status,
                evidence=provenance.get("evidence") or provenance.get("kind"),
                tool=provenance.get("tool"),
                query=query,
            )
        if capability == "C4" and result.get("novelty"):
            session["novelty"] = result["novelty"]
        if capability == "OPT" and result.get("analogues"):
            existing = list(session.get("candidates") or [])
            ids = {row.get("candidate_id") for row in existing}
            for child in result["analogues"]:
                if child.get("candidate_id") not in ids:
                    existing.append(child)
            session["candidates"] = existing
        if capability == "DOCK" and result.get("docking") and (result.get("provenance") or {}).get("status") == "completed":
            session.setdefault("docking_results", []).append(result["docking"])
        if capability == "ADMET" and result.get("properties"):
            session.setdefault("admet_results", []).append({
                "properties": result["properties"],
                "evidence": "calculated",
            })


def accept_generated(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Keep molecules that a generation engine actually emitted and RDKit accepted."""
    accepted = []
    for row in result.get("candidates") or []:
        stamped = stamp_molecule(row, state="structure_validated")
        if stamped:
            accepted.append(stamped)
    return accepted


def generation_failure(gene: str | None, attempted: int, *, reason: str | None = None) -> dict[str, Any]:
    label = gene or "the selected target"
    if reason == "rdkit":
        summary = f"Generated strings for {label} were not validated."
        narrative = (
            "The generator returned candidate strings, but RDKit is not available to validate them. "
            "Unvalidated structures were not stored, and scaffold placeholders were not substituted."
        )
    else:
        summary = f"No validated molecules were generated for {label}."
        narrative = (
            "The molecular generation engine did not return validated structures. "
            "Scaffold placeholders were not added to the session."
        )
    return {
        "capability": "C3",
        "capability_name": "Neural Molecule Generation",
        "summary": summary,
        "narrative": narrative,
        "candidates": [],
        "neural_count": 0,
        "tools_used": ["SMILES Char-RNN"],
        "provenance": {
            "kind": "generation",
            "status": "failed",
            "evidence": "not_run",
            "tool": "RDKit" if reason == "rdkit" else "SMILES Char-RNN",
            "source": "smiles_char_rnn",
        },
        "parameters": {"gene": gene, "requested": attempted, "reason": reason},
    }


def _concept_narrative(concept: str) -> str:
    key = (concept or "").lower()
    if "tanimoto" in key:
        return (
            "Tanimoto similarity is a coefficient from 0 to 1 between two molecular fingerprints. "
            "The number depends on the fingerprint and the reference set. "
            "It is not a patent or freedom-to-operate determination. "
            "No similarity calculation was run."
        )
    if key == "agonist":
        return (
            "An agonist binds a receptor and increases its signaling. "
            "For a class B receptor such as GLP1R, agonists include peptides and non-peptides, "
            "and they are not inhibitors or antagonists. "
            "No compounds were retrieved."
        )
    if "admet" in key:
        return (
            "I can calculate eight physicochemical properties from a structure: "
            "molecular weight, logP, TPSA, hydrogen-bond donors, hydrogen-bond acceptors, "
            "rotatable bonds, QED, and Lipinski violations. "
            "I cannot predict ADMET endpoints such as absorption, distribution, metabolism, excretion, "
            "clearance, hERG, or toxicity, because no predictive ADMET model is connected. "
            "Ask for the properties of a designed molecule when you want those eight calculated values."
        )
    if key == "antagonist":
        return (
            "An antagonist binds a receptor and blocks activation by an agonist. "
            "It is not the same as an agonist, and a binding assay alone does not prove which one a ligand is. "
            "No compounds were retrieved."
        )
    return (
        f"This is an explanation of {concept}. "
        "No compounds were retrieved and no calculation was run."
    )


def public_session(session: dict[str, Any] | None) -> dict[str, Any]:
    if not session:
        return {}
    ensure_research(session)
    return {
        "id": session.get("id"),
        "target": session.get("target"),
        "last_pdb_id": session.get("last_pdb_id"),
        "last_smiles": session.get("last_smiles"),
        "structures_count": len(session.get("structures") or []),
        "actives_count": len(session.get("actives") or []),
        "candidates_count": len(designed_molecules(session)),
        "cards_count": len(session.get("cards") or []),
        "selection": session.get("selection"),
        "next_actions": next_actions(session),
        "workflows": [
            {"workflow_id": row.get("workflow_id"), "kind": row.get("kind"), "status": row.get("status")}
            for row in session.get("workflows") or []
        ],
    }


def export_session_package(session: dict[str, Any]) -> dict[str, Any]:
    ensure_research(session)
    missing = [
        card.get("card_id")
        for card in session.get("cards") or []
        if not (card.get("narrative") or card.get("answer") or card.get("summary"))
    ]
    molecules = []
    for row in session.get("candidates") or []:
        molecules.append({
            "candidate_id": row.get("candidate_id"),
            "smiles": row.get("smiles"),
            "canonical_smiles": row.get("canonical_smiles"),
            "inchikey": row.get("inchikey"),
            "origin": row.get("origin"),
            "state": row.get("state"),
            "lineage": row.get("lineage") or [],
            "parent_id": row.get("parent_id"),
        })
    return {
        "export_version": 2,
        "session_id": session.get("id"),
        "transcript": session.get("messages") or [],
        "cards": session.get("cards") or [],
        "target": session.get("target"),
        "structures": session.get("structures") or [],
        "known_ligands": session.get("actives") or [],
        "molecules": molecules,
        "novelty": session.get("novelty") or [],
        "workflows": session.get("workflows") or [],
        "research": session.get("research") or {},
        "selection": session.get("selection"),
        "missing_answers": missing,
        "session": session,
    }


def structure_identity_for_actives(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stamped = []
    for row in rows:
        identity = identify_structure(row.get("smiles") or "")
        copied = dict(row)
        if identity.get("valid"):
            copied["canonical_smiles"] = identity.get("canonical_smiles")
            copied["isomeric_smiles"] = identity.get("isomeric_smiles")
            copied["inchikey"] = identity.get("inchikey")
            copied["smiles"] = identity.get("isomeric_smiles") or copied.get("smiles")
        stamped.append(copied)
    return stamped
