"""Deterministic scientific calculations. No model calls."""

from __future__ import annotations

import math
import statistics

_OPS = {
    ">=": lambda v, t: v >= t,
    "<=": lambda v, t: v <= t,
    ">": lambda v, t: v > t,
    "<": lambda v, t: v < t,
    "==": lambda v, t: v == t,
}


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return statistics.fmean(values)


def sample_stdev(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    return statistics.stdev(values)


def coefficient_of_variation(values: list[float]) -> float | None:
    """Sample coefficient of variation, percent. Uses the n-1 standard deviation."""
    avg = mean(values)
    sd = sample_stdev(values)
    if avg is None or sd is None or avg == 0:
        return None
    return abs(sd / avg) * 100.0


def round_sci(value: float | None, digits: int = 4) -> float | None:
    if value is None or isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return round(float(value), digits)


def compare(operator: str, value: float, threshold: float) -> bool:
    fn = _OPS.get(operator)
    if fn is None:
        raise ValueError(f"Unsupported operator: {operator}")
    return bool(fn(value, threshold))


def outcome_label(passed: bool) -> str:
    return "pass" if passed else "fail"
