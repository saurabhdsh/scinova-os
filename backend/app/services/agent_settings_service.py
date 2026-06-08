"""Persist and apply user custom instructions for agent tasks."""

from copy import deepcopy
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.db_models import Agent, AgentTaskSettings
from app.services.agent_capabilities import get_specialized_task_type

TASK_TYPES = (
    "literature",
    "hypothesis",
    "experiment",
    "report",
    "target_discovery",
    "knowledge_graph",
    "qa",
)

DEFAULT_SETTINGS = {
    "global_instructions": "",
    "task_instructions": {task: "" for task in TASK_TYPES},
    "agent_instructions": {},
    "agent_tool_bindings": {},
}


def _empty_settings() -> dict:
    return deepcopy(DEFAULT_SETTINGS)


def _get_or_create_row(db: Session, user_id: str) -> AgentTaskSettings:
    row = db.query(AgentTaskSettings).filter(AgentTaskSettings.user_id == user_id).first()
    if row:
        return row
    row = AgentTaskSettings(user_id=user_id, settings_json=_empty_settings(), updated_at=datetime.utcnow())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_agent_task_settings(db: Session, user_id: str) -> dict:
    row = _get_or_create_row(db, user_id)
    if not row.settings_json:
        return _empty_settings()
    merged = _empty_settings()
    stored = row.settings_json or {}
    merged["global_instructions"] = str(stored.get("global_instructions") or "")
    merged["task_instructions"] = {**merged["task_instructions"], **(stored.get("task_instructions") or {})}
    merged["agent_instructions"] = dict(stored.get("agent_instructions") or {})
    merged["agent_tool_bindings"] = dict(stored.get("agent_tool_bindings") or {})
    return merged


def save_agent_task_settings(db: Session, user_id: str, payload: dict) -> dict:
    merged = _empty_settings()
    if payload.get("global_instructions") is not None:
        merged["global_instructions"] = str(payload["global_instructions"]).strip()
    if payload.get("task_instructions"):
        for key, value in payload["task_instructions"].items():
            if key in merged["task_instructions"]:
                merged["task_instructions"][key] = str(value or "").strip()
    if payload.get("agent_instructions") is not None:
        merged["agent_instructions"] = {
            str(k): str(v or "").strip()
            for k, v in (payload.get("agent_instructions") or {}).items()
            if str(v or "").strip()
        }
    if payload.get("agent_tool_bindings") is not None:
        cleaned: dict[str, dict[str, str]] = {}
        for agent_id, roles in (payload.get("agent_tool_bindings") or {}).items():
            if not isinstance(roles, dict):
                continue
            role_map = {
                str(role): str(tool_id)
                for role, tool_id in roles.items()
                if role and tool_id
            }
            if role_map:
                cleaned[str(agent_id)] = role_map
        merged["agent_tool_bindings"] = cleaned

    row = _get_or_create_row(db, user_id)
    row.settings_json = merged
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return get_agent_task_settings(db, user_id)


def build_custom_instructions(db: Session, user_id: str, agent: Agent, input_data: dict) -> str:
    settings = get_agent_task_settings(db, user_id)
    parts: list[str] = []

    global_text = (settings.get("global_instructions") or "").strip()
    if global_text:
        parts.append(global_text)

    task_type = input_data.get("task_type") or get_specialized_task_type(agent)
    if task_type == "qa" or (not task_type and str(input_data.get("task_type", "")).lower() in ("qa", "query")):
        task_type = "qa"
    task_text = (settings.get("task_instructions") or {}).get(task_type or "", "").strip()
    if task_text:
        parts.append(task_text)

    agent_text = (settings.get("agent_instructions") or {}).get(agent.id, "").strip()
    if agent_text:
        parts.append(agent_text)

    run_text = str(input_data.get("custom_instructions") or "").strip()
    if run_text and run_text not in parts:
        parts.append(run_text)

    return "\n\n".join(parts)


def apply_agent_task_settings(db: Session, user_id: str, agent: Agent, input_data: dict) -> dict:
    settings = get_agent_task_settings(db, user_id)
    enriched = dict(input_data)
    custom = build_custom_instructions(db, user_id, agent, input_data)
    if custom:
        enriched["custom_instructions"] = custom
        base_query = str(enriched.get("query") or "").strip()
        if base_query:
            enriched["query"] = f"{base_query}\n\n--- Custom instructions ---\n{custom}"
        else:
            enriched["query"] = custom

    from app.services.tool_fabric_service import apply_tool_fabric_to_input
    from app.models.db_models import User
    user = db.query(User).filter(User.id == user_id).first()
    actor = user.username if user else user_id
    enriched = apply_tool_fabric_to_input(
        agent,
        enriched,
        settings,
        db=db,
        user_id=user_id,
        actor=actor,
    )
    return enriched
