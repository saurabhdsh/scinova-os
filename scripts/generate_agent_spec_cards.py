#!/usr/bin/env python3
"""Generate AGENT_SPEC_CARDS.md from seed data and pipeline metadata."""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.models.schemas import ModelRouteRequest  # noqa: E402
from app.seed_data import AGENTS, WORKFLOW_TEMPLATES  # noqa: E402
from app.services.agent_capabilities import (  # noqa: E402
    agent_supports_specialized,
    get_specialized_task_type,
)
from app.services.model_router import route_model  # noqa: E402
from app.services.rag_service import agent_supports_rag  # noqa: E402

PIPELINE_SPECS = {
    "hypothesis": {
        "service": "hypothesis_service.run_hypothesis_agent",
        "file": "backend/app/services/hypothesis_service.py",
        "evidence": "Vector index, PubMed, KEGG, Knowledge Graph",
        "runtime_input": "query (required), document_id?, document_ids?, top_k?, report_type?",
        "runtime_output": "summary, answer, hypotheses[], gaps[], verdict?, evidence_for/against[], confidence",
        "design": (
            "Two-mode pipeline: **build** (structured hypotheses + narrative) or **validate** "
            "(verdict + evidence for/against). Report mode expands answer when report_type is "
            "hypothesis_report or target_discovery."
        ),
        "report_integration": "Scientific Reports: hypothesis_report, target_discovery — two-pass expand_report_narrative()",
    },
    "experiment": {
        "service": "experiment_service.run_experiment_agent",
        "file": "backend/app/services/experiment_service.py",
        "evidence": "Vector, PubMed, KEGG, KG, ELN/LIMS; assay QC from linked documents",
        "runtime_input": "query (required), document_id?, top_k?, report_type?",
        "runtime_output": "summary, answer, experiment_plan{}, doe_design? (DOE agent), resources, risks",
        "design": "Branches on agent name: DOE Designer → DOE_SYSTEM; others → EXPERIMENT_PLAN_SYSTEM.",
        "report_integration": "Scientific Reports: experiment_plan — two-pass narrative expansion",
    },
    "report": {
        "service": "report_service.run_report_agent",
        "file": "backend/app/services/report_service.py",
        "evidence": "Vector, PubMed, KEGG, KG, ELN",
        "runtime_input": "query, report_type?, document_id?, prior_context?",
        "runtime_output": "title, summary, answer, sections[], figures[], limitations[], recommendations[]",
        "design": "GxP-aware report writer. Result Capture uses CAPTURE_SYSTEM for ELN/LIMS records.",
        "report_integration": "study_report, cmc_readiness; workflow finalize_workflow_report()",
    },
    "literature": {
        "service": "literature_service.run_literature_agent",
        "file": "backend/app/services/literature_service.py",
        "evidence": "Vector, PubMed, KEGG, KG",
        "runtime_input": "query (required), top_k?",
        "runtime_output": "summary, answer, key_findings / evidence_items / connections (by variant)",
        "design": "Agent name selects Miner, Evidence Scout, or Knowledge Scout JSON schema.",
        "report_integration": "Steps 1–2 in Literature → Hypothesis workflow",
    },
    "target_discovery": {
        "service": "target_discovery_service.run_target_discovery_agent",
        "file": "backend/app/services/target_discovery_service.py",
        "evidence": "Vector, PubMed, KEGG, KG",
        "runtime_input": "query (required), top_k?",
        "runtime_output": "pathways, druggable_targets, validation_score, biomarkers, druggability_score",
        "design": "Name-based branch: Pathway, Validation, Biomarker, or Druggability specialist.",
        "report_integration": "Target Discovery Brief workflow; Scientific Reports target_discovery",
    },
    "knowledge_graph": {
        "service": "knowledge_agent_service.run_knowledge_agent",
        "file": "backend/app/services/knowledge_agent_service.py",
        "evidence": "Vector, PubMed, KEGG, KG (include_kg=True)",
        "runtime_input": "query (required), top_k?",
        "runtime_output": "mapped_entities[] or suggested_nodes/relationships[]",
        "design": "Ontology Mapper vs KG Builder prompts; suggests graph updates from evidence.",
        "report_integration": "Steps 3–4 in Literature → Hypothesis workflow",
    },
    "molecular": {
        "service": "molecular_service.run_molecular_agent",
        "file": "backend/app/services/molecular_service.py",
        "evidence": "RDKit descriptors; optional docking_service shape screen",
        "runtime_input": "compound_list / smiles lines in query; demo compounds if empty",
        "runtime_output": "admet_predictions or hit_list, admet_flags, recommendations",
        "design": "Virtual Screening: Lipinski + QED ranking. ADMET: RDKit + LLM narrative.",
        "report_integration": "None",
    },
    "rag": {
        "service": "rag_service.run_rag_query",
        "file": "backend/app/services/rag_service.py",
        "evidence": "ChromaDB vector index (user documents)",
        "runtime_input": "query (required), task_type qa|query, document_id?, top_k?",
        "runtime_output": "answer, mode: rag, chunks_used, citations",
        "design": "Retrieve-then-generate over ingested docs; no PubMed/KEGG synthesis.",
        "report_integration": "None",
    },
    "mock": {
        "service": "agent_executor._generate_mock_output",
        "file": "backend/app/services/agent_executor.py",
        "evidence": "Optional 3-chunk vector stub citations",
        "runtime_input": "query optional",
        "runtime_output": "placeholder summary/answer, mode: mock",
        "design": "Catalog placeholder until dedicated pipeline is wired.",
        "report_integration": "None — avoid in partner demos",
    },
}

