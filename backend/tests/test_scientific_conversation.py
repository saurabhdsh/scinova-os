"""Acceptance checks for scientific conversation: intent, evidence, and export."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.chem import session_store
from app.services.chem.intent_engine import classify_scientific_intent
from app.services.chem.chembl_client import activity_relation
from app.services.chem.conversation_orchestrator import ScientificConversationOrchestrator
from app.services.chem.orchestrator import _speak, export_session_json, export_session_markdown, run_chem_query
from app.services.chem.pdb_catalog import experimental_method, other_components
from app.services.chem.smiles_rnn import rejection_reason
from app.services.chem.value_chain_bridge import select_triggered_agents
from app.services.chem.target_intel import build_target_profile, extract_gene_symbol


def _candidate(index: int, smiles: str) -> dict:
    return {
        "candidate_id": f"RNN-{index:02d}",
        "smiles": smiles,
        "origin": "neural_smiles_rnn",
        "qed": round(0.9 - (index * 0.1), 2),
        "state": "generated",
    }


class ScientificConversationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._dir = session_store.SESSIONS_DIR
        session_store.SESSIONS_DIR = Path(self.tmp.name)
        session_store._SESSIONS.clear()

    def tearDown(self):
        session_store.SESSIONS_DIR = self._dir
        session_store._SESSIONS.clear()
        self.tmp.cleanup()

    def _session_with_target(self):
        session = session_store.create_session()
        session_store.update_session(
            session["id"],
            target={"gene_symbol": "GLP1R", "name": "Glucagon-like peptide 1 receptor", "uniprot_id": "P43220"},
            structures=[{"pdb_id": "7KI0", "title": "GLP-1 bound receptor"}],
        )
        return session["id"]

    def test_value_chain_agent_matches_the_question(self):
        structures = select_triggered_agents(
            "What are the available crystal structures of KARS in the Protein Data Bank?",
            "C1",
        )
        self.assertEqual(structures[0]["name"], "Druggability Finder Agent")
        self.assertEqual(structures[0]["stage"], "Target Discovery")
        admet = select_triggered_agents(
            "Can you predicted ADMET properties?",
            "EXPLAIN",
            {"scientificConcept": "ADMET prediction"},
        )
        self.assertEqual(admet[0]["name"], "ADMET Prediction Agent")
        generated = select_triggered_agents("Generate 12 candidates for KARS.", "C3")
        self.assertEqual(generated[0]["name"], "Molecule Generation Agent")
        self.assertEqual(select_triggered_agents("Hello", "CHAT"), [])

    def test_biological_role_quotes_uniprot_and_names_pathway_insight(self):
        question = "What is the biological role of KRAS in the Ras-MAPK signaling pathway?"
        self.assertEqual(classify_scientific_intent(question)["capability"], "ROLE")
        agents = select_triggered_agents(question, "ROLE")
        self.assertEqual([agent["name"] for agent in agents], ["Pathway Insight Agent"])
        profile = {
            "gene_symbol": "KRAS",
            "uniprot_id": "P01116",
            "name": "GTPase KRas",
            "function": "Ras proteins bind GDP/GTP and possess intrinsic GTPase activity.",
        }
        with patch("app.services.chem.target_intel.resolve_uniprot", return_value=profile):
            result = run_chem_query(question)
        self.assertEqual(result["intent"], "ROLE")
        self.assertIn("intrinsic GTPase activity", result["card"]["answer"])
        self.assertNotIn("that concept", result["card"]["answer"].lower())
        self.assertEqual(result["card"]["triggered_agents"][0]["name"], "Pathway Insight Agent")

    def test_structure_count_does_not_call_every_nonpolymer_a_ligand(self):
        catalog = {
            "structures": [{
                "pdb_id": "9IAY",
                "resolution": 0.95,
                "method": "X-RAY DIFFRACTION",
                "other_ligands": ["WYU"],
            }],
            "total_count": 459,
            "filters": {
                "max_resolution_A": 2.5,
                "nonpolymer_required": True,
                "ligand_filter": "other_component",
                "inspected": 40,
            },
            "source": "rcsb",
        }
        profile = {
            "gene_symbol": "KRAS",
            "uniprot_id": "P01116",
            "name": "GTPase KRas",
            "organism": "Homo sapiens",
            "function": "Plays a role in cell proliferation. PubMed:22711838",
            "source": "uniprot",
        }
        with patch("app.services.chem.target_intel.resolve_uniprot", return_value=profile), patch(
            "app.services.chem.target_intel.fetch_structure_catalog", return_value=catalog
        ):
            result = build_target_profile("KRAS")
        narrative = result["narrative"]
        self.assertNotIn("co-crystal ligand", narrative)
        self.assertIn("GDP", narrative)
        self.assertNotIn("22711838", narrative)
        self.assertEqual(experimental_method(
            {"experimental_method": "X-ray"},
            {"exptl": [{"method": "X-RAY DIFFRACTION"}]},
        ), "X-RAY DIFFRACTION")
        self.assertEqual(other_components(["GDP", "MG", "EDO", "WYU"]), ["WYU"])
        self.assertEqual(other_components(["GDP", "MG", "PEG", "ACE"]), [])

    def test_bad_chemistry_is_rejected_and_ranking_prefers_stored_ligands(self):
        radical = "O[CH][C@@H](O)CCc1ccc(Nc2ccnc(Nc3ccc(N4CCCC4)cc3)n2)cc1"
        hexazine = "CCCOC(=O)Oc1ccc2c(n1)NN=NN=N2"
        self.assertIn("radical", rejection_reason(radical))
        self.assertIn("nitrogen", rejection_reason(hexazine))
        self.assertIsNone(rejection_reason("c1ccccc1O"))
        nucleotide = (
            "Nc1nc2c(ncn2[C@@H]2O[C@H](COP(=O)(O)OP(=O)(O)O)[C@@H](O)[C@H]2O)c(=O)[nH]1"
        )
        self.assertEqual(activity_relation({"smiles": nucleotide, "assay": "GTP probe"}), "nucleotide probe")
        self.assertEqual(activity_relation({
            "smiles": "c1ccccc1",
            "assay": "Inhibition of ERK phosphorylation in human HCT116 cells",
        }), "cellular pathway readout")
        self.assertEqual(activity_relation({
            "smiles": "c1ccccc1O",
            "assay": "Binding affinity to KRAS by SPR",
        }), "biochemical")
        sid = self._session_with_target()
        session_store.update_session(
            sid,
            actives=[{"smiles": "c1ccccc1O", "relation": "biochemical", "chembl_id": "CHEMBL1"}],
            candidates=[
                _candidate(1, hexazine),
                _candidate(3, "c1ccccc1O"),
                _candidate(2, "CCN(CC)CC"),
            ],
        )
        ranked = ScientificConversationOrchestrator()._rank(
            "Which five candidates should we investigate first?",
            session_store.get_session(sid),
            5,
        )
        ids = [row["candidate_id"] for row in ranked["candidates"]]
        self.assertEqual(ids[0], "RNN-03")
        self.assertNotIn("RNN-01", ids)
        self.assertIn("set aside", ranked["narrative"])
        self.assertNotIn("docking score", ranked["narrative"].lower())

    def test_spoken_reply_drops_a_pubmed_id_the_tool_did_not_return(self):
        narrative = "RCSB lists 459 entries for GTPase KRas at 2.5 Å or better."
        invented = (
            "RCSB lists 459 entries for GTPase KRas. "
            "It regulates proliferation, as supported by literature [PubMed:22711838]. "
            "What should we look at next?"
        )
        with patch("app.services.chem.orchestrator._conversation_model", return_value="gpt-4o-mini"), patch(
            "app.services.llm_service.llm_service.chat", return_value=invented
        ), patch("app.services.llm_service.LLMService.available", new=property(lambda self: True)):
            spoken = _speak("What structures of KRAS are available?", {"capability": "C1", "narrative": narrative})
        self.assertNotIn("22711838", spoken)
        self.assertIn("459", spoken)

    def test_available_drugs_for_this_target_uses_the_open_protein(self):
        question = "What are the available drugs for this target?"
        self.assertIsNone(extract_gene_symbol(question))
        self.assertEqual(classify_scientific_intent(question)["capability"], "C2")
        sid = self._session_with_target()
        found = {
            "capability": "C2",
            "summary": "Retrieved 1 known actives for GLP1R from ChEMBL.",
            "narrative": "Retrieved 1 known actives for GLP1R from ChEMBL.",
            "actives": [{"chembl_id": "CHEMBL1", "smiles": "CCO", "pref_name": "Example", "rank": 1}],
            "source": "chembl",
            "tools_used": ["ChEMBL"],
            "parameters": {},
            "provenance": {"status": "ok", "evidence": "measured", "tool": "ChEMBL"},
        }
        with patch("app.services.chem.orchestrator.discover_known_actives", return_value=found) as chembl:
            result = run_chem_query(question, session_id=sid)
        self.assertEqual(chembl.call_args.args[0], "P43220")
        self.assertEqual(result["intent"], "C2")
        self.assertNotIn("reviewed human protein", result["card"]["answer"].lower())
        empty = run_chem_query(question)
        self.assertIn("No protein is open", empty["card"]["answer"])

    def test_unresolved_drug_lookup_is_answered_by_the_model(self):
        question = "What are the available drugs for this KRAS?"
        sid = self._session_with_target()
        session_store.update_session(
            sid,
            target={"gene_symbol": "KRAS", "name": "GTPase KRas", "uniprot_id": "P01116"},
        )
        missed = {
            "capability": "C2",
            "summary": "ChEMBL returned no activities at the requested cutoff for KRAS.",
            "narrative": "ChEMBL returned no activities at the requested cutoff for KRAS. No substitute compounds were added.",
            "actives": [],
            "source": "chembl",
            "tools_used": ["ChEMBL"],
            "parameters": {},
            "provenance": {"status": "empty", "evidence": "unavailable", "tool": "ChEMBL"},
        }
        model_reply = "Sotorasib and adagrasib are oral inhibitors used against KRAS G12C."
        with patch("app.services.chem.orchestrator.discover_known_actives", return_value=missed), patch(
            "app.services.chem.orchestrator._conversation_model", return_value="gpt-4o-mini"
        ), patch("app.services.llm_service.llm_service.chat", return_value=model_reply), patch(
            "app.services.llm_service.LLMService.available", new=property(lambda self: True)
        ):
            result = run_chem_query(question, session_id=sid)
        self.assertIn("language model", result["card"]["answer"])
        self.assertIn("Sotorasib", result["card"]["answer"])
        self.assertEqual(result["card"]["triggered_agents"], [])
        self.assertEqual(result["card"]["provenance"]["evidence"], "model")

    def test_greeting_and_unrelated_questions_stay_conversation(self):
        self.assertEqual(classify_scientific_intent("Hello")["capability"], "CHAT")
        self.assertEqual(classify_scientific_intent("What is the capital of France?")["capability"], "CHAT")
        sid = self._session_with_target()
        self.assertEqual(classify_scientific_intent("Hello", session_store.get_session(sid))["capability"], "CHAT")
        with patch("app.services.chem.orchestrator.discover_known_actives") as chembl, patch(
            "app.services.chem.orchestrator.design_candidates"
        ) as design, patch("app.services.chem.orchestrator.assess_novelty") as novelty:
            result = run_chem_query("Hello", session_id=sid)
        chembl.assert_not_called()
        design.assert_not_called()
        novelty.assert_not_called()
        self.assertEqual(result["intent"], "CHAT")
        self.assertNotIn("does not name a protein", result["card"]["answer"])
        self.assertTrue(result["card"]["answer"].strip())

    def test_structure_reply_does_not_invent_patent_or_affinity_caveats(self):
        narrative = (
            "There are currently 6 crystal structures of Lysine--tRNA ligase "
            "(KARS1, UniProt Q15046) in the PDB that feature a co-crystal ligand "
            "and possess a resolution of 2.5 Å or better."
        )
        invented = (
            "There are six crystal structures of Lysine--tRNA ligase available. "
            "This information does not constitute a patent assessment, and the comparison may not be like-for-like. "
            "The specific binding affinities were not measured. "
            "What aspect of KARS1 should we look at next?"
        )
        with patch("app.services.chem.orchestrator._conversation_model", return_value="gpt-4o-mini"), patch(
            "app.services.llm_service.llm_service.chat", return_value=invented
        ), patch("app.services.llm_service.LLMService.available", new=property(lambda self: True)):
            spoken = _speak("What structures of KARS are available?", {"capability": "C1", "narrative": narrative})
        self.assertIn("six crystal structures", spoken)
        self.assertNotIn("patent", spoken.lower())
        self.assertNotIn("like-for-like", spoken.lower())
        self.assertNotIn("binding affinit", spoken.lower())
        self.assertIn("next", spoken.lower())

    def test_can_you_predict_admet_explains_the_limit_without_inventing_endpoints(self):
        question = "Can you predicted ADMET properties?"
        self.assertEqual(classify_scientific_intent(question)["capability"], "EXPLAIN")
        result = run_chem_query(question)
        self.assertEqual(result["intent"], "EXPLAIN")
        self.assertIn("eight physicochemical properties", result["card"]["answer"])
        self.assertIn("no predictive ADMET model", result["card"]["answer"])
        self.assertNotIn("hERG risk", result["card"]["answer"].lower())
        self.assertEqual(result["card"]["triggered_agents"][0]["name"], "ADMET Prediction Agent")
        self.assertEqual(result["card"]["triggered_agents"][0]["stage"], "Lead Optimization")

    def test_designed_molecule_table_lists_smiles_and_does_not_invent_bioactivity(self):
        question = (
            "Show a table for each designed molecule with SMILES string, "
            "predicted bioactivity and other important ADMET properties"
        )
        self.assertEqual(classify_scientific_intent(question)["capability"], "TABLE")
        sid = self._session_with_target()
        empty = run_chem_query(question, session_id=sid)
        self.assertEqual(empty["intent"], "PRECONDITION")
        self.assertIn("No designed molecules are stored", empty["card"]["answer"])
        session_store.update_session(sid, candidates=[_candidate(1, "CCO"), _candidate(2, "c1ccccc1")])
        result = run_chem_query(question, session_id=sid)
        self.assertEqual(result["intent"], "TABLE")
        self.assertIn("not predicted", result["card"]["answer"])
        table = result["card"]["payload"]["property_table"]
        self.assertEqual(len(table), 2)
        self.assertEqual(table[0]["smiles"], "CCO")
        self.assertEqual(table[0]["predicted_bioactivity"], "not predicted")
        self.assertIsNotNone(table[0]["molecular_weight"])

    def test_property_count_question_calculates_descriptors(self):
        question = "How many properties predicted for this molecule?"
        self.assertEqual(classify_scientific_intent(question)["capability"], "ADMET")
        sid = self._session_with_target()
        session_store.update_session(
            sid,
            candidates=[_candidate(1, "CCO")],
            last_smiles="CCO",
            selection={"molecule_id": "RNN-01"},
        )
        result = run_chem_query(question, session_id=sid)
        self.assertEqual(result["intent"], "ADMET")
        self.assertIn("8 physicochemical properties", result["card"]["answer"])
        self.assertIn("no separate predictive ADMET model", result["card"]["answer"])

    def test_naming_a_protein_opens_it_instead_of_explaining_a_concept(self):
        self.assertEqual(classify_scientific_intent("KRAS")["capability"], "C1")
        self.assertEqual(classify_scientific_intent("new protein Like KRAS")["capability"], "C1")
        self.assertEqual(classify_scientific_intent("insulin")["capability"], "C1")
        self.assertEqual(classify_scientific_intent("tp53")["capability"], "C1")
        self.assertEqual(classify_scientific_intent("estrogen receptor")["capability"], "C1")
        self.assertEqual(classify_scientific_intent("What is the capital of France?")["capability"], "CHAT")
        self.assertEqual(classify_scientific_intent("What is pChEMBL 7.10?")["capability"], "EXPLAIN")
        sid = self._session_with_target()
        session_store.update_session(sid, actives=[{"chembl_id": "CHEMBL1", "smiles": "CCO", "source": "chembl"}])
        profile = {
            "capability": "C1",
            "capability_name": "Target Intelligence",
            "summary": "KRAS is open.",
            "narrative": "KRAS, UniProt P01116, has structures in the PDB.",
            "target": {"gene_symbol": "KRAS", "uniprot_id": "P01116", "name": "GTPase KRas"},
            "structures": [{"pdb_id": "4OBE", "title": "KRAS"}],
            "structure_count": 1,
            "default_pdb_id": "4OBE",
            "tools_used": ["UniProt", "RCSB PDB"],
            "parameters": {"gene": "KRAS"},
        }
        with patch("app.services.chem.orchestrator.build_target_profile", return_value=profile):
            result = run_chem_query("new protein Like KRAS", session_id=sid)
        self.assertEqual(result["intent"], "C1")
        self.assertNotIn("explanation of that concept", result["card"]["answer"])
        self.assertIn("KRAS", result["card"]["answer"])
        self.assertEqual(result["session"]["target"]["gene_symbol"], "KRAS")
        self.assertEqual(result["session"]["actives_count"], 0)

    def test_any_protein_name_is_resolved_instead_of_a_fixed_list(self):
        found = {
            "gene_symbol": "INS",
            "uniprot_id": "P01308",
            "name": "Insulin",
            "organism": "Homo sapiens",
            "function": "Hormone.",
            "source": "uniprot",
        }
        catalog = {"structures": [{"pdb_id": "1MSO"}], "total_count": 1, "filters": {}}
        with patch("app.services.chem.target_intel.resolve_uniprot", return_value=found), patch(
            "app.services.chem.target_intel.fetch_structure_catalog", return_value=catalog
        ):
            opened = build_target_profile("insulin")
        self.assertEqual(opened["target"]["gene_symbol"], "INS")
        self.assertEqual(opened["target"]["uniprot_id"], "P01308")
        with patch("app.services.chem.target_intel.resolve_uniprot", return_value=None):
            missing = build_target_profile("notarealprotein")
        self.assertIsNone(missing["target"])
        self.assertIn("No reviewed human protein matched", missing["narrative"])

    def test_structure_question_is_target_retrieval_not_a_compound_lookup(self):
        classified = classify_scientific_intent(
            "What are the available crystal structures of the glucagon-like peptide 1 receptor in the Protein Data Bank?"
        )
        self.assertEqual(classified["primaryIntent"], "TARGET_RETRIEVAL")
        self.assertFalse(classified["requiresCompoundRetrieval"])
        profile = {
            "capability": "C1",
            "capability_name": "Target Intelligence",
            "summary": "15 PDB structures for GLP1R.",
            "narrative": "There are currently 15 crystal structures of GLP1R, UniProt P43220.",
            "target": {
                "gene_symbol": "GLP1R",
                "uniprot_id": "P43220",
                "name": "Glucagon-like peptide 1 receptor",
            },
            "structures": [{"pdb_id": "7KI0", "title": "GLP-1 bound"}],
            "structure_count": 15,
            "default_pdb_id": "7KI0",
            "tools_used": ["UniProt", "RCSB PDB"],
            "parameters": {"gene": "GLP1R"},
        }
        with patch("app.services.chem.orchestrator.build_target_profile", return_value=profile) as called:
            result = run_chem_query(classified and "What are the available crystal structures of GLP1R in the Protein Data Bank?")
        called.assert_called_once()
        self.assertEqual(result["intent"], "C1")
        self.assertEqual(result["session"]["target"]["uniprot_id"], "P43220")
        self.assertEqual(result["session"]["structures_count"], 1)
        self.assertEqual(result["card"]["provenance"]["source"], "UniProt and RCSB PDB")
        exported = export_session_markdown(result["session_id"])
        self.assertIn("15 crystal structures", exported)
        self.assertIn("P43220", exported)

    def test_pchembl_definition_does_not_retrieve_or_inject_demo_rows(self):
        classified = classify_scientific_intent("What is pChEMBL 7.10?")
        self.assertEqual(classified["primaryIntent"], "SCIENTIFIC_EXPLANATION")
        self.assertFalse(classified["requiresCompoundRetrieval"])
        self.assertFalse(classified["requiresExternalTool"])
        with patch("app.services.chem.orchestrator.discover_known_actives") as chembl:
            result = run_chem_query("What is pChEMBL 7.10?")
        chembl.assert_not_called()
        self.assertEqual(result["intent"], "EXPLAIN")
        self.assertIn("79.4 nM", result["card"]["answer"])
        self.assertNotIn("CHEMBL4297610", result["card"]["answer"])
        package = export_session_json(result["session_id"])
        transcript = "\n".join(message["content"] for message in package["transcript"])
        self.assertIn("79.4 nM", transcript)
        self.assertEqual(package["missing_answers"], [])
        restored = session_store.import_session(package)
        answers = [message["content"] for message in restored["messages"] if message["role"] == "studio"]
        self.assertTrue(any("79.4 nM" in text for text in answers))

    def test_novelty_without_molecules_does_not_calculate_or_generate(self):
        sid = self._session_with_target()
        with patch("app.services.chem.orchestrator.design_candidates") as design, patch(
            "app.services.chem.orchestrator.discover_known_actives"
        ) as chembl, patch("app.services.chem.orchestrator.assess_novelty") as novelty:
            result = run_chem_query(
                "Are the designed molecules novel versus the known inhibitors?",
                session_id=sid,
            )
        design.assert_not_called()
        chembl.assert_not_called()
        novelty.assert_not_called()
        self.assertEqual(result["intent"], "PRECONDITION")
        self.assertIn("No candidate molecules have been designed in this session.", result["card"]["answer"])
        self.assertNotIn("Tanimoto", result["card"]["answer"])

    def test_novelty_with_real_records_calculates_similarity(self):
        sid = self._session_with_target()
        session_store.update_session(
            sid,
            candidates=[_candidate(1, "CCO"), _candidate(2, "c1ccccc1")],
            actives=[{
                "chembl_id": "CHEMBL1",
                "smiles": "CCN",
                "source": "chembl",
                "evidence": "measured",
                "pchembl": 7.2,
                "assay": "GLP1R agonist EC50",
                "standard_type": "EC50",
            }],
        )
        result = run_chem_query(
            "Are the designed molecules novel versus the known agonists?",
            session_id=sid,
        )
        self.assertEqual(result["intent"], "C4")
        answer = result["card"]["answer"]
        rows = result["card"]["payload"]["novelty"]
        try:
            import rdkit  # noqa: F401
        except ImportError:
            self.assertIn("No similarity score was estimated", answer)
            self.assertEqual(rows, [])
        else:
            self.assertIn("Tanimoto", answer)
            self.assertIn("not a patent", answer)
            self.assertEqual(len(rows), 2)
            self.assertTrue(all(isinstance(row["max_tanimoto"], float) for row in rows))

    def test_generation_keeps_only_engine_molecules(self):
        sid = self._session_with_target()
        produced = {
            "capability": "C3",
            "summary": "engine",
            "narrative": "engine",
            "candidates": [
                _candidate(1, "CCO"),
                {"candidate_id": "DSN-01", "smiles": "CC", "origin": "scaffold_fill", "qed": 0.4},
            ],
            "tools_used": ["SMILES Char-RNN"],
            "generator": {"name": "test-rnn"},
            "parameters": {},
        }
        with patch("app.services.chem.orchestrator.design_candidates", return_value=produced) as design:
            result = run_chem_query("Generate 20 candidates using the selected design constraints.", session_id=sid)
        design.assert_called_once()
        stored = session_store.get_session(sid)["candidates"]
        self.assertFalse(any(row.get("origin") == "scaffold_fill" for row in stored))
        try:
            import rdkit  # noqa: F401
        except ImportError:
            self.assertEqual(result["session"]["candidates_count"], 0)
            self.assertIn("RDKit is not available", result["card"]["answer"])
        else:
            self.assertEqual(result["session"]["candidates_count"], 1)
            self.assertEqual(stored[0]["origin"], "neural_smiles_rnn")
            self.assertTrue(stored[0].get("canonical_smiles"))

    def test_generation_does_not_substitute_placeholders_when_the_engine_returns_none(self):
        sid = self._session_with_target()
        produced = {
            "capability": "C3",
            "summary": "fallback",
            "narrative": "fallback",
            "candidates": [{"candidate_id": "DSN-01", "smiles": "CCO", "origin": "scaffold_fill"}],
            "tools_used": ["Scaffold Fallback"],
            "parameters": {},
        }
        with patch("app.services.chem.orchestrator.design_candidates", return_value=produced):
            result = run_chem_query("Generate 12 candidates for GLP1R.", session_id=sid)
        self.assertEqual(result["session"]["candidates_count"], 0)
        self.assertIn("did not return validated structures", result["card"]["answer"])
        self.assertEqual(session_store.get_session(sid)["candidates"], [])

    def test_large_campaign_waits_for_approval(self):
        sid = self._session_with_target()
        with patch("app.services.chem.orchestrator.design_candidates") as design:
            waiting = run_chem_query("Generate 50 candidates for GLP1R.", session_id=sid)
        design.assert_not_called()
        self.assertEqual(waiting["intent"], "APPROVAL")
        self.assertIn("No molecules were generated", waiting["card"]["answer"])
        with patch("app.services.chem.orchestrator.design_candidates", return_value={
            "capability": "C3",
            "summary": "engine",
            "narrative": "engine",
            "candidates": [_candidate(1, "CCO")],
            "tools_used": ["SMILES Char-RNN"],
            "generator": {"name": "test-rnn"},
            "parameters": {},
        }) as design:
            approved = run_chem_query("I approve the generation campaign.", session_id=sid)
        design.assert_called_once()
        try:
            import rdkit  # noqa: F401
        except ImportError:
            self.assertEqual(approved["session"]["candidates_count"], 0)
            self.assertIn("RDKit is not available", approved["card"]["answer"])
        else:
            self.assertEqual(approved["session"]["candidates_count"], 1)

    def test_solubility_edit_keeps_the_parent(self):
        sid = self._session_with_target()
        session_store.update_session(sid, candidates=[
            _candidate(1, "CCO"),
            _candidate(2, "CCN"),
            _candidate(3, "c1ccccc1"),
        ])
        result = run_chem_query("Improve the solubility of molecule 3.", session_id=sid)
        self.assertEqual(result["intent"], "OPT")
        stored = session_store.get_session(sid)["candidates"]
        self.assertEqual(stored[2]["candidate_id"], "RNN-03")
        try:
            import rdkit  # noqa: F401
        except ImportError:
            self.assertIn("not a measured solubility", result["card"]["answer"])
            self.assertEqual(len(stored), 3)
        else:
            self.assertIn("not measured solubility", result["card"]["answer"])
            self.assertGreaterEqual(len(stored), 4)
            child = stored[-1]
            self.assertEqual(child["parent_id"], "RNN-03")
            self.assertEqual(child["origin"], "lead_optimization")
            self.assertTrue(child.get("lineage"))

    def test_agonist_retrieval_preserves_assay_context_and_skips_demo_rows(self):
        sid = self._session_with_target()
        rows = [{
            "chembl_id": "CHEMBL2109999",
            "pref_name": "Example agonist",
            "pchembl": 8.1,
            "smiles": "CCO",
            "assay": "GLP1R agonist cAMP EC50",
            "assay_type": "F",
            "standard_type": "EC50",
            "standard_units": "nM",
            "modality": "agonist",
            "activity_id": 1,
            "target_chembl_id": "CHEMBL1784",
        }]
        with patch("app.services.chem.chembl_client.fetch_actives_status", return_value=(rows, "ok")):
            result = run_chem_query("Retrieve known GLP1R agonists from ChEMBL.", session_id=sid)
        self.assertEqual(result["intent"], "C2")
        self.assertNotIn("demo_curated", result["card"]["answer"])
        self.assertIn("not labeled as inhibitors", result["card"]["answer"])
        active = session_store.get_session(sid)["actives"][0]
        self.assertEqual(active["source"], "chembl")
        self.assertEqual(active["evidence"], "measured")
        self.assertEqual(active["standard_type"], "EC50")
        self.assertEqual(active["assay_type"], "F")

    def test_session_reopens_after_memory_is_cleared(self):
        result = run_chem_query("What is pChEMBL 7.10?")
        session_store._SESSIONS.clear()
        restored = session_store.get_session(result["session_id"])
        answers = [message["content"] for message in restored["messages"] if message["role"] == "studio"]
        self.assertTrue(any("79.4 nM" in text for text in answers))
        self.assertEqual(restored["cards"][0]["answer"], restored["cards"][0]["narrative"])


if __name__ == "__main__":
    unittest.main()
