# SciNova OS — Domain Business Logic & Agent Outcomes

> How marketplace agents map to **pharma R&D business outcomes** across the value chain.  
> Complements technical specs in [AGENT_SPEC_CARDS.md](./AGENT_SPEC_CARDS.md) and platform status in [design.md](./design.md).  
> Last updated: 2026-06-07

---

## 1. Executive summary

SciNova OS is an **Agent Operating System on a Scientific Data Fabric**. The business logic is not “run an AI chat” — it is:

1. **Ingest** proprietary and external scientific evidence (**Data Fabric**).
2. **Invoke** registered scientific tools (**Tool Fabric** — RDKit, AutoDock, PubMed, KEGG, etc.).
3. **Reason** with **SLMs** (fast extraction) and **Scientific LLMs** (complex decisions).
4. **Execute** via **Agents** scoped to R&D outcomes.
5. **Decide** with traceable citations, confidence scores, and governance gates.
6. **Record** outcomes as GxP-aware scientific reports, audit events, and workflow artifacts.

### Enterprise five-layer stack

```
┌─────────────────────────────────────────────────────────────────┐
│  AGENTS (78 marketplace) — business outcomes & orchestration       │
├─────────────────────────────────────────────────────────────────┤
│  Scientific LLMs (OpenAI gpt-4o-mini) + SLMs (Ministral 8B)      │
├─────────────────────────────────────────────────────────────────┤
│  TOOL FABRIC — RDKit, AutoDock Vina, PubMed, KEGG, Neo4j, ELN…    │
├─────────────────────────────────────────────────────────────────┤
│  DATA FABRIC — documents, vectors, knowledge graph, LIMS/ELN     │
└─────────────────────────────────────────────────────────────────┘
```

**Settings → Tool Fabric (per agent):** Any user assigns tool bindings per agent in **Platform → Settings → Agent Tasks** — e.g. Virtual Screening Agent → **AutoDock Vina** for docking; ADMET Prediction Agent → **RDKit**, **DeepChem**, or a **custom QSAR API** for properties. Bindings persist per user workspace and apply automatically to **Agent Workspace** runs and **Workflow** steps.

**Settings → Tool Registry (admin only):** Administrators register organization-specific REST tools (internal QSAR, proprietary docking APIs, ELN connectors). Registered tools merge into the platform catalog, appear in agent tool dropdowns for all users, and are invoked at runtime when bound. Invocations are audit-logged in Governance (`custom_tool_registered`, `custom_tool_invoked`, `custom_tool_invocation_failed`).

**Agent Workspace → Execution Context:** When a scientist selects an agent, the workspace shows **Data Fabric** (indexed document count + optional document scope) and **Tool Fabric** (resolved tool bindings for that agent) side by side *before* running. After a run, **Tools used this run** confirms which engines executed, including custom integrations.

| Example agent | Tool Fabric roles | Platform default | Enterprise override example |
|---------------|-------------------|------------------|----------------------------|
| Virtual Screening Agent | Descriptors, ADMET, Docking | RDKit → RDKit → RDKit 3D Shape | Custom hit scorer + AutoDock Vina |
| ADMET Prediction Agent | Descriptors, Property prediction | RDKit | `custom_acme_qsar_v3` REST API |
| Literature/Patent Miner | Literature, Knowledge graph | PubMed, Neo4j/SQL KG | Vector Search only (internal docs) |
| Pathway Insight Agent | Pathway, Literature, KG | KEGG, PubMed, Neo4j/SQL KG | Custom pathway DB connector |

**Implementation references:** `backend/app/services/tool_fabric_service.py`, `custom_tool_service.py`, `custom_tool_executor.py` · UI: Settings (Agent Tasks + Tool Registry), Agent Workspace (Execution Context).

**Today:** 24 agents deliver real business outcomes; 4 provide document Q&A; 50 are catalogued for future capability. Three featured **business processes** (workflows) chain agents into end-to-end outcomes with auto-generated reports. **Tool Fabric** is live for platform tools + admin-registered custom REST integrations.

