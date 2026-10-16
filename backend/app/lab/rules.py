"""Documented scientific rules. Thresholds live here; an empty override table is the configuration hook."""

from __future__ import annotations

# Build-later NFR-08: load_rules() will prefer lab_rule_overrides when rows exist.
RULES = {
    "LAB-RULE-VIAB-ABS": {
        "id": "LAB-RULE-VIAB-ABS",
        "description": "Flag a viability measurement below 70 percent as low viability.",
        "metric": "viability_percent",
        "operator": "<",
        "threshold": 70.0,
        "unit": "percent",
    },
    "LAB-RULE-VIAB-HIST": {
        "id": "LAB-RULE-VIAB-HIST",
        "description": "Flag experiment mean viability below the historical mean minus two sample standard deviations when at least five comparable experiments exist.",
        "metric": "mean_viability_percent",
        "operator": "<",
        "threshold_expr": "historical_mean - 2 * historical_sd",
        "min_comparators": 5,
        "unit": "percent",
    },
    "LAB-RULE-CV-001": {
        "id": "LAB-RULE-CV-001",
        "description": "Flag a coefficient of variation above the plan criterion, defaulting to 10 percent when the plan has no CV criterion.",
        "metric": "cv_percent",
        "operator": ">",
        "threshold": 10.0,
        "unit": "percent",
    },
    "LAB-RULE-NEXT-001": {
        "id": "LAB-RULE-NEXT-001",
        "description": (
            "When mean viability is below the plan success threshold, increase seeding density "
            "by 20 percent of the planned value and hold every other planned parameter constant."
        ),
        "parameter": "seeding_density_cells_per_ml",
        "operation": "multiply",
        "factor": 1.2,
        "requires_insight_rules": ["LAB-RULE-VIAB-ABS", "LAB-RULE-VIAB-HIST"],
    },
}

NARRATIVE_PROMPT_ID = "dossier-narrative-v1"
NARRATIVE_MODEL_VERSION = "deterministic-template-v1"
NARRATIVE_PROMPT = (
    "State only the calculated result values, criterion outcomes, and insight rule identifiers "
    "supplied in the context. Cite each result and measurement id. Do not invent numbers. "
    "Label the text as machine-generated and unapproved."
)


def load_rules(db=None) -> dict:
    """Return code rules, replaced per id when an active lab_rule_overrides row exists."""
    rules = {k: dict(v) for k, v in RULES.items()}
    if db is None:
        return rules
    from app.lab.models import LabRuleOverride

    rows = db.query(LabRuleOverride).filter(LabRuleOverride.active.is_(True)).all()
    for row in rows:
        base = rules.get(row.rule_id, {"id": row.rule_id})
        merged = dict(base)
        merged.update(row.config_json or {})
        merged["id"] = row.rule_id
        merged["override"] = True
        rules[row.rule_id] = merged
    return rules
