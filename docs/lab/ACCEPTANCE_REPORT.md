# Lab acceptance report

Date: 13 Oct 2026

Command:

```bash
cd backend && ./venv/bin/python -m unittest tests.test_lab_acceptance -v
```

Result: 4 tests, all passed, about 1.0 second.

- `test_parser_acceptance_rate` — 20 of 20 supported synthetic Vi-CELL XR files parsed
- `test_ontology_and_documents` — NCIT:C139278 lookup and trypan-blue SOP citation
- `test_five_moments_and_acceptance_criteria` — plan, G1, readiness, G2, ingest, results, dossier, G6, follow-up, lineage, audit
- `test_feature_flag_can_publish_when_enabled` — `ExperimentCompleted` publishes only when the flag is on

Observed demo outcomes inside that run:

- Unmatched sample `SYN-UNMATCHED-999` raised a quality flag
- Completeness of the current fixture was 100 percent
- Mean viability and CV both failed the plan criteria
- Recommendation proposed seeding density 240000 from 200000
- Follow-up plan stayed in draft and cited the recommendation insight
- Dossier was not publishable until the scientist decision
- Data steward approval was rejected with 403
- Raw SHA-256 was unchanged after a measurement correction
- Gate order was G1, then G2, then G6, and those decisions appear in the experiment audit history
- Lineage resolved Measurement → Run → Instrument → Sample → Experiment → ExperimentPlan → ProtocolVersion → Protocol

The run used a temporary SQLite database. It did not call AWS, an ELN, or an LLM.