MOCK_ROADMAP: dict[str, str] = {
    "Molecule Generation Agent": "Generative chemistry from pharmacophore constraints (RDKit + LLM).",
    "Deduplication, Filtering & Hit-Ranking Agent": "RDKit dedup, MPO scoring, PAINS/reactive filters.",
    "Early Risk Profiling Agent": "ToxPredict + off-target DB + literature fusion.",
    "Multitarget QSAR Agent": "Sklearn QSAR on RDKit fingerprints per target.",
    "Off-Target Risk Prediction Agent": "SEA/similarity ensemble against proteome DBs.",
    "Developability Scoring Agent": "Rule engine on solubility, permeability, stability.",
    "Efficacy Modelling Agent": "PK/PD curve fit + dose recommendation narrative.",
    "PK/PD Modelling Agent": "Compartment model integration (NONMEM-class tools).",
    "Toxicity Prediction Agent": "ToxPredict + study data synthesis.",
    "Formulation Strategy Agent": "Formulation DB + property-based recommendations.",
    "Translational Package Assembly Agent": "Report assembly + IND gap checklist.",
    "Analytical Characterization Agent": "Method DB + GxP validation templates.",
    "Formulation Optimisation Agent": "DOE + stability model optimization loop.",
    "Process Design and Scale-up Agent": "QbD process parameter risk assessment.",
    "Manufacturing Planning Agent": "Scheduler + capacity planning integration.",
    "Stability Prediction Agent": "Stability ML on formulation time-series.",
    "Quality by Design Agent": "CQA / design space documentation via compliance SLM.",
    "Competitive Intel Assistant": "Patent DB + ClinicalTrials.gov mining.",
    "ELN/LIMS Copilot Assistant": "lims_service + ELN document RAG copilot.",
    "Scheduler Ops Assistant": "Lab calendar / resource API.",
    "Sample Tracker Assistant": "LIMS sample lineage queries.",
    "Inventory Manager Assistant": "Reagent inventory DB.",
    "Omics Ingestion Assistant": "Omics QC extension to ingestion pipeline.",
    "Bioinformatics Assistant": "DESeq2 / pathway enrichment pipeline runner.",
    "Decision Capture Assistant": "Governance audit + structured decision records.",
    "NGS Data Quality Assistant": "FastQC metrics parser + pass/fail rules.",
    "Model Ops Assistant": "Model registry drift monitoring.",
    "Synthetic Data Generator": "Schema-aware synthetic dataset generator.",
    "Data Governance Assistant": "Policy engine on dataset lineage.",
    "Privacy Guard Assistant": "PII NER + redaction pipeline.",
    "IP Landscape Screener": "Patent structure search + FTO scoring.",
    "GxP Compliance Assistant": "gxp-check rules + document audit.",
    "Contract Review Assistant": "Clause extraction + compliance risk LLM.",
    "AI Risk Assessor": "Model card + regulatory AI risk framework.",
    "Web Search Agent": "Web search API + summarization.",
    "Scientific DB Query Agent": "PubChem / UniProt / ChEMBL REST wrappers.",
    "Document Parser Agent": "**Live elsewhere:** document_parser.py in ingestion pipeline.",
    "Entity Resolver Agent": "**Live elsewhere:** entity_resolver.py during ingestion.",
    "Schema Mapper Agent": "Schema transformation engine.",
    "Model Evaluator Agent": "SLM profile benchmark harness.",
    "Feature Engineer Agent": "RDKit + bio feature matrix builder.",
    "Model Tuner Agent": "Optuna hyperparameter search wrapper.",
    "Drift/Bias Monitor Agent": "Production drift/bias dashboards.",
    "Image Segmenter Agent": "CV segmentation model integration.",
    "Data Profiler/Validator": "experiment_qc_service extension.",
    "Plot/Graph Generator": "Matplotlib/Plotly report figures.",
    "Workflow Orchestrator": "**Live elsewhere:** workflow_orchestrator.py + Workflow Builder UI.",
    "Tool Selection Router": "**Partial:** model_router.py + agent_executor dispatch.",
    "Notification/Alert Agent": "Audit-event notification service.",
    "Table/Figure Generator": "Report export figure/table builder.",
}

