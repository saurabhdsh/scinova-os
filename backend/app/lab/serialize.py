"""JSON helpers for lab rows."""

from __future__ import annotations

from datetime import date, datetime


def dump(row) -> dict:
    payload = {}
    for column in row.__table__.columns:
        value = getattr(row, column.name)
        if isinstance(value, datetime):
            payload[column.name] = value.isoformat() + "Z"
        elif isinstance(value, date):
            payload[column.name] = value.isoformat()
        else:
            payload[column.name] = value
    return payload


def dumps(rows) -> list[dict]:
    return [dump(row) for row in rows]
