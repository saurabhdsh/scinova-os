# SciNova OS — Design & Build Status

> Living document tracking platform architecture, build phases, and completion status.  
> Last updated: 2026-06-07

---

## Platform Vision

**SciNova OS (SciFabric AgentOS)** is an AI-native Scientific Data Fabric and Agent Operating System for Pharma R&D. It connects evidence, generates hypotheses, designs experiments, and produces traceable scientific outputs across the research value chain.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     React Frontend (Vite)                        │
│  Dashboard · Data Fabric · KG Explorer · Agents · Workflows      │
│  Reports · Collaboration · Settings · Admin (users)               │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST /api  (JWT auth)
┌────────────────────────────▼────────────────────────────────────┐
│                     FastAPI Backend                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Data Fabric  │  │ Agent Engine │  │ Workflow Orchestrator│   │
│  │  Pipeline    │  │ Model Router │  │                      │   │
│  └──────┬───────┘  └──────────────┘  └──────────────────────┘   │
└─────────┼───────────────────────────────────────────────────────┘
          │
    ┌─────▼─────┐  ┌──────────┐  ┌────────┐  ┌─────────┐  ┌─────────────┐
    │ PostgreSQL │  │ ChromaDB │  │ Neo4j  │  │  Redis  │  │ File Storage│
    │ (metadata) │  │ (vectors)│  │ (graph)│  │ (queue) │  │ (uploads)   │
    └───────────┘  └──────────┘  └────────┘  └────┬────┘  └─────────────┘
                                                     │
                                              ┌──────▼──────┐
                                              │ Celery Worker│
                                              │ (ingestion)  │
                                              └─────────────┘
```

---

## Build Phases

| Phase | Name | Status | Completion |
|-------|------|--------|------------|
| 0 | Prototype Shell (UI + mock APIs) | **Complete** | 100% |
| 1 | Foundation (Postgres, auth, Celery, workspace scoping) | **Complete** | 100% |
| 2 | Data Fabric (ingestion pipeline) | **Complete** | 100% |
| 3 | Knowledge Graph (Neo4j + live entities) | **Complete** | 100% |
| 4 | Real Agents (RAG + LLM) | **Complete** | 100% |
| 5 | Orchestrator + SLM + Governance | **Complete** | 100% |
| 6 | Specialized Agents + External Integrations | **Complete** | 100% |
| 7 | More Real Agents + E2E Workflows | **Complete** | 100% |
| 8 | Ministral 8B SLM + Workflow Downloads | **Complete** | 100% |
| 9 | Detailed Scientific Reports + UI polish | **Complete** | 100% |

## Phase 1 — Foundation ✅ Complete

| Component | Status | Implementation |
|-----------|--------|----------------|
| PostgreSQL as primary DB | ✅ | `docker-compose.yml` — Postgres 16; `SQLITE_FALLBACK=false` in Docker |
| JWT authentication | ✅ | `routes/auth.py`, `dependencies/auth.py` — bearer tokens with `user_id` |
| Password hashing (bcrypt) | ✅ | `core/security.py` — legacy hash migration on login |
| Protected API routes | ✅ | `CurrentUser` dependency on fabric, agents, workflows, reports, projects |
| Per-user workspace scoping | ✅ | `user_id` FKs on documents, runs, reports; workspace filters |
| Projects & members | ✅ | `project_service.py`, `GET/POST /api/projects`, member management |
| Per-user quotas | ✅ | `quota_service.py` — upload/workflow limits (admin bypass) |
| Celery + Redis async ingestion | ✅ | `celery_app.py`, `tasks/ingestion_tasks.py`, `task_queue.py` |
| Admin user management | ✅ | `routes/admin.py` — list/create/delete users; `AdminUsersPanel.jsx` |
| CLI user management | ✅ | `cli.py` — create/delete users from shell |
| Startup DB migrations | ✅ | `db_migrate.py` — additive column/FK migrations on boot |
| Docker full stack | ✅ | postgres, neo4j, redis, chromadb, backend, celery-worker, frontend |
| Dev hot-reload mounts | ✅ | `./backend/app:/app/app`, `./frontend:/app` volume mounts |
| Root `.env` for secrets | ✅ | `env_file: .env` on backend + celery-worker |

Default demo login: `admin` / `admin123` (seeded in `seed.py`).

## Phase 2 — Data Fabric ✅ Complete

| Component | Status | Implementation |
|-----------|--------|----------------|
| File upload to disk | ✅ | `storage/uploads/{doc_id}/{filename}` |
| Document parser (PDF/DOCX/CSV/XLSX/JSON/TXT) | ✅ | `services/document_parser.py` |
| Chunking + embedding + ChromaDB indexing | ✅ | `chunker.py`, `embedding_service.py`, `chromadb_client.py` |
| Ingestion job tracking | ✅ | Real stage progress in DB |
| Semantic search API | ✅ | `POST /api/fabric/search` |
| Frontend live pipeline UI | ✅ | Polls job status, semantic search |

### Ingestion Pipeline Stages

```
upload → metadata_extract → text_extract → chunk → embed → vector_index
  → entity_extract → relationship_extract → ontology_map → graph_update
  → neo4j_sync → complete