---

## 1.1 Tool Fabric — business operating model

Tool Fabric is how enterprises **plug their own scientific engines** into agents without rewriting agent logic. It separates *what decision the agent makes* from *which certified tool computes the evidence*.

### Three configuration layers (Settings)

| Layer | Who | Business purpose |
|-------|-----|------------------|
| **Global instructions** | Any user | Company standards, therapeutic area, citation style |
| **Task-type instructions** | Any user | Guidance for literature, hypothesis, experiment, report, etc. |
| **Per-agent Tool Fabric bindings** | Any user | Which engine runs for each tool role (RDKit vs custom QSAR) |
| **Custom Tool Registry** | **Admin only** | Register proprietary REST endpoints into the catalog |

Bindings stack at runtime: **global → task → agent tools & instructions → user query**.

### Tool roles (what business capability is outsourced)

| Role ID | Business capability | Built-in options | Custom tool example |
|---------|---------------------|------------------|---------------------|
| `molecular_descriptors` | Compute physicochemical descriptors | RDKit, DeepChem (planned) | In-house descriptor service |
| `property_prediction` | ADMET / property prediction | RDKit, DeepChem (planned) | Corporate QSAR v3 API |
| `docking` | Structure-based or shape screening | RDKit 3D Shape, AutoDock Vina | Proprietary FEP/docking farm |
| `literature` | External literature retrieval | PubMed, Vector Search | Licensed literature API |
| `pathway` | Pathway database lookup | KEGG | Internal pathway knowledge base |
| `knowledge_graph` | Entity neighborhood query | Neo4j/SQL KG | Enterprise graph service |

Agent type determines **which roles appear** (keyword mapping on agent name — e.g. “virtual screening” → descriptors + property + docking).

### Runtime flow (Agent Workspace & workflows)

```
Scientist selects agent
        │
        ▼
Execution Context panel shows:
  • Data Fabric — N indexed docs, optional scope
  • Tool Fabric — resolved bindings (defaults + Settings overrides)
        │
        ▼
Run Agent / Workflow step
        │
        ├── Built-in tool (RDKit, PubMed, KEGG…) → native service
        └── Custom tool (custom_*) → HTTP POST/GET to registered endpoint
        │
        ▼
Output includes tool_fabric + custom_tool_results + audit events
```

**Custom ADMET API contract:** endpoints should return JSON with a `predictions` array of compound rows; SciNova merges into agent output and falls back to RDKit if the call fails.

### API surfaces (for integrators)

| Endpoint | Access | Purpose |
|----------|--------|---------|
| `GET /settings/tool-fabric` | Authenticated user | Full catalog (built-in + custom) |
| `GET /agents/{id}/tool-fabric/bindings` | Authenticated user | Resolved bindings for workspace display |
| `GET/POST/PUT/DELETE /admin/tool-fabric` | **Admin** | Custom tool CRUD |
| `POST /admin/tool-fabric/{id}/test` | **Admin** | Connectivity test before go-live |

---

## 2. Domain model — pharma R&D as a decision chain

Every agent exists to advance one link in this chain:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  EVIDENCE   │───▶│   INSIGHT   │───▶│  DECISION   │───▶│   ACTION    │───▶│   RECORD    │
│  Data       │    │  Analysis   │    │  Go/no-go   │    │  Plan /     │    │  Report /   │
│  Fabric +   │    │  agents +   │    │  rank       │    │  design     │    │  audit      │
│  Tool       │    │  Tool       │    │             │    │             │    │             │
│  Fabric     │    │  Fabric     │    │             │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

