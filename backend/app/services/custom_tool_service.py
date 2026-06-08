"""Admin-managed custom Tool Fabric registrations."""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.db_models import AuditEvent, CustomTool, User
from app.services.tool_fabric_service import TOOL_ROLES, normalize_custom_tool_id, CUSTOM_TOOL_PREFIX, normalize_custom_tool_id

_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")


class CustomToolError(ValueError):
    pass


class CustomToolNotFoundError(CustomToolError):
    pass


class CustomToolConflictError(CustomToolError):
    pass


def _mask_secret(secret: str | None) -> bool:
    return bool(secret and str(secret).strip())


def _serialize_tool(tool: CustomTool, *, username: str | None = None) -> dict:
    role_spec = TOOL_ROLES.get(tool.role_id) or {}
    runtime = "available" if tool.status == "active" else "disabled"
    return {
        "id": tool.id,
        "tool_id": tool.tool_id,
        "label": tool.label,
        "description": tool.description,
        "role_id": tool.role_id,
        "role_label": role_spec.get("label", tool.role_id),
        "endpoint_url": tool.endpoint_url,
        "http_method": tool.http_method or "POST",
        "auth_type": tool.auth_type or "none",
        "auth_header_name": tool.auth_header_name,
        "auth_secret_configured": _mask_secret(tool.auth_secret),
        "request_template": tool.request_template or {},
        "status": tool.status,
        "is_custom": True,
        "runtime_status": runtime,
        "registered_by": tool.registered_by,
        "registered_by_username": username,
        "created_at": tool.created_at,
        "updated_at": tool.updated_at,
    }


def _validate_role(role_id: str) -> None:
    if role_id not in TOOL_ROLES:
        raise CustomToolError(f"Unknown role '{role_id}'. Valid roles: {', '.join(sorted(TOOL_ROLES))}")


def _validate_endpoint(url: str) -> None:
    if not url.lower().startswith(("http://", "https://")):
        raise CustomToolError("Endpoint URL must start with http:// or https://")


def _validate_auth(auth_type: str, auth_header_name: str | None, auth_secret: str | None) -> None:
    if auth_type == "api_key_header" and not (auth_header_name or "").strip():
        raise CustomToolError("auth_header_name is required when auth_type is api_key_header")
    if auth_type in ("bearer", "api_key_header") and not (auth_secret or "").strip():
        raise CustomToolError("auth_secret is required for bearer and api_key_header auth")


def list_custom_tools(db: Session) -> list[dict]:
    tools = db.query(CustomTool).order_by(CustomTool.created_at.desc()).all()
    usernames = {
        u.id: u.username
        for u in db.query(User).filter(User.id.in_({t.registered_by for t in tools})).all()
    }
    return [_serialize_tool(t, username=usernames.get(t.registered_by)) for t in tools]


def list_active_custom_tools(db: Session) -> list[CustomTool]:
    return (
        db.query(CustomTool)
        .filter(CustomTool.status == "active")
        .order_by(CustomTool.label.asc())
        .all()
    )


def get_custom_tool_by_tool_id(db: Session, tool_id: str) -> CustomTool | None:
    normalized = normalize_custom_tool_id(tool_id)
    return db.query(CustomTool).filter(CustomTool.tool_id == normalized).first()


def get_custom_tool_row(db: Session, row_id: str) -> CustomTool | None:
    return db.query(CustomTool).filter(CustomTool.id == row_id).first()


