"""Tool Fabric — pluggable scientific tool registry and per-agent bindings."""

from __future__ import annotations

from copy import deepcopy

from sqlalchemy.orm import Session

from app.services.chemoinformatics_service import rdkit_available
from app.services.docking_service import vina_available

CUSTOM_TOOL_PREFIX = "custom_"

# Tool catalog: id → metadata (enterprise integrations)
TOOL_CATALOG: dict[str, dict] = {
    # Molecular / cheminformatics
    "rdkit": {
        "label": "RDKit",
        "category": "molecular_descriptors",
        "description": "Open-source cheminformatics: descriptors, Lipinski, QED, fingerprints",
        "status": "available",
    },
    "deepchem": {
        "label": "DeepChem",
        "category": "property_prediction",
        "description": "Graph neural network ADMET and property models",
        "status": "planned",
    },
    "rdkit_shape": {
        "label": "RDKit 3D Shape",
        "category": "docking",
        "description": "3D conformer embedding + shape Tanimoto screening",
        "status": "available",
    },
    "autodock_vina": {
        "label": "AutoDock Vina",
        "category": "docking",
        "description": "Structure-based docking when Vina binary is installed",
        "status": "conditional",
    },
    # Data & evidence
    "vector_search": {
        "label": "Vector Search (ChromaDB)",
        "category": "retrieval",
        "description": "Semantic search over ingested documents",
        "status": "available",
    },
    "pubmed": {
        "label": "PubMed (NCBI)",
        "category": "literature",
        "description": "Literature retrieval via E-utilities",
        "status": "available",
    },
    "kegg": {
        "label": "KEGG",
        "category": "pathway",
        "description": "Pathway and gene entry lookup",
        "status": "available",
    },
    "neo4j_kg": {
        "label": "Knowledge Graph (Neo4j/SQL)",
        "category": "knowledge_graph",
        "description": "Entity neighborhood and graph query",
        "status": "available",
    },
    "eln_lims": {
        "label": "ELN / LIMS Connector",
        "category": "operations",
        "description": "Indexed protocol and assay records from Data Fabric",
        "status": "available",
    },
    "doe_engine": {
        "label": "DOE Engine",
        "category": "experiment",
        "description": "Design of experiments matrix generation",
        "status": "planned",
    },
    "nonmem": {
        "label": "NONMEM / PK/PD",
        "category": "pkpd",
        "description": "Pharmacometric modelling integration",
        "status": "planned",
    },
}

# Roles users can assign per agent class
TOOL_ROLES: dict[str, dict] = {
    "molecular_descriptors": {
        "label": "Molecular descriptors",
        "options": ["rdkit", "deepchem"],
        "default": "rdkit",
    },
    "property_prediction": {
        "label": "Property / ADMET prediction",
        "options": ["rdkit", "deepchem"],
        "default": "rdkit",
    },
    "docking": {
        "label": "Docking / shape screen",
        "options": ["rdkit_shape", "autodock_vina"],
        "default": "rdkit_shape",
    },
    "literature": {
        "label": "Literature retrieval",
        "options": ["pubmed", "vector_search"],
        "default": "pubmed",
    },
    "pathway": {
        "label": "Pathway databases",
        "options": ["kegg"],
        "default": "kegg",
    },
    "knowledge_graph": {
        "label": "Knowledge graph",
        "options": ["neo4j_kg"],
        "default": "neo4j_kg",
    },
}

# Default role sets by agent name keyword
AGENT_TOOL_ROLE_MAP: list[tuple[tuple[str, ...], list[str]]] = [
    (("virtual screening", "mpo", "admet", "molecule", "compound", "screening"), [
        "molecular_descriptors", "property_prediction", "docking",
    ]),
    (("literature", "patent", "paper", "evidence", "scout"), ["literature", "knowledge_graph"]),
    (("pathway", "target", "biomarker", "druggability"), ["pathway", "literature", "knowledge_graph"]),
    (("hypothesis", "validation"), ["literature", "knowledge_graph"]),
    (("experiment", "doe", "assay", "in-vivo", "study design"), ["literature", "eln_lims"]),
    (("ontology", "kg builder", "knowledge scout"), ["knowledge_graph", "literature"]),
    (("report", "writer", "capture"), ["literature", "eln_lims"]),
    (("pk/pd", "efficacy", "bioinfo", "omics", "ngs"), ["literature"]),
]


