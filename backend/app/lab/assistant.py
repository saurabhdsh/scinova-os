"""Scientist questions and intent-based plan drafts for the lab assistant."""

from __future__ import annotations

import json
import re

from sqlalchemy.orm import Session

from app.config import settings
from app.lab.errors import LabError
from app.lab.models import (
    LabExperiment,
    LabExperimentPlan,
    LabInsight,
    LabInstrument,
    LabLot,
    LabProtocol,
    LabProtocolVersion,
    LabReadinessIssue,
    LabResult,
    LabTrainingRecord,
)
from app.lab.operations import storyline
from app.services.llm_service import is_openai_model, llm_service

_SYSTEM = """You are the SciNova lab assistant, talking with the scientist who is looking at the screen.
Answer only from the lab record in the message. Name the actual instruments, lots, operators, measurements, and statuses written there.
Speak in short plain sentences. Five sentences at most. No pep talk and no general lecture.
Readiness checks are only these: instrument calibration, reagent expiry, operator training, compliance holds, samples, and materials. Do not add other checks.
If the record does not contain the fact, say that you do not have it. Do not invent measurements, instruments, lots, operators, or outcomes.
Do not approve a plan, start a run, or change a parameter. If current_draft is present, the scientist is still planning that experiment. Its intent is why the run exists. Answer from that draft. If the scientist wants a new experiment, tell them to describe the run and you will draft a plan for them to approve.
The follow_ups are one or two short questions the scientist might type next.
Return JSON with keys "answer" and "follow_ups"."""


def answer_question(db: Session, question: str, history: list | None, experiment_id: str | None, draft: dict | None = None) -> dict:
    record = _record(db, experiment_id)
    context = _draft_context(draft)
    if context:
        record["current_draft"] = context
    turns = _history(history)
    model = _openai_model()
    parsed = _ask_model(model, question, turns, record) if model else None
    if parsed is None:
        return {
            "answer": _from_record(question, record),
            "follow_ups": _fallback_follow_ups(record),
            "source": "lab_record",
        }
    follow_ups = parsed.get("follow_ups") if isinstance(parsed.get("follow_ups"), list) else []
    clean = [str(item).strip() for item in follow_ups if str(item).strip()][:2]
    return {"answer": str(parsed.get("answer") or "").strip(), "follow_ups": clean, "source": "openai"}


def _openai_model() -> str | None:
    if not llm_service.openai_available:
        return None
    configured = (settings.llm_model or "").strip()
    if is_openai_model(configured):
        return configured
    return "gpt-4o-mini"


def _ask_model(model: str, question: str, turns: list[dict], record: dict) -> dict | None:
    user = _prompt(question, turns, record)
    parsed = llm_service.chat_json(_SYSTEM, user, model=model, temperature=0.3)
    if isinstance(parsed, dict) and str(parsed.get("answer") or "").strip():
        return parsed
    text = llm_service.chat(_SYSTEM, user, model=model, temperature=0.3)
    return _coerce(text)


def _prompt(question: str, turns: list[dict], record: dict) -> str:
    lines = [f"Lab record:\n{json.dumps(record, default=str)}"]
    if turns:
        lines.append("Conversation so far:")
        lines.extend(f"{item['role']}: {item['text']}" for item in turns)
    lines.append(f"Scientist: {question}")
    return "\n".join(lines)


def _coerce(text: str | None) -> dict | None:
    if not text or not text.strip():
        return None
    body = text.strip()
    if body.startswith("```"):
        body = body.strip("`")
        body = body.removeprefix("json").strip()
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return {"answer": text.strip(), "follow_ups": []}
    if isinstance(parsed, dict) and str(parsed.get("answer") or "").strip():
        return parsed
    return {"answer": text.strip(), "follow_ups": []}


def _history(history: list | None) -> list[dict]:
    turns = []
    for item in history or []:
        if not isinstance(item, dict):
            continue
        role = "Scientist" if item.get("role") == "scientist" else "Assistant"
        text = str(item.get("text") or "").strip()
        if text:
            turns.append({"role": role, "text": text[:500]})
    return turns[-8:]