| Link | Business question | Platform capability | Typical deliverable |
|------|-------------------|---------------------|---------------------|
| **Evidence** | What do we know, and from where? | **Data Fabric** (ingestion, vector index, KG) + **Tool Fabric** (PubMed, KEGG, ELN, custom APIs) | Indexed documents, citations, computed descriptors |
| **Insight** | What does the evidence imply? | Literature, target, hypothesis, molecular agents + bound Tool Fabric engines | Ranked lists, scores, narratives |
| **Decision** | What should we pursue or stop? | Validation agents, governance approval gates | Verdict, validation score, approval record |
| **Action** | What do we do next in the lab? | Experiment planner, DOE, assay design | Protocol outline, DOE matrix, timeline |
| **Record** | What is the auditable output? | Scientific Reports, workflow exports, audit trail | PDF/DOCX report, Markdown bundle, audit event |

**Business rule:** No agent output is a final regulatory submission by itself — it is a **decision-support artifact** with evidence trail, suitable for scientist review and GxP workflows.

---

## 3. Business outcome taxonomy

Outcomes are grouped by what the **business user** receives:

| Outcome type | Description | Example deliverable | Primary consumers |
|--------------|-------------|---------------------|-------------------|
| **O1 — Evidence bundle** | Curated sources supporting a claim | Citation list with excerpts, PubMed/KEGG hits | Scientists, medical affairs |
| **O2 — Ranked shortlist** | Ordered candidates (targets, hits, hypotheses) | Top 3 hypotheses with confidence | Discovery teams, portfolio committees |
| **O3 — Validation verdict** | Go / conditional / stop with rationale | `supported`, `partially_supported`, validation score | Target review boards |
| **O4 — Experimental plan** | Actionable study design | Endpoints, controls, sample size, timeline | Lab leads, CRO planners |
| **O5 — Compound profile** | ADMET / screening characterization | Lipinski, QED, hit list, flags | Medicinal chemistry |
| **O6 — Scientific report** | Formal narrative for internal/external use | Hypothesis report, study report PDF | Regulatory prep, program teams |
| **O7 — Knowledge map** | Entity relationships and gaps | KG suggestions, ontology mappings | Bioinformatics, data stewards |
| **O8 — Compliance artifact** | Traceability and approval | Audit event, approval request, GxP check | QA, governance |

Agents are designed to produce one or more of **O1–O8**. Workflows chain them so later steps consume earlier outcomes (e.g. O1 → O2 → O3 → O6).

---

## 4. Value chain stages — business logic by domain

### 4.1 Target Discovery

**Business problem:** *Which targets are biologically plausible, evidence-backed, and druggable for our indication?*

| Business outcome | Decision enabled | Agents (runtime) | Business logic |
|------------------|------------------|------------------|----------------|
| Pathway & mechanism map | Prioritize nodes in cascade | Pathway Insight Agent ✅ | KEGG/Reactome + KG → druggable nodes |
| Evidence aggregation | Stop debating “is there literature?” | Evidence Scout Agent ✅ | PubMed + patents + internal docs → evidence report |
| Ranked target hypotheses | Portfolio shortlist | Target Hypothesis Generation Agent ✅ | Multi-source synthesis → ranked hypotheses |
| Target go/no-go | Investment in validation studies | Target Validation Agent ✅ | Evidence for/against → validation score + gaps |
| Biomarker options | Patient stratification strategy | Biomarker Discovery Agent ✅ | Omics/clinical context → candidate panel |
| Druggability assessment | Small molecule vs biologic modality | Druggability Finder Agent ✅ | Structural/ligand logic → druggability score |

**Featured business process:** **Target Discovery Brief** workflow → **O6** target discovery report.

**KPIs:** time to first ranked target list; number of cited sources; validation score distribution.

---

### 4.2 Lead Identification

**Business problem:** *Which chemical matter should we buy, make, or screen against the target?*