def normalize_custom_tool_id(tool_id: str) -> str:
    slug = (tool_id or "").strip().lower()
    if not slug:
        return slug
    if slug.startswith(CUSTOM_TOOL_PREFIX):
        return slug
    return f"{CUSTOM_TOOL_PREFIX}{slug}"


def is_custom_tool_id(tool_id: str) -> bool:
    return (tool_id or "").startswith(CUSTOM_TOOL_PREFIX)


def _custom_tool_catalog_entries(db: Session) -> tuple[list[dict], dict[str, list[str]]]:
    """Return catalog tool dicts and role_id → custom tool_ids."""
    from app.services.custom_tool_service import list_active_custom_tools

    tools: list[dict] = []
    role_options: dict[str, list[str]] = {}
    for row in list_active_custom_tools(db):
        runtime = "available" if row.status == "active" else "disabled"
        tools.append({
            "id": row.tool_id,
            "label": row.label,
            "category": row.role_id,
            "description": row.description or f"Custom integration — {row.endpoint_url}",
            "status": row.status,
            "runtime_status": runtime,
            "is_custom": True,
            "endpoint_url": row.endpoint_url,
        })
        role_options.setdefault(row.role_id, []).append(row.tool_id)
    return tools, role_options


def _valid_tool_ids(db: Session | None = None) -> set[str]:
    ids = set(TOOL_CATALOG.keys())
    if db is not None:
        from app.services.custom_tool_service import list_active_custom_tools
        for row in list_active_custom_tools(db):
            ids.add(row.tool_id)
    return ids


def _agent_name_lower(agent) -> str:
    return (agent.name or "").lower()


def _tool_label(tool_id: str, db: Session | None = None) -> str:
    if tool_id in TOOL_CATALOG:
        return TOOL_CATALOG[tool_id].get("label", tool_id)
    if db is not None and is_custom_tool_id(tool_id):
        from app.services.custom_tool_service import get_custom_tool_by_tool_id
        row = get_custom_tool_by_tool_id(db, tool_id)
        if row:
            return row.label
    return tool_id.replace("custom_", "").replace("_", " ").title()


def suggested_roles_for_agent(agent) -> list[str]:
    name = _agent_name_lower(agent)
    roles: list[str] = []
    for keywords, role_list in AGENT_TOOL_ROLE_MAP:
        if any(k in name for k in keywords):
            for r in role_list:
                if r not in roles:
                    roles.append(r)
    if not roles:
        roles = ["literature", "knowledge_graph"]
    return roles


def default_bindings_for_agent(agent) -> dict[str, str]:
    bindings: dict[str, str] = {}
    for role in suggested_roles_for_agent(agent):
        spec = TOOL_ROLES.get(role)
        if spec:
            bindings[role] = spec["default"]
    return bindings


def resolve_tool_status(tool_id: str, db: Session | None = None) -> str:
    if is_custom_tool_id(tool_id) and db is not None:
        from app.services.custom_tool_service import get_custom_tool_by_tool_id
        row = get_custom_tool_by_tool_id(db, tool_id)
        if row:
            return "available" if row.status == "active" else "disabled"
        return "unavailable"
    if tool_id == "rdkit" or tool_id == "rdkit_shape":
        return "available" if rdkit_available() else "unavailable"
    if tool_id == "autodock_vina":
        return "available" if vina_available() else "unavailable"
    if tool_id == "deepchem":
        return "planned"
    meta = TOOL_CATALOG.get(tool_id, {})
    return meta.get("status", "planned")


def get_tool_fabric_catalog(db: Session | None = None) -> dict:
    custom_tools, custom_by_role = ([], {})
    if db is not None:
        custom_tools, custom_by_role = _custom_tool_catalog_entries(db)

    tools = []
    for tid, meta in TOOL_CATALOG.items():
        tools.append({
            "id": tid,
            **meta,
            "is_custom": False,
            "runtime_status": resolve_tool_status(tid, db),
        })
    tools.extend(custom_tools)

    custom_labels = {t["id"]: t["label"] for t in custom_tools}
    roles = []
    for rid, spec in TOOL_ROLES.items():
        option_ids = list(dict.fromkeys(spec["options"] + custom_by_role.get(rid, [])))
        roles.append({
            "id": rid,
            "label": spec["label"],
            "options": [
                {
                    "id": opt,
                    "label": TOOL_CATALOG.get(opt, {}).get("label") or custom_labels.get(opt, opt),
                    "runtime_status": resolve_tool_status(opt, db),
                    "is_custom": is_custom_tool_id(opt),
                }
                for opt in option_ids
            ],
            "default": spec["default"],
        })
    return {"tools": tools, "roles": roles}