def _record(db: Session, experiment_id: str | None) -> dict:
    protocols = []
    versions = (
        db.query(LabProtocolVersion)
        .join(LabProtocol, LabProtocol.id == LabProtocolVersion.protocol_id)
        .filter(LabProtocolVersion.status == "approved")
        .all()
    )
    protocol_rows = {row.id: row for row in db.query(LabProtocol).all()}
    for version in versions:
        protocol = protocol_rows.get(version.protocol_id)
        if protocol is None or protocol.status != "approved":
            continue
        protocols.append({
            "code": protocol.code,
            "title": protocol.title,
            "version": version.version_label,
            "summary": protocol.summary,
            "parameters": version.parameters_json or {},
            "success_criteria": version.success_criteria_json or [],
        })
    instruments = [
        {
            "name": row.name,
            "serial_number": row.serial_number,
            "calibration_status": row.calibration_status,
            "calibration_due": row.calibration_due.isoformat() if row.calibration_due else None,
        }
        for row in db.query(LabInstrument).all()
    ]
    recent = []
    for experiment in db.query(LabExperiment).order_by(LabExperiment.created_at.desc()).limit(8).all():
        recent.append({
            "id": experiment.id,
            "title": experiment.title,
            "status": experiment.status,
            "outcome": experiment.outcome,
        })
    return {
        "protocols": protocols,
        "instruments": instruments,
        "recent_experiments": recent,
        "open_experiment": _open_experiment(db, experiment_id),
    }


def _open_experiment(db: Session, experiment_id: str | None) -> dict | None:
    if not experiment_id:
        return None
    experiment = db.get(LabExperiment, experiment_id)
    if experiment is None:
        return None
    plan = db.get(LabExperimentPlan, experiment.plan_id)
    try:
        line = storyline(db, experiment_id)
    except LabError:
        line = None
    issues = db.query(LabReadinessIssue).filter(LabReadinessIssue.experiment_id == experiment_id).all()
    results = (
        db.query(LabResult)
        .filter(LabResult.experiment_id == experiment_id, LabResult.status == "active")
        .all()
    )
    insights = (
        db.query(LabInsight)
        .filter(LabInsight.experiment_id == experiment_id, LabInsight.status == "active")
        .all()
    )
    return {
        "id": experiment.id,
        "title": experiment.title,
        "status": experiment.status,
        "outcome": experiment.outcome,
        "plan": None if plan is None else {
            "title": plan.title,
            "status": plan.status,
            "parameters": plan.parameters_json or {},
            "success_criteria": plan.success_criteria_json or [],
            "intent": (plan.parameters_json or {}).get("_scientist_intent"),
        },
        "storyline": None if line is None else line.get("moments"),
        "readiness": [
            {"code": row.code, "status": row.status, "message": row.message, "recommendation": row.recommendation_json or {}}
            for row in issues
        ],
        "results": [
            {
                "metric": row.metric,
                "value": row.value,
                "unit": row.unit,
                "operator": row.operator,
                "threshold": row.threshold,
                "outcome": row.outcome,
            }
            for row in results
        ],
        "findings": [
            {"type": row.insight_type, "title": row.title, "statement": row.statement, "evidence": row.evidence_json or {}}
            for row in insights
        ],
    }


def _draft_context(draft: dict | None) -> dict | None:
    if not isinstance(draft, dict):
        return None
    intent = str(draft.get("intent") or "").strip()[:1000]
    name = str(draft.get("experiment_name") or "").strip()[:160]
    protocol = str(draft.get("protocol_code") or "").strip()[:40]
    reason = str(draft.get("reason") or "").strip()[:500]
    raw_parameters = draft.get("parameters") if isinstance(draft.get("parameters"), dict) else {}
    parameters = {}
    for key, value in list(raw_parameters.items())[:12]:
        name_key = str(key)
        if name_key.startswith("_") or len(name_key) > 80:
            continue
        if isinstance(value, (int, float, str)):
            parameters[name_key] = value if not isinstance(value, str) else value[:120]
    criteria = []
    raw_criteria = draft.get("criteria") if isinstance(draft.get("criteria"), list) else []
    for item in raw_criteria[:8]:
        if not isinstance(item, dict):
            continue
        criteria.append({
            "metric": str(item.get("metric") or "")[:80],
            "operator": str(item.get("operator") or "")[:8],
            "threshold": item.get("threshold"),
            "unit": str(item.get("unit") or "")[:40],
        })
    if not any([intent, name, protocol, parameters, criteria]):
        return None
    return {
        "intent": intent or None,
        "experiment_name": name or None,
        "protocol_code": protocol or None,
        "parameters": parameters,
        "success_criteria": criteria,
        "reason": reason or None,
    }