| Business outcome | Decision enabled | Agents (runtime) | Business logic |
|------------------|------------------|------------------|----------------|
| Virtual hit list | Compound purchase / synthesis | Virtual Screening Agent ✅ | Tool Fabric: RDKit screen + optional AutoDock Vina / custom scorer → ranked hits |
| MPO trade-off view | Lead quality vs diversity | MPO Scoring Agent ✅ | Multi-parameter scores → radar-friendly ranking |
| Assay blueprint | HTS / validation assay startup | Assay Design Agent ✅ | Protocol + controls from target context |
| Novel structures | IP / series expansion | Molecule Generation Agent ⬜ | *Planned:* generative chemistry |
| Hit triage | Remove duplicates / PAINS | Deduplication & Hit-Ranking Agent ⬜ | *Planned:* RDKit filters + composite score |
| Early safety flag | Kill weak series early | Early Risk Profiling Agent ⬜ | *Planned:* tox + off-target fusion |

**Enterprise note:** Lead Identification agents expose **Tool Fabric** roles for descriptors, property prediction, and docking — bind **AutoDock Vina** or a **custom screening API** in Settings without changing the agent card.

**KPIs:** hits per library; % Lipinski-compliant; time from target to assay-ready protocol.

---

### 4.3 Lead Optimization

**Business problem:** *Which leads do we advance, and what liabilities must we fix?*

| Business outcome | Decision enabled | Agents (runtime) | Business logic |
|------------------|------------------|------------------|----------------|
| ADMET profile | Series prioritization | ADMET Prediction Agent ✅ | Tool Fabric: RDKit descriptors + LLM narrative; optional **custom QSAR** via REST |
| Explainable liabilities | Chemist action list | Explainable ADMET Agent ✅ | Flags + structural rationale |
| Selectivity / MoA | De-risk wrong mechanism | Selectivity & Mechanism Agent 🟡 | *Partial:* doc Q&A only today |
| Off-target risk | Safety-driven deprioritization | Off-Target Risk Prediction Agent ⬜ | *Planned:* proteome SEA-style screen |
| QSAR multi-target | Series optimization | Multitarget QSAR Agent ⬜ | *Planned:* per-target models |
| Developability | Candidate nomination | Developability Scoring Agent ⬜ | *Planned:* developability rules |

**KPIs:** % compounds flagged hERG/CYP; cycle time to nominated candidate.

---

### 4.4 Preclinical Studies

**Business problem:** *How do we design studies that prove efficacy and safety efficiently?*

| Business outcome | Decision enabled | Agents (runtime) | Business logic |
|------------------|------------------|------------------|----------------|
| In-vivo protocol | Study startup | In-vivo Study Design Agent ✅ | Model, endpoints, power rationale |
| Efficacy model | Dose selection | Efficacy Modelling Agent ⬜ | *Planned:* PK/PD fit |
| PK/PD simulation | FIH dose projection | PK/PD Modelling Agent ⬜ | *Planned:* compartment models |
| Tox liability | Study design / stop rules | Toxicity Prediction Agent ⬜ | *Planned:* tox prediction fusion |
| Formulation path | Dose form for tox/efficacy | Formulation Strategy Agent ⬜ | *Planned:* formulation DB |
| IND package gaps | Translational readiness | Translational Package Assembly Agent ⬜ | *Planned:* gap checklist + report |

**Featured business process (partial):** Experiment Planning workflow — steps 1–3 ✅ deliver **O4**; steps 4–6 ⬜ (scheduler/inventory/ELN mock).

**KPIs:** protocol approval cycle time; study failure rate; IND gap count.

---

### 4.5 Early Development & CMC

**Business problem:** *Can we manufacture a stable, compliant product at scale?*

| Business outcome | Decision enabled | Agents (catalog) | Maturity |
|------------------|------------------|------------------|----------|
| Analytical method plan | Release/stability testing | Analytical Characterization Agent | ⬜ Planned |
| Formulation optimization | Bioavailability + stability | Formulation Optimisation Agent | ⬜ Planned |
| Process & scale-up | Tech transfer | Process Design and Scale-up Agent | ⬜ Planned |
| Manufacturing schedule | Supply for trials | Manufacturing Planning Agent | ⬜ Planned |
| Shelf-life prediction | Label claims / storage | Stability Prediction Agent | ⬜ Planned |
| QbD design space | Regulatory CMC narrative | Quality by Design Agent | ⬜ Planned |