```

---

## Phase 3 — Knowledge Graph ✅ Complete

| Component | Status | Implementation |
|-----------|--------|----------------|
| Neo4j driver integration | ✅ | `services/neo4j_client.py` |
| Sync SQL graph → Neo4j | ✅ | `services/graph_sync.py` — runs on each ingestion |
| LLM entity extraction | ✅ | `services/llm_entity_extractor.py` (hybrid with patterns) |
| LLM relationship extraction | ✅ | OpenAI JSON mode when `OPENAI_API_KEY` set |
| Entity resolution / dedup | ✅ | `services/entity_resolver.py` |
| Entity quality filtering | ✅ | `services/entity_quality.py` — blocklist, gene heuristics, confidence gates |
| Relationship quality | ✅ | Capped co-occurrence, LLM-first merge, confidence threshold ≥ 0.55 |
| Evidence panel with chunk citations | ✅ | Neighborhood API returns `source_chunks` |
| Graph Explorer live data | ✅ | Filter by document, live-only, refresh |
| Graph stats API | ✅ | `GET /api/graph/stats` |

### Entity Extraction Modes

| Mode | When | Method |
|------|------|--------|
| Pattern only | No `OPENAI_API_KEY` | Regex NER (`entity_extractor.py`) |
| Hybrid | `OPENAI_API_KEY` set | LLM + patterns merged + resolved + quality filtered |

### Graph Quality (Entity & Relationship Filtering)

| Filter | Implementation |
|--------|----------------|
| Gene noise (AA, AE, RA…) | Expanded blocklist + `_looks_like_gene()` heuristics |
| Short-token genes | Require ≥3 chars or known symbol (JAK1, EGFR) |
| Confidence gate | Entities ≥ 0.65, relationships ≥ 0.55 |
| Co-occurrence cap | Max 6 pairs per chunk; skip Gene–Gene generic edges |
| LLM priority | LLM relationships merged before pattern co-occurrence |
| Dedup | Highest-confidence relationship kept per source/target/type |

Re-ingest documents to apply filters to existing graph data.

---

## OpenAI Configuration (Recommended)

Set in `.env` at project root (copy from `.env.example`):

```bash
OPENAI_API_KEY=sk-your-key-here
OPENAI_BASE_URL=https://api.openai.com/v1
EMBEDDING_MODEL=text-embedding-3-small
LLM_MODEL=gpt-4o-mini
```

| Setting | Purpose |
|---------|---------|
| `OPENAI_API_KEY` | **Required for best results** — enables `text-embedding-3-small` embeddings and LLM entity/relationship extraction |
| `EMBEDDING_MODEL` | Vector quality for semantic search (default: `text-embedding-3-small`) |
| `LLM_MODEL` | Entity/relationship extraction during ingestion (default: `gpt-4o-mini`) |

Without `OPENAI_API_KEY`:
- Embeddings fall back to ChromaDB default (MiniLM) or local hash vectors
- Entity extraction uses pattern-based NER only
- Platform still fully functional without OpenAI key (retrieval-only mode)

With `OPENAI_API_KEY`:
- Higher-quality semantic search over uploaded documents
- Richer entity and relationship extraction from PDFs
- Agent citations pull from real vector index results

---

## Neo4j Configuration

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=scinova12
NEO4J_ENABLED=true
```

Start Neo4j via Docker (requires Docker Desktop running):

```bash
docker-compose up -d neo4j
```

Docker Compose includes:
- **Healthcheck** on Neo4j (port 7474)
- **Backend `depends_on`** neo4j when using full stack
- Explicit `NEO4J_USER` / `NEO4J_PASSWORD` env for backend service

Verify connection: `GET /api/graph/stats` → `neo4j_connected: true`

Neo4j Browser: http://localhost:7474 (user `neo4j`, password `scinova12`)

If Neo4j is offline, the platform continues using the SQL graph (PostgreSQL/SQLite). The Knowledge Graph Explorer shows connection status.

### Neo4j Integration in Knowledge Graph Explorer

When Neo4j is connected, the explorer can query the graph DB directly:

| Mode | Behavior |
|------|----------|
| **Auto** (default) | Uses Neo4j when online; falls back to SQL |
| **Neo4j** | Cypher queries + multi-hop neighborhood (2-hop) |
| **SQL** | Original PostgreSQL/SQLite graph |

- Evidence and source chunks are **enriched from SQL** even when querying Neo4j
- Header shows **Querying: NEO4J** or **SQL**
- **Sync Neo4j** button bulk-syncs SQL → Neo4j
- API: `GET /graph/full?source=neo4j`, `POST /graph/sync`

---

## Module Completion Matrix

| Module | Backend | Frontend | Real Data | Production Ready |
|--------|---------|----------|-----------|------------------|
| Executive Dashboard | ✅ | ✅ | Partial | ⬜ |
| Scientific Data Fabric | ✅ | ✅ | ✅ | 🟡 |
| Knowledge Graph | ✅ | ✅ | ✅ | 🟡 |
| Agent Marketplace | ✅ | ✅ | 28/78 agents real (see inventory) | 🟡 |
| Agent Execution | ✅ | ✅ | 7 specialized pipelines + RAG | 🟡 |
| Workflow Builder | ✅ | ✅ | ✅ Real orchestration | 🟡 |
| SLM Console | ✅ | ✅ | ✅ Ministral 8B via Mistral API | 🟡 |
| Governance | ✅ | ✅ | ✅ Live approvals + GxP | 🟡 |
| Scientific Reports | ✅ | ✅ | ✅ Two-pass LLM + rich PDF/DOCX/MD | 🟡 |
| Collaboration / Meeting Briefs | ✅ | ✅ | ✅ LLM briefs + export | 🟡 |
| Projects & Workspace Scoping | ✅ | ✅ | ✅ Per-user data isolation | 🟡 |
| Authentication & Admin | ✅ | ✅ | JWT + bcrypt; user CRUD | 🟡 |
| App Shell (TopBar, search, notifications) | ✅ | ✅ | ✅ Command palette, status strip | 🟡 |
| Molecular / Cheminformatics | ✅ | ✅ | ✅ RDKit ADMET + virtual screening | 🟡 |

Legend: ✅ Done · 🟡 Functional (needs hardening for prod) · ⬜ Not done

### Agent Marketplace — quick summary

