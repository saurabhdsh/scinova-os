"""Append-only audit via the existing AuditEvent table."""

from __future__ import annotations

from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from app.models.db_models import AuditEvent


def record(
    db: Session,
    *,
    event_type: str,
    actor: str,
    resource_type: str,
    resource_id: str,
    action: str,
    details: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        event_type=event_type,
        actor=actor,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        details_json=details or {},
    )
    db.add(event)
    db.flush()
    return event


def history(db: Session, entity_ref: str) -> list[AuditEvent]:
    """entity_ref is a bare id or type:id.

    Direct resource rows and events that cite the id in details are both returned.
    Gate decisions are stored on the plan, issue, or dossier and name the experiment
    in details, so an experiment query still shows G1, G2, and G6 in order.
    """
    token = entity_ref.split(":")[-1]
    if not token:
        return []
    return (
        db.query(AuditEvent)
        .filter(
            or_(
                AuditEvent.resource_id == token,
                cast(AuditEvent.details_json, String).contains(token),
            )
        )
        .order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
        .all()
    )