**Scientific Reports:** **CMC Readiness** report type uses Study Report Generator ✅ for narrative assessment today.

**KPIs:** batch success rate; stability failures; CMC review cycles.

---

### 4.6 Cross-Functional (decision support layer)

**Business problem:** *How do teams find knowledge, form hypotheses, plan work, and document decisions across programs?*

| Business capability | Outcome | Key agents | Maturity |
|---------------------|---------|------------|----------|
| **Literature intelligence** | O1, O2 | Literature/Patent Miner ✅, Paper Summarizer ✅ | Working |
| **Internal knowledge Q&A** | O1 | Semantic Q&A Assistant 🟡 | Partial (needs uploaded docs) |
| **Hypothesis formation** | O2 | Hypothesis Builder ✅ | Working |
| **Hypothesis gate** | O3 | Hypothesis Validation ✅ | Working |
| **Experiment planning** | O4 | Experiment Planner ✅, DOE Designer ✅ | Working |
| **Scientific writing** | O6 | Scientific Writer ✅, Study Report Generator ✅ | Working |
| **ELN/LIMS bridge** | O1, O8 | Result Capture ✅; ELN Copilot ⬜ | Mixed |
| **Competitive / IP** | O2, O3 | Competitive Intel ⬜, IP Landscape ⬜ | Planned |
| **GxP / compliance** | O8 | GxP Compliance ⬜; Governance console ✅ | Mixed |
| **Program operations** | O4 | Scheduler, Inventory, Sample Tracker ⬜ | Planned |

**Featured business process:** **Literature → Hypothesis** workflow — full chain O1 → O2 → O3 → O6 (7 steps, all real agents).

---

### 4.7 Foundation (platform enablers)

Foundation agents support **infrastructure outcomes** that enable business agents:

| Enabler | Business value | Live today? |
|---------|----------------|-------------|
| Document parsing & indexing | Evidence enters the fabric | ✅ Ingestion pipeline (not agent card) |
| **Tool Fabric registry** | Enterprise owns which engines agents call | ✅ Built-in catalog + admin custom REST tools |
| Entity resolution & KG build | Reusable organizational knowledge | ✅ Ingestion + KG Builder Agent ✅ |
| Ontology mapping | Cross-study comparability | ✅ Ontology Mapper ✅ |
| Workflow orchestration | Repeatable business processes | ✅ Workflow Builder + orchestrator |
| Model routing (SLM vs LLM) | Cost/latency vs reasoning depth | ✅ model_router |
| Audit & traceability | GxP-ready provenance | ✅ audit events + reports |

---

## 5. End-to-end business processes (workflows)

Workflows are **compiled business logic** — fixed agent sequences that produce a **single business outcome** at the end.

### 5.1 Target Discovery Brief

| Step | Business activity | Agent | Outcome produced |
|------|-------------------|-------|------------------|
| 1 | Map biology | Pathway Insight | O7 pathway map, druggable nodes |
| 2 | Gather proof | Evidence Scout | O1 evidence bundle |
| 3 | Stratify patients | Biomarker Discovery | O2 biomarker candidates |
| 4 | **Decision gate** | Target Validation | O3 validation score ⚠️ approval |
| 5 | Modality check | Druggability Finder | O2 druggability assessment |
| **Final** | Executive brief | Auto report | **O6** target discovery report |

**Business outcome:** *“Should we invest in this target for this indication?”* — answered with a traceable brief.

---

### 5.2 Literature → Hypothesis

| Step | Business activity | Agent | Outcome produced |
|------|-------------------|-------|------------------|
| 1 | Mine literature | Literature/Patent Miner | O1 mined corpus + summary |
| 2 | Connect concepts | Knowledge Scout | O7 knowledge map |
| 3 | Normalize entities | Ontology Mapper | O7 mapped entities |
| 4 | Extend graph | KG Builder | O7 suggested relationships |
| 5 | **Form hypotheses** | Hypothesis Builder | O2 ranked hypotheses ⚠️ approval |
| 6 | **Validate** | Hypothesis Validation | O3 verdict ⚠️ approval |
| 7 | Write-up | Scientific Writer | O6 narrative sections |
| **Final** | Program document | Auto report | **O6** hypothesis report |

