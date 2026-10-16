# Lab fabric architecture

The lab module extends SciAi-Nova OS. It does not replace the existing agent marketplace, molecular studio, document ingest, or knowledge-graph tables.

## What was added

- `backend/app/lab/` — entity model, Vi-CELL XR parser, deterministic statistics, readiness rules, dossier rendering, and the LAB-A1 through LAB-A6 contract
- `backend/app/routes/lab.py` — HTTP API under `/api/lab`
- `frontend/src/pages/lab/` — command center and the five demo workspaces
- Seeded synthetic catalog, loaded once from application startup

Lab entities are also written into the existing `scientific_entities`, `graph_nodes`, and `graph_relationships` tables. Audit rows are written into the existing `audit_events` table. The lab routes live under `/api/lab` because `/api/entities/{id}` and `/api/graph/search` already belong to the research fabric.

## Runtime path

1. A scientist selects an approved protocol version. LAB-A1 copies its parameters, criteria, and sample panel into a draft plan.
2. Gate G1 approval creates the experiment, samples, run, and run schedule.
3. LAB-A2 through LAB-A5 evaluate lot expiry, calibration, training, and compliance. Each corrective action is a Gate G2 decision.
4. LAB-A6 writes the file once into the landing zone, checks SHA-256, parses it, maps columns, records completeness, and publishes measurements.
5. Results, insights, and the dossier are calculated in code. The dossier narrative is a labelled template. Gate G6 is the only way it becomes publishable.
6. LAB-A1 builds a draft follow-up plan from the recommendation insight and changes seeding density.

## Adapters

| Adapter | When it is used | Mode |
| --- | --- | --- |
| Local landing zone and data lake | `LAB_LANDING_BUCKET` / `LAB_LAKE_BUCKET` empty | Real filesystem, not a simulation |
| S3 landing zone and data lake | Those bucket settings are set | Real AWS calls |
| Knowledge graph | Always | Existing SQL graph, Neo4j only through the current sync path |
| ELN | Dossier view | Simulation. The response says no external ELN was called |

Replacing the local landing zone with S3 does not change agent code. Both classes implement `put_immutable`, `read`, and `verify`.

## Feature flags and build-later hooks

- `LAB_EMIT_EXPERIMENT_COMPLETED` defaults to false. Approval still records a suppressed `ExperimentCompleted` row.
- `lab_rule_overrides` is empty. `load_rules()` will honor an active row when one exists.
- Retry with backoff is reported by agent health as disabled.
- Job rows store latency and `llm_called: false`. There is no token-cost dashboard.
- Secrets stay in the existing process settings. `LAB_SECRET_BACKEND=aws-secrets-manager` reports that a vault is not connected.

## Unresolved external dependencies

- No site SOP, assay definition, or official Vi-CELL file was in the repository. The parser accepts the publicly documented Vi-CELL XR tabular fields (Sample ID, viability, counts, diameter, circularity). Fixtures are marked `data_class: SYNTHETIC`.
- Cell line mapping uses Cellosaurus `CVCL:0214` (CHO-K1). Viability uses NCIT:C139278. Diameter uses unit UO:0000017 and does not invent a measurand code.
- AWS buckets, a secret vault, and an ELN endpoint are not configured in this workspace.
- Numeric conclusions do not call an LLM. Narrative text uses `deterministic-template-v1` and records the prompt id and prompt SHA-256.

## Tests and local API

```bash
cd backend && ./venv/bin/python -m unittest tests.test_lab_acceptance -v
```

The Docker image on port 8000 does not contain this module until it is rebuilt. A process started from this working tree serves `/api/lab`.

Demo login remains `scientist` / `sci123`. Open **Lab Command Center**.