| Status | Count | What happens when you run the agent |
|--------|-------|--------------------------------------|
| ✅ **Working** | **24** | Dedicated pipeline — LLM + evidence (PubMed, KEGG, KG, vector, ELN) or RDKit |
| 🟡 **Partial** | **4** | RAG only — answers from your uploaded documents |
| ⬜ **Not working** | **50** | Mock placeholder output |

See **[All Agents — Status Registry](#all-agents--status-registry)** below for the full per-agent list.

For full design specs (mission, pipeline, I/O, routing, governance, workflows), see **[AGENT_SPEC_CARDS.md](./AGENT_SPEC_CARDS.md)** — 78 Super Agent Spec Cards (~4,300 lines). Regenerate with `python scripts/generate_agent_spec_cards.py`.

For **business domain logic** — how agents map to pharma R&D outcomes, workflows, and KPIs — see **[DOMAIN_BUSINESS_LOGIC_AGENTS.md](./DOMAIN_BUSINESS_LOGIC_AGENTS.md)**.

---

## All Agents — Status Registry

Complete inventory of all **78 agents** in the Agent Marketplace, grouped by value-chain stage.

### Status legend

| Status | Meaning |
|--------|---------|
| ✅ **Working** | Dedicated pipeline — LLM synthesis + multi-source evidence (or RDKit for molecular agents) |
| 🟡 **Partial** | RAG only — answers from uploaded documents via vector search; no specialized synthesis |
| ⬜ **Not working** | Mock placeholder — structured demo output until a dedicated pipeline is implemented |

**Prerequisites:** Working and partial agents need a `query` in the run payload. Working agents also need `OPENAI_API_KEY` (and `MISTRAL_API_KEY` for SLM-routed tasks). Partial agents benefit from documents uploaded in Data Fabric.

**Execution dispatch** (`agent_executor.py`): specialized pipeline → RAG fallback → mock. Agent name keywords route to the correct service (`hypothesis_service`, `experiment_service`, `report_service`, `literature_service`, `target_discovery_service`, `knowledge_agent_service`, `molecular_service`).

**Related (not counted as working agents):** Document parsing runs via the **Data Fabric ingestion pipeline** (`document_parser.py`), not the Document Parser Agent card. Workflow orchestration runs via **Workflow Builder** (`workflow_orchestrator.py`), not the Workflow Orchestrator agent card.

### Summary

| Status | Count |
|--------|-------|
| ✅ Working | 24 |
| 🟡 Partial | 4 |
| ⬜ Not working | 50 |
| **Total** | **78** |

### Target Discovery (6 agents — 6 working, 0 partial, 0 not working)

| Agent | Pipeline | Status | Notes |
|-------|----------|--------|-------|
| Biomarker Discovery Agent | Target discovery pipeline | ✅ Working | LLM + evidence (vector, PubMed, KEGG, KG, ELN) — requires OPENAI_API_KEY |
| Druggability Finder Agent | Target discovery pipeline | ✅ Working | LLM + evidence (vector, PubMed, KEGG, KG, ELN) — requires OPENAI_API_KEY |
| Evidence Scout Agent | Literature pipeline | ✅ Working | LLM + evidence (vector, PubMed, KEGG, KG, ELN) — requires OPENAI_API_KEY |
| Pathway Insight Agent | Target discovery pipeline | ✅ Working | LLM + evidence (vector, PubMed, KEGG, KG, ELN) — requires OPENAI_API_KEY |
| Target Hypothesis Generation Agent | Hypothesis pipeline | ✅ Working | LLM + evidence (vector, PubMed, KEGG, KG, ELN) — requires OPENAI_API_KEY |
| Target Validation Agent | Target discovery pipeline | ✅ Working | LLM + evidence (vector, PubMed, KEGG, KG, ELN) — requires OPENAI_API_KEY |

### Lead Identification (6 agents — 3 working, 0 partial, 3 not working)

| Agent | Pipeline | Status | Notes |
|-------|----------|--------|-------|
| Assay Design Agent | Experiment pipeline | ✅ Working | LLM + evidence (vector, PubMed, KEGG, KG, ELN) — requires OPENAI_API_KEY |
| Deduplication, Filtering & Hit-Ranking Agent | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Early Risk Profiling Agent | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| MPO Scoring Agent | Molecular / RDKit pipeline | ✅ Working | Provide SMILES/compounds in query; demo compounds used if empty |
| Molecule Generation Agent | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Virtual Screening Agent | Molecular / RDKit pipeline | ✅ Working | Provide SMILES/compounds in query; demo compounds used if empty |

### Lead Optimization (6 agents — 2 working, 1 partial, 3 not working)

| Agent | Pipeline | Status | Notes |
|-------|----------|--------|-------|
| ADMET Prediction Agent | Molecular / RDKit pipeline | ✅ Working | Provide SMILES/compounds in query; demo compounds used if empty |
| Developability Scoring Agent | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Explainable ADMET Agent | Molecular / RDKit pipeline | ✅ Working | Provide SMILES/compounds in query; demo compounds used if empty |
| Multitarget QSAR Agent | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Off-Target Risk Prediction Agent | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Selectivity & Mechanism Agent | RAG (document Q&A only) | 🟡 Partial | Answers from ingested docs only — no PubMed/KEGG synthesis |

### Preclinical Studies (6 agents — 1 working, 0 partial, 5 not working)

| Agent | Pipeline | Status | Notes |
|-------|----------|--------|-------|
| Efficacy Modelling Agent | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Formulation Strategy Agent | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| In-vivo Study Design Agent | Experiment pipeline | ✅ Working | LLM + evidence (vector, PubMed, KEGG, KG, ELN) — requires OPENAI_API_KEY |
| PK/PD Modelling Agent | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Toxicity Prediction Agent | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Translational Package Assembly Agent | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |

### Early Development & CMC (6 agents — 0 working, 0 partial, 6 not working)

| Agent | Pipeline | Status | Notes |
|-------|----------|--------|-------|
| Analytical Characterization Agent | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Formulation Optimisation Agent | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Manufacturing Planning Agent | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Process Design and Scale-up Agent | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Quality by Design Agent | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Stability Prediction Agent | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |

### Cross-Functional (28 agents — 9 working, 2 partial, 17 not working)

| Agent | Pipeline | Status | Notes |
|-------|----------|--------|-------|
| AI Risk Assessor | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Bioinformatics Assistant | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Competitive Intel Assistant | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Contract Review Assistant | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| DOE Designer Assistant | Experiment pipeline | ✅ Working | LLM + evidence (vector, PubMed, KEGG, KG, ELN) — requires OPENAI_API_KEY |
| Data Governance Assistant | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Decision Capture Assistant | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| ELN/LIMS Copilot Assistant | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Experiment Planner Assistant | Experiment pipeline | ✅ Working | LLM + evidence (vector, PubMed, KEGG, KG, ELN) — requires OPENAI_API_KEY |
| GxP Compliance Assistant | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Hypothesis Builder Assistant | Hypothesis pipeline | ✅ Working | LLM + evidence (vector, PubMed, KEGG, KG, ELN) — requires OPENAI_API_KEY |
| Hypothesis Validation Assistant | Hypothesis pipeline | ✅ Working | LLM + evidence (vector, PubMed, KEGG, KG, ELN) — requires OPENAI_API_KEY |
| IP Landscape Screener | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Inventory Manager Assistant | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Knowledge Scout Assistant | Literature pipeline | ✅ Working | LLM + evidence (vector, PubMed, KEGG, KG, ELN) — requires OPENAI_API_KEY |
| Literature/Patent Miner | Literature pipeline | ✅ Working | LLM + evidence (vector, PubMed, KEGG, KG, ELN) — requires OPENAI_API_KEY |
| Model Ops Assistant | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| NGS Data Quality Assistant | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Omics Ingestion Assistant | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Ontology Mapper Assistant | Knowledge graph pipeline | ✅ Working | LLM + evidence (vector, PubMed, KEGG, KG, ELN) — requires OPENAI_API_KEY |
| Privacy Guard Assistant | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Sample Tracker Assistant | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Scheduler Ops Assistant | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Scientific Writer Assistant | Report pipeline | ✅ Working | LLM + evidence (vector, PubMed, KEGG, KG, ELN) — requires OPENAI_API_KEY |
| Semantic Q&A Assistant | RAG (document Q&A only) | 🟡 Partial | Answers from ingested docs only — no PubMed/KEGG synthesis |
| Study Report Generator | Report pipeline | ✅ Working | LLM + evidence (vector, PubMed, KEGG, KG, ELN) — requires OPENAI_API_KEY |
| Synthetic Data Generator | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Traceability Management Assistant | RAG (document Q&A only) | 🟡 Partial | Answers from ingested docs only — no PubMed/KEGG synthesis |

### Foundation (20 agents — 3 working, 1 partial, 16 not working)

| Agent | Pipeline | Status | Notes |
|-------|----------|--------|-------|
| Data Profiler/Validator | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Document Parser Agent | Mock placeholder | ⬜ Not working | Parsing works via ingestion pipeline, not this agent card |
| Drift/Bias Monitor Agent | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Entity Resolver Agent | Mock placeholder | ⬜ Not working | Entity resolution runs during ingestion (`entity_resolver.py`), not as agent |
| Feature Engineer Agent | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Image Segmenter Agent | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| KG Builder Agent | Knowledge graph pipeline | ✅ Working | LLM + evidence (vector, PubMed, KEGG, KG, ELN) — requires OPENAI_API_KEY |
| Model Evaluator Agent | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Model Tuner Agent | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Notification/Alert Agent | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Paper Summarizer Agent | Literature pipeline | ✅ Working | LLM + evidence (vector, PubMed, KEGG, KG, ELN) — requires OPENAI_API_KEY |
| Plot/Graph Generator | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Relationship Identifier Agent | RAG (document Q&A only) | 🟡 Partial | Answers from ingested docs only — no PubMed/KEGG synthesis |
| Result Capture Agent | Report pipeline | ✅ Working | LLM + evidence (vector, PubMed, KEGG, KG, ELN) — requires OPENAI_API_KEY |
| Schema Mapper Agent | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Scientific DB Query Agent | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Table/Figure Generator | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Tool Selection Router | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Web Search Agent | Mock placeholder | ⬜ Not working | Returns placeholder text until dedicated pipeline is built |
| Workflow Orchestrator | Mock placeholder | ⬜ Not working | Workflows run via Workflow Builder UI, not this agent card |

### Working agents by pipeline (24 total)

| Pipeline | Agents |
|----------|--------|
| Hypothesis (3) | Target Hypothesis Generation Agent, Hypothesis Builder Assistant, Hypothesis Validation Assistant |
| Experiment (4) | Experiment Planner Assistant, DOE Designer Assistant, Assay Design Agent, In-vivo Study Design Agent |
| Report (3) | Study Report Generator, Scientific Writer Assistant, Result Capture Agent |
| Literature (4) | Literature/Patent Miner, Evidence Scout Agent, Knowledge Scout Assistant, Paper Summarizer Agent |
| Target discovery (4) | Pathway Insight Agent, Target Validation Agent, Biomarker Discovery Agent, Druggability Finder Agent |
| Knowledge graph (2) | Ontology Mapper Assistant, KG Builder Agent |
| Molecular (4) | Virtual Screening Agent, MPO Scoring Agent, ADMET Prediction Agent, Explainable ADMET Agent |

### Partial agents (4 total)

| Agent | Limitation |
|-------|------------|
| Semantic Q&A Assistant | Document Q&A only — primary RAG entry point |
| Selectivity & Mechanism Agent | No pathway/mechanism synthesis — vector search answers only |
| Traceability Management Assistant | No audit trail synthesis — document retrieval only |
| Relationship Identifier Agent | No NLP relationship extraction — document Q&A only |

---

## API Endpoint Status

### Data Fabric

| Endpoint | Status | Real Implementation |
|----------|--------|---------------------|
| `POST /api/ingest/upload` | ✅ | Async pipeline v3 |
| `GET /api/ingest/status/{job_id}` | ✅ | Live progress |
| `GET /api/fabric/search` | ✅ | ChromaDB semantic search |
| `GET /api/fabric/stats` | ✅ | Index stats |

### Agents (RAG)

| Endpoint | Status | Real Implementation |
|----------|--------|---------------------|
| `POST /api/rag/query` | ✅ | Direct RAG Q&A with citations |
| `POST /api/agents/{id}/run` | ✅ | RAG + hypothesis/experiment/report pipelines |
| `GET /api/agents/{id}/runs` | ✅ | Run history with citations |

### Knowledge Graph

| Endpoint | Status | Real Implementation |
|----------|--------|---------------------|
| `GET /api/graph/full` | ✅ | Live SQL graph, filters |
| `GET /api/graph/search` | ✅ | Search + document filter |
| `GET /api/graph/stats` | ✅ | SQL + Neo4j stats |
| `GET /api/graph/neighborhood/{id}` | ✅ | Evidence + source chunks |
| `POST /api/graph/node` | ✅ | Manual node creation |
| `POST /api/graph/relationship` | ✅ | Manual relationship creation |

### Workflows & Governance

| Endpoint | Status | Real Implementation |
|----------|--------|---------------------|
| `POST /api/workflows/run` | ✅ | Step-by-step agent execution with chaining |
| `GET /api/workflows/{id}/export` | ✅ | Download all agent outputs (Markdown / JSON) |
| `GET /api/workflows/{id}/steps/{n}/export` | ✅ | Download single agent step (Markdown) |
| `POST /api/workflows/{id}/resume` | ✅ | Resume after Governance approval |
| `POST /api/approval` | ✅ | Approve/reject → audit + workflow resume |
| `GET /api/governance/gxp-check` | ✅ | Computed GxP readiness checks |
| `POST /api/risk-alerts/{id}/acknowledge` | ✅ | Acknowledge risk with audit trail |
| `GET /api/audit` | ✅ | Live audit events from ingest/agents/workflows |

### Auth, Admin & Projects

| Endpoint | Status | Real Implementation |
|----------|--------|---------------------|
| `POST /api/auth/login` | ✅ | JWT bearer token |
| `GET /api/auth/me` | ✅ | Current user profile |
| `GET/POST /api/admin/users` | ✅ | Admin-only user list + create |
| `DELETE /api/admin/users/{id}` | ✅ | Admin delete with FK cleanup |
| `GET/POST /api/projects` | ✅ | User-scoped projects |
| `GET /api/quotas/me` | ✅ | Per-user upload/workflow quotas |

### Scientific Reports & Collaboration

| Endpoint | Status | Real Implementation |
|----------|--------|---------------------|
| `POST /api/reports/generate` | ✅ | Two-pass LLM for hypothesis/experiment types |
| `GET /api/reports` | ✅ | User-scoped report list |
| `GET /api/reports/{id}/export?format=pdf\|docx\|markdown` | ✅ | Multi-section GxP export |
| `PATCH /api/reports/{id}/status` | ✅ | Draft → review → approved → published |
| `POST /api/collaboration/meeting-brief` | ✅ | LLM meeting brief generation |
| `GET /api/collaboration/meeting-brief/{id}/export` | ✅ | Brief export |
| `GET /api/collaboration/activity` | ✅ | Recent collaboration events |

---

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `SECRET_KEY` | **Yes (prod)** | JWT signing — change from dev default before deploy |
| `DATABASE_URL` | **Yes (prod)** | PostgreSQL connection string |
| `REDIS_URL` | Recommended | Celery broker for async ingestion |
| `USE_CELERY` | No | Default `true` — async ingestion via worker |
| `OPENAI_API_KEY` | Recommended | Embeddings + frontier LLM (hypothesis, validation, experiment design, reports) |
| `MISTRAL_API_KEY` | Recommended | Ministral 8B for all SLM-routed agent tasks |
| `SLM_MODEL` | No | Default `ministral-8b-latest` |
| `MISTRAL_BASE_URL` | No | Default `https://api.mistral.ai/v1` |
| `EMBEDDING_MODEL` | No | Default `text-embedding-3-small` |
| `LLM_MODEL` | No | Frontier default `gpt-4o-mini` |
| `OPENAI_BASE_URL` | No | Compatible API endpoint |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` | No | Graph DB sync |
| `NEO4J_ENABLED` | No | Toggle Neo4j sync (default `true`) |
| `CHROMA_HOST` / `CHROMA_PORT` / `CHROMA_USE_HTTP` | No | Remote ChromaDB in Docker (`chromadb:8000`) |
| `CHROMA_PERSIST_DIR` | No | Local vector store path (non-Docker) |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | No | Default 512 / 64 |
| `QUOTA_MAX_UPLOADS` / `QUOTA_MAX_WORKFLOWS` | No | Per-user limits (admin bypass) |
| `CORS_ORIGINS` | Prod | Frontend origin(s) for API access |

**Note:** Docker Compose loads root `.env` into **backend** and **celery-worker** via `env_file`. Service hostnames in `docker-compose.yml` override localhost values for DB, Redis, Neo4j, and ChromaDB.

---

---

## Phase 4 — Real Agents (RAG + LLM) ✅ Complete

| Component | Status | Implementation |
|-----------|--------|----------------|
| RAG retrieval pipeline | ✅ | `services/rag_service.py` — ChromaDB semantic search + document titles |
| LLM grounded answers | ✅ | `llm_service.chat()` — OpenAI-compatible chat completions |
| Citation enrichment | ✅ | Chunk ID, document title, excerpt, relevance score |
| Agent executor RAG path | ✅ | `agent_executor.py` — Vector Search / Q&A agents use real RAG |
| Direct RAG API | ✅ | `POST /api/rag/query` |
| Agent run API | ✅ | `POST /api/agents/{id}/run` with `task_type: qa` |
| Agent Workspace UI | ✅ | Answer panel, citations, document scope, RAG agent grouping |
| Citation → Knowledge Graph | ✅ | Links with `?document_id=` filter |

### RAG Agent Detection

Agents use **real RAG** when the run includes a `query` and any of:

- `task_type` is `qa`, `query`, or `question`
- `Vector Search` or `KG Query` in `tools_used`
- Agent name contains "Q&A" or "Knowledge Scout"

Primary agent: **Semantic Q&A Assistant** (seed data).

### RAG Request Shape

```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "What is ABT-494 and its primary indication?",
    "task_type": "qa",
    "document_id": "optional-scope-to-one-doc",
    "top_k": 8
  }
}
```

Direct endpoint: `POST /api/rag/query` with `{ "query", "document_id?", "top_k?" }`.

### Output Shape

```json
{
  "output_json": {
    "answer": "...",
    "mode": "rag",
    "chunks_used": 8,
    "model_used": "gpt-4o-mini",
    "findings": ["..."]
  },
  "citations_json": [
    {
      "index": 1,
      "title": "Document title",
      "document_id": "...",
      "chunk_index": 3,
      "relevance": 0.78,
      "excerpt": "..."
    }
  ]
}
```

Non-RAG agents without a specialized pipeline match return **mock output** (50 catalog agents). Agents with specialized or RAG pipelines require a `query` in `input_data`.

---

## Phase 5 — Orchestrator + Governance ✅ Complete

| Component | Status | Implementation |
|-----------|--------|----------------|
| Workflow step execution | ✅ | `workflow_orchestrator.py` — calls `execute_agent()` per step |
| Step chaining | ✅ | Prior step outputs passed as context to next agent |
| Approval gates | ✅ | Pauses at `requires_approval` steps → `ApprovalRequest` |
| Workflow resume | ✅ | Governance approve → `POST /api/workflows/{id}/resume` |
| Agent approval gates | ✅ | High-risk agents create `ApprovalRequest` on `pending_review` |
| Audit trail | ✅ | `governance_service.py` — ingest, agents, workflows, approvals |
| GxP readiness API | ✅ | `GET /api/governance/gxp-check` |
| Risk acknowledge | ✅ | `POST /api/risk-alerts/{id}/acknowledge` |
| Workflow Builder UI | ✅ | Live step status, pending approval link to Governance |
| Governance UI | ✅ | Dynamic GxP checks, approval actions resume workflows |

### Workflow Lifecycle

```
POST /workflows/run → step 1 agent → step 2 agent → …
  → [approval gate] → status: pending_approval
  → Governance approve → POST /workflows/{id}/resume → continue steps → completed
