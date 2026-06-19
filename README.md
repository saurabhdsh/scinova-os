# SciAi-Nova OS

**SciFabric AgentOS** — An AI-native Scientific Data Fabric and Agent Operating System for Pharma R&D.

SciAi-Nova OS enables scientists to connect evidence, generate hypotheses, design experiments, analyze results, and produce traceable scientific outputs across the full pharma research value chain.

## Platform Capabilities

- **Scientific Data Fabric** — Ingest, normalize, classify, and connect scientific data (PDFs, papers, patents, ELN/LIMS exports, omics, compound libraries)
- **Scientific Knowledge Graph** — Entity-relationship modeling with evidence traceability
- **Agent Marketplace** — 80+ specialized agents across Target Discovery → CMC
- **SLM Layer** — Pluggable small language model routing with frontier LLM fallback
- **Research Orchestrator** — Multi-agent workflow coordination with human approval checkpoints
- **Governance & Compliance** — Audit trails, risk alerts, GxP checks, model decision traceability

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React, Vite, Tailwind CSS, React Router, Recharts, React Flow |
| Backend | Python FastAPI, SQLAlchemy, Pydantic |
| Database | PostgreSQL (SQLite fallback for local dev) |
| Vector DB | ChromaDB (placeholder) |
| Graph DB | Neo4j (placeholder) |
| LLM | OpenAI-compatible interface + local SLM abstraction |

## Quick Start

### Option 1: start.sh (Recommended)

```bash
chmod +x start.sh
./start.sh
```

Open http://localhost:5173 and sign in with:
- **scientist** / **sci123**
- **admin** / **admin123**
- **reviewer** / **rev123**

### Option 2: Manual

**Backend:**
```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### Option 3: Docker Compose (Full Stack)

```bash
cp .env.example .env
docker compose up -d
```

### Option 4: Azure VM (personal account)

See **[AZURE.md](./AZURE.md)** for portal VM setup, NSG rules, and:

```bash
./scripts/deploy-azure.sh
./scripts/preflight-azure.sh
```

## API Documentation

Once the backend is running: http://localhost:8000/docs

### Key Endpoints

| Module | Endpoints |
|--------|-----------|
| Data Fabric | `POST /api/ingest/upload`, `GET /api/documents`, `GET /api/entities` |
| Knowledge Graph | `POST /api/graph/node`, `GET /api/graph/search`, `GET /api/graph/neighborhood/{id}` |
| Agents | `GET /api/agents`, `POST /api/agents/{id}/run` |
| Workflows | `GET /api/workflows/templates`, `POST /api/workflows/run` |
| SLM | `GET /api/models/slm`, `POST /api/models/route` |
| Governance | `GET /api/audit`, `GET /api/risk-alerts`, `POST /api/approval` |
| Reports | `GET /api/reports`, `POST /api/reports/generate` |

## Seeded Mock Data

On first startup, the platform seeds:
- 50 scientific documents
- 100 scientific entities
- 80 graph relationships
- 80+ research agents (all categories)
- 6 SLM profiles
- 5 workflow templates
- 20 audit events, 10 risk alerts, 10 reports

## UI Pages

1. Executive Dashboard
2. Research Value Chain View
3. Scientific Data Fabric Console
4. Knowledge Graph Explorer
5. Agent Marketplace
6. Agent Execution Workspace
7. Workflow Builder
8. SLM Management Console
9. Governance & Compliance
10. Scientific Reports

## Project Structure

```
SciNova OS/
├── frontend/          # React + Vite application
├── backend/           # FastAPI application
│   ├── app/
│   │   ├── models/    # SQLAlchemy + Pydantic models
│   │   ├── routes/    # API endpoints
│   │   ├── services/  # Business logic, model router, orchestrator
│   │   └── seed.py    # Database seeding
├── docker-compose.yml
├── start.sh
└── .env.example
```

## Key Outcome

> AI Assistance empowers scientists to reclaim an extra day each week for high-value research, driving faster innovation and enhanced productivity.
