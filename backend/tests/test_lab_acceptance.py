"""Acceptance tests for the lab fabric and the five demo moments."""

from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("ANONYMIZED_TELEMETRY", "FALSE")

from app.config import settings
from app.database import Base, get_db
from app.dependencies.auth import get_current_user
from app.lab.catalog import supported_parser_files
from app.lab.errors import LabError
from app.lab.models import LabEvent, LabMeasurement, LabRawDataFile
from app.lab.parsers.base import select_parser
from app.lab.seed_lab import seed_lab
from app.models.db_models import User
from app.routes.lab import router
import app.lab.models  # noqa: F401
import app.models.db_models  # noqa: F401


class LabAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        settings.lab_landing_dir = str(root / "landing")
        settings.lab_lake_dir = str(root / "lake")
        settings.lab_dossier_dir = str(root / "dossiers")
        settings.lab_landing_bucket = ""
        settings.lab_lake_bucket = ""
        settings.lab_emit_experiment_completed = False
        cls.engine = create_engine("sqlite:///" + str(root / "lab.db"), connect_args={"check_same_thread": False})
        Base.metadata.create_all(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine, expire_on_commit=False, autoflush=False)
        cls.session = cls.Session()
        cls.user = User(username="scientist", password_hash="x", role="scientist", full_name="Sarah Chen")
        cls.session.add(cls.user)
        cls.session.commit()
        started = time.perf_counter()
        seed_lab(cls.session)
        cls.seed_seconds = time.perf_counter() - started
        app = FastAPI()
        app.include_router(router, prefix="/api")

        @app.exception_handler(LabError)
        async def _handle(_request, exc: LabError):
            return JSONResponse(status_code=exc.status_code, content=exc.as_dict())

        def _db():
            try:
                yield cls.session
            finally:
                pass

        app.dependency_overrides[get_db] = _db
        app.dependency_overrides[get_current_user] = lambda: cls.user
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.session.close()
        cls.tmp.cleanup()

    def test_parser_acceptance_rate(self):
        files = supported_parser_files()
        self.assertGreaterEqual(len(files), 20)
        parsed = 0
        for name, content in files:
            select_parser(name, content).parse(content, name)
            parsed += 1
        self.assertGreaterEqual(parsed / len(files), 0.95)

    def test_ontology_and_documents(self):
        lookup = self.client.get("/api/lab/ontology/lookup", params={"q": "viability"})
        self.assertEqual(lookup.status_code, 200, lookup.text)
        ids = {item["id"] for item in lookup.json()["terms"]}
        self.assertIn("NCIT:C139278", ids)
        mapped = self.client.post("/api/lab/ontology/map", json={"header": "Viability (%)"})
        self.assertEqual(mapped.status_code, 200, mapped.text)
        self.assertEqual(mapped.json()["ontology_id"], "NCIT:C139278")
        self.assertGreaterEqual(mapped.json()["confidence"], 0.9)
        search = self.client.get("/api/lab/documents/search", params={"q": "trypan"})
        self.assertEqual(search.status_code, 200, search.text)
        self.assertTrue(search.json()["hits"])
        self.assertTrue(search.json()["hits"][0]["citation"])

    def test_five_moments_and_acceptance_criteria(self):
        self.assertLess(self.seed_seconds, 60)
        protocols = self.client.get("/api/lab/protocols")
        self.assertEqual(protocols.status_code, 200, protocols.text)
        primary = next(row for row in protocols.json() if row["protocol_code"] == "SYN-CVP-001")
        self.assertGreaterEqual(len({row["protocol_code"] for row in protocols.json()}), 3)

        started = time.perf_counter()
        plan = self.client.post(
            "/api/lab/plans",
            json={"protocol_version_id": primary["id"], "title": "Plan: CHO-K1 viability demo"},
        )
        self.assertEqual(plan.status_code, 200, plan.text)
        self.assertLess(time.perf_counter() - started, 5)
        plan_id = plan.json()["id"]
        self.assertEqual(plan.json()["status"], "draft")

        started = time.perf_counter()
        approved = self.client.post(f"/api/lab/plans/{plan_id}/approve", json={"comment": "G1 approved for the demo run."})
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertLess(time.perf_counter() - started, 60)
        experiment_id = approved.json()["id"]

        started = time.perf_counter()
        readiness = self.client.post(f"/api/lab/experiments/{experiment_id}/readiness")
        self.assertEqual(readiness.status_code, 200, readiness.text)
        self.assertLess(time.perf_counter() - started, 60)
        issues = {row["code"]: row for row in readiness.json()}
        self.assertIn("NEAR_EXPIRY", issues)
        self.assertIn("CALIBRATION_DUE", issues)
        self.assertIn("TRAINING_GAP", issues)
        self.assertIn("COMPLIANCE_HOLD", issues)
        self.assertEqual(issues["CALIBRATION_DUE"]["recommendation_json"]["instrument_serial"], "VC-XR-1042")
        self.assertEqual(issues["TRAINING_GAP"]["recommendation_json"]["operator_name"], "Priya Nair")
        self.assertEqual(issues["NEAR_EXPIRY"]["recommendation_json"]["lot_number"], "TB-LOT-778")

        blocked = self.client.post(
            f"/api/lab/experiments/{experiment_id}/ingest",
            files={"file": ("vicell.csv", b"sample id,viability (%)\nSYN-S-001,90\n", "text/csv")},
        )
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.json()["error"], "readiness_blocked")

        for code in ("NEAR_EXPIRY", "CALIBRATION_DUE", "TRAINING_GAP", "COMPLIANCE_HOLD"):
            resolved = self.client.post(
                f"/api/lab/readiness/{issues[code]['id']}/resolve",
                json={"decision": "approve", "comment": f"G2 approve {code}"},
            )
            self.assertEqual(resolved.status_code, 200, resolved.text)
            self.assertEqual(resolved.json()["status"], "resolved")

        fixture = self.client.get("/api/lab/fixtures/vicell-current.csv")
        self.assertEqual(fixture.status_code, 200, fixture.text)
        started = time.perf_counter()
        ingested = self.client.post(
            f"/api/lab/experiments/{experiment_id}/ingest",
            files={"file": ("vicell-current-synthetic.csv", fixture.content, "text/csv")},
        )
        self.assertEqual(ingested.status_code, 200, ingested.text)
        self.assertLess(time.perf_counter() - started, 5)
        body = ingested.json()
        self.assertTrue(body["checksum_verified"])
        self.assertEqual(body["landing_mode"], "local")
        self.assertFalse(body["simulation"])
        self.assertEqual(body["data_origin"], "synthetic")
        self.assertEqual(body["parser_id"], "vicell-xr-tabular")
        self.assertEqual(body["completeness_percent"], 100)
        self.assertTrue(any(flag["code"] == "UNMATCHED_SAMPLE" for flag in body["quality_flags"]))
        raw = self.session.get(LabRawDataFile, body["raw_file_id"])
        self.assertEqual(raw.sha256, body["sha256"])
        again = self.client.post(
            f"/api/lab/experiments/{experiment_id}/ingest",
            files={"file": ("vicell-current-synthetic.csv", fixture.content, "text/csv")},
        )
        self.assertEqual(again.status_code, 200, again.text)
        self.assertTrue(again.json()["idempotent"])
        self.assertEqual(again.json()["raw_file_id"], body["raw_file_id"])

        started = time.perf_counter()
        compiled = self.client.post(f"/api/lab/experiments/{experiment_id}/results")
        self.assertEqual(compiled.status_code, 200, compiled.text)
        self.assertLess(time.perf_counter() - started, 15)
        compiled_body = compiled.json()
        self.assertEqual(compiled_body["outcome"], "fail")
        self.assertGreaterEqual(len(compiled_body["historical_comparator_ids"]), 10)
        outcomes = {row["metric"]: row for row in compiled_body["results"]}
        self.assertEqual(outcomes["mean_viability_percent"]["outcome"], "fail")
        self.assertEqual(outcomes["cv_percent"]["outcome"], "fail")
        self.assertTrue(outcomes["mean_viability_percent"]["measurement_ids"])
        kinds = {row["rule_id"] for row in compiled_body["insights"]}
        self.assertIn("LAB-RULE-VIAB-ABS", kinds)
        self.assertIn("LAB-RULE-VIAB-HIST", kinds)
        self.assertIn("LAB-RULE-CV-001", kinds)
        self.assertIn("LAB-RULE-NEXT-001", kinds)
        recommendation = next(row for row in compiled_body["insights"] if row["rule_id"] == "LAB-RULE-NEXT-001")
        self.assertEqual(recommendation["evidence"]["proposed_value"], 240000)
        self.assertTrue(recommendation["evidence"]["measurement_ids"])
        self.assertFalse(recommendation["ai_generated"])

        dossier = self.client.post(f"/api/lab/experiments/{experiment_id}/dossier")
        self.assertEqual(dossier.status_code, 200, dossier.text)
        dossier_body = dossier.json()
        self.assertEqual(dossier_body["status"], "pending_approval")
        self.assertFalse(dossier_body["publishable"])
        self.assertTrue(dossier_body["ai_generated"])
        self.assertFalse(dossier_body["llm_called"])
        reported = dossier_body["content_json"]["reported_values"]
        self.assertTrue(reported)
        self.assertTrue(all(item["measurement_ids"] for item in reported))
        explained = self.client.get(
            "/api/lab/agents/LAB-A6/explain",
            params={"entityRef": f"experiment_dossier:{dossier_body['id']}"},
        )
        self.assertEqual(explained.status_code, 200, explained.text)
        self.assertTrue(explained.json()["citations"])
        self.assertTrue(explained.json()["ai_generated"])

        self.user.role = "data_steward"
        denied = self.client.post(
            f"/api/lab/dossiers/{dossier_body['id']}/decision",
            json={"decision": "approve", "comment": "steward cannot approve science"},
        )
        self.assertEqual(denied.status_code, 403)
        self.user.role = "scientist"

        decision = self.client.post(
            f"/api/lab/dossiers/{dossier_body['id']}/decision",
            json={"decision": "approve", "comment": "G6 scientist approval"},
        )
        self.assertEqual(decision.status_code, 200, decision.text)
        self.assertTrue(decision.json()["publishable"])
        self.assertEqual(decision.json()["approval_json"]["actor"], "scientist")
        self.assertEqual(decision.json()["approval_json"]["version"], dossier_body["version"])
        exported = self.client.get(f"/api/lab/dossiers/{dossier_body['id']}/export", params={"format": "pdf"})
        self.assertEqual(exported.status_code, 200, exported.text)
        self.assertGreater(len(exported.content), 500)
        self.assertEqual(exported.headers["x-dossier-publishable"], "true")
        docx = self.client.get(f"/api/lab/dossiers/{dossier_body['id']}/export", params={"format": "docx"})
        self.assertEqual(docx.status_code, 200, docx.text[:200] if docx.status_code != 200 else "ok")
        suppressed = [
            row
            for row in self.session.query(LabEvent).filter(LabEvent.event_type == "ExperimentCompleted").all()
            if (row.payload_json or {}).get("experiment_id") == experiment_id
        ]
        self.assertTrue(suppressed)
        self.assertTrue(all(not row.published for row in suppressed))

        started = time.perf_counter()
        preview = self.client.get(f"/api/lab/experiments/{experiment_id}/what-if")
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertLess(time.perf_counter() - started, 15)
        self.assertFalse(preview.json()["persisted"])
        self.assertEqual(preview.json()["change"]["to"], 240000)

        started = time.perf_counter()
        follow = self.client.post(f"/api/lab/experiments/{experiment_id}/follow-up")
        self.assertEqual(follow.status_code, 200, follow.text)
        self.assertLess(time.perf_counter() - started, 15)
        self.assertEqual(follow.json()["status"], "draft")
        self.assertEqual(follow.json()["parameters_json"]["seeding_density_cells_per_ml"], 240000)
        self.assertNotEqual(
            follow.json()["parameters_json"]["seeding_density_cells_per_ml"],
            200000,
        )
        self.assertIn(recommendation["id"], follow.json()["cited_insight_ids_json"])

        lineage = self.client.get(f"/api/lab/graph/lineage/measurement:{outcomes['mean_viability_percent']['measurement_ids'][0]}")
        self.assertEqual(lineage.status_code, 200, lineage.text)
        chain = [item["entity_type"] for item in lineage.json()["chain"] if item]
        self.assertEqual(
            chain,
            ["Measurement", "Run", "Instrument", "Sample", "Experiment", "ExperimentPlan", "ProtocolVersion", "Protocol"],
        )
        self.assertTrue(lineage.json()["resolvable"])
        self.assertTrue(lineage.json()["checksum"])

        story = self.client.get(f"/api/lab/experiments/{experiment_id}/storyline")
        self.assertEqual(story.status_code, 200, story.text)
        moments = story.json()["moments"]
        self.assertTrue(all(moments[key]["complete"] for key in moments))
        gates = [row["gate"] for row in story.json()["gates"]]
        self.assertLess(gates.index("G1"), gates.index("G2"))
        self.assertLess(gates.index("G2"), gates.index("G6"))

        audit = self.client.get(f"/api/lab/audit/{experiment_id}")
        self.assertEqual(audit.status_code, 200, audit.text)
        self.assertGreaterEqual(len(audit.json()), 3)
        actions = [row["action"] for row in audit.json()]
        self.assertIn("G1 approve", actions)
        self.assertTrue(any(action.startswith("G2 ") for action in actions))
        self.assertIn("G6 approve", actions)
        self.assertLess(actions.index("G1 approve"), next(i for i, action in enumerate(actions) if action.startswith("G2 ")))
        self.assertLess(
            next(i for i, action in enumerate(actions) if action.startswith("G2 ")),
            actions.index("G6 approve"),
        )
        first_id = audit.json()[0]["id"]
        self.client.post(f"/api/lab/experiments/{experiment_id}/results")
        audit_again = self.client.get(f"/api/lab/audit/{experiment_id}")
        self.assertEqual(audit_again.json()[0]["id"], first_id)
        self.assertGreater(len(audit_again.json()), len(audit.json()))

        measurement_id = outcomes["mean_viability_percent"]["measurement_ids"][0]
        before = self.session.get(LabRawDataFile, body["raw_file_id"]).sha256
        corrected = self.client.post(
            f"/api/lab/entities/measurement/{measurement_id}/corrections",
            json={"value": 92.1, "reason": "transcription check"},
        )
        self.assertEqual(corrected.status_code, 200, corrected.text)
        self.assertEqual(corrected.json()["version"], 2)
        self.assertEqual(self.session.get(LabMeasurement, measurement_id).status, "superseded")
        self.assertEqual(self.session.get(LabRawDataFile, body["raw_file_id"]).sha256, before)
        raw_reject = self.client.post(
            f"/api/lab/entities/raw_data_file/{body['raw_file_id']}/corrections",
            json={"value": 1},
        )
        self.assertEqual(raw_reject.status_code, 409)
        self.assertEqual(raw_reject.json()["error"], "raw_immutable")

        health = self.client.get("/api/lab/agents/LAB-A6/health")
        self.assertEqual(health.status_code, 200, health.text)
        self.assertEqual(health.json()["dependencies"]["landing_zone"]["mode"], "local")
        self.assertFalse(health.json()["dependencies"]["landing_zone"]["simulation"])
        self.assertIn("vicell-xr-tabular", health.json()["dependencies"]["parsers"])

        job = self.client.post(
            "/api/lab/agents/LAB-A1/invoke",
            json={"trigger": "what_if", "experiment_id": experiment_id, "context": {}},
            headers={"Idempotency-Key": "demo-what-if"},
        )
        self.assertEqual(job.status_code, 200, job.text)
        self.assertEqual(job.json()["status"], "SUCCEEDED")
        repeat = self.client.post(
            "/api/lab/agents/LAB-A1/invoke",
            json={"trigger": "what_if", "experiment_id": experiment_id, "context": {}},
            headers={"Idempotency-Key": "demo-what-if"},
        )
        self.assertEqual(repeat.json()["id"], job.json()["id"])
        status = self.client.get(f"/api/lab/agents/jobs/{job.json()['id']}")
        self.assertEqual(status.json()["status"], "SUCCEEDED")
        outputs = self.client.get("/api/lab/agents/LAB-A1/outputs", params={"experimentId": experiment_id})
        self.assertEqual(outputs.status_code, 200, outputs.text)
        self.assertTrue(any(item["id"] == follow.json()["id"] for item in outputs.json()["refs"]))

    def test_feature_flag_can_publish_when_enabled(self):
        settings.lab_emit_experiment_completed = True
        try:
            published = self.client.post(
                "/api/lab/events/publish",
                json={"event_type": "ExperimentCompleted", "payload": {"experiment_id": "demo", "outcome": "fail"}},
            )
            self.assertEqual(published.status_code, 200, published.text)
            self.assertTrue(published.json()["published"])
        finally:
            settings.lab_emit_experiment_completed = False


if __name__ == "__main__":
    unittest.main()
