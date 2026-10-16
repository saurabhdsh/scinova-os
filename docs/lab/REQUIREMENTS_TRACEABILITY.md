# Lab requirements traceability

Status after the acceptance run on 13 Oct 2026. Tests: `backend/tests/test_lab_acceptance.py` (4 tests, all passed).

| ID | Implementation | Test |
| --- | --- | --- |
| FR-DC-001 | `adapters.LocalLandingZone.put_immutable` writes once and stores SHA-256 on `lab_raw_data_files` | Re-ingest is idempotent; checksum verified |
| FR-DC-002 | `parsers/vicell.py` `vicell-xr-tabular` `v1`, registry in `parsers/base.py` | 20/20 supported files parse |
| FR-DC-003 | Ingestion matches sample codes and writes `UNMATCHED_SAMPLE` | Fixture contains `SYN-UNMATCHED-999` |
| FR-DC-004 | Completeness is matched samples × expected readouts, stored on the run | Current fixture reports 100 |
| FR-DC-005 | `lab/audit.py` inserts into existing `audit_events` only | Audit list grows and the first id is unchanged |
| FR-DC-006 | Harmonized JSON in the lake plus graph nodes | Ingest response includes lake metadata; lineage resolves |
| FR-RC-001 | `results.compile_results` aggregates matched viability | Mean and CV results exist |
| FR-RC-002 | `graph_bridge` relationships `EXECUTES`, `FOLLOWS`, `HAS_RUN`, `USES_INSTRUMENT`, `HAS_SAMPLE`, `PRODUCED_MEASUREMENT` | Lineage chain has eight steps |
| FR-RC-003 | `stats.compare` against plan criteria | Mean and CV both fail on the demo file |
| FR-RC-004 | `dossier.py` PDF and DOCX; every reported value has measurement ids | Export returns PDF and DOCX; trace check is 100% |
| FR-RC-005 | Result and Insight nodes published on the existing graph | Graph query returns nodes |
| FR-RC-006 | `ExperimentCompleted` implemented and suppressed unless `LAB_EMIT_EXPERIMENT_COMPLETED` | Flag-off rows are unpublished; flag-on publish works |
| FR-RC-007 | Rules `LAB-RULE-VIAB-ABS`, `LAB-RULE-VIAB-HIST`, `LAB-RULE-CV-001` store comparators, thresholds, and values | Insights present with evidence |
| FR-RC-008 | `LAB-RULE-NEXT-001` raises seeding density 20% and LAB-A1 copies it onto a draft plan | Follow-up value is 240000 and cites the insight |
| BR-DR-001 | Raw correction returns 409; measurement correction creates version 2 | `raw_immutable` and version 2 |
| BR-DR-002 | Parser classes register by id and version | Health lists `vicell-xr-tabular` |
| BR-DR-003 | Dossier narrative is labelled, `llm_called` is false, status stays `pending_approval` until G6 | Data steward receives 403; scientist approval sets publishable |
| NFR-01 | Plan, readiness, ingest, compile, and what-if are timed in the acceptance test | All under the stated limits on the synthetic catalog |
| NFR-02 | Gates G1, G2, and G6 append audit and `lab_gate_decisions` | Gate order is G1, then G2, then G6 |
| NFR-03 | Dossier paragraphs and `explain` carry fabric citations | Explain response has citations |
| NFR-04 | Statistics and rules are Python; prompt id and model version are stored | `llm_called` is false |
| NFR-05 | Lab routes check scientist, reviewer, admin, data steward, and principal investigator. Vault is not configured | Steward cannot approve G6; health reports env secrets |
| NFR-06 | Landing objects are content-addressed and verified | SHA-256 unchanged after correction |
| NFR-07–10 | Hooks only: retries disabled, `lab_rule_overrides` empty, job latency stored, event subscribe API present | Health payload reports retries disabled |

## Demo moments

| Moment | API the UI calls |
| --- | --- |
| Planning | `POST /api/lab/plans`, `POST /api/lab/plans/{id}/approve` |
| Readiness | `POST /api/lab/experiments/{id}/readiness`, `POST /api/lab/readiness/{id}/resolve` |
| Data capture | `GET /api/lab/fixtures/vicell-current.csv`, `POST /api/lab/experiments/{id}/ingest` |
| Results | `POST /api/lab/experiments/{id}/results`, `POST /api/lab/experiments/{id}/dossier` |
| Next experiment | `GET /api/lab/experiments/{id}/what-if`, `POST /api/lab/experiments/{id}/follow-up` |

## Not claimed

- The Vi-CELL fixture is not a Beckman-validated file and not live instrument data.
- ELN attachment is a labelled simulation.
- S3 is not called unless a bucket is configured.
- Docker's published image does not include this module until the backend image is rebuilt.
