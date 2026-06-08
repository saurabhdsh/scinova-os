"""Automated QC for experiment / assay CSV and Excel uploads."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

ASSAY_COLUMN_HINTS = (
    "sample", "well", "plate", "replicate", "value", "result", "measurement",
    "concentration", "response", "signal", "readout", "assay", "compound",
    "dose", "timepoint", "subject", "animal", "batch", "run",
)


def _load_table(file_path: str, file_format: str) -> pd.DataFrame:
    path = Path(file_path)
    fmt = (file_format or path.suffix).upper().lstrip(".")
    if fmt == "XLSX":
        return pd.read_excel(path)
    if fmt == "CSV":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported QC format: {fmt}")


def _outlier_count(series: pd.Series) -> int:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if len(numeric) < 8:
        return 0
    q1, q3 = numeric.quantile(0.25), numeric.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return 0
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return int(((numeric < lower) | (numeric > upper)).sum())


def run_experiment_qc(file_path: str, file_format: str) -> dict[str, Any]:
    """Run structured QC checks on tabular experiment data."""
    checks: list[dict[str, Any]] = []
    flags: list[str] = []

    try:
        df = _load_table(file_path, file_format)
    except Exception as exc:
        return {
            "status": "fail",
            "score": 0.0,
            "row_count": 0,
            "column_count": 0,
            "checks": [{"name": "file_readable", "status": "fail", "message": str(exc)}],
            "flags": ["File could not be parsed as tabular data"],
            "column_profile": [],
        }

    row_count, col_count = len(df), len(df.columns)
    checks.append({
        "name": "file_readable",
        "status": "pass",
        "message": f"Loaded {row_count} rows × {col_count} columns",
    })

    if row_count == 0:
        flags.append("Empty dataset")
        checks.append({"name": "non_empty", "status": "fail", "message": "No data rows"})
    else:
        checks.append({"name": "non_empty", "status": "pass", "message": f"{row_count} rows"})

    duplicate_rows = int(df.duplicated().sum())
    if duplicate_rows > 0:
        flags.append(f"{duplicate_rows} duplicate rows")
        checks.append({"name": "duplicates", "status": "warn", "message": f"{duplicate_rows} duplicate rows"})
    else:
        checks.append({"name": "duplicates", "status": "pass", "message": "No duplicate rows"})

    assay_cols = [
        c for c in df.columns
        if any(h in str(c).lower() for h in ASSAY_COLUMN_HINTS)
    ]
    if assay_cols:
        checks.append({
            "name": "assay_columns",
            "status": "pass",
            "message": f"Detected assay columns: {', '.join(map(str, assay_cols[:5]))}",
        })
    else:
        flags.append("No standard assay column names detected")
        checks.append({
            "name": "assay_columns",
            "status": "warn",
            "message": "Could not match common assay column names",
        })

    column_profile = []
    for col in df.columns:
        col_series = df[col]
        missing_pct = round(float(col_series.isna().mean()) * 100, 1)
        numeric = pd.to_numeric(col_series, errors="coerce")
        numeric_pct = round(float(numeric.notna().mean()) * 100, 1)
        outliers = _outlier_count(col_series)
        profile = {
            "column": str(col),
            "dtype": str(col_series.dtype),
            "missing_pct": missing_pct,
            "numeric_pct": numeric_pct,
            "outliers": outliers,
            "unique_values": int(col_series.nunique(dropna=True)),
        }
        column_profile.append(profile)

        if missing_pct > 20:
            flags.append(f"Column '{col}' has {missing_pct}% missing values")
            checks.append({
                "name": f"missing_{col}",
                "status": "warn" if missing_pct < 50 else "fail",
                "message": f"{missing_pct}% missing in '{col}'",
            })
        if outliers > 0 and numeric_pct > 80:
            flags.append(f"Column '{col}' has {outliers} statistical outliers")
            checks.append({
                "name": f"outliers_{col}",
                "status": "warn",
                "message": f"{outliers} IQR outliers in '{col}'",
            })

    fail_count = sum(1 for c in checks if c["status"] == "fail")
    warn_count = sum(1 for c in checks if c["status"] == "warn")
    if fail_count:
        status = "fail"
        score = max(0.0, 0.5 - fail_count * 0.15)
    elif warn_count:
        status = "warn"
        score = max(0.5, 0.85 - warn_count * 0.05)
    else:
        status = "pass"
        score = 0.95

    return {
        "status": status,
        "score": round(score, 2),
        "row_count": row_count,
        "column_count": col_count,
        "checks": checks,
        "flags": flags,
        "column_profile": column_profile,
        "assay_columns": assay_cols,
        "summary": (
            f"QC {status.upper()}: {row_count} rows, {col_count} columns, "
            f"{fail_count} failures, {warn_count} warnings"
        ),
    }
