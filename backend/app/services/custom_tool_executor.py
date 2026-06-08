"""Invoke admin-registered custom Tool Fabric HTTP endpoints."""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.models.db_models import AuditEvent, CustomTool
from app.services.custom_tool_service import get_custom_tool_by_tool_id
from app.services.tool_fabric_service import is_custom_tool_id, normalize_custom_tool_id


def build_custom_tool_payload(tool: CustomTool, role_id: str, input_data: dict) -> dict:
    """Merge request template with standard agent run context."""
    base = dict(tool.request_template or {})
    context = {
        "role_id": role_id,
        "query": input_data.get("query", ""),
        "task_type": input_data.get("task_type"),
        "compounds": input_data.get("compounds") or input_data.get("library") or [],
        "smiles": input_data.get("query_smiles") or input_data.get("smiles"),
        "document_ids": input_data.get("document_ids") or [],
        "agent_input": {
            k: v
            for k, v in input_data.items()
            if k not in ("auth_secret", "_tool_fabric_logs") and not str(k).startswith("_")
        },
    }
    if isinstance(base, dict):
        payload = {**base}
        payload.setdefault("context", context)
        if "query" not in payload and context["query"]:
            payload["query"] = context["query"]
        return payload
    return {"context": context}


def _auth_headers(tool: CustomTool) -> dict[str, str]:
    auth_type = (tool.auth_type or "none").lower()
    if auth_type == "bearer" and tool.auth_secret:
        return {"Authorization": f"Bearer {tool.auth_secret}"}
    if auth_type == "api_key_header" and tool.auth_secret:
        header = (tool.auth_header_name or "X-API-Key").strip()
        return {header: tool.auth_secret}
    return {}


def invoke_custom_tool_http(
    tool: CustomTool,
    payload: dict,
    *,
    timeout: float = 30.0,
) -> dict[str, Any]:
    method = (tool.http_method or "POST").upper()
    headers = {"Content-Type": "application/json", **_auth_headers(tool)}
    started = time.perf_counter()

    with httpx.Client(timeout=timeout) as client:
        if method == "GET":
            resp = client.get(tool.endpoint_url, params=payload if isinstance(payload, dict) else None, headers=headers)
        elif method == "PUT":
            resp = client.put(tool.endpoint_url, json=payload, headers=headers)
        else:
            resp = client.post(tool.endpoint_url, json=payload, headers=headers)

    latency_ms = int((time.perf_counter() - started) * 1000)
    resp.raise_for_status()

    try:
        body = resp.json()
    except json.JSONDecodeError:
        body = {"raw_text": resp.text[:4000]}

    return {
        "status_code": resp.status_code,
        "latency_ms": latency_ms,
        "body": body,
    }


def test_custom_tool_connection(tool: CustomTool, sample_payload: dict | None = None) -> dict:
    payload = sample_payload or build_custom_tool_payload(tool, tool.role_id, {"query": "SciNova Tool Fabric connectivity test"})
    try:
        result = invoke_custom_tool_http(tool, payload, timeout=15.0)
        preview = json.dumps(result.get("body"), default=str)[:500]
        return {
            "ok": True,
            "status_code": result["status_code"],
            "response_preview": preview,
            "latency_ms": result["latency_ms"],
        }
    except httpx.HTTPStatusError as exc:
        return {
            "ok": False,
            "status_code": exc.response.status_code,
            "error": f"HTTP {exc.response.status_code}: {exc.response.text[:300]}",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def invoke_bound_custom_tools(
    db: Session,
    bindings: dict[str, str],
    input_data: dict,
    *,
    actor: str,
    agent_name: str,
) -> tuple[dict, list[dict]]:
    """Invoke custom tools referenced in resolved bindings; enrich input_data."""
    enriched = dict(input_data)
    results: dict[str, dict] = {}
    logs: list[dict] = []

    for role_id, tool_id in bindings.items():
        if not is_custom_tool_id(tool_id):
            continue
        normalized = normalize_custom_tool_id(tool_id)
        tool = get_custom_tool_by_tool_id(db, normalized)
        if not tool:
            logs.append({"message": f"Custom tool '{tool_id}' not found in registry"})
            results[role_id] = {"tool_id": tool_id, "error": "not_registered"}
            continue
        if tool.status != "active":
            logs.append({"message": f"Custom tool '{tool.label}' is disabled"})
            results[role_id] = {"tool_id": tool.tool_id, "error": "disabled"}
            continue

        payload = build_custom_tool_payload(tool, role_id, enriched)
        try:
            http_result = invoke_custom_tool_http(tool, payload)
            results[role_id] = {
                "tool_id": tool.tool_id,
                "label": tool.label,
                "role_id": role_id,
                "status_code": http_result["status_code"],
                "latency_ms": http_result["latency_ms"],
                "body": http_result["body"],
            }
            logs.append({
                "message": (
                    f"Custom tool '{tool.label}' ({tool.tool_id}) invoked for {role_id} "
                    f"— HTTP {http_result['status_code']} in {http_result['latency_ms']}ms"
                ),
            })
            db.add(AuditEvent(
                event_type="custom_tool_invoked",
                actor=actor,
                resource_type="custom_tool",
                resource_id=tool.id,
                action=f"Custom tool '{tool.label}' invoked for agent '{agent_name}'",
                details_json={
                    "tool_id": tool.tool_id,
                    "role_id": role_id,
                    "agent_name": agent_name,
                    "status_code": http_result["status_code"],
                    "latency_ms": http_result["latency_ms"],
                },
            ))
        except Exception as exc:
            results[role_id] = {
                "tool_id": tool.tool_id,
                "label": tool.label,
                "error": str(exc),
            }
            logs.append({"message": f"Custom tool '{tool.label}' failed: {exc}"})
            db.add(AuditEvent(
                event_type="custom_tool_invocation_failed",
                actor=actor,
                resource_type="custom_tool",
                resource_id=tool.id,
                action=f"Custom tool '{tool.label}' failed for agent '{agent_name}'",
                details_json={
                    "tool_id": tool.tool_id,
                    "role_id": role_id,
                    "agent_name": agent_name,
                    "error": str(exc),
                },
            ))

    if results:
        enriched["custom_tool_results"] = results
    enriched["_tool_fabric_logs"] = list(enriched.get("_tool_fabric_logs") or []) + logs
    return enriched, logs
