"""Session store for Molecular Discovery Studio.

The live copy is in memory. Each change is also written to disk so a restart
can reopen the same research record.
"""

from __future__ import annotations

import json
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_lock = threading.Lock()
_SESSIONS: dict[str, dict[str, Any]] = {}
SESSIONS_DIR = Path(__file__).resolve().parents[3] / "storage" / "chem_sessions"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.json"


def _persist(session: dict[str, Any]) -> None:
    try:
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        _path(session["id"]).write_text(json.dumps(session, default=str), encoding="utf-8")
    except OSError:
        return


def _load(session_id: str) -> dict[str, Any] | None:
    path = _path(session_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("id") != session_id:
        return None
    return data


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
        "messages": [],
        "research": {
            "design_objectives": [],
            "hypotheses": [],
            "decisions": [],
            "pending_workflows": [],
            "completed_workflows": [],
            "artifacts": [],
            "answered_questions": [],
        },
        "selection": {"molecule_id": None, "pdb_id": None},
        "workflows": [],
        "docking_results": [],
        "admet_results": [],
        "similarity_results": [],
    }
    with _lock:
        _SESSIONS[sid] = session
        _persist(session)
    return deepcopy(session)


def get_session(session_id: str) -> dict[str, Any] | None:
    with _lock:
        s = _SESSIONS.get(session_id)
        if s is None:
            s = _load(session_id)
            if s is not None:
                _SESSIONS[session_id] = s
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
        _persist(s)
        return deepcopy(s)


def append_card(session_id: str, card: dict[str, Any]) -> dict[str, Any] | None:
    with _lock:
        s = _SESSIONS.get(session_id)
        if not s:
            s = _load(session_id)
            if s is None:
                return None
            _SESSIONS[session_id] = s
        s.setdefault("messages", [])
        s["cards"].append(card)
        asked = (card.get("query") or "").strip()
        answered = (card.get("narrative") or card.get("summary") or "").strip()
        if asked:
            s["messages"].append({
                "role": "scientist",
                "content": asked,
                "at": _now(),
                "card_id": card.get("card_id"),
            })
        if answered:
            s["messages"].append({
                "role": "studio",
                "content": answered,
                "at": _now(),
                "card_id": card.get("card_id"),
                "intent": card.get("intent"),
            })
        s["updated_at"] = _now()
        _persist(s)
        return deepcopy(s)


def ensure_session(session_id: str | None, user_id: str | None = None) -> dict[str, Any]:
    if session_id:
        existing = get_session(session_id)
        if existing:
            return existing
    return create_session(user_id)


def set_selection(
    session_id: str,
    *,
    molecule_id: str | None = None,
    pdb_id: str | None = None,
) -> dict[str, Any] | None:
    with _lock:
        session = _SESSIONS.get(session_id) or _load(session_id)
        if session is None:
            return None
        _SESSIONS[session_id] = session
        selection = dict(session.get("selection") or {})
        selection["molecule_id"] = molecule_id
        selection["pdb_id"] = pdb_id
        session["selection"] = selection
        if pdb_id:
            session["last_pdb_id"] = pdb_id
        session["updated_at"] = _now()
        _persist(session)
        return deepcopy(session)


def import_session(payload: dict[str, Any], user_id: str | None = None) -> dict[str, Any]:
    """Reopen an exported package. The stored transcript is kept as exported."""
    incoming = payload.get("session") if isinstance(payload.get("session"), dict) else payload
    if not isinstance(incoming, dict):
        raise ValueError("A session export is required")
    sid = str(incoming.get("id") or uuid.uuid4())
    session = deepcopy(incoming)
    session["id"] = sid
    session["user_id"] = user_id or session.get("user_id")
    session.setdefault("messages", payload.get("transcript") or [])
    session.setdefault("cards", payload.get("cards") or [])
    session.setdefault("candidates", payload.get("molecules") or [])
    session["updated_at"] = _now()
    with _lock:
        _SESSIONS[sid] = session
        _persist(session)
    return deepcopy(session)
