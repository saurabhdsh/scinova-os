"""ADMET and virtual screening agent pipelines (RDKit + optional LLM narrative)."""

from sqlalchemy.orm import Session

from app.config import settings
from app.services.agent_capabilities import is_screening_agent
from app.services.chemoinformatics_service import (
    extract_compounds,
    rdkit_available,
    virtual_screen_compounds,
    compute_molecule_properties,
)
from app.services.docking_service import run_docking_pipeline
from app.services.tool_fabric_service import is_custom_tool_id
from app.services.llm_output_utils import coerce_text, pick_text
from app.services.llm_service import llm_service

ADMET_SYSTEM = """You are a medicinal chemistry ADMET analyst.
Given computed molecular descriptors (RDKit or heuristic), produce a concise scientific summary.

Return JSON with:
- summary: string (executive summary)
- answer: string (detailed markdown narrative)
- admet_flags: array of strings (key risks or strengths)
- recommendations: array of strings (lead optimization suggestions)
- confidence: float 0-1"""

SCREENING_SYSTEM = """You are a virtual screening lead identification scientist.
Given ranked screening hits with computed properties, summarize the hit list for medicinal chemists.

Return JSON with:
- summary: string
- answer: string (markdown hit list narrative)
- hit_list: array of objects {compound_id, smiles, rationale, priority: high|medium|low}
- recommendations: array of strings
- confidence: float 0-1"""


def run_molecular_agent(
    db: Session,
    agent,
    input_data: dict,
    *,
    model: str | None = None,
) -> dict:
    agent_name = agent.name or "Molecular Agent"
    fabric = input_data.get("tool_fabric") or {}
    custom_results = input_data.get("custom_tool_results") or {}
    desc_engine = fabric.get("molecular_descriptors") or fabric.get("property_prediction") or "rdkit"
    prop_engine = fabric.get("property_prediction") or desc_engine
    dock_engine = fabric.get("docking") or "rdkit_shape"
    compounds = extract_compounds(input_data)
    logs: list[dict] = [{"message": f"Parsed {len(compounds)} compounds for {agent_name}"}]
    logs.append({
        "message": f"Tool Fabric — descriptors: {desc_engine}, property: {prop_engine}, docking: {dock_engine}",
    })
    if is_custom_tool_id(desc_engine) or is_custom_tool_id(prop_engine):
        custom_hit = custom_results.get("molecular_descriptors") or custom_results.get("property_prediction")
        if custom_hit and not custom_hit.get("error"):
            logs.append({"message": f"Custom property engine '{custom_hit.get('label')}' returned results"})
        elif custom_hit and custom_hit.get("error"):
            logs.append({"message": f"Custom property engine failed — falling back to RDKit: {custom_hit.get('error')}"})
    if desc_engine == "deepchem":
        logs.append({"message": "DeepChem selected — using RDKit fallback until DeepChem integration is enabled"})
    logs.append({"message": f"Cheminformatics runtime: {'RDKit' if rdkit_available() else 'heuristic fallback'}"})

    screening = is_screening_agent(agent)
    docking_result = None
    custom_prop = custom_results.get("property_prediction") or custom_results.get("molecular_descriptors")
    if screening:
        hits = virtual_screen_compounds(compounds, max_hits=int(input_data.get("max_hits") or 25))
        logs.append({"message": f"Virtual screen returned {len(hits)} hits after Lipinski filter"})
        run_dock = input_data.get("query_smiles") or input_data.get("run_docking") or dock_engine
        if run_dock:
            dock_input = {**input_data, "docking_engine": dock_engine}
            docking_result = run_docking_pipeline(dock_input)
            logs.append({
                "message": f"Docking ({dock_engine}): {len(docking_result.get('shape_hits') or [])} hits",
            })
            if docking_result.get("shape_hits"):
                shape_by_smiles = {h["smiles"]: h for h in docking_result["shape_hits"]}
                for hit in hits:
                    sh = shape_by_smiles.get(hit["smiles"])
                    if sh:
                        hit["shape_similarity"] = sh["shape_similarity"]
                        hit["docking_method"] = sh.get("method")
                hits.sort(key=lambda h: h.get("shape_similarity", h.get("screening_score", 0)), reverse=True)
        props_key = "hit_list"
        computed = hits
        system = SCREENING_SYSTEM
        mode = "virtual_screening"
        summary_intro = f"Virtual screening ranked {len(hits)} compounds from a library of {len(compounds)}."
    else:
        predictions = []
        if custom_prop and not custom_prop.get("error") and custom_prop.get("body"):
            body = custom_prop["body"]
            if isinstance(body, dict) and isinstance(body.get("predictions"), list):
                predictions = body["predictions"]
                logs.append({"message": f"Using {len(predictions)} predictions from custom tool '{custom_prop.get('label')}'"})
        if not predictions:
            for item in compounds:
                row = {"compound_id": item["compound_id"], **compute_molecule_properties(item["smiles"])}
                predictions.append(row)
        logs.append({"message": f"Computed ADMET descriptors for {len(predictions)} compounds"})
        props_key = "admet_predictions"
        computed = predictions
        system = ADMET_SYSTEM
        mode = "admet_prediction"
        lipinski_pass = sum(1 for p in predictions if p.get("lipinski_pass"))
        summary_intro = f"ADMET profile computed for {len(predictions)} compounds ({lipinski_pass} Lipinski-compliant)."

    llm_payload = {
        "agent": agent_name,
        "mode": mode,
        "compounds": computed,
        "query": input_data.get("query", ""),
    }

    narrative = {}
    try:
        llm_result = llm_service.chat_json(
            system=system,
            user=f"Analyze these computed results:\n{llm_payload}",
            model=model or settings.slm_model,
        )
        narrative = llm_result or {}
    except Exception as exc:
        logs.append({"message": f"LLM narrative skipped: {exc}"})

    output = {
        "mode": mode,
        "engine": prop_engine if not is_custom_tool_id(prop_engine) else (custom_prop.get("label") if custom_results.get("property_prediction") else "custom"),
        "tool_fabric": fabric,
        "custom_tool_results": custom_results or None,
        "summary": pick_text(narrative, "summary", default=summary_intro),
        "answer": pick_text(narrative, "answer", "summary", default=summary_intro),
        props_key: computed,
        "admet_flags": narrative.get("admet_flags") or [],
        "recommendations": narrative.get("recommendations") or [],
        "hit_list": narrative.get("hit_list") or ([
            {"compound_id": h["compound_id"], "smiles": h["smiles"], "rationale": f"QED={h.get('qed')}", "priority": "high" if h.get("qed", 0) >= 0.6 else "medium"}
            for h in computed[:10]
        ] if screening else []),
        "compound_count": len(compounds),
        "confidence": float(narrative.get("confidence") or (0.88 if rdkit_available() else 0.72)),
    }
    if docking_result:
        output["docking"] = docking_result

    citations = [
        {
            "index": i + 1,
            "title": f"{row.get('compound_id')} — computed descriptors",
            "source": "rdkit" if rdkit_available() else "heuristic_chem",
            "document_id": row.get("compound_id"),
            "relevance": row.get("qed", row.get("screening_score", 0.7)),
            "excerpt": f"MW={row.get('molecular_weight')} LogP={row.get('logp')} Lipinski={'pass' if row.get('lipinski_pass') else 'fail'}",
        }
        for i, row in enumerate(computed[:12])
    ]

    return {
        "output": output,
        "citations": citations,
        "confidence": output["confidence"],
        "logs": logs,
    }