**Business outcome:** *“What testable hypotheses should the program pursue, backed by evidence?”*

---

### 5.3 Hypothesis → Experiment Plan

| Step | Business activity | Agent | Outcome | Maturity |
|------|-------------------|-------|---------|----------|
| 1 | Confirm hypothesis | Hypothesis Validation | O3 | ✅ |
| 2 | **Plan studies** | Experiment Planner | O4 | ✅ ⚠️ approval |
| 3 | Design matrix | DOE Designer | O4 DOE | ✅ |
| 4 | Schedule | Scheduler Ops | O4 timeline | ⬜ mock |
| 5 | Materials | Inventory Manager | O4 resources | ⬜ mock |
| 6 | ELN hook | ELN/LIMS Copilot | O8 | ⬜ mock |
| **Final** | Protocol package | Auto report | **O6** experiment plan | ✅ (from real steps) |

**Business outcome:** *“What experiments do we run next, and how?”* — core plan is real; ops steps are roadmap.

---

## 6. Scientific Reports — business deliverable catalog

Reports translate agent/workflow output into **stakeholder-ready documents**:

| Report type | Business purpose | Agent logic | Typical reader |
|-------------|------------------|-------------|----------------|
| **Hypothesis report** | Program direction / target rationale | Hypothesis pipeline + 2-pass narrative expansion | Discovery lead |
| **Target discovery** | Target review committee pack | Target discovery agents + expansion | Portfolio governance |
| **Experiment plan** | CRO / lab handoff | Experiment + DOE agents + expansion | Study director |
| **Study report** | GxP study summary | Report agent + evidence | QA / regulatory |
| **CMC readiness** | Early CMC gap assessment | Study report generator | CMC lead |
| **Meeting brief** | Collaboration sync | meeting_brief_service | Program team |

**Export formats:** PDF, DOCX, Markdown — for email, Veeva-adjacent workflows, or internal wiki.

---

## 7. Governance as business logic

High-risk decisions require **human approval** before outcomes are treated as approved:

| Risk trigger | Business reason | Platform behavior |
|--------------|-----------------|-------------------|
| Agent `risk_level: high` | Target validation, tox, IP | Approval request in Governance |
| Workflow `requires_approval: true` | Hypothesis commit, experiment spend | Workflow pauses → resume after approve |
| Agent `pending_review` | Model uncertainty / policy | Run status until approved |
| Custom tool invocation | Proprietary engine used in decision | Audit event with tool_id, latency, HTTP status |
| Custom tool registration change | IT/governance change to production integrations | `custom_tool_registered/updated/deleted` audit |

**Demo / pipeline runs** use `auto_approve: true` in Workflow Builder to complete uninterrupted; **production** should leave gates on for real go/no-go control.

**Business outcome O8:** every approval, report generation, and **custom tool invocation** writes an **audit event** — who, what, when, confidence, which engine.

---

## 8. Model routing — business trade-offs (SLM vs LLM)

| Business need | Route | Why |
|---------------|-------|-----|
| Fast literature scan, low decision impact | **SLM** (Ministral 8B) | Cost, latency, repetitive extraction |
| Hypothesis, validation, experiment design | **Frontier LLM** (GPT-4o-mini) | Reasoning depth, scientific risk |
| High-risk regulatory-adjacent | **Frontier + approval** | Quality + human checkpoint |

This mirrors how pharma orgs use **junior analyst** vs **senior scientist** roles — automated in the router.

---

## 9. Master matrix — agent → business outcome

Legend: ✅ Working · 🟡 Partial · ⬜ Planned

