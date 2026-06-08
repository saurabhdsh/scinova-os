# SciNova OS — Super Agent Spec Cards

> Full design specification for all **78 marketplace agents**.  
> Sources: `seed_data.py`, `agent_capabilities.py`, `model_router.py`, specialized services.  
> Last updated: 2026-06-07

---

## How to read these cards

| Field | Meaning |
|-------|---------|
| **Runtime status** | Behavior when run from Agent Workspace or Workflow Builder |
| **Catalog model** | SLM profile name in marketplace metadata |
| **Resolved inference** | Model after routing (`gpt-4o-mini` or `ministral-8b-latest`) |
| **Governance** | High-risk → approval in Governance unless `auto_approve: true` |

**Dispatch:** specialized → RAG → mock (`agent_executor.py`).

---

## Table of contents

### Target Discovery
- [Biomarker Discovery Agent](#biomarker-discovery-agent)
- [Druggability Finder Agent](#druggability-finder-agent)
- [Evidence Scout Agent](#evidence-scout-agent)
- [Pathway Insight Agent](#pathway-insight-agent)
- [Target Hypothesis Generation Agent](#target-hypothesis-generation-agent)
- [Target Validation Agent](#target-validation-agent)

### Lead Identification
- [Assay Design Agent](#assay-design-agent)
- [Deduplication, Filtering & Hit-Ranking Agent](#deduplication--filtering-and-hit-ranking-agent)
- [Early Risk Profiling Agent](#early-risk-profiling-agent)
- [MPO Scoring Agent](#mpo-scoring-agent)
- [Molecule Generation Agent](#molecule-generation-agent)
- [Virtual Screening Agent](#virtual-screening-agent)

### Lead Optimization
- [ADMET Prediction Agent](#admet-prediction-agent)
- [Developability Scoring Agent](#developability-scoring-agent)
- [Explainable ADMET Agent](#explainable-admet-agent)
- [Multitarget QSAR Agent](#multitarget-qsar-agent)
- [Off-Target Risk Prediction Agent](#off-target-risk-prediction-agent)
- [Selectivity & Mechanism Agent](#selectivity-and-mechanism-agent)

### Preclinical Studies
- [Efficacy Modelling Agent](#efficacy-modelling-agent)
- [Formulation Strategy Agent](#formulation-strategy-agent)
- [In-vivo Study Design Agent](#in-vivo-study-design-agent)
- [PK/PD Modelling Agent](#pk-pd-modelling-agent)
- [Toxicity Prediction Agent](#toxicity-prediction-agent)
- [Translational Package Assembly Agent](#translational-package-assembly-agent)

### Early Development & CMC
- [Analytical Characterization Agent](#analytical-characterization-agent)
- [Formulation Optimisation Agent](#formulation-optimisation-agent)
- [Manufacturing Planning Agent](#manufacturing-planning-agent)
- [Process Design and Scale-up Agent](#process-design-and-scale-up-agent)
- [Quality by Design Agent](#quality-by-design-agent)
- [Stability Prediction Agent](#stability-prediction-agent)

### Cross-Functional
- [AI Risk Assessor](#ai-risk-assessor)
- [Bioinformatics Assistant](#bioinformatics-assistant)
- [Competitive Intel Assistant](#competitive-intel-assistant)
- [Contract Review Assistant](#contract-review-assistant)
- [DOE Designer Assistant](#doe-designer-assistant)
- [Data Governance Assistant](#data-governance-assistant)
- [Decision Capture Assistant](#decision-capture-assistant)
- [ELN/LIMS Copilot Assistant](#eln-lims-copilot-assistant)
- [Experiment Planner Assistant](#experiment-planner-assistant)
- [GxP Compliance Assistant](#gxp-compliance-assistant)
- [Hypothesis Builder Assistant](#hypothesis-builder-assistant)
- [Hypothesis Validation Assistant](#hypothesis-validation-assistant)
- [IP Landscape Screener](#ip-landscape-screener)
- [Inventory Manager Assistant](#inventory-manager-assistant)
- [Knowledge Scout Assistant](#knowledge-scout-assistant)
- [Literature/Patent Miner](#literature-patent-miner)
- [Model Ops Assistant](#model-ops-assistant)
- [NGS Data Quality Assistant](#ngs-data-quality-assistant)
- [Omics Ingestion Assistant](#omics-ingestion-assistant)
- [Ontology Mapper Assistant](#ontology-mapper-assistant)
- [Privacy Guard Assistant](#privacy-guard-assistant)
- [Sample Tracker Assistant](#sample-tracker-assistant)
- [Scheduler Ops Assistant](#scheduler-ops-assistant)
- [Scientific Writer Assistant](#scientific-writer-assistant)
- [Semantic Q&A Assistant](#semantic-qanda-assistant)
- [Study Report Generator](#study-report-generator)
- [Synthetic Data Generator](#synthetic-data-generator)
- [Traceability Management Assistant](#traceability-management-assistant)

### Foundation
- [Data Profiler/Validator](#data-profiler-validator)
- [Document Parser Agent](#document-parser-agent)
- [Drift/Bias Monitor Agent](#drift-bias-monitor-agent)
- [Entity Resolver Agent](#entity-resolver-agent)
- [Feature Engineer Agent](#feature-engineer-agent)
- [Image Segmenter Agent](#image-segmenter-agent)
- [KG Builder Agent](#kg-builder-agent)
- [Model Evaluator Agent](#model-evaluator-agent)
- [Model Tuner Agent](#model-tuner-agent)
- [Notification/Alert Agent](#notification-alert-agent)
- [Paper Summarizer Agent](#paper-summarizer-agent)
- [Plot/Graph Generator](#plot-graph-generator)
- [Relationship Identifier Agent](#relationship-identifier-agent)
- [Result Capture Agent](#result-capture-agent)
- [Schema Mapper Agent](#schema-mapper-agent)
- [Scientific DB Query Agent](#scientific-db-query-agent)
- [Table/Figure Generator](#table-figure-generator)
- [Tool Selection Router](#tool-selection-router)
- [Web Search Agent](#web-search-agent)
- [Workflow Orchestrator](#workflow-orchestrator)

---

# Target Discovery

## 1. Biomarker Discovery Agent {#biomarker-discovery-agent}

**Runtime status:** ✅ Working  
**Category:** Target Discovery · **Value chain:** Target Discovery

### Mission
Identifies candidate biomarkers from omics and clinical datasets.

### Design logic
Name-based branch: Pathway, Validation, Biomarker, or Druggability specialist.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `target_discovery` |
| Service | `target_discovery_service.run_target_discovery_agent` |
| Source file | `backend/app/services/target_discovery_service.py` |
| Catalog model profile | `bioinformatics-slm` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Medium-risk task with mixed complexity routed to frontier LLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **medium** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** omics_dataset, cohort_metadata
- **Outputs:** biomarker_candidates, statistical_report
- **Tools (declared):** Bioinformatics Pipeline, Data Profiler

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "target_discovery",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query (required), top_k?
- **Runtime output:** pathways, druggable_targets, validation_score, biomarkers, druggability_score

### Evidence chain
Vector, PubMed, KEGG, KG

### Workflow appearances
- **Target Discovery** — step 3

### Scientific Reports integration
Target Discovery Brief workflow; Scientific Reports target_discovery

---

## 2. Druggability Finder Agent {#druggability-finder-agent}

**Runtime status:** ✅ Working  
**Category:** Target Discovery · **Value chain:** Target Discovery

### Mission
Assesses target druggability using structural and ligandability data.

### Design logic
Name-based branch: Pathway, Validation, Biomarker, or Druggability specialist.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `target_discovery` |
| Service | `target_discovery_service.run_target_discovery_agent` |
| Source file | `backend/app/services/target_discovery_service.py` |
| Catalog model profile | `molecular-intelligence-slm` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** protein_id, structure_data
- **Outputs:** druggability_score, binding_site_analysis
- **Tools (declared):** PDB Query, ChEMBL

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "target_discovery",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query (required), top_k?
- **Runtime output:** pathways, druggable_targets, validation_score, biomarkers, druggability_score

### Evidence chain
Vector, PubMed, KEGG, KG

### Workflow appearances
- **Target Discovery** — step 5

### Scientific Reports integration
Target Discovery Brief workflow; Scientific Reports target_discovery

---

## 3. Evidence Scout Agent {#evidence-scout-agent}

**Runtime status:** ✅ Working  
**Category:** Target Discovery · **Value chain:** Target Discovery

### Mission
Scouts and aggregates evidence from papers, patents, and clinical databases.

### Design logic
Agent name selects Miner, Evidence Scout, or Knowledge Scout JSON schema.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `literature` |
| Service | `literature_service.run_literature_agent` |
| Source file | `backend/app/services/literature_service.py` |
| Catalog model profile | `literature-intelligence-slm` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** target_name, disease
- **Outputs:** evidence_report, citations
- **Tools (declared):** PubMed, Patent DB, Vector Search

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "literature",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query (required), top_k?
- **Runtime output:** summary, answer, key_findings / evidence_items / connections (by variant)

### Evidence chain
Vector, PubMed, KEGG, KG

### Workflow appearances
- **Target Discovery** — step 2

### Scientific Reports integration
Steps 1–2 in Literature → Hypothesis workflow

---

## 4. Pathway Insight Agent {#pathway-insight-agent}

**Runtime status:** ✅ Working  
**Category:** Target Discovery · **Value chain:** Target Discovery

### Mission
Analyzes biological pathways to identify druggable nodes and cascade effects.

### Design logic
Name-based branch: Pathway, Validation, Biomarker, or Druggability specialist.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `target_discovery` |
| Service | `target_discovery_service.run_target_discovery_agent` |
| Source file | `backend/app/services/target_discovery_service.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** pathway_id, gene_list
- **Outputs:** pathway_map, druggable_nodes
- **Tools (declared):** KEGG, Reactome, KG Query

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "target_discovery",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query (required), top_k?
- **Runtime output:** pathways, druggable_targets, validation_score, biomarkers, druggability_score

### Evidence chain
Vector, PubMed, KEGG, KG

### Workflow appearances
- **Target Discovery** — step 1

### Scientific Reports integration
Target Discovery Brief workflow; Scientific Reports target_discovery

---

## 5. Target Hypothesis Generation Agent {#target-hypothesis-generation-agent}

**Runtime status:** ✅ Working  
**Category:** Target Discovery · **Value chain:** Target Discovery

### Mission
Generates ranked target hypotheses from literature and omics evidence.

### Design logic
Two-mode pipeline: **build** (structured hypotheses + narrative) or **validate** (verdict + evidence for/against). Report mode expands answer when report_type is hypothesis_report or target_discovery.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `hypothesis` |
| Service | `hypothesis_service.run_hypothesis_agent` |
| Source file | `backend/app/services/hypothesis_service.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Complex reasoning or scientific decision task routed to frontier LLM. |
| SLM eligible (catalog) | No |
| Risk level | **medium** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** disease, omics_data
- **Outputs:** hypothesis_list, evidence_bundle
- **Tools (declared):** Literature Miner, KG Builder

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "hypothesis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query (required), document_id?, document_ids?, top_k?, report_type?
- **Runtime output:** summary, answer, hypotheses[], gaps[], verdict?, evidence_for/against[], confidence

### Evidence chain
Vector index, PubMed, KEGG, Knowledge Graph

### Scientific Reports integration
Scientific Reports: hypothesis_report, target_discovery — two-pass expand_report_narrative()

---

## 6. Target Validation Agent {#target-validation-agent}

**Runtime status:** ✅ Working  
**Category:** Target Discovery · **Value chain:** Target Discovery

### Mission
Validates target-disease associations using multi-source evidence scoring.

### Design logic
Name-based branch: Pathway, Validation, Biomarker, or Druggability specialist.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `target_discovery` |
| Service | `target_discovery_service.run_target_discovery_agent` |
| Source file | `backend/app/services/target_discovery_service.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — High-risk task requires frontier LLM with human review checkpoint. |
| SLM eligible (catalog) | No |
| Risk level | **high** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** target_id, evidence_bundle
- **Outputs:** validation_score, gap_analysis
- **Tools (declared):** KG Query, Ontology Mapper

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "target_discovery",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query (required), top_k?
- **Runtime output:** pathways, druggable_targets, validation_score, biomarkers, druggability_score

### Evidence chain
Vector, PubMed, KEGG, KG

### Workflow appearances
- **Target Discovery** — step 4 ⚠️ approval gate

### Scientific Reports integration
Target Discovery Brief workflow; Scientific Reports target_discovery

---

# Lead Identification

## 7. Assay Design Agent {#assay-design-agent}

**Runtime status:** ✅ Working  
**Category:** Lead Identification · **Value chain:** Lead Identification

### Mission
Designs biochemical and cell-based assays for hit validation.

### Design logic
Branches on agent name: DOE Designer → DOE_SYSTEM; others → EXPERIMENT_PLAN_SYSTEM.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `experiment` |
| Service | `experiment_service.run_experiment_agent` |
| Source file | `backend/app/services/experiment_service.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Complex reasoning or scientific decision task routed to frontier LLM. |
| SLM eligible (catalog) | No |
| Risk level | **medium** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** target_info, compound_list
- **Outputs:** assay_protocol, controls
- **Tools (declared):** Protocol DB, Literature Miner

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "experiment",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query (required), document_id?, top_k?, report_type?
- **Runtime output:** summary, answer, experiment_plan{}, doe_design? (DOE agent), resources, risks

### Evidence chain
Vector, PubMed, KEGG, KG, ELN/LIMS; assay QC from linked documents

### Scientific Reports integration
Scientific Reports: experiment_plan — two-pass narrative expansion

---

## 8. Deduplication, Filtering & Hit-Ranking Agent {#deduplication--filtering-and-hit-ranking-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Lead Identification · **Value chain:** Lead Identification

### Mission
Deduplicates, filters, and ranks screening hits by multi-criteria scoring.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** RDKit dedup, MPO scoring, PAINS/reactive filters.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `molecular-intelligence-slm` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** hit_list, filters
- **Outputs:** ranked_hits, filter_report
- **Tools (declared):** RDKit, Data Profiler

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 9. Early Risk Profiling Agent {#early-risk-profiling-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Lead Identification · **Value chain:** Lead Identification

### Mission
Profiles early-stage compounds for toxicity and off-target risks.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** ToxPredict + off-target DB + literature fusion.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — High-risk task requires frontier LLM with human review checkpoint. |
| SLM eligible (catalog) | No |
| Risk level | **high** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** compound_list
- **Outputs:** risk_profile, alerts
- **Tools (declared):** ToxPredict, Off-Target DB

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 10. MPO Scoring Agent {#mpo-scoring-agent}

**Runtime status:** ✅ Working  
**Category:** Lead Identification · **Value chain:** Lead Identification

### Mission
Multi-parameter optimization scoring for lead compounds.

### Design logic
Virtual Screening: Lipinski + QED ranking. ADMET: RDKit + LLM narrative.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `molecular` |
| Service | `molecular_service.run_molecular_agent` |
| Source file | `backend/app/services/molecular_service.py` |
| Catalog model profile | `molecular-intelligence-slm` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** compound_list
- **Outputs:** mpo_scores, radar_chart_data
- **Tools (declared):** RDKit, ADMET Predictor

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "molecular",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** compound_list / smiles lines in query; demo compounds if empty
- **Runtime output:** admet_predictions or hit_list, admet_flags, recommendations

### Evidence chain
RDKit descriptors; optional docking_service shape screen

---

## 11. Molecule Generation Agent {#molecule-generation-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Lead Identification · **Value chain:** Lead Identification

### Mission
Generates novel molecular structures based on target pharmacophore constraints.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Generative chemistry from pharmacophore constraints (RDKit + LLM).

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Complex reasoning or scientific decision task routed to frontier LLM. |
| SLM eligible (catalog) | No |
| Risk level | **medium** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** target_structure, scaffold
- **Outputs:** molecule_list, SMILES
- **Tools (declared):** RDKit, Generative Model

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 12. Virtual Screening Agent {#virtual-screening-agent}

**Runtime status:** ✅ Working  
**Category:** Lead Identification · **Value chain:** Lead Identification

### Mission
Performs virtual screening against compound libraries.

### Design logic
Virtual Screening: Lipinski + QED ranking. ADMET: RDKit + LLM narrative.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `molecular` |
| Service | `molecular_service.run_molecular_agent` |
| Source file | `backend/app/services/molecular_service.py` |
| Catalog model profile | `molecular-intelligence-slm` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** target_structure, compound_library
- **Outputs:** hit_list, docking_scores
- **Tools (declared):** AutoDock, Compound DB

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "molecular",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** compound_list / smiles lines in query; demo compounds if empty
- **Runtime output:** admet_predictions or hit_list, admet_flags, recommendations

### Evidence chain
RDKit descriptors; optional docking_service shape screen

---

# Lead Optimization

## 13. ADMET Prediction Agent {#admet-prediction-agent}

**Runtime status:** ✅ Working  
**Category:** Lead Optimization · **Value chain:** Lead Optimization

### Mission
Predicts ADMET properties for lead optimization candidates.

### Design logic
Virtual Screening: Lipinski + QED ranking. ADMET: RDKit + LLM narrative.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `molecular` |
| Service | `molecular_service.run_molecular_agent` |
| Source file | `backend/app/services/molecular_service.py` |
| Catalog model profile | `molecular-intelligence-slm` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** compound_list
- **Outputs:** admet_predictions, property_radar
- **Tools (declared):** ADMET Model, RDKit

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "molecular",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** compound_list / smiles lines in query; demo compounds if empty
- **Runtime output:** admet_predictions or hit_list, admet_flags, recommendations

### Evidence chain
RDKit descriptors; optional docking_service shape screen

---

## 14. Developability Scoring Agent {#developability-scoring-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Lead Optimization · **Value chain:** Lead Optimization

### Mission
Scores compounds on developability criteria for candidate selection.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Rule engine on solubility, permeability, stability.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Medium-risk task with mixed complexity routed to frontier LLM. |
| SLM eligible (catalog) | No |
| Risk level | **medium** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** compound_list
- **Outputs:** developability_scores, recommendations
- **Tools (declared):** Property Calculator, Rule Engine

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 15. Explainable ADMET Agent {#explainable-admet-agent}

**Runtime status:** ✅ Working  
**Category:** Lead Optimization · **Value chain:** Lead Optimization

### Mission
Provides explainable ADMET predictions with structural alerts.

### Design logic
Virtual Screening: Lipinski + QED ranking. ADMET: RDKit + LLM narrative.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `molecular` |
| Service | `molecular_service.run_molecular_agent` |
| Source file | `backend/app/services/molecular_service.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Medium-risk task with mixed complexity routed to frontier LLM. |
| SLM eligible (catalog) | No |
| Risk level | **medium** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** compound_id
- **Outputs:** admet_explanation, structural_alerts
- **Tools (declared):** SHAP, ADMET Model

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "molecular",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** compound_list / smiles lines in query; demo compounds if empty
- **Runtime output:** admet_predictions or hit_list, admet_flags, recommendations

### Evidence chain
RDKit descriptors; optional docking_service shape screen

---

## 16. Multitarget QSAR Agent {#multitarget-qsar-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Lead Optimization · **Value chain:** Lead Optimization

### Mission
Builds QSAR models across multiple biological targets.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Sklearn QSAR on RDKit fingerprints per target.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `molecular-intelligence-slm` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Medium-risk task with mixed complexity routed to frontier LLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **medium** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** training_data, target_list
- **Outputs:** qsar_models, predictions
- **Tools (declared):** Scikit-learn, RDKit

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 17. Off-Target Risk Prediction Agent {#off-target-risk-prediction-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Lead Optimization · **Value chain:** Lead Optimization

### Mission
Predicts off-target binding risks across the proteome.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** SEA/similarity ensemble against proteome DBs.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `molecular-intelligence-slm` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — High-risk task requires frontier LLM with human review checkpoint. |
| SLM eligible (catalog) | Yes |
| Risk level | **high** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** compound_list
- **Outputs:** off_target_risks, risk_heatmap
- **Tools (declared):** SEA, Off-Target DB

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 18. Selectivity & Mechanism Agent {#selectivity-and-mechanism-agent}

**Runtime status:** 🟡 Partial  
**Category:** Lead Optimization · **Value chain:** Lead Optimization

### Mission
Analyzes compound selectivity profiles and mechanism of action.

### Design logic
Retrieve-then-generate over ingested docs; no PubMed/KEGG synthesis.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `rag` |
| Service | `rag_service.run_rag_query` |
| Source file | `backend/app/services/rag_service.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Medium-risk task with mixed complexity routed to frontier LLM. |
| SLM eligible (catalog) | No |
| Risk level | **medium** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** compound_id, panel_data
- **Outputs:** selectivity_matrix, moa_hypothesis
- **Tools (declared):** KG Query, Pathway Analysis

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query (required), task_type qa|query, document_id?, top_k?
- **Runtime output:** answer, mode: rag, chunks_used, citations

### Evidence chain
ChromaDB vector index (user documents)

---

# Preclinical Studies

## 19. Efficacy Modelling Agent {#efficacy-modelling-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Preclinical · **Value chain:** Preclinical Studies

### Mission
Models dose-response and efficacy outcomes from preclinical data.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** PK/PD curve fit + dose recommendation narrative.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `bioinformatics-slm` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Medium-risk task with mixed complexity routed to frontier LLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **medium** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** study_data
- **Outputs:** efficacy_model, dose_recommendation
- **Tools (declared):** PK/PD Model, Plot Generator

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 20. Formulation Strategy Agent {#formulation-strategy-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Preclinical · **Value chain:** Preclinical Studies

### Mission
Recommends formulation strategies for preclinical dosing.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Formulation DB + property-based recommendations.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Medium-risk task with mixed complexity routed to frontier LLM. |
| SLM eligible (catalog) | No |
| Risk level | **medium** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** compound_properties
- **Outputs:** formulation_options, stability_notes
- **Tools (declared):** Formulation DB, Property Calculator

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 21. In-vivo Study Design Agent {#in-vivo-study-design-agent}

**Runtime status:** ✅ Working  
**Category:** Preclinical · **Value chain:** Preclinical Studies

### Mission
Designs in-vivo efficacy and safety study protocols.

### Design logic
Branches on agent name: DOE Designer → DOE_SYSTEM; others → EXPERIMENT_PLAN_SYSTEM.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `experiment` |
| Service | `experiment_service.run_experiment_agent` |
| Source file | `backend/app/services/experiment_service.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — High-risk task requires frontier LLM with human review checkpoint. |
| SLM eligible (catalog) | No |
| Risk level | **high** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** compound_id, indication
- **Outputs:** study_protocol, power_analysis
- **Tools (declared):** Protocol DB, Statistical Planner

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "experiment",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query (required), document_id?, top_k?, report_type?
- **Runtime output:** summary, answer, experiment_plan{}, doe_design? (DOE agent), resources, risks

### Evidence chain
Vector, PubMed, KEGG, KG, ELN/LIMS; assay QC from linked documents

### Scientific Reports integration
Scientific Reports: experiment_plan — two-pass narrative expansion

---

## 22. PK/PD Modelling Agent {#pk-pd-modelling-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Preclinical · **Value chain:** Preclinical Studies

### Mission
Builds pharmacokinetic and pharmacodynamic models.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Compartment model integration (NONMEM-class tools).

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `bioinformatics-slm` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Medium-risk task with mixed complexity routed to frontier LLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **medium** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** pk_data, pd_data
- **Outputs:** pkpd_model, simulation_results
- **Tools (declared):** NONMEM, Plot Generator

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 23. Toxicity Prediction Agent {#toxicity-prediction-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Preclinical · **Value chain:** Preclinical Studies

### Mission
Predicts organ toxicity and safety liabilities.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** ToxPredict + study data synthesis.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — High-risk task requires frontier LLM with human review checkpoint. |
| SLM eligible (catalog) | No |
| Risk level | **high** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** compound_id, study_data
- **Outputs:** toxicity_profile, risk_flags
- **Tools (declared):** ToxPredict, Literature Miner

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 24. Translational Package Assembly Agent {#translational-package-assembly-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Preclinical · **Value chain:** Preclinical Studies

### Mission
Assembles translational research packages for IND-enabling studies.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Report assembly + IND gap checklist.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — High-risk task requires frontier LLM with human review checkpoint. |
| SLM eligible (catalog) | No |
| Risk level | **high** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** study_results, compound_data
- **Outputs:** translational_package, gap_analysis
- **Tools (declared):** Report Generator, Compliance Checker

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

# Early Development & CMC

## 25. Analytical Characterization Agent {#analytical-characterization-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Early Development & CMC · **Value chain:** Early Development & CMC

### Mission
Plans analytical characterization methods for drug substance and product.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Method DB + GxP validation templates.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `compliance-gxp-slm` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Medium-risk task with mixed complexity routed to frontier LLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **medium** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** compound_id, formulation
- **Outputs:** analytical_plan, method_list
- **Tools (declared):** Method DB, Compliance Checker

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

### Workflow appearances
- **CMC Readiness** — step 2

---

## 26. Formulation Optimisation Agent {#formulation-optimisation-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Early Development & CMC · **Value chain:** Early Development & CMC

### Mission
Optimizes formulation parameters for stability and bioavailability.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** DOE + stability model optimization loop.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Medium-risk task with mixed complexity routed to frontier LLM. |
| SLM eligible (catalog) | No |
| Risk level | **medium** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** formulation_data
- **Outputs:** optimized_formulation, DOE_results
- **Tools (declared):** DOE Designer, Stability Model

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

### Workflow appearances
- **CMC Readiness** — step 1 ⚠️ approval gate

---

## 27. Manufacturing Planning Agent {#manufacturing-planning-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Early Development & CMC · **Value chain:** Early Development & CMC

### Mission
Plans manufacturing schedules and resource allocation.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Scheduler + capacity planning integration.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Medium-risk task with mixed complexity routed to frontier LLM. |
| SLM eligible (catalog) | No |
| Risk level | **medium** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** process_design, demand_forecast
- **Outputs:** manufacturing_plan, timeline
- **Tools (declared):** Scheduler, Inventory Manager

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

### Workflow appearances
- **CMC Readiness** — step 4

---

## 28. Process Design and Scale-up Agent {#process-design-and-scale-up-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Early Development & CMC · **Value chain:** Early Development & CMC

### Mission
Designs manufacturing processes and scale-up strategies.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** QbD process parameter risk assessment.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — High-risk task requires frontier LLM with human review checkpoint. |
| SLM eligible (catalog) | No |
| Risk level | **high** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** synthesis_route, batch_data
- **Outputs:** process_design, scale_up_plan
- **Tools (declared):** Process DB, QbD Framework

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

### Workflow appearances
- **CMC Readiness** — step 3 ⚠️ approval gate

---

## 29. Quality by Design Agent {#quality-by-design-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Early Development & CMC · **Value chain:** Early Development & CMC

### Mission
Implements QbD framework for process and product quality.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** CQA / design space documentation via compliance SLM.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `compliance-gxp-slm` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — High-risk task requires frontier LLM with human review checkpoint. |
| SLM eligible (catalog) | Yes |
| Risk level | **high** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** process_data, CQAs
- **Outputs:** qbd_document, design_space
- **Tools (declared):** QbD Framework, Compliance Checker

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

### Workflow appearances
- **CMC Readiness** — step 5 ⚠️ approval gate

---

## 30. Stability Prediction Agent {#stability-prediction-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Early Development & CMC · **Value chain:** Early Development & CMC

### Mission
Predicts product stability under various storage conditions.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Stability ML on formulation time-series.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `molecular-intelligence-slm` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Medium-risk task with mixed complexity routed to frontier LLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **medium** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** formulation_data, stability_data
- **Outputs:** stability_prediction, shelf_life
- **Tools (declared):** Stability Model, Plot Generator

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

### Workflow appearances
- **CMC Readiness** — step 6

---

# Cross-Functional

## 31. AI Risk Assessor {#ai-risk-assessor}

**Runtime status:** ⬜ Not implemented  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Assesses AI/ML model risks for regulatory and ethical compliance.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Model card + regulatory AI risk framework.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — High-risk task requires frontier LLM with human review checkpoint. |
| SLM eligible (catalog) | No |
| Risk level | **high** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** model_metadata
- **Outputs:** risk_assessment, mitigation_plan
- **Tools (declared):** Risk Engine, Audit Logger

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 32. Bioinformatics Assistant {#bioinformatics-assistant}

**Runtime status:** ⬜ Not implemented  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Runs bioinformatics analyses on genomic and proteomic data.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** DESeq2 / pathway enrichment pipeline runner.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `bioinformatics-slm` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Medium-risk task with mixed complexity routed to frontier LLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **medium** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** analysis_type, data
- **Outputs:** analysis_results, visualizations
- **Tools (declared):** Bioinformatics Pipeline, Plot Generator

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 33. Competitive Intel Assistant {#competitive-intel-assistant}

**Runtime status:** ⬜ Not implemented  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Analyzes competitive landscape from patents and clinical trials.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Patent DB + ClinicalTrials.gov mining.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Medium-risk task with mixed complexity routed to frontier LLM. |
| SLM eligible (catalog) | No |
| Risk level | **medium** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** therapeutic_area, target
- **Outputs:** competitive_landscape, pipeline_analysis
- **Tools (declared):** Patent DB, ClinicalTrials.gov

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 34. Contract Review Assistant {#contract-review-assistant}

**Runtime status:** ⬜ Not implemented  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Reviews CRO/CDMO contracts for scientific and compliance terms.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Clause extraction + compliance risk LLM.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — High-risk task requires frontier LLM with human review checkpoint. |
| SLM eligible (catalog) | No |
| Risk level | **high** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** contract_document
- **Outputs:** review_summary, risk_items
- **Tools (declared):** Document Parser, Compliance Checker

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 35. DOE Designer Assistant {#doe-designer-assistant}

**Runtime status:** ✅ Working  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Designs design-of-experiments matrices for optimization studies.

### Design logic
Branches on agent name: DOE Designer → DOE_SYSTEM; others → EXPERIMENT_PLAN_SYSTEM.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `experiment` |
| Service | `experiment_service.run_experiment_agent` |
| Source file | `backend/app/services/experiment_service.py` |
| Catalog model profile | `bioinformatics-slm` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Complex reasoning or scientific decision task routed to frontier LLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** factors, responses
- **Outputs:** doe_matrix, power_analysis
- **Tools (declared):** DOE Engine, Statistical Planner

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "experiment",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query (required), document_id?, top_k?, report_type?
- **Runtime output:** summary, answer, experiment_plan{}, doe_design? (DOE agent), resources, risks

### Evidence chain
Vector, PubMed, KEGG, KG, ELN/LIMS; assay QC from linked documents

### Workflow appearances
- **Experiment Planning** — step 3

### Scientific Reports integration
Scientific Reports: experiment_plan — two-pass narrative expansion

---

## 36. Data Governance Assistant {#data-governance-assistant}

**Runtime status:** ⬜ Not implemented  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Enforces data governance policies and lineage tracking.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Policy engine on dataset lineage.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `compliance-gxp-slm` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — High-risk task requires frontier LLM with human review checkpoint. |
| SLM eligible (catalog) | Yes |
| Risk level | **high** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** dataset_id
- **Outputs:** governance_report, policy_violations
- **Tools (declared):** Audit Logger, Policy Engine

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 37. Decision Capture Assistant {#decision-capture-assistant}

**Runtime status:** ⬜ Not implemented  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Captures and documents scientific decisions with rationale.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Governance audit + structured decision records.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `scientific-writing-slm` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Complex reasoning or scientific decision task routed to frontier LLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** decision_context
- **Outputs:** decision_record, audit_trail
- **Tools (declared):** Audit Logger

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 38. ELN/LIMS Copilot Assistant {#eln-lims-copilot-assistant}

**Runtime status:** ⬜ Not implemented  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Assists with ELN and LIMS data entry and retrieval.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** lims_service + ELN document RAG copilot.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** experiment_id, query
- **Outputs:** eln_data, suggestions
- **Tools (declared):** ELN Connector, LIMS Connector

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

### Workflow appearances
- **Experiment Planning** — step 6

---

## 39. Experiment Planner Assistant {#experiment-planner-assistant}

**Runtime status:** ✅ Working  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Plans experiments with resource and timeline optimization.

### Design logic
Branches on agent name: DOE Designer → DOE_SYSTEM; others → EXPERIMENT_PLAN_SYSTEM.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `experiment` |
| Service | `experiment_service.run_experiment_agent` |
| Source file | `backend/app/services/experiment_service.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Medium-risk task with mixed complexity routed to frontier LLM. |
| SLM eligible (catalog) | No |
| Risk level | **medium** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** hypothesis, constraints
- **Outputs:** experiment_plan, timeline
- **Tools (declared):** Scheduler, Inventory Manager

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "experiment",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query (required), document_id?, top_k?, report_type?
- **Runtime output:** summary, answer, experiment_plan{}, doe_design? (DOE agent), resources, risks

### Evidence chain
Vector, PubMed, KEGG, KG, ELN/LIMS; assay QC from linked documents

### Workflow appearances
- **Experiment Planning** — step 2 ⚠️ approval gate

### Scientific Reports integration
Scientific Reports: experiment_plan — two-pass narrative expansion

---

## 40. GxP Compliance Assistant {#gxp-compliance-assistant}

**Runtime status:** ⬜ Not implemented  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Checks documents and processes for GxP compliance.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** gxp-check rules + document audit.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `compliance-gxp-slm` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — High-risk task requires frontier LLM with human review checkpoint. |
| SLM eligible (catalog) | Yes |
| Risk level | **high** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** document, process_type
- **Outputs:** compliance_report, findings
- **Tools (declared):** Compliance Checker, Audit Logger

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

### Workflow appearances
- **Study Report Generation** — step 6 ⚠️ approval gate

---

## 41. Hypothesis Builder Assistant {#hypothesis-builder-assistant}

**Runtime status:** ✅ Working  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Builds structured scientific hypotheses from evidence.

### Design logic
Two-mode pipeline: **build** (structured hypotheses + narrative) or **validate** (verdict + evidence for/against). Report mode expands answer when report_type is hypothesis_report or target_discovery.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `hypothesis` |
| Service | `hypothesis_service.run_hypothesis_agent` |
| Source file | `backend/app/services/hypothesis_service.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Complex reasoning or scientific decision task routed to frontier LLM. |
| SLM eligible (catalog) | No |
| Risk level | **medium** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** evidence_bundle
- **Outputs:** hypothesis, supporting_evidence
- **Tools (declared):** KG Builder, Literature Miner

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "hypothesis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query (required), document_id?, document_ids?, top_k?, report_type?
- **Runtime output:** summary, answer, hypotheses[], gaps[], verdict?, evidence_for/against[], confidence

### Evidence chain
Vector index, PubMed, KEGG, Knowledge Graph

### Workflow appearances
- **Literature to Hypothesis** — step 5 ⚠️ approval gate

### Scientific Reports integration
Scientific Reports: hypothesis_report, target_discovery — two-pass expand_report_narrative()

---

## 42. Hypothesis Validation Assistant {#hypothesis-validation-assistant}

**Runtime status:** ✅ Working  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Validates scientific hypotheses against available evidence.

### Design logic
Two-mode pipeline: **build** (structured hypotheses + narrative) or **validate** (verdict + evidence for/against). Report mode expands answer when report_type is hypothesis_report or target_discovery.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `hypothesis` |
| Service | `hypothesis_service.run_hypothesis_agent` |
| Source file | `backend/app/services/hypothesis_service.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Complex reasoning or scientific decision task routed to frontier LLM. |
| SLM eligible (catalog) | No |
| Risk level | **medium** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** hypothesis
- **Outputs:** validation_report, evidence_for_against
- **Tools (declared):** KG Query, Literature Miner

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "hypothesis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query (required), document_id?, document_ids?, top_k?, report_type?
- **Runtime output:** summary, answer, hypotheses[], gaps[], verdict?, evidence_for/against[], confidence

### Evidence chain
Vector index, PubMed, KEGG, Knowledge Graph

### Workflow appearances
- **Literature to Hypothesis** — step 6 ⚠️ approval gate
- **Experiment Planning** — step 1

### Scientific Reports integration
Scientific Reports: hypothesis_report, target_discovery — two-pass expand_report_narrative()

---

## 43. IP Landscape Screener {#ip-landscape-screener}

**Runtime status:** ⬜ Not implemented  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Screens intellectual property landscape for freedom-to-operate.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Patent structure search + FTO scoring.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — High-risk task requires frontier LLM with human review checkpoint. |
| SLM eligible (catalog) | No |
| Risk level | **high** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** compound_structure, therapeutic_area
- **Outputs:** ip_landscape, fto_assessment
- **Tools (declared):** Patent DB, Structure Search

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 44. Inventory Manager Assistant {#inventory-manager-assistant}

**Runtime status:** ⬜ Not implemented  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Manages reagent and compound inventory levels.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Reagent inventory DB.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** inventory_query
- **Outputs:** inventory_status, reorder_alerts
- **Tools (declared):** Inventory DB

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

### Workflow appearances
- **Experiment Planning** — step 5

---

## 45. Knowledge Scout Assistant {#knowledge-scout-assistant}

**Runtime status:** ✅ Working  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Scouts knowledge graph for relevant connections and gaps.

### Design logic
Agent name selects Miner, Evidence Scout, or Knowledge Scout JSON schema.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `literature` |
| Service | `literature_service.run_literature_agent` |
| Source file | `backend/app/services/literature_service.py` |
| Catalog model profile | `literature-intelligence-slm` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** entity_id, depth
- **Outputs:** knowledge_map, gaps
- **Tools (declared):** KG Query, Vector Search

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "literature",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query (required), top_k?
- **Runtime output:** summary, answer, key_findings / evidence_items / connections (by variant)

### Evidence chain
Vector, PubMed, KEGG, KG

### Workflow appearances
- **Literature to Hypothesis** — step 2

### Scientific Reports integration
Steps 1–2 in Literature → Hypothesis workflow

---

## 46. Literature/Patent Miner {#literature-patent-miner}

**Runtime status:** ✅ Working  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Mines scientific literature and patents for relevant insights.

### Design logic
Agent name selects Miner, Evidence Scout, or Knowledge Scout JSON schema.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `literature` |
| Service | `literature_service.run_literature_agent` |
| Source file | `backend/app/services/literature_service.py` |
| Catalog model profile | `literature-intelligence-slm` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** query, date_range
- **Outputs:** mined_documents, summary
- **Tools (declared):** PubMed, Patent DB, Vector Search

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "literature",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query (required), top_k?
- **Runtime output:** summary, answer, key_findings / evidence_items / connections (by variant)

### Evidence chain
Vector, PubMed, KEGG, KG

### Workflow appearances
- **Literature to Hypothesis** — step 1

### Scientific Reports integration
Steps 1–2 in Literature → Hypothesis workflow

---

## 47. Model Ops Assistant {#model-ops-assistant}

**Runtime status:** ⬜ Not implemented  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Monitors and manages deployed ML models in production.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Model registry drift monitoring.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Medium-risk task with mixed complexity routed to frontier LLM. |
| SLM eligible (catalog) | No |
| Risk level | **medium** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** model_id
- **Outputs:** model_health, drift_report
- **Tools (declared):** Model Monitor, Drift Detector

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 48. NGS Data Quality Assistant {#ngs-data-quality-assistant}

**Runtime status:** ⬜ Not implemented  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Assesses quality of next-generation sequencing data.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** FastQC metrics parser + pass/fail rules.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `bioinformatics-slm` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** ngs_files
- **Outputs:** qc_metrics, pass_fail
- **Tools (declared):** FastQC, Data Profiler

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 49. Omics Ingestion Assistant {#omics-ingestion-assistant}

**Runtime status:** ⬜ Not implemented  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Ingests and normalizes omics datasets into the data fabric.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Omics QC extension to ingestion pipeline.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `bioinformatics-slm` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** omics_files
- **Outputs:** normalized_data, qc_report
- **Tools (declared):** Data Profiler, Bioinformatics Pipeline

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 50. Ontology Mapper Assistant {#ontology-mapper-assistant}

**Runtime status:** ✅ Working  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Maps extracted entities to standard biomedical ontologies.

### Design logic
Ontology Mapper vs KG Builder prompts; suggests graph updates from evidence.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `knowledge_graph` |
| Service | `knowledge_agent_service.run_knowledge_agent` |
| Source file | `backend/app/services/knowledge_agent_service.py` |
| Catalog model profile | `ontology-mapping-slm` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** entity_list
- **Outputs:** mapped_entities, confidence_scores
- **Tools (declared):** UMLS, GO, ChEBI

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "knowledge_graph",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query (required), top_k?
- **Runtime output:** mapped_entities[] or suggested_nodes/relationships[]

### Evidence chain
Vector, PubMed, KEGG, KG (include_kg=True)

### Workflow appearances
- **Literature to Hypothesis** — step 3

### Scientific Reports integration
Steps 3–4 in Literature → Hypothesis workflow

---

## 51. Privacy Guard Assistant {#privacy-guard-assistant}

**Runtime status:** ⬜ Not implemented  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Detects and redacts personally identifiable information in datasets.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** PII NER + redaction pipeline.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `compliance-gxp-slm` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — High-risk task requires frontier LLM with human review checkpoint. |
| SLM eligible (catalog) | Yes |
| Risk level | **high** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** document
- **Outputs:** redacted_document, pii_report
- **Tools (declared):** PII Detector

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 52. Sample Tracker Assistant {#sample-tracker-assistant}

**Runtime status:** ⬜ Not implemented  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Tracks biological and chemical samples across studies.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** LIMS sample lineage queries.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** sample_id
- **Outputs:** sample_lineage, location
- **Tools (declared):** LIMS Connector, Barcode Scanner

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 53. Scheduler Ops Assistant {#scheduler-ops-assistant}

**Runtime status:** ⬜ Not implemented  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Manages lab scheduling and resource allocation.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Lab calendar / resource API.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** experiments, resources
- **Outputs:** schedule, conflicts
- **Tools (declared):** Scheduler

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

### Workflow appearances
- **Experiment Planning** — step 4

---

## 54. Scientific Writer Assistant {#scientific-writer-assistant}

**Runtime status:** ✅ Working  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Assists with scientific writing for publications and reports.

### Design logic
GxP-aware report writer. Result Capture uses CAPTURE_SYSTEM for ELN/LIMS records.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `report` |
| Service | `report_service.run_report_agent` |
| Source file | `backend/app/services/report_service.py` |
| Catalog model profile | `scientific-writing-slm` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Medium-risk task with mixed complexity routed to frontier LLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **medium** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** content_outline, data
- **Outputs:** draft_document, references
- **Tools (declared):** Literature Miner, Citation Manager

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "report",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query, report_type?, document_id?, prior_context?
- **Runtime output:** title, summary, answer, sections[], figures[], limitations[], recommendations[]

### Evidence chain
Vector, PubMed, KEGG, KG, ELN

### Workflow appearances
- **Literature to Hypothesis** — step 7
- **Study Report Generation** — step 5 ⚠️ approval gate

### Scientific Reports integration
study_report, cmc_readiness; workflow finalize_workflow_report()

---

## 55. Semantic Q&A Assistant {#semantic-qanda-assistant}

**Runtime status:** 🟡 Partial  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Answers scientific questions using RAG over knowledge base.

### Design logic
Retrieve-then-generate over ingested docs; no PubMed/KEGG synthesis.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `rag` |
| Service | `rag_service.run_rag_query` |
| Source file | `backend/app/services/rag_service.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | No |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** question
- **Outputs:** answer, citations
- **Tools (declared):** Vector Search, KG Query

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query (required), task_type qa|query, document_id?, top_k?
- **Runtime output:** answer, mode: rag, chunks_used, citations

### Evidence chain
ChromaDB vector index (user documents)

---

## 56. Study Report Generator {#study-report-generator}

**Runtime status:** ✅ Working  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Generates structured study reports from experimental data.

### Design logic
GxP-aware report writer. Result Capture uses CAPTURE_SYSTEM for ELN/LIMS records.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `report` |
| Service | `report_service.run_report_agent` |
| Source file | `backend/app/services/report_service.py` |
| Catalog model profile | `scientific-writing-slm` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Medium-risk task with mixed complexity routed to frontier LLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **medium** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** study_data
- **Outputs:** study_report, figures
- **Tools (declared):** Report Generator, Plot Generator

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "report",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query, report_type?, document_id?, prior_context?
- **Runtime output:** title, summary, answer, sections[], figures[], limitations[], recommendations[]

### Evidence chain
Vector, PubMed, KEGG, KG, ELN

### Workflow appearances
- **Study Report Generation** — step 4 ⚠️ approval gate

### Scientific Reports integration
study_report, cmc_readiness; workflow finalize_workflow_report()

---

## 57. Synthetic Data Generator {#synthetic-data-generator}

**Runtime status:** ⬜ Not implemented  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Generates synthetic datasets for model training and testing.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Schema-aware synthetic dataset generator.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | No |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** schema, row_count
- **Outputs:** synthetic_dataset, quality_report
- **Tools (declared):** Data Generator

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 58. Traceability Management Assistant {#traceability-management-assistant}

**Runtime status:** 🟡 Partial  
**Category:** Cross-Functional · **Value chain:** Cross-Functional

### Mission
Manages end-to-end traceability of data and samples.

### Design logic
Retrieve-then-generate over ingested docs; no PubMed/KEGG synthesis.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `rag` |
| Service | `rag_service.run_rag_query` |
| Source file | `backend/app/services/rag_service.py` |
| Catalog model profile | `compliance-gxp-slm` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Medium-risk task with mixed complexity routed to frontier LLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **medium** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** entity_id
- **Outputs:** traceability_chain, provenance
- **Tools (declared):** Audit Logger, KG Query

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query (required), task_type qa|query, document_id?, top_k?
- **Runtime output:** answer, mode: rag, chunks_used, citations

### Evidence chain
ChromaDB vector index (user documents)

---

# Foundation

## 59. Data Profiler/Validator {#data-profiler-validator}

**Runtime status:** ⬜ Not implemented  
**Category:** Foundation · **Value chain:** Foundation

### Mission
Profiles and validates scientific datasets for quality.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** experiment_qc_service extension.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `bioinformatics-slm` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** dataset
- **Outputs:** profile_report, validation_errors
- **Tools (declared):** Data Profiler

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

### Workflow appearances
- **Study Report Generation** — step 2

---

## 60. Document Parser Agent {#document-parser-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Foundation · **Value chain:** Foundation

### Mission
Parses and extracts structured content from scientific documents.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** **Live elsewhere:** document_parser.py in ingestion pipeline.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `literature-intelligence-slm` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** document_file
- **Outputs:** parsed_content, metadata
- **Tools (declared):** PDF Parser, OCR

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 61. Drift/Bias Monitor Agent {#drift-bias-monitor-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Foundation · **Value chain:** Foundation

### Mission
Monitors model drift and bias in production deployments.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Production drift/bias dashboards.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Medium-risk task with mixed complexity routed to frontier LLM. |
| SLM eligible (catalog) | No |
| Risk level | **medium** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** model_id, production_data
- **Outputs:** drift_report, bias_metrics
- **Tools (declared):** Drift Detector, Bias Analyzer

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 62. Entity Resolver Agent {#entity-resolver-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Foundation · **Value chain:** Foundation

### Mission
Resolves entity mentions to canonical identifiers.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** **Live elsewhere:** entity_resolver.py during ingestion.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `ontology-mapping-slm` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** entity_mentions
- **Outputs:** resolved_entities, disambiguation
- **Tools (declared):** UMLS, Entity DB

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 63. Feature Engineer Agent {#feature-engineer-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Foundation · **Value chain:** Foundation

### Mission
Engineers molecular and biological features for ML models.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** RDKit + bio feature matrix builder.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `molecular-intelligence-slm` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** compound_list, feature_types
- **Outputs:** feature_matrix, descriptors
- **Tools (declared):** RDKit, Bioinformatics Pipeline

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 64. Image Segmenter Agent {#image-segmenter-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Foundation · **Value chain:** Foundation

### Mission
Segments microscopy and histology images.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** CV segmentation model integration.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `bioinformatics-slm` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** image_file
- **Outputs:** segmentation_mask, cell_counts
- **Tools (declared):** CV Pipeline

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 65. KG Builder Agent {#kg-builder-agent}

**Runtime status:** ✅ Working  
**Category:** Foundation · **Value chain:** Foundation

### Mission
Builds knowledge graph nodes and relationships from extracted entities.

### Design logic
Ontology Mapper vs KG Builder prompts; suggests graph updates from evidence.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `knowledge_graph` |
| Service | `knowledge_agent_service.run_knowledge_agent` |
| Source file | `backend/app/services/knowledge_agent_service.py` |
| Catalog model profile | `ontology-mapping-slm` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** entities, relationships
- **Outputs:** graph_update, stats
- **Tools (declared):** Neo4j, Entity Resolver

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "knowledge_graph",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query (required), top_k?
- **Runtime output:** mapped_entities[] or suggested_nodes/relationships[]

### Evidence chain
Vector, PubMed, KEGG, KG (include_kg=True)

### Workflow appearances
- **Literature to Hypothesis** — step 4

### Scientific Reports integration
Steps 3–4 in Literature → Hypothesis workflow

---

## 66. Model Evaluator Agent {#model-evaluator-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Foundation · **Value chain:** Foundation

### Mission
Evaluates ML model performance against benchmarks.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** SLM profile benchmark harness.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Medium-risk task with mixed complexity routed to frontier LLM. |
| SLM eligible (catalog) | No |
| Risk level | **medium** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** model_id, test_data
- **Outputs:** evaluation_metrics, comparison
- **Tools (declared):** Model Monitor

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 67. Model Tuner Agent {#model-tuner-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Foundation · **Value chain:** Foundation

### Mission
Tunes hyperparameters for ML models.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Optuna hyperparameter search wrapper.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Medium-risk task with mixed complexity routed to frontier LLM. |
| SLM eligible (catalog) | No |
| Risk level | **medium** |
| Human approval (catalog) | Yes |
| Governance at runtime | Approval gate when high-risk or pending_review |

### Task & I/O contract (catalog)
- **Inputs:** model_config, training_data
- **Outputs:** tuned_model, metrics
- **Tools (declared):** Optuna, Model Monitor

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 68. Notification/Alert Agent {#notification-alert-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Foundation · **Value chain:** Foundation

### Mission
Sends notifications and alerts for platform events.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Audit-event notification service.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o-mini` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** event, recipients
- **Outputs:** notification_status
- **Tools (declared):** Notification Service

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 69. Paper Summarizer Agent {#paper-summarizer-agent}

**Runtime status:** ✅ Working  
**Category:** Foundation · **Value chain:** Foundation

### Mission
Summarizes research papers with key findings extraction.

### Design logic
Agent name selects Miner, Evidence Scout, or Knowledge Scout JSON schema.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `literature` |
| Service | `literature_service.run_literature_agent` |
| Source file | `backend/app/services/literature_service.py` |
| Catalog model profile | `literature-intelligence-slm` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** paper_pdf
- **Outputs:** summary, key_findings
- **Tools (declared):** Document Parser, Vector Search

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "literature",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query (required), top_k?
- **Runtime output:** summary, answer, key_findings / evidence_items / connections (by variant)

### Evidence chain
Vector, PubMed, KEGG, KG

### Scientific Reports integration
Steps 1–2 in Literature → Hypothesis workflow

---

## 70. Plot/Graph Generator {#plot-graph-generator}

**Runtime status:** ⬜ Not implemented  
**Category:** Foundation · **Value chain:** Foundation

### Mission
Generates publication-quality plots and graphs.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Matplotlib/Plotly report figures.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o-mini` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** data, plot_type
- **Outputs:** plot_image, plot_config
- **Tools (declared):** Matplotlib, Plotly

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

### Workflow appearances
- **Study Report Generation** — step 3

---

## 71. Relationship Identifier Agent {#relationship-identifier-agent}

**Runtime status:** 🟡 Partial  
**Category:** Foundation · **Value chain:** Foundation

### Mission
Identifies relationships between scientific entities in text.

### Design logic
Retrieve-then-generate over ingested docs; no PubMed/KEGG synthesis.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `rag` |
| Service | `rag_service.run_rag_query` |
| Source file | `backend/app/services/rag_service.py` |
| Catalog model profile | `ontology-mapping-slm` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** text, entities
- **Outputs:** relationships, confidence_scores
- **Tools (declared):** NLP Pipeline, KG Query

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query (required), task_type qa|query, document_id?, top_k?
- **Runtime output:** answer, mode: rag, chunks_used, citations

### Evidence chain
ChromaDB vector index (user documents)

---

## 72. Result Capture Agent {#result-capture-agent}

**Runtime status:** ✅ Working  
**Category:** Foundation · **Value chain:** Foundation

### Mission
Captures and structures experimental results.

### Design logic
GxP-aware report writer. Result Capture uses CAPTURE_SYSTEM for ELN/LIMS records.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `report` |
| Service | `report_service.run_report_agent` |
| Source file | `backend/app/services/report_service.py` |
| Catalog model profile | `scientific-writing-slm` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** raw_results
- **Outputs:** structured_results, metadata
- **Tools (declared):** ELN Connector, Data Profiler

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "report",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query, report_type?, document_id?, prior_context?
- **Runtime output:** title, summary, answer, sections[], figures[], limitations[], recommendations[]

### Evidence chain
Vector, PubMed, KEGG, KG, ELN

### Workflow appearances
- **Study Report Generation** — step 1

### Scientific Reports integration
study_report, cmc_readiness; workflow finalize_workflow_report()

---

## 73. Schema Mapper Agent {#schema-mapper-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Foundation · **Value chain:** Foundation

### Mission
Maps data schemas between different scientific data formats.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Schema transformation engine.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o-mini` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** source_schema, target_schema
- **Outputs:** mapping_rules, transformed_sample
- **Tools (declared):** Schema Engine

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 74. Scientific DB Query Agent {#scientific-db-query-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Foundation · **Value chain:** Foundation

### Mission
Queries external scientific databases (PubChem, UniProt, etc.).

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** PubChem / UniProt / ChEMBL REST wrappers.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o-mini` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** db_query
- **Outputs:** query_results
- **Tools (declared):** PubChem, UniProt, ChEMBL

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 75. Table/Figure Generator {#table-figure-generator}

**Runtime status:** ⬜ Not implemented  
**Category:** Foundation · **Value chain:** Foundation

### Mission
Generates formatted tables and figures for reports.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Report export figure/table builder.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `scientific-writing-slm` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** data, format
- **Outputs:** table, figure
- **Tools (declared):** Report Generator

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 76. Tool Selection Router {#tool-selection-router}

**Runtime status:** ⬜ Not implemented  
**Category:** Foundation · **Value chain:** Foundation

### Mission
Routes tasks to appropriate tools and agents.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** **Partial:** model_router.py + agent_executor dispatch.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o-mini` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** task_description
- **Outputs:** selected_tools, routing_plan
- **Tools (declared):** Agent Registry

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 77. Web Search Agent {#web-search-agent}

**Runtime status:** ⬜ Not implemented  
**Category:** Foundation · **Value chain:** Foundation

### Mission
Searches the web for scientific information and news.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** Web search API + summarization.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o-mini` |
| Resolved inference model | ministral-8b-latest (Mistral API) |
| Router | slm — Repetitive, domain-specific, low-risk task routed to specialized SLM. |
| SLM eligible (catalog) | Yes |
| Risk level | **low** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** query
- **Outputs:** search_results, summaries
- **Tools (declared):** Web Search API

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---

## 78. Workflow Orchestrator {#workflow-orchestrator}

**Runtime status:** ⬜ Not implemented  
**Category:** Foundation · **Value chain:** Foundation

### Mission
Orchestrates multi-agent workflow execution.

### Design logic
Catalog placeholder until dedicated pipeline is wired.

**Roadmap:** **Live elsewhere:** workflow_orchestrator.py + Workflow Builder UI.

### Implementation
| Property | Detail |
|----------|--------|
| Pipeline | `mock` |
| Service | `agent_executor._generate_mock_output` |
| Source file | `backend/app/services/agent_executor.py` |
| Catalog model profile | `gpt-4o` |
| Resolved inference model | gpt-4o-mini (OpenAI API) |
| Router | frontier — Medium-risk task with mixed complexity routed to frontier LLM. |
| SLM eligible (catalog) | No |
| Risk level | **medium** |
| Human approval (catalog) | No |
| Governance at runtime | Auto-complete unless workflow step requires approval |

### Task & I/O contract (catalog)
- **Inputs:** workflow_definition
- **Outputs:** execution_status, results
- **Tools (declared):** Agent Router, Audit Logger

### Runtime API
```json
POST /api/agents/{agent_id}/run
{
  "input_data": {
    "query": "<scientific question>",
    "task_type": "analysis",
    "document_id": "<optional>",
    "top_k": 8
  }
}
```
- **Runtime input:** query optional
- **Runtime output:** placeholder summary/answer, mode: mock

### Evidence chain
Optional 3-chunk vector stub citations

---
