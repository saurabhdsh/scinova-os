"""In-memory session store for Molecular Discovery Studio."""

from __future__ import annotations

import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

_lock = threading.Lock()
_SESSIONS: dict[str, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_session(user_id: str | None = None) -> dict[str, Any]:
    sid = str(uuid.uuid4())
    session = {
        "id": sid,
        "user_id": user_id,
        "created_at": _now(),
        "updated_at": _now(),
        "target": None,
        "structures": [],
        "actives": [],
        "candidates": [],
        "novelty": [],
        "motifs": None,
        "routes": None,
        "last_pdb_id": None,
        "last_smiles": None,
        "cards": [],
    }
    with _lock:
        _SESSIONS[sid] = session
    return deepcopy(session)


def get_session(session_id: str) -> dict[str, Any] | None:
    with _lock:
        s = _SESSIONS.get(session_id)
        return deepcopy(s) if s else None


def update_session(session_id: str, **kwargs) -> dict[str, Any] | None:
    with _lock:
        s = _SESSIONS.get(session_id)
        if not s:
            return None
        for k, v in kwargs.items():
            if v is not None:
                s[k] = v
        s["updated_at"] = _now()
        return deepcopy(s)


def append_card(session_id: str, card: dict[str, Any]) -> dict[str, Any] | None:
    with _lock:
        s = _SESSIONS.get(session_id)
        if not s:
            return None
        s["cards"].append(card)
        s["updated_at"] = _now()
        return deepcopy(s)


def ensure_session(session_id: str | None, user_id: str | None = None) -> dict[str, Any]:
    if session_id:
        existing = get_session(session_id)
        if existing:
            return existing
    return create_session(user_id)