def resolve_agent_tool_bindings(agent, user_bindings: dict | None, db: Session | None = None) -> dict[str, str]:
    """Merge defaults with user overrides for one agent."""
    merged = default_bindings_for_agent(agent)
    valid = _valid_tool_ids(db)
    overrides = (user_bindings or {}).get(agent.id) or (user_bindings or {}).get(str(agent.id)) or {}
    if isinstance(overrides, dict):
        for role, tool_id in overrides.items():
            if role in TOOL_ROLES and tool_id in valid:
                merged[role] = tool_id
    return merged


def bindings_to_tools_used(bindings: dict[str, str], db: Session | None = None) -> list[str]:
    """Map fabric bindings to legacy tools_used labels for evidence_service."""
    mapping = {
        "rdkit": "RDKit",
        "deepchem": "DeepChem",
        "rdkit_shape": "RDKit",
        "autodock_vina": "AutoDock",
        "vector_search": "Vector Search",
        "pubmed": "PubMed",
        "kegg": "KEGG",
        "neo4j_kg": "KG Query",
        "eln_lims": "ELN Connector",
    }
    labels: list[str] = []
    for tool_id in bindings.values():
        if is_custom_tool_id(tool_id):
            label = _tool_label(tool_id, db)
        else:
            label = mapping.get(tool_id, tool_id)
        if label not in labels:
            labels.append(label)
    return labels


def apply_tool_fabric_to_input(
    agent,
    input_data: dict,
    user_settings: dict,
    *,
    db: Session | None = None,
    user_id: str | None = None,
    actor: str | None = None,
) -> dict:
    """Attach resolved Tool Fabric bindings and invoke custom tools."""
    enriched = dict(input_data)
    all_bindings = user_settings.get("agent_tool_bindings") or {}
    bindings = resolve_agent_tool_bindings(agent, all_bindings, db)
    enriched["tool_fabric"] = bindings
    enriched["tool_fabric_catalog_version"] = "2"

    fabric_tools = bindings_to_tools_used(bindings, db)
    seed_tools = list(agent.tools_used or [])
    merged_tools = list(dict.fromkeys(fabric_tools + seed_tools))
    enriched["tools_used"] = merged_tools

    if db is not None and any(is_custom_tool_id(t) for t in bindings.values()):
        from app.services.custom_tool_executor import invoke_bound_custom_tools
        enriched, _ = invoke_bound_custom_tools(
            db,
            bindings,
            enriched,
            actor=actor or user_id or "system",
            agent_name=agent.name or "Agent",
        )
    return enriched


def get_agent_tool_fabric_bindings_view(db: Session, user_id: str, agent) -> dict:
    """Resolved Tool Fabric bindings for workspace display."""
    from app.services.agent_settings_service import get_agent_task_settings

    settings = get_agent_task_settings(db, user_id)
    all_user_bindings = settings.get("agent_tool_bindings") or {}
    user_overrides = all_user_bindings.get(agent.id) or all_user_bindings.get(str(agent.id)) or {}
    bindings = resolve_agent_tool_bindings(agent, all_user_bindings, db)

    items: list[dict] = []
    for role_id, tool_id in bindings.items():
        role_spec = TOOL_ROLES.get(role_id) or {}
        items.append({
            "role_id": role_id,
            "role_label": role_spec.get("label", role_id),
            "tool_id": tool_id,
            "tool_label": _tool_label(tool_id, db),
            "runtime_status": resolve_tool_status(tool_id, db),
            "is_custom": is_custom_tool_id(tool_id),
            "is_user_override": role_id in user_overrides,
        })

    return {
        "agent_id": agent.id,
        "agent_name": agent.name,
        "bindings": items,
        "has_custom_overrides": bool(user_overrides),
        "suggested_roles": suggested_roles_for_agent(agent),
    }
