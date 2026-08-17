# SciNova — 2–3 Minute Demo Script  
## Research Value Chain · Agent Catalog · Hypothesis Builder · Agent Execution · Research Orchestrator

**Duration:** ~2 min 30 sec (fast) · up to 3 min (with orchestrator completion)  
**Audience:** Discovery leads, R&D IT, innovation partners  
**Login:** `scientist` / `sci123` (or `admin` / `admin123`)  
**Project:** Select **MASH-417** (or any project with indexed PDFs)

---

## Architecture framing — agents vs instruments & tools

Use this one-liner early in the demo if stakeholders ask *“What is SciNova, really?”*

> **Agents decide. Tools compute. The Data Fabric holds evidence — including outputs from lab instruments.**

| Layer | What it is | Pharma analogy | SciNova module |
|-------|------------|----------------|----------------|
| **Evidence** | Documents, assay files, ELN/LIMS exports, vectors, graph | Lab notebooks, instrument readouts, papers | **Scientific Data Fabric** |
| **Instruments & tools** | Engines agents invoke to gather or compute facts | HPLC, plate readers, RDKit, docking, PubMed, KEGG | **Tool Fabric** (+ custom REST tools) |
| **Reasoning** | Fast extraction vs deep scientific judgment | Junior analyst vs senior scientist | **SLMs** + **Scientific LLMs** |
| **Workers** | Scoped AI roles that orchestrate tools toward an outcome | Target biologist, med chemist, study director | **Agents** (Catalog + Workspace) |
| **Pipelines** | Multi-step programs chaining agents and tools | Program workflow from lit review → hypothesis → plan | **Research Orchestrator** |

**Important distinction for demos:**

- **Agents are not tools.** An agent is a *role* (e.g. Hypothesis Builder) that selects and calls the right tools.
- **Tool Fabric = instruments & computational tools** — RDKit, AutoDock Vina, PubMed, KEGG, vector search, knowledge graph, plus admin-registered APIs (proprietary QSAR, ELN connectors).
- **Lab instrument data** enters via **Data Fabric** (CSV/XLSX assay exports, ELN/LIMS PDFs) — not live instrument drivers in the current pilot.
- After each run, point to **Tools used this run** in Agent Workspace — that is the audit trail of which instruments/tools executed.

**15-second demo line:**

> “We don’t replace your scientists or your instruments. SciNova is an **Agent OS** that connects **evidence** from the Data Fabric, invokes certified **tools** like RDKit and PubMed through Tool Fabric, and delivers **traceable outcomes** through governed agents and orchestrated workflows.”

---

## Pre-demo checklist (30 sec before you share screen)

| Check | Why |
|-------|-----|
| Backend + frontend running | Avoid spinners on first agent run |
| At least 1–2 PDFs **indexed** in Scientific Data Fabric | Hypothesis Builder cites real evidence |
| OpenAI / Bedrock key configured | Real LLM output (not mock) |
| Project **MASH-417** selected in top bar | Scoped evidence for MASH narrative |

**Optional MASH query pack** (swap in anywhere below):

> *GLP-1 receptor agonists for metabolic dysfunction-associated steatohepatitis (MASH) — fibrosis, inflammation, and clinical biomarkers from indexed studies and literature*

---

## Demo flow at a glance

| Time | Screen | Message |
|------|--------|---------|
| 0:00–0:25 | Research Value Chain | How agents map to the drug discovery pipeline |
| 0:25–0:50 | Research Agent Catalog | Discover, filter, launch specialized agents |
| 0:50–1:35 | Ask & Run Agents → Hypothesis Builder | Single-agent execution with evidence + citations |
| 1:35–2:30+ | Research Orchestrator | Multi-agent pipeline → hypothesis report |

---

## Segment 1 — Research Value Chain (~25 sec)

**Navigate:** Left rail → **Research Value Chain** (`/value-chain`)

**Say:**

> "SciNova organizes AI agents along the full **research value chain** — from Target Discovery through Lead Identification, Lead Optimization, Preclinical Studies, and Early Development.
>
> This isn't a flat chatbot list. Each stage has purpose-built agents — pathway analysis, virtual screening, ADMET, study design — so scientists see **where** AI fits in their program, not just **what** it can answer."

**Show:**

1. Scroll horizontally across the five stage columns.
2. Pause on **Target Discovery** — point out agent count.
3. Optionally click **Launch** on one card (e.g. Pathway Insight Agent) — you can return without running.

**Key line:**

> "The value chain view is our **operating map** — agents aligned to how pharma R&D actually runs."

---

## Segment 2 — Research Agent Catalog (~25 sec)

**Navigate:** Left rail → **Research Agent Catalog** (`/agents`)

**Say:**

> "The **Research Agent Catalog** is the full library — every agent with category, risk level, SLM eligibility, and human-approval requirements.
>
> Scientists can filter by value-chain stage, category, or risk — for example, only **medium-risk** agents that need a governance checkpoint before outputs are treated as approved."

**Show:**

1. Point to the header count (e.g. *78 agents available*).
2. Set **Stage** filter → **Target Discovery** (or **Cross-Functional**).
3. Toggle **SLM Eligible Only** briefly — explain cost/latency vs frontier LLM routing.
4. Open one agent card — note **Risk** badge and **Approval** chip.

**Key line:**

> "Catalog is **governance-aware discovery** — the right agent for the right decision, with risk visible upfront."

---

## Segment 3 — Hypothesis Builder + Agent Execution (~45 sec)

**Navigate:** Left rail → **Ask & Run Agents** (`/agents/workspace`)  
**Or:** From Catalog → **Launch** on **Hypothesis Builder Assistant**

