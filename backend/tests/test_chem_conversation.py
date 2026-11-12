"""The session failures that sent a definition to ChEMBL and a novelty question to an empty comparison."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.chem import session_store
from app.services.chem.chembl_client import discover_known_actives
from app.services.chem.orchestrator import export_session_markdown, run_chem_query


class ChemConversationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._dir = session_store.SESSIONS_DIR
        session_store.SESSIONS_DIR = Path(self.tmp.name)
        session_store._SESSIONS.clear()

    def tearDown(self):
        session_store.SESSIONS_DIR = self._dir
        session_store._SESSIONS.clear()
        self.tmp.cleanup()

    def test_pchembl_is_an_explanation(self):
        result = run_chem_query("What is pChEMBL 7.10?")
        card = result["card"]
        self.assertEqual(result["intent"], "EXPLAIN")
        self.assertEqual(result["session"]["actives_count"], 0)
        self.assertIn("79.4 nM", card["narrative"])
        self.assertIn("No compounds were retrieved.", card["narrative"])
        self.assertNotIn("CHEMBL4297610", card["narrative"])
        exported = export_session_markdown(result["session_id"])
        self.assertIn("79.4 nM", exported)
        self.assertIn("No compounds were retrieved.", exported)
        self.assertNotIn("CHEMBL4297610", exported)

    def test_novelty_without_designed_molecules_does_not_invent_a_score(self):
        session = session_store.create_session()
        session_store.update_session(
            session["id"],
            target={"gene_symbol": "GLP1R", "name": "Glucagon-like peptide 1 receptor", "uniprot_id": "P43220"},
            structures=[{"pdb_id": "4ZGM", "title": "Semaglutide peptide backbone"}],
        )
        result = run_chem_query(
            "Are the designed molecules novel versus the known inhibitors?",
            session_id=session["id"],
        )
        card = result["card"]
        self.assertEqual(result["intent"], "PRECONDITION")
        self.assertEqual(result["session"]["candidates_count"], 0)
        self.assertEqual(result["session"]["actives_count"], 0)
        self.assertIn("No candidate molecules have been designed in this session.", card["narrative"])
        self.assertIn("molecular novelty cannot yet be evaluated", card["narrative"])
        self.assertNotIn("Tanimoto", card["narrative"])
        self.assertFalse((card.get("payload") or {}).get("llm_called"))

    def test_empty_chembl_does_not_insert_demo_compounds(self):
        with patch(
            "app.services.chem.chembl_client.fetch_actives_status",
            return_value=([], "empty"),
        ):
            found = discover_known_actives("P43220", "GLP1R")
        self.assertEqual(found["actives"], [])
        self.assertEqual(found["source"], "chembl")
        self.assertNotIn("demo_curated", found["summary"])
        ids = " ".join(row.get("chembl_id", "") for row in found["actives"])
        self.assertNotIn("CHEMBL4297610", ids)

    def test_glp1r_snapshot_is_used_only_when_chembl_is_down(self):
        with patch(
            "app.services.chem.chembl_client.fetch_actives_status",
            return_value=([], "unavailable"),
        ):
            glp = discover_known_actives("P43220", "GLP1R", modality="agonist")
            other = discover_known_actives("P00533", "EGFR", modality="agonist")
        self.assertEqual(glp["source"], "chembl_snapshot")
        self.assertTrue(glp["actives"])
        self.assertIn("saved from ChEMBL", glp["narrative"])
        self.assertTrue(all(row["evidence"] == "measured" for row in glp["actives"]))
        self.assertEqual(other["actives"], [])
        self.assertEqual(other["source"], "chembl")

    def test_session_reopens_after_memory_is_cleared(self):
        result = run_chem_query("What is pChEMBL 7.10?")
        sid = result["session_id"]
        session_store._SESSIONS.clear()
        restored = session_store.get_session(sid)
        self.assertIsNotNone(restored)
        answers = [message["content"] for message in restored["messages"] if message["role"] == "studio"]
        self.assertTrue(any("79.4 nM" in text for text in answers))


if __name__ == "__main__":
    unittest.main()