def _from_record(question: str, record: dict) -> str:
    experiment = record.get("open_experiment") or {}
    draft = record.get("current_draft") or {}
    results = experiment.get("results") or []
    if results:
        parts = []
        for row in results:
            parts.append(
                f"{row['metric'].replace('_', ' ')} is {row['value']} {row['unit'] or ''}. "
                f"The plan required {row['operator']} {row['threshold']}. The outcome is {row['outcome']}."
            )
        lead = experiment.get("title") or "This experiment"
        return (
            f"The lab model is not connected, so this is only what is already on the record for {lead}. "
            + " ".join(parts)
        )
    if draft.get("intent"):
        name = draft.get("experiment_name") or "This experiment"
        protocol = draft.get("protocol_code") or "the selected protocol"
        return (
            f"The lab model is not connected. {name} is still a draft on {protocol}. "
            f"The intent is: {draft['intent']}"
        )
    if experiment.get("title"):
        return (
            f"The lab model is not connected. {experiment['title']} is {experiment.get('status') or 'open'}. "
            "I can still draft a new experiment if you describe the run you want."
        )
    return "The lab model is not connected right now. Describe the run you want and I will draft a plan for you to approve."


def _fallback_follow_ups(record: dict) -> list[str]:
    if (record.get("open_experiment") or {}).get("results"):
        return ["What should I change on the next run?", "Which readiness checks were exceptions?"]
    return ["What does readiness check before a run?", "Which instruments have a current calibration?"]


_DRAFT_SYSTEM = """You write one experiment protocol from the scientist's intent.
Approved protocols are examples. If one fits, set protocol_code to that code and return that protocol's parameters, changing only values the intent requires.
If none fits, set protocol_code to an empty string and write a new protocol_title. parameters are the fields that experiment needs, each already filled with a value.
When you name an instrument, operator, or lot, use only the lab assets in the message.
criteria is a list of objects with metric, operator, threshold, and unit. operator is one of >=, <=, >, <, ==.
experiment_name is a short name taken from the intent.
reason is one or two plain sentences that say why this protocol and these values match the intent.
Return JSON with keys protocol_code, protocol_title, experiment_name, reason, parameters, criteria."""

_INTENT_RULES = (
    ("SYN-SEQ-001", ("sequenc", "mutation", "tumor", "dna", "ngs", "variant")),
    ("SYN-CVP-003", ("thaw", "cryo", "recover")),
    ("SYN-CVP-002", ("density screen", "seeding-density", "seeding density screen")),
    ("SYN-CVP-001", ("viab", "trypan", "vicell")),
)
_OPERATORS = {">=", "<=", ">", "<", "=="}


def draft_from_intent(db: Session, intent: str) -> dict:
    catalog = _protocol_catalog(db)
    assets = _lab_assets(db)
    if not catalog and not assets["instruments"]:
        raise LabError("No approved protocol is available to draft a plan.", status_code=409, code="no_protocol")
    model = _openai_model()
    parsed = _ask_draft(model, intent, catalog, assets) if model else None
    if parsed is None:
        parsed = _draft_without_model(intent, catalog)
        source = "lab_record"
    else:
        source = "openai"
    return _accepted_draft(intent, catalog, parsed, source, assets)


def _protocol_catalog(db: Session) -> list[dict]:
    versions = (
        db.query(LabProtocolVersion)
        .join(LabProtocol, LabProtocol.id == LabProtocolVersion.protocol_id)
        .filter(LabProtocolVersion.status == "approved", LabProtocol.status == "approved")
        .all()
    )
    protocols = {row.id: row for row in db.query(LabProtocol).all()}
    catalog = []
    for version in versions:
        protocol = protocols.get(version.protocol_id)
        if protocol is None:
            continue
        catalog.append({
            "code": protocol.code,
            "title": protocol.title,
            "summary": protocol.summary,
            "parameters": version.parameters_json or {},
            "success_criteria": version.success_criteria_json or [],
        })
    return catalog


def _ask_draft(model: str, intent: str, catalog: list[dict], assets: dict) -> dict | None:
    user = "\n\n".join([
        f"Approved protocols:\n{json.dumps(catalog, default=str)}",
        f"Lab assets:\n{json.dumps(assets, default=str)}",
        f"Scientist intent: {intent}",
    ])
    parsed = llm_service.chat_json(_DRAFT_SYSTEM, user, model=model, temperature=0.2)
    if _draft_payload(parsed):
        return parsed
    text = llm_service.chat(_DRAFT_SYSTEM, user, model=model, temperature=0.2)
    coerced = _coerce(text)
    if _draft_payload(coerced):
        return coerced
    return None