**Say:**

> "For a focused scientific task, we run a single agent in the **Agent Workspace**.
>
> Before execution, the workspace shows **Execution Context** — indexed documents in the Data Fabric and which **Tool Fabric** bindings this agent can use: vector search, PubMed, KEGG, knowledge graph.
>
> I'll run the **Hypothesis Builder Assistant** — it turns evidence into **ranked, testable hypotheses** with supporting citations."

**Show:**

1. Select **Hypothesis Builder Assistant** in the left picker.
2. **Execution Context** panel — mention indexed doc count; optionally scope one MASH PDF.
3. Switch to **Pipeline** mode (not Q&A) if needed.
4. Paste query:

   ```
   Generate ranked target hypotheses for GLP-1 pathway modulation in MASH —
   focus on fibrosis regression, inflammatory biomarkers, and druggable nodes
   ```

5. Click **Run Agent**.
6. When results appear, highlight:
   - **Summary** / structured **hypotheses[]**
   - **Citations** `[1]`, `[2]` from indexed chunks
   - **Confidence** score
   - **Tools used this run** (PubMed, KG, vector index)

**Key line:**

> "Every answer is **grounded and traceable** — not a black-box paragraph. That's the Scientific Data Fabric feeding the agent."

**If time is tight:** Stop after the summary; skip expanding every hypothesis card.

---

## Segment 4 — Research Orchestrator (~55 sec – 2 min)

**Navigate:** Left rail → **Research Orchestrator** (`/workflows`)

**Say:**

> "Individual agents answer one question. The **Research Orchestrator** chains them into **multi-step pipelines** — literature mining, knowledge mapping, hypothesis build and validation, and a final scientific report — with live progress on each step."

**Show:**

1. Read the hero subtitle: *multi-agent pipelines … traceable scientific reports*.
2. In **Research Question**, use the pre-filled query or paste:

   ```
   GLP-1 agonists for MASH — synthesize evidence on efficacy, fibrosis, and safety
   from indexed studies and literature
   ```

3. Select the **Literature → Hypothesis** pipeline card (7 steps · auto-report).
4. Point to step chips: **Literature Miner · Knowledge Scout · Hypothesis Builder · Scientific Writer**.
5. Click **Run Workflow**.

**While orchestrating (narrate over progress UI):**

> "Step 1 — **Literature/Patent Miner** gathers corpus evidence.
> Step 2 — **Knowledge Scout** connects concepts.
> Steps 3–4 — **Ontology Mapper** and **KG Builder** normalize entities and extend the graph.
> Step 5 — **Hypothesis Builder** forms ranked hypotheses — this is a **governance gate** in production.
> Step 6 — **Hypothesis Validation** checks evidence for and against.
> Step 7 — **Scientific Writer** produces the narrative sections."

**On completion:**

1. Show the completed step timeline (green checkmarks, confidence per step).
2. Open **Download** / link to **Scientific Reports** if a hypothesis report was generated.
3. Optional one-liner: *"In demo mode we auto-approve gates; in production, Discovery leads approve before hypotheses commit to the program."*

**Key line:**

> "One research question → seven specialized agents → one **traceable hypothesis report** — that's the Agent Operating System on the Scientific Data Fabric."

---

## Closing (~15 sec)

**Say:**

> "To recap: the **Research Value Chain** shows where agents fit in R&D. The **Agent Catalog** lets scientists find and govern them. **Agent Workspace** runs focused tasks like hypothesis generation with citations. And the **Research Orchestrator** delivers end-to-end, multi-agent workflows with reports.
>
> Happy to go deeper on Data Fabric ingestion, Knowledge Graph, or governance next."

---

## Quick reference — navigation labels

| UI label | Route |
|----------|-------|
| Research Value Chain | `/value-chain` |
| Research Agent Catalog | `/agents` |
| Ask & Run Agents | `/agents/workspace` |
| Hypothesis Builder (direct) | `/agents/run/{agent-id}` via Launch |
| Research Orchestrator | `/workflows` |

---

## Literature → Hypothesis pipeline (7 steps)

| Step | Agent | Business outcome |
|------|-------|------------------|
| 1 | Literature/Patent Miner | Mined corpus + summary |
| 2 | Knowledge Scout Assistant | Knowledge map |
| 3 | Ontology Mapper Assistant | Normalized entities |
| 4 | KG Builder Agent | Suggested relationships |
| 5 | Hypothesis Builder Assistant | Ranked hypotheses ⚠️ approval |
| 6 | Hypothesis Validation Assistant | Verdict + evidence ⚠️ approval |
| 7 | Scientific Writer Assistant | Narrative sections |
| **Final** | Auto report | **Hypothesis report** (Scientific Reports) |

---

## Troubleshooting (presenter notes)

| Issue | Fix |
|-------|-----|
| Agent returns mock / generic text | Set `OPENAI_API_KEY` or Bedrock; restart backend |
| No citations | Upload PDFs in Data Fabric; wait for `indexed` status |
| Workflow quota error | Use admin account or raise quota in Settings |
| Orchestrator slow | Narrate over progress; pre-run workflow before live demo |
| 0 graph relationships (old ingest) | Re-upload PDFs or run relationship backfill on server |

---

## Alternate 2-minute cut (if orchestrator won't finish live)

1. **Value Chain** — 20 sec (one stage only)  
2. **Agent Catalog** — 20 sec (filter + one card)  
3. **Hypothesis Builder run** — 50 sec (full result)  
4. **Research Orchestrator** — 30 sec (show pipeline card + step list **without** clicking Run; say "runs live in ~90 seconds")

**Total:** ~2 min with no wait for workflow completion.
