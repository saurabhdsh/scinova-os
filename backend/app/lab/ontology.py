"""Public ontology terms used for Vi-CELL readout mapping.

Identifiers below were checked against public sources:
- UO:0000187 percent, UO:0000017 micrometer (Unit Ontology)
- NCIT:C139278 Sample Viability Percent Measurement
- NCIT:C48938 Cell Count
- NCIT:C130166 Viable Cell Count
- Cellosaurus CVCL_0214 CHO-K1

Readouts without a confirmed public identifier are mapped with a null ontology id
and a lower confidence. They are not assigned invented codes.
"""

from __future__ import annotations

TERMS = [
    {
        "id": "NCIT:C139278",
        "label": "Sample Viability Percent Measurement",
        "ontology": "NCIT",
        "definition": "A measurement of the percent of a cell or tissue sample that is viable.",
        "synonyms": ["viability", "viability percent", "cell viability"],
    },
    {
        "id": "NCIT:C48938",
        "label": "Cell Count",
        "ontology": "NCIT",
        "definition": "A measurement of the total nucleated cells in a biological specimen.",
        "synonyms": ["total cell count", "cell count"],
    },
    {
        "id": "NCIT:C130166",
        "label": "Viable Cell Count",
        "ontology": "NCIT",
        "definition": "The determination of the number of viable cells in a sample.",
        "synonyms": ["viable cell count", "viable cells"],
    },
    {
        "id": "UO:0000187",
        "label": "percent",
        "ontology": "UO",
        "definition": "A dimensionless ratio unit which denotes numbers as fractions of 100.",
        "synonyms": ["%", "percent"],
    },
    {
        "id": "UO:0000017",
        "label": "micrometer",
        "ontology": "UO",
        "definition": "A length unit which is equal to one millionth of a meter.",
        "synonyms": ["um", "micrometre", "micron"],
    },
    {
        "id": "CVCL:0214",
        "label": "CHO-K1",
        "ontology": "Cellosaurus",
        "definition": "Cellosaurus CVCL_0214 CHO-K1.",
        "synonyms": ["cho-k1", "cvcl_0214"],
    },
]

# Header aliases -> readout. ontology_id is null when no public id was confirmed.
READOUTS = {
    "viability_percent": {
        "ontology_id": "NCIT:C139278",
        "ontology_label": "Sample Viability Percent Measurement",
        "unit": "percent",
        "unit_ontology_id": "UO:0000187",
        "aliases": ["viability", "viability (%)", "viability %", "viability percent"],
    },
    "total_cell_count": {
        "ontology_id": "NCIT:C48938",
        "ontology_label": "Cell Count",
        "unit": "count",
        "unit_ontology_id": None,
        "aliases": ["total cell count", "total cells", "cell count"],
    },
    "viable_cell_count": {
        "ontology_id": "NCIT:C130166",
        "ontology_label": "Viable Cell Count",
        "unit": "count",
        "unit_ontology_id": None,
        "aliases": ["viable cell count", "viable cells"],
    },
    "viable_cells_per_ml": {
        "ontology_id": None,
        "ontology_label": "Viable cell density",
        "unit": "cells/mL",
        "unit_ontology_id": None,
        "aliases": [
            "viable cells /ml",
            "viable cells/ml",
            "viable cell density",
            "viable cells / ml",
        ],
        "unconfirmed_reason": "No public ontology id was confirmed for viable cell density.",
    },
    "total_cells_per_ml": {
        "ontology_id": None,
        "ontology_label": "Total cell density",
        "unit": "cells/mL",
        "unit_ontology_id": None,
        "aliases": ["total cells /ml", "total cells/ml", "total cell density", "total cells / ml"],
        "unconfirmed_reason": "No public ontology id was confirmed for total cell density.",
    },
    "average_diameter_um": {
        "ontology_id": None,
        "ontology_label": "Average cell diameter",
        "unit": "micrometer",
        "unit_ontology_id": "UO:0000017",
        "aliases": [
            "average diameter",
            "avg diameter",
            "avg. diam.",
            "average total cell diameter",
            "average total cell diameter um",
        ],
        "unconfirmed_reason": "Unit is UO:0000017. No public measurand id was confirmed for average diameter.",
    },
    "average_circularity": {
        "ontology_id": None,
        "ontology_label": "Average cell circularity",
        "unit": "dimensionless",
        "unit_ontology_id": None,
        "aliases": ["average circularity", "avg circularity", "average total cell circularity"],
        "unconfirmed_reason": "No public ontology id was confirmed for circularity.",
    },
    "minimum_diameter_um": {
        "ontology_id": None,
        "ontology_label": "Minimum cell diameter",
        "unit": "micrometer",
        "unit_ontology_id": "UO:0000017",
        "aliases": ["minimum diameter", "min diameter", "minimum cell diameter", "minimum cell diameter um"],
    },
    "maximum_diameter_um": {
        "ontology_id": None,
        "ontology_label": "Maximum cell diameter",
        "unit": "micrometer",
        "unit_ontology_id": "UO:0000017",
        "aliases": ["maximum diameter", "max diameter", "maximum cell diameter", "maximum cell diameter um"],
    },
    "dilution_factor": {
        "ontology_id": None,
        "ontology_label": "Dilution factor",
        "unit": "dimensionless",
        "unit_ontology_id": None,
        "aliases": ["dilution factor", "dilution", "cell density dilution factor"],
    },
    "images": {
        "ontology_id": None,
        "ontology_label": "Image count",
        "unit": "count",
        "unit_ontology_id": None,
        "aliases": ["images", "image count"],
    },
}