def _draft_payload(parsed) -> bool:
    return isinstance(parsed, dict) and bool(
        parsed.get("protocol_code") or parsed.get("protocol_title") or parsed.get("parameters")
    )


def _draft_without_model(intent: str, catalog: list[dict]) -> dict:
    lowered = intent.lower()
    code = ""
    for candidate, words in _INTENT_RULES:
        if any(word in lowered for word in words) and any(row["code"] == candidate for row in catalog):
            code = candidate
            break
    if code:
        protocol = next(row for row in catalog if row["code"] == code)
        parameters = {}
        seeding = _number(r"seeding[^\d]{0,24}(\d[\d,]*)", intent)
        if seeding is not None:
            parameters["seeding_density_cells_per_ml"] = int(seeding)
        incubation = _number(r"incubat\w*[^\d]{0,16}(\d+)", intent)
        if incubation is not None:
            parameters["incubation_hours"] = incubation
        threshold = _number(r"(?:viability|threshold)[^\d]{0,16}(\d+(?:\.\d+)?)", intent)
        criteria = [{"metric": "mean_viability_percent", "threshold": threshold}] if threshold is not None else []
        return {
            "protocol_code": code,
            "protocol_title": protocol["title"],
            "experiment_name": protocol["title"][:80],
            "reason": f"{protocol['title']} matches what you described. Review the filled fields before you approve.",
            "parameters": parameters,
            "criteria": criteria,
        }
    title = _short_title(intent)
    return {
        "protocol_code": "",
        "protocol_title": title,
        "experiment_name": title,
        "reason": "No approved protocol matches this description, so this protocol is suggested from your intent. Review the filled fields before you approve.",
        "parameters": {"sample_type": "As described in the intent", "assay": title},
        "criteria": [{"metric": "primary_readout", "operator": ">=", "threshold": 1, "unit": "unit"}],
    }


def _accepted_draft(intent: str, catalog: list[dict], parsed: dict, source: str, assets: dict) -> dict:
    by_code = {row["code"]: row for row in catalog}
    code = str(parsed.get("protocol_code") or "").strip()
    existing = by_code.get(code)
    incoming = parsed.get("parameters") if isinstance(parsed.get("parameters"), dict) else {}
    if existing:
        parameters = dict(existing["parameters"] or {})
        for key, value in incoming.items():
            if str(key).startswith("_"):
                continue
            sample = parameters.get(key, value)
            coerced = _coerce_param(sample, value) if key in parameters else _coerce_free(value)
            if coerced is not None:
                parameters[key] = coerced
        criteria = _merge_criteria(existing.get("success_criteria") or [], parsed.get("criteria"))
        protocol_title = existing["title"]
        new_protocol = False
    else:
        parameters = {}
        for key, value in list(incoming.items())[:16]:
            if str(key).startswith("_"):
                continue
            coerced = _coerce_free(value)
            if coerced is not None:
                parameters[str(key)[:80]] = coerced
        criteria = _normalize_criteria(parsed.get("criteria"))
        protocol_title = str(parsed.get("protocol_title") or parsed.get("experiment_name") or _short_title(intent)).strip()[:160]
        new_protocol = True
        code = ""
    parameters, notes = _snap_assets(parameters, assets)
    if not criteria:
        criteria = [{"id": "SC-1", "metric": "primary_readout", "operator": ">=", "threshold": 1, "unit": "unit"}]
    name = str(parsed.get("experiment_name") or protocol_title).strip()[:120]
    reason = str(parsed.get("reason") or "").strip()
    if not reason:
        reason = f"{protocol_title} is suggested from your intent. Review the filled fields before you approve."
    if notes:
        reason = f"{reason} {' '.join(notes)}".strip()
    return {
        "protocol_code": code or None,
        "protocol_title": protocol_title or name,
        "new_protocol": new_protocol,
        "experiment_name": name or protocol_title,
        "reason": reason[:500],
        "parameters": parameters,
        "criteria": criteria,
        "intent": intent,
        "source": source,
    }


def _lab_assets(db: Session) -> dict:
    instruments = [
        {
            "serial_number": row.serial_number,
            "name": row.name,
            "calibration_status": row.calibration_status,
        }
        for row in db.query(LabInstrument).all()
        if row.serial_number
    ]
    lots = [
        {"lot_number": row.lot_number, "status": row.status}
        for row in db.query(LabLot).all()
        if row.lot_number
    ]
    operators = []
    for row in db.query(LabTrainingRecord).filter(LabTrainingRecord.qualified.is_(True)).all():
        if row.person_name and row.person_name not in operators:
            operators.append(row.person_name)
    return {"instruments": instruments, "lots": lots, "operators": operators}