| Agent | Primary outcomes | Value chain | Status |
|-------|------------------|-------------|--------|
| Pathway Insight Agent | O2, O7 | Target Discovery | ✅ |
| Target Hypothesis Generation Agent | O2, O6 | Target Discovery | ✅ |
| Evidence Scout Agent | O1, O2 | Target Discovery | ✅ |
| Target Validation Agent | O3, O8 | Target Discovery | ✅ |
| Biomarker Discovery Agent | O2 | Target Discovery | ✅ |
| Druggability Finder Agent | O2, O3 | Target Discovery | ✅ |
| Virtual Screening Agent | O2, O5 | Lead Identification | ✅ |
| MPO Scoring Agent | O5 | Lead Identification | ✅ |
| Assay Design Agent | O4 | Lead Identification | ✅ |
| Molecule Generation Agent | O2, O5 | Lead Identification | ⬜ |
| Deduplication & Hit-Ranking Agent | O2, O5 | Lead Identification | ⬜ |
| Early Risk Profiling Agent | O3, O5 | Lead Identification | ⬜ |
| ADMET Prediction Agent | O5 | Lead Optimization | ✅ |
| Explainable ADMET Agent | O5 | Lead Optimization | ✅ |
| Selectivity & Mechanism Agent | O2, O7 | Lead Optimization | 🟡 |
| Multitarget QSAR Agent | O5 | Lead Optimization | ⬜ |
| Off-Target Risk Prediction Agent | O3, O5 | Lead Optimization | ⬜ |
| Developability Scoring Agent | O3, O5 | Lead Optimization | ⬜ |
| In-vivo Study Design Agent | O4 | Preclinical | ✅ |
| Efficacy / PK/PD / Tox / Formulation / Translational agents | O4, O6 | Preclinical | ⬜ |
| All CMC stage agents | O4, O6, O8 | Early Dev & CMC | ⬜ |
| Literature/Patent Miner | O1, O2 | Cross-Functional | ✅ |
| Semantic Q&A Assistant | O1 | Cross-Functional | 🟡 |
| Knowledge Scout Assistant | O7 | Cross-Functional | ✅ |
| Ontology Mapper Assistant | O7 | Cross-Functional | ✅ |
| Hypothesis Builder / Validation | O2, O3 | Cross-Functional | ✅ |
| Experiment Planner / DOE Designer | O4 | Cross-Functional | ✅ |
| Scientific Writer / Study Report / Result Capture | O6, O8 | Cross-Functional | ✅ |
| Competitive Intel / IP / GxP / Contract / AI Risk | O3, O8 | Cross-Functional | ⬜ |
| Scheduler / Inventory / Sample / ELN / Omics / Bioinformatics | O4, O8 | Cross-Functional | ⬜ |
| KG Builder / Paper Summarizer / Result Capture | O1, O7, O6 | Foundation | ✅ |
| Document Parser / Entity Resolver / Workflow Orchestrator | O1, O8 | Foundation | ✅ (non-card) |
| Remaining Foundation agents | Various | Foundation | ⬜ |

Full per-agent technical specs: [AGENT_SPEC_CARDS.md](./AGENT_SPEC_CARDS.md).

---

## 10. Example business case — JAK1 in rheumatoid arthritis

**Stakeholder question:** *Should we pursue JAK1 inhibition in RA, and what experiments prove it?*

| Phase | Business action | SciNova capability | Outcome |
|-------|-----------------|-------------------|---------|
| 0 | Admin registers **Acme QSAR v3** in Tool Registry; scientist binds ADMET Agent → custom tool | Tool Fabric (admin + Settings) | Enterprise engine in catalog |
| 1 | Upload internal Phase II summary + protocols | Data Fabric | O1 indexed evidence |
| 2 | Scientist opens ADMET Agent — **Execution Context** shows 12 indexed docs + Acme QSAR binding | Agent Workspace | Transparency before run |
| 3 | Run **Target Discovery Brief** | Workflow | O6 target brief with validation score |
| 4 | Committee reviews approval gate | Governance | O8 decision recorded |
| 5 | Run **Literature → Hypothesis** | Workflow | O2 ranked hypotheses + O6 report |
| 6 | Run **Experiment Plan** (validation + DOE steps) | Workflow | O4 study plan + O6 PDF |
| 7 | Export PDF for partner / CRO | Scientific Reports | O6 handoff package |

