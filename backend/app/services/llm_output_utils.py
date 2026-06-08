"""Normalize LLM structured fields that may be str, dict, or list."""

import json
from typing import Any


def coerce_text(value: Any, *, max_len: int | None = None) -> str:
    """Convert LLM output fields to a safe string for storage and slicing."""
    if value is None:
        text = ""
    elif isinstance(value, str):
        text = value
    elif isinstance(value, dict):
        for key in ("text", "content", "answer", "summary", "narrative", "body"):
            if key in value and value[key]:
                nested = coerce_text(value[key], max_len=max_len)
                if nested:
                    return nested
        text = json.dumps(value, default=str, ensure_ascii=False)
    elif isinstance(value, list):
        parts = [coerce_text(item) for item in value[:8]]
        text = "\n".join(p for p in parts if p) or json.dumps(value, default=str, ensure_ascii=False)
    else:
        text = str(value)

    if max_len is not None and len(text) > max_len:
        return text[:max_len]
    return text


def pick_text(data: dict, *keys: str, default: str = "", max_len: int | None = None) -> str:
    for key in keys:
        if key in data and data[key] is not None:
            text = coerce_text(data[key], max_len=max_len)
            if text:
                return text
    return coerce_text(default, max_len=max_len)