```

SLM-routed tasks invoke **Ministral 8B** via Mistral API; frontier tasks use OpenAI (`LLM_MODEL`).

---

## Phase 8 — Ministral 8B SLM + Workflow Exports ✅ Complete

| Component | Status | Implementation |
|-----------|--------|----------------|
| Dual LLM provider | ✅ | `llm_service.py` — OpenAI (frontier) + Mistral (SLM) |
| Ministral 8B inference | ✅ | `SLM_MODEL=ministral-8b-latest` via `MISTRAL_API_KEY` |
| SLM routing | ✅ | `model_router.py` → `model_type: slm` uses Ministral |
| Frontier routing | ✅ | Hypothesis, validation, experiment design → `LLM_MODEL` |
| Agent pipelines | ✅ | All specialized services pass routed model to `chat_json` |
| SLM profiles | ✅ | Six logical profiles; runtime model `ministral-8b-latest` |
| Workflow export (all steps) | ✅ | `GET /api/workflows/{id}/export?format=markdown\|json` |
| Per-agent download | ✅ | `GET /api/workflows/{id}/steps/{n}/export` |
| Workflow UI downloads | ✅ | Per-step + bundle buttons in `WorkflowProgress.jsx` |

### Model routing

| Task class | Model | Provider |
|------------|-------|----------|
| Literature mining, ontology mapping, summarization, extraction | Ministral 8B | Mistral API |
| Hypothesis build/validate, experiment design, high-risk | `LLM_MODEL` | OpenAI API |
| Embeddings, entity extraction (ingest) | `EMBEDDING_MODEL` / `LLM_MODEL` | OpenAI API |

### Workflow downloads

After running **Literature → Hypothesis** (or any workflow):

- **Download all agent outputs (.md)** — single Markdown file with all 7 agent sections
- **Export JSON** — structured bundle with full `output_json` per step
- **Per-step Download** — each completed agent (e.g. Scientific Writer Assistant) as its own `.md` file

---

## Agent Task Settings ✅ Complete

| Component | Status | Implementation |
|-----------|--------|----------------|
| Settings persistence | ✅ | `AgentTaskSettings` table + `agent_settings_service.py` |
| Settings API | ✅ | `GET/PUT /api/settings/agent-tasks` |
| Settings UI | ✅ | `frontend/src/pages/Settings.jsx` — global, task-type, per-agent |
| Agent Workspace apply | ✅ | `apply_agent_task_settings()` on `/agents/{id}/run` |
| Workflow apply | ✅ | Same merge applied before each workflow step |

### Instruction stacking

Saved instructions merge in order (then appended to the user query):

1. **Global** — platform-wide defaults (therapeutic area, citation style, etc.)
2. **Task type** — literature, hypothesis, experiment, report, target discovery, knowledge graph, QA
3. **Per-agent** — override for a specific agent (e.g. Literature Miner)
4. **Run-level** — optional `custom_instructions` in request payload (future UI)

Nav: **Platform → Settings** in the left rail.

---

## Phase 6 — Specialized Agents + External Integrations ✅ Complete

| Component | Status | Implementation |
|-----------|--------|----------------|
| Evidence gathering pipeline | ✅ | `evidence_service.py` — vector + PubMed + KEGG + KG + ELN |
| PubMed connector | ✅ | `external_integrations.search_pubmed` — NCBI E-utilities |
| KEGG connector | ✅ | `external_integrations.search_kegg` — KEGG REST API |
| ELN/LIMS connector | ✅ | Indexed protocol/ELN documents from Data Fabric |
| Hypothesis agents | ✅ | `hypothesis_service.py` — build + validate with structured JSON |
| Experiment design agents | ✅ | `experiment_service.py` — plans + DOE designs |
| Report agents | ✅ | `report_service.py` — GxP-aware sections + citations |
| Molecular / ADMET | ✅ | `molecular_service.py` — RDKit descriptors, virtual screening, docking hook |
| Agent output polish | ✅ | `output_style.py`, `AgentOutputRenderer.jsx` — professional prose, no raw markdown |
| Agent executor dispatch | ✅ | Specialized → RAG → mock fallback |
| Report generation API | ✅ | `POST /api/reports/generate` invokes real pipelines |
| Integrations health API | ✅ | `GET /api/integrations/status` |
| Agent Workspace UI | ✅ | Hypothesis/Experiment/Report agent group + structured output |
| Reports UI | ✅ | Report type selector + query-driven generation |

### Specialized Agent Names (real LLM pipelines)

| Pipeline | Agents |
|----------|--------|
| Hypothesis | Target Hypothesis Generation, Hypothesis Builder, Hypothesis Validation |
| Experiment | Experiment Planner, DOE Designer, Assay Design, In-vivo Study Design |
| Report | Study Report Generator, Scientific Writer, Result Capture |
| Literature | Literature/Patent Miner, Evidence Scout, Knowledge Scout, Paper Summarizer |
| Target discovery | Pathway Insight, Target Validation, Biomarker Discovery, Druggability Finder |
| Knowledge graph | Ontology Mapper, KG Builder |
| Molecular | Virtual Screening, MPO Scoring, ADMET Prediction, Explainable ADMET |

### Evidence Sources per Run

```
query → Vector Search (ChromaDB)
      → PubMed (NCBI)
      → KEGG (pathways/genes)
      → Knowledge Graph (SQL/Neo4j)
      → ELN/LIMS (indexed protocol documents)
      → LLM synthesis (Ministral 8B for SLM tasks · OpenAI frontier for complex reasoning) → structured output + unified citations