**Without uploads:** steps 3–5 still run using PubMed, KEGG, and KG — but **O1 from proprietary studies** requires Data Fabric ingestion. **Without custom tools:** ADMET steps use platform RDKit defaults.

---

## 11. Business maturity summary

| Value chain stage | Agents | Real outcomes today | Primary gap |
|-------------------|--------|---------------------|-------------|
| Target Discovery | 6 | **Full** — end-to-end workflow + report | — |
| Lead Identification | 6 | **Partial** — screen, MPO, assay | Generative chemistry, hit triage |
| Lead Optimization | 6 | **Partial** — ADMET | Selectivity (RAG only), off-target, QSAR |
| Preclinical | 6 | **Minimal** — in-vivo design only | PK/PD, tox, translational |
| CMC | 6 | **Narrative only** (CMC report type) | All CMC specialist agents |
| Cross-Functional | 28 | **Strong** — lit, hypothesis, experiment, reports | Ops, compliance, competitive |
| Foundation | 20 | **Platform live** incl. Tool Fabric + custom registry | Many specialist cards still roadmap |
| **Tool Fabric** | 11 built-in + ∞ custom | **Live** — per-agent binding, workspace visibility, audit | DeepChem/NONMEM native adapters planned |

**Partner demo recommendation:** Target Discovery Brief or Literature → Hypothesis — both deliver **O6** with only real agents.

---

## 12. Success metrics (business KPIs)

| KPI | What it measures | Where captured |
|-----|------------------|----------------|
| Time-to-hypothesis | Days from question to ranked hypotheses | Workflow run timestamps |
| Evidence depth | Citations per agent run | `citations_json` on AgentRun |
| Confidence trend | Model certainty on decisions | `confidence` on runs / reports |
| Approval cycle time | Governance latency | Audit events |
| Report completeness | Word count / sections | Scientific Reports `content_json` |
| Fabric coverage | % questions answerable from internal docs | Vector hit rate in RAG |
| Cost per outcome | SLM vs LLM routing mix | `model_selected` on runs |
| **Tool Fabric utilization** | % molecular runs using custom vs built-in engines | `tool_fabric` + `custom_tool_invoked` audit events |
| **Custom tool reliability** | Custom integration success rate | `custom_tool_invocation_failed` vs `custom_tool_invoked` |
| **Binding customization** | Agents with user-specific tool overrides | `agent_tool_bindings` in Settings |

---

## 13. Related documents

| Document | Audience | Content |
|----------|----------|---------|
| [design.md](./design.md) | Engineering / PM | Build status, architecture, API |
| [AGENT_SPEC_CARDS.md](./AGENT_SPEC_CARDS.md) | Engineering / architects | 78 agent technical spec cards |
| **This file** | Business, product, partners | Domain logic and business outcomes |

---

## 14. Glossary

| Term | Business meaning |
|------|------------------|
| **Data Fabric** | Single place for scientific documents and derived knowledge (vectors, KG, LIMS/ELN index) |
| **Tool Fabric** | Registry of callable scientific engines (RDKit, PubMed, custom REST APIs) bound to agents by role |
| **Tool role** | Category of capability an agent can outsource (e.g. property prediction, docking, literature) |
| **Custom tool** | Admin-registered REST integration (`custom_*` id) merged into catalog for all users |
| **Execution Context** | Agent Workspace panel showing Data Fabric scope + resolved Tool Fabric before a run |
| **Agent** | AI worker scoped to one R&D decision type |
| **Workflow** | Repeatable multi-agent business process |
| **Scientific Report** | Auditable outcome document for stakeholders |
| **Governance gate** | Human approval before high-impact decisions stick |
| **SLM** | Small model for fast, low-risk extraction tasks |
| **Frontier LLM** | Large model for complex scientific reasoning |