SAMPLE_ALIASES = ["sample id", "sample identifier", "sampleid"]


def _norm(text: str) -> str:
    value = (text or "").replace("\ufeff", "").strip().lower()
    value = value.replace("μ", "u").replace("µ", "u")
    value = " ".join(value.split())
    return value


def lookup(query: str, limit: int = 10) -> list[dict]:
    q = _norm(query)
    if not q:
        return []
    hits = []
    for term in TERMS:
        hay = " ".join([term["id"], term["label"], term["definition"], *term["synonyms"]]).lower()
        if q in hay or any(q in _norm(s) or _norm(s) in q for s in term["synonyms"]):
            hits.append({**term, "match": "synonym" if q not in term["id"].lower() else "id"})
    return hits[:limit]


def map_header(header: str) -> dict:
    """Map one instrument column to a readout. Confidence reflects match quality and ontology certainty."""
    normalized = _norm(header)
    if normalized in SAMPLE_ALIASES or normalized.replace(" ", "") in {"sampleid", "sampleidentifier"}:
        return {
            "role": "sample_id",
            "readout_key": None,
            "confidence": 0.99,
            "method": "exact_alias",
            "ontology_id": None,
            "ontology_label": "Sample identifier",
        }
    for key, spec in READOUTS.items():
        aliases = {_norm(a) for a in spec["aliases"]}
        if normalized in aliases:
            confirmed = bool(spec.get("ontology_id"))
            confidence = 0.97 if confirmed else 0.8
            return {
                "role": "measurement",
                "readout_key": key,
                "confidence": confidence,
                "method": "exact_alias",
                "ontology_id": spec.get("ontology_id"),
                "ontology_label": spec.get("ontology_label"),
                "unit": spec.get("unit"),
                "unit_ontology_id": spec.get("unit_ontology_id"),
                "unconfirmed_reason": spec.get("unconfirmed_reason"),
            }
    return {
        "role": "ignored",
        "readout_key": None,
        "confidence": 0.0,
        "method": "unmapped",
        "ontology_id": None,
        "ontology_label": None,
        "header": header,
    }


def map_headers(headers: list[str]) -> list[dict]:
    mapped = []
    for header in headers:
        item = map_header(header)
        item["header"] = header
        mapped.append(item)
    return mapped