STAGE_ORDER = [
    "Target Discovery",
    "Lead Identification",
    "Lead Optimization",
    "Preclinical Studies",
    "Early Development & CMC",
    "Cross-Functional",
    "Foundation",
]


def classify(agent_data: dict) -> tuple[str, str]:
    agent = SimpleNamespace(**agent_data)
    input_data = {"query": "demo", "task_type": get_specialized_task_type(agent) or "analysis"}
    if agent_supports_specialized(agent, input_data):
        return get_specialized_task_type(agent) or "specialized", "working"
    if agent_supports_rag(agent, input_data):
        return "rag", "partial"
    return "mock", "not_working"


def anchor(name: str) -> str:
    slug = name.lower().replace("/", "-").replace("&", "and")
    return "".join(c if c.isalnum() or c == "-" else "-" for c in slug).strip("-")


def status_label(status: str) -> str:
    return {
        "working": "✅ Working",
        "partial": "🟡 Partial",
        "not_working": "⬜ Not implemented",
    }[status]


def main() -> None:
    agent_in_workflows: dict[str, list] = {a["name"]: [] for a in AGENTS}
    for wf in WORKFLOW_TEMPLATES:
        for step in wf["steps_json"]:
            name = step["agent"]
            if name in agent_in_workflows:
                agent_in_workflows[name].append({
                    "workflow": wf["name"],
                    "order": step["order"],
                    "requires_approval": step.get("requires_approval", False),
                })

    lines: list[str] = [
        "# SciAi-Nova OS — Super Agent Spec Cards",
        "",
        "> Full design specification for all **78 marketplace agents**.  ",
        "> Sources: `seed_data.py`, `agent_capabilities.py`, `model_router.py`, specialized services.  ",
        "> Last updated: 2026-06-07",
        "",
        "---",
        "",
        "## How to read these cards",
        "",
        "| Field | Meaning |",
        "|-------|---------|",
        "| **Runtime status** | Behavior when run from Agent Workspace or Workflow Builder |",
        "| **Catalog model** | SLM profile name in marketplace metadata |",
        "| **Resolved inference** | Model after routing (`gpt-4o-mini` or `ministral-8b-latest`) |",
        "| **Governance** | High-risk → approval in Governance unless `auto_approve: true` |",
        "",
        "**Dispatch:** specialized → RAG → mock (`agent_executor.py`).",
        "",
        "---",
        "",
        "## Table of contents",
        "",
    ]

    by_stage: dict[str, list[str]] = defaultdict(list)
    for a in AGENTS:
        by_stage[a["value_chain_stage"]].append(a["name"])

    for stage in STAGE_ORDER:
        lines.append(f"### {stage}")
        for name in sorted(by_stage[stage]):
            lines.append(f"- [{name}](#{anchor(name)})")
        lines.append("")

    lines.extend(["---", ""])

    card_num = 0
    for stage in STAGE_ORDER:
        agents = sorted(
            [a for a in AGENTS if a["value_chain_stage"] == stage],
            key=lambda x: x["name"],
        )
        lines.append(f"# {stage}")
        lines.append("")

        for a in agents:
            card_num += 1
            pipeline, status = classify(a)
            spec = PIPELINE_SPECS[pipeline]
            task_type = pipeline if pipeline not in {"mock", "rag"} else "analysis"
            routing = route_model(ModelRouteRequest(
                agent_name=a["name"],
                task_type=task_type,
                risk_level=a["risk_level"],
                user_query="demo",
            ))
            resolved = (
                "ministral-8b-latest (Mistral API)"
                if routing.model_type == "slm"
                else "gpt-4o-mini (OpenAI API)"
            )
            gov = (
                "Approval gate when high-risk or pending_review"
                if a["risk_level"] == "high" or a["human_approval_required"]
                else "Auto-complete unless workflow step requires approval"
            )

            lines.extend([
                f"## {card_num}. {a['name']} {{#{anchor(a['name'])}}}",
                "",
                f"**Runtime status:** {status_label(status)}  ",
                f"**Category:** {a['category']} · **Value chain:** {a['value_chain_stage']}",
                "",
                "### Mission",
                a["description"],
                "",
                "### Design logic",
                spec["design"],
            ])

            if status == "not_working" and a["name"] in MOCK_ROADMAP:
                lines.extend(["", f"**Roadmap:** {MOCK_ROADMAP[a['name']]}"])

            lines.extend([
                "",
                "### Implementation",
                "| Property | Detail |",
                "|----------|--------|",
                f"| Pipeline | `{pipeline}` |",
                f"| Service | `{spec['service']}` |",
                f"| Source file | `{spec['file']}` |",
                f"| Catalog model profile | `{a['model_used']}` |",
                f"| Resolved inference model | {resolved} |",
                f"| Router | {routing.model_type} — {routing.reason_for_selection} |",
                f"| SLM eligible (catalog) | {'Yes' if a['slm_eligible'] else 'No'} |",
                f"| Risk level | **{a['risk_level']}** |",
                f"| Human approval (catalog) | {'Yes' if a['human_approval_required'] else 'No'} |",
                f"| Governance at runtime | {gov} |",
                "",
                "### Task & I/O contract (catalog)",
                f"- **Inputs:** {', '.join(a['input_types'])}",
                f"- **Outputs:** {', '.join(a['output_types'])}",
                f"- **Tools (declared):** {', '.join(a['tools_used'])}",
                "",
                "### Runtime API",
                "```json",
                "POST /api/agents/{agent_id}/run",
                json.dumps({
                    "input_data": {
                        "query": "<scientific question>",
                        "task_type": task_type,
                        "document_id": "<optional>",
                        "top_k": 8,
                    },
                }, indent=2),
                "```",
                f"- **Runtime input:** {spec['runtime_input']}",
                f"- **Runtime output:** {spec['runtime_output']}",
                "",
                "### Evidence chain",
                spec["evidence"],
                "",
            ])

            wfs = agent_in_workflows.get(a["name"], [])
            if wfs:
                lines.append("### Workflow appearances")
                for w in wfs:
                    gate = " ⚠️ approval gate" if w["requires_approval"] else ""
                    lines.append(f"- **{w['workflow']}** — step {w['order']}{gate}")
                lines.append("")

            if spec.get("report_integration") and spec["report_integration"] not in {"None", "None — avoid in partner demos"}:
                lines.extend([
                    "### Scientific Reports integration",
                    spec["report_integration"],
                    "",
                ])

            lines.extend(["---", ""])

    out = Path(os.environ.get("AGENT_SPEC_OUTPUT", ROOT / "AGENT_SPEC_CARDS.md"))
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {card_num} agent spec cards to {out}")


if __name__ == "__main__":
    main()