def _snap_assets(parameters: dict, assets: dict) -> tuple[dict, list[str]]:
    params = dict(parameters)
    notes = []
    instruments = assets.get("instruments") or []
    serials = {row["serial_number"] for row in instruments}
    current = next((row for row in instruments if row.get("calibration_status") == "current"), None)
    fallback = current or (instruments[0] if instruments else None)
    if fallback:
        serial = str(params.get("instrument_serial") or "")
        if serial not in serials:
            if serial:
                notes.append(f"Instrument {serial} is not in the lab, so the plan uses {fallback['serial_number']}.")
            params["instrument_serial"] = fallback["serial_number"]
    operators = assets.get("operators") or []
    preferred = "Priya Nair" if "Priya Nair" in operators else (operators[0] if operators else "")
    if preferred:
        named = str(params.get("operator") or "")
        if named not in operators:
            if named:
                notes.append(f"{named} is not a qualified operator here, so the plan names {preferred}.")
            params["operator"] = preferred
    known_lots = {row["lot_number"] for row in assets.get("lots") or []}
    good_lot = next((row["lot_number"] for row in assets.get("lots") or [] if row.get("status") != "near_expiry"), None)
    for key in ("reagent_lot", "library_lot"):
        if key not in params or not good_lot:
            continue
        lot = str(params.get(key) or "")
        if lot not in known_lots:
            if lot:
                notes.append(f"Lot {lot} is not in the lab, so the plan uses {good_lot}.")
            params[key] = good_lot
    return params, notes


def _merge_criteria(base: list, incoming) -> list:
    criteria = [dict(item) for item in base if isinstance(item, dict)]
    updates = _normalize_criteria(incoming)
    if not updates:
        return criteria
    by_metric = {item.get("metric"): item for item in updates}
    merged = []
    seen = set()
    for item in criteria:
        update = by_metric.get(item.get("metric"))
        if update:
            item = {**item, "threshold": update["threshold"], "operator": update.get("operator") or item.get("operator")}
            if update.get("unit"):
                item["unit"] = update["unit"]
        merged.append(item)
        seen.add(item.get("metric"))
    for item in updates:
        if item["metric"] not in seen:
            merged.append(item)
    return merged


def _normalize_criteria(incoming) -> list:
    if not isinstance(incoming, list):
        return []
    criteria = []
    for index, item in enumerate(incoming[:8]):
        if not isinstance(item, dict):
            continue
        metric = re.sub(r"[^a-z0-9_]+", "_", str(item.get("metric") or "").strip().lower()).strip("_")[:80]
        if not metric:
            continue
        try:
            threshold = float(item.get("threshold"))
        except (TypeError, ValueError):
            continue
        operator = str(item.get("operator") or ">=").strip()
        if operator == "=":
            operator = "=="
        if operator not in _OPERATORS:
            operator = ">="
        unit = str(item.get("unit") or "unit").strip()[:40] or "unit"
        criteria.append({
            "id": str(item.get("id") or f"SC-{index + 1}")[:40],
            "metric": metric,
            "operator": operator,
            "threshold": threshold,
            "unit": unit,
        })
    return criteria


def _short_title(intent: str) -> str:
    words = re.sub(r"\s+", " ", intent).strip()
    return (words[:80] or "Suggested protocol").rstrip(" .")


def _coerce_free(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int(value) if isinstance(value, int) else float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        compact = text.replace(",", "")
        if re.fullmatch(r"-?\d+", compact):
            return int(compact)
        if re.fullmatch(r"-?\d+\.\d+", compact):
            return float(compact)
        return text[:160]
    return None


def _coerce_param(sample, value):
    if isinstance(sample, bool):
        return None
    if isinstance(sample, (int, float)):
        try:
            number = float(str(value).replace(",", ""))
        except (TypeError, ValueError):
            return None
        if isinstance(sample, int) and not isinstance(sample, bool):
            return int(number)
        return number
    if isinstance(sample, str):
        text = str(value).strip()
        return text[:120] if text else None
    return _coerce_free(value)


def _number(pattern: str, text: str):
    found = re.search(pattern, text, re.I)
    if not found:
        return None
    try:
        return float(found.group(1).replace(",", ""))
    except ValueError:
        return None