def create_custom_tool(db: Session, admin: User, payload: dict) -> dict:
    tool_id = normalize_custom_tool_id(payload["tool_id"])
    slug = tool_id[len(CUSTOM_TOOL_PREFIX):] if tool_id.startswith(CUSTOM_TOOL_PREFIX) else tool_id
    if not _SLUG_RE.match(slug):
        raise CustomToolError("tool_id must be lowercase letters, digits, and underscores (3–64 chars)")

    from app.services.tool_fabric_service import TOOL_CATALOG
    if tool_id in TOOL_CATALOG:
        raise CustomToolConflictError(f"tool_id '{tool_id}' conflicts with a built-in tool")

    _validate_role(payload["role_id"])
    _validate_endpoint(payload["endpoint_url"])
    auth_type = payload.get("auth_type") or "none"
    _validate_auth(auth_type, payload.get("auth_header_name"), payload.get("auth_secret"))

    if get_custom_tool_by_tool_id(db, tool_id):
        raise CustomToolConflictError(f"Custom tool '{tool_id}' already exists")

    tool = CustomTool(
        tool_id=tool_id,
        label=payload["label"].strip(),
        description=(payload.get("description") or "").strip() or None,
        role_id=payload["role_id"],
        endpoint_url=payload["endpoint_url"].strip(),
        http_method=(payload.get("http_method") or "POST").upper(),
        auth_type=auth_type,
        auth_header_name=(payload.get("auth_header_name") or "").strip() or None,
        auth_secret=(payload.get("auth_secret") or "").strip() or None,
        request_template=payload.get("request_template") or {},
        status=payload.get("status") or "active",
        registered_by=admin.id,
        updated_at=datetime.utcnow(),
    )
    db.add(tool)
    db.flush()

    db.add(AuditEvent(
        event_type="custom_tool_registered",
        actor=admin.username,
        resource_type="custom_tool",
        resource_id=tool.id,
        action=f"Registered custom tool '{tool.label}'",
        details_json={
            "tool_id": tool.tool_id,
            "role_id": tool.role_id,
            "endpoint_url": tool.endpoint_url,
        },
    ))
    db.commit()
    db.refresh(tool)
    return _serialize_tool(tool, username=admin.username)


def update_custom_tool(db: Session, row_id: str, admin: User, payload: dict) -> dict:
    tool = get_custom_tool_row(db, row_id)
    if not tool:
        raise CustomToolNotFoundError(f"Custom tool '{row_id}' not found")

    if payload.get("role_id") is not None:
        _validate_role(payload["role_id"])
        tool.role_id = payload["role_id"]
    if payload.get("label") is not None:
        tool.label = payload["label"].strip()
    if payload.get("description") is not None:
        tool.description = payload["description"].strip() or None
    if payload.get("endpoint_url") is not None:
        _validate_endpoint(payload["endpoint_url"])
        tool.endpoint_url = payload["endpoint_url"].strip()
    if payload.get("http_method") is not None:
        tool.http_method = payload["http_method"].upper()
    if payload.get("auth_type") is not None:
        tool.auth_type = payload["auth_type"]
    if payload.get("auth_header_name") is not None:
        tool.auth_header_name = payload["auth_header_name"].strip() or None
    if payload.get("auth_secret") is not None and payload["auth_secret"].strip():
        tool.auth_secret = payload["auth_secret"].strip()
    if payload.get("request_template") is not None:
        tool.request_template = payload["request_template"]
    if payload.get("status") is not None:
        tool.status = payload["status"]

    auth_type = tool.auth_type or "none"
    if auth_type != "none" and not (tool.auth_secret or "").strip():
        _validate_auth(auth_type, tool.auth_header_name, None)

    tool.updated_at = datetime.utcnow()
    db.add(AuditEvent(
        event_type="custom_tool_updated",
        actor=admin.username,
        resource_type="custom_tool",
        resource_id=tool.id,
        action=f"Updated custom tool '{tool.label}'",
        details_json={"tool_id": tool.tool_id, "status": tool.status},
    ))
    db.commit()
    db.refresh(tool)
    return _serialize_tool(tool, username=admin.username)


def delete_custom_tool(db: Session, row_id: str, admin: User) -> None:
    tool = get_custom_tool_row(db, row_id)
    if not tool:
        raise CustomToolNotFoundError(f"Custom tool '{row_id}' not found")

    label = tool.label
    tool_id = tool.tool_id
    db.add(AuditEvent(
        event_type="custom_tool_deleted",
        actor=admin.username,
        resource_type="custom_tool",
        resource_id=tool.id,
        action=f"Deleted custom tool '{label}'",
        details_json={"tool_id": tool_id},
    ))
    db.delete(tool)
    db.commit()