```

Optional: set `NCBI_EMAIL` in `.env` for PubMed API etiquette.

---

## Phase 7 — More Real Agents + E2E Workflows ✅ Complete

| Component | Status | Implementation |
|-----------|--------|----------------|
| Literature agents | ✅ | `literature_service.py` — Miner, Evidence Scout, Knowledge Scout |
| Target discovery agents | ✅ | `target_discovery_service.py` — Pathway, Validation, Biomarker, Druggability |
| KG/Ontology agents | ✅ | `knowledge_agent_service.py` — Ontology Mapper, KG Builder |
| Specialized before RAG | ✅ | `agent_executor.py` dispatch order |
| Express workflow runs | ✅ | `auto_approve` for uninterrupted pipeline execution |
| Auto report on completion | ✅ | `finalize_workflow_report()` → `ScientificReport` |
| Pipeline catalog API | ✅ | `GET /api/workflows/pipelines` |
| Workflow Builder UI | ✅ | 3 pipeline cards, query input, live step progress, report link |

### Real Agent Pipelines (Phase 6 + 7)

| Pipeline | Example agents |
|----------|----------------|
| Literature | Literature/Patent Miner, Evidence Scout, Knowledge Scout |
| Target Discovery | Pathway Insight, Target Validation, Biomarker Discovery, Druggability Finder |
| Knowledge Graph | Ontology Mapper, KG Builder |
| Hypothesis | Hypothesis Builder, Hypothesis Validation, Target Hypothesis Generation |
| Experiment | Experiment Planner, DOE Designer, Assay Design, In-vivo Study Design |
| Report | Study Report Generator, Scientific Writer, Result Capture |
| Molecular | Virtual Screening, MPO Scoring, ADMET Prediction, Explainable ADMET |
| RAG Q&A | Semantic Q&A Assistant (+ 3 Vector Search agents) |

### End-to-End Workflows

| Workflow | Template | Output report |
|----------|----------|---------------|
| Literature → Hypothesis | Literature to Hypothesis (7 steps) | `hypothesis_report` |
| Hypothesis → Experiment Plan | Experiment Planning (6 steps) | `experiment_plan` |
| Target Discovery Brief | Target Discovery (5 steps) | `target_discovery` |

Run from **Workflow Builder** → edit query → **Run Workflow** → view report when complete → **Download all agent outputs**.

---

## Phase 9 — Detailed Scientific Reports + UI Polish ✅ Complete

| Component | Status | Implementation |
|-----------|--------|----------------|
| Two-pass report generation | ✅ | `report_service.py` — structured agent → `expand_report_narrative()` for hypothesis/experiment/target types |
| Report section enrichment | ✅ | `report_content_builder.py` — builds `section_content` for UI and exports |
| Rich PDF export | ✅ | `report_export_service.py` — multi-section, references, hypotheses, experiment plans |
| DOCX + Markdown export | ✅ | Same payload; export-time re-enrichment for legacy sparse reports |
| Report types (Scientific Reports UI) | ✅ | hypothesis, experiment_plan, study_report, target_discovery, cmc_readiness |
| Reports detail view | ✅ | `Reports.jsx` — section_content, hypotheses, export buttons |
| Agent output renderer | ✅ | `AgentOutputRenderer.jsx` — structured, styled agent results |
| TopBar shell | ✅ | `TopBar.jsx` — search (⌘K), notifications, fullscreen, project modal |
| Command palette | ✅ | `CommandPalette.jsx` — global navigation search |
| Live status strip | ✅ | `StatusStrip.jsx` — backend/Neo4j/Chroma health |
| Admin user delete | ✅ | `DELETE /api/admin/users/{id}` with optimistic UI update |

### Scientific Report generation flow

```
User query → specialized agent (hypotheses / experiment plan / etc.)
          → expand_report_narrative()  [800–1500 word GxP narrative]
          → enrich_report_content()    [section_content for UI + export]
          → ScientificReport saved
          → export PDF / DOCX / Markdown
```

**Note:** Reports generated before 2026-06-07 may be sparse — regenerate for full content. Re-export alone partially enriches old reports but does not re-run the LLM.

---

## Docker Deployment

Full local stack:

```bash
docker compose up -d
```

| Service | Port | Purpose |
|---------|------|---------|
| frontend | 5173 | Vite dev server (proxies `/api` → backend) |
| backend | 8000 | FastAPI API |
| postgres | 5432 | Metadata + graph SQL |
| neo4j | 7474 / 7687 | Graph DB (Browser + Bolt) |
| redis | 6379 | Celery broker |
| chromadb | 8001 | Vector store (HTTP mode in Docker) |
| celery-worker | — | Async document ingestion |

Restart backend after Python changes: `docker compose restart backend` (app code is volume-mounted).

For remote partner access, deploy the stack to a VPS or Railway — partners use the **web app URL + login**, not the Docker host directly.

---

## Next Recommended Steps

1. **Wire more mock agents** — prioritize Competitive Intel, GxP Compliance, PK/PD Modelling, Bioinformatics (50 stubs remain)
2. **Production hardening** — rotate `SECRET_KEY`, TLS, rate limiting, email/OAuth auth
3. **Workflow report parity** — apply two-pass expansion in `finalize_workflow_report()` for hypothesis/experiment workflow outputs
4. **Re-ingest documents** — Apply graph quality filters to existing index
5. **OCR** — Scanned PDF support via Tesseract or cloud OCR
6. **Remote deployment** — Railway/VPS config for partner demos

---

## Changelog

| Date | Change |
|------|--------|
| 2026-06-06 | Phase 0 prototype complete |
| 2026-06-06 | Phase 2 Data Fabric pipeline implemented |
| 2026-06-06 | Phase 3 Knowledge Graph — Neo4j sync, LLM extraction, live explorer |
| 2026-06-06 | OpenAI embedding + LLM extraction documented in `.env.example` |
| 2026-06-06 | Backend config loads root `.env`; OpenAI key validated; ChromaDB corrupt-store recovery |
| 2026-06-06 | Phase 4 RAG agents — rag_service, llm_service.chat, Agent Workspace Q&A UI |
| 2026-06-06 | Document library page (`/documents`) with search and pagination |
| 2026-06-06 | Graph quality — entity_quality.py, gene heuristics, relationship filtering |
| 2026-06-06 | Phase 5 — real workflow orchestration, governance approvals, GxP API |
| 2026-06-06 | Phase 8 — Ministral 8B SLM integration (Mistral API) + workflow agent output downloads |
| 2026-06-06 | Agent Task Settings page — global, task-type, and per-agent custom instructions |
| 2026-06-06 | Neo4j integrated into Knowledge Graph Explorer (query source toggle, sync API) |
| 2026-06-06 | Phase 6 — specialized hypothesis/experiment/report agents + PubMed/KEGG/ELN integrations |
| 2026-06-06 | Phase 7 — literature/target/KG agents + E2E workflows with auto-report |
| 2026-06-07 | Phase 1 — JWT auth, bcrypt, Postgres-only Docker, Celery+Redis ingestion, user workspace scoping |
| 2026-06-07 | Admin user CRUD + delete API; projects, quotas, CLI user management |
| 2026-06-07 | Molecular agents — RDKit ADMET, virtual screening, chemoinformatics + docking hook |
| 2026-06-07 | Phase 9 — two-pass Scientific Reports, `report_content_builder`, rich PDF/DOCX/MD export |
| 2026-06-07 | Agent output polish — `output_style.py`, `AgentOutputRenderer.jsx` |
| 2026-06-07 | App shell — CommandPalette (⌘K), notifications, StatusStrip, project modal |
| 2026-06-07 | Docker — `env_file: .env`, backend/celery hot-reload mounts, full 7-service stack |
| 2026-06-07 | Agent inventory documented — 24 specialized + 4 RAG + 50 mock of 78 total |
| 2026-06-07 | All Agents — Status Registry section added (per-agent working/partial/not-working tables) |
| 2026-06-07 | AGENT_SPEC_CARDS.md — 78 Super Agent Spec Cards with full design logic, I/O, routing, workflows |
| 2026-06-07 | DOMAIN_BUSINESS_LOGIC_AGENTS.md — value chain, business outcomes O1–O8, workflow logic, KPIs |
