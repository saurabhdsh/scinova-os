"""Synthetic catalog and Vi-CELL XR tabular fixtures.

Protocols and numeric rows are synthetic. They are not site-validated SOPs or live
instrument exports. Column names follow publicly documented Vi-CELL XR export fields.
"""

from __future__ import annotations

import csv
import io
from datetime import date, timedelta

PROTOCOL_CODE = "SYN-CVP-001"

EXPECTED_READOUTS = ["viability_percent", "viable_cells_per_ml", "average_diameter_um"]

SAMPLE_PANEL = [
    {
        "sample_code": f"SYN-S-00{i}",
        "cell_line": "CHO-K1",
        "cell_line_ontology": "CVCL:0214",
        "passage": 18,
        "qc_status": "pass",
        "lineage": {"parent_vial": "SYN-VIAL-014", "data_origin": "synthetic"},
    }
    for i in range(1, 6)
]

DEFAULT_PARAMETERS = {
    "seeding_density_cells_per_ml": 200000,
    "incubation_hours": 24,
    "passage_number": 18,
    "trypan_blue_percent": 0.4,
    "operator": "Alex Rivera",
    "instrument_serial": "VC-XR-2088",
    "reagent_lot": "TB-LOT-441",
}

SUCCESS_CRITERIA = [
    {
        "id": "SC-VIAB",
        "metric": "mean_viability_percent",
        "operator": ">=",
        "threshold": 85,
        "unit": "percent",
    },
    {
        "id": "SC-CV",
        "metric": "cv_percent",
        "operator": "<=",
        "threshold": 10,
        "unit": "percent",
    },
]

CURRENT_ROWS = [
    {"sample_id": "SYN-S-001", "viability": 92.1, "total_count": 1240, "viable_count": 1142, "total_ml": 1.24e6, "viable_ml": 1.142e6, "diameter": 14.8, "circularity": 0.87, "min_d": 8.1, "max_d": 24.0, "images": 50},
    {"sample_id": "SYN-S-002", "viability": 90.4, "total_count": 1188, "viable_count": 1074, "total_ml": 1.188e6, "viable_ml": 1.074e6, "diameter": 15.1, "circularity": 0.85, "min_d": 8.0, "max_d": 25.2, "images": 50},
    {"sample_id": "SYN-S-003", "viability": 89.7, "total_count": 1210, "viable_count": 1085, "total_ml": 1.21e6, "viable_ml": 1.085e6, "diameter": 14.6, "circularity": 0.86, "min_d": 7.9, "max_d": 23.4, "images": 49},
    {"sample_id": "SYN-S-004", "viability": 91.2, "total_count": 1302, "viable_count": 1187, "total_ml": 1.302e6, "viable_ml": 1.187e6, "diameter": 15.0, "circularity": 0.88, "min_d": 8.2, "max_d": 24.6, "images": 50},
    {"sample_id": "SYN-S-005", "viability": 58.0, "total_count": 980, "viable_count": 568, "total_ml": 0.98e6, "viable_ml": 0.568e6, "diameter": 16.4, "circularity": 0.74, "min_d": 7.4, "max_d": 28.1, "images": 50},
    {"sample_id": "SYN-UNMATCHED-999", "viability": 95.0, "total_count": 1100, "viable_count": 1045, "total_ml": 1.10e6, "viable_ml": 1.045e6, "diameter": 14.9, "circularity": 0.89, "min_d": 8.0, "max_d": 22.0, "images": 50},
]

CANONICAL_HEADERS = [
    "Sample ID",
    "Sample Date",
    "Cell Type",
    "Dilution Factor",
    "Total Cell Count",
    "Viable Cell Count",
    "Viability (%)",
    "Total Cells /mL",
    "Viable Cells /mL",
    "Average Diameter",
    "Average Circularity",
    "Minimum Diameter",
    "Maximum Diameter",
    "Images",
]


def _historical_viabilities(index: int) -> list[float]:
    shift = (index % 5) * 0.4
    return [round(value + shift, 1) for value in (90.0, 91.0, 92.0, 93.0)]


def historical_experiments(count: int = 12) -> list[dict]:
    rows = []
    for index in range(count):
        viabilities = _historical_viabilities(index)
        samples = []
        for offset, viability in enumerate(viabilities, start=1):
            samples.append(
                {
                    "sample_id": f"HIST-{index + 1:02d}-S{offset}",
                    "viability": viability,
                    "total_count": 1200,
                    "viable_count": int(round(1200 * viability / 100)),
                    "total_ml": 1.2e6,
                    "viable_ml": round(1.2e6 * viability / 100, 1),
                    "diameter": 15.0,
                    "circularity": 0.86,
                    "min_d": 8.0,
                    "max_d": 24.0,
                    "images": 50,
                    "cell_line": "CHO-K1",
                    "passage": 12,
                }
            )
        rows.append({"index": index + 1, "samples": samples})
    return rows


def render_vicell_csv(rows: list[dict], *, serial: str, headers: list[str] | None = None, extra_note: str = "") -> bytes:
    chosen = headers or CANONICAL_HEADERS
    meta = [
        "# data_class: SYNTHETIC",
        "# instrument_model: Vi-CELL XR",
        f"# instrument_serial: {serial}",
        "# software_version: 2.04",
        "# schema: vicell-xr-tabular-v1",
        "# note: Synthetic numeric values. Headers follow publicly documented Vi-CELL XR export fields. Not a Beckman-validated fixture.",
    ]
    if extra_note:
        meta.append(f"# {extra_note}")
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=chosen, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(_project_row(row, chosen))
    return ("\n".join(meta) + "\n" + buffer.getvalue()).encode("utf-8")


def _project_row(row: dict, headers: list[str]) -> dict:
    values = {
        "Sample ID": row["sample_id"],
        "Sample identifier": row["sample_id"],
        "Sample Date": "2026-03-01",
        "Cell Type": row.get("cell_line", "CHO-K1"),
        "Dilution Factor": "1",
        "Total Cell Count": row["total_count"],
        "Total cell count": row["total_count"],
        "Viable Cell Count": row["viable_count"],
        "Viability (%)": row["viability"],
        "Viability %": row["viability"],
        "Total Cells /mL": row["total_ml"],
        "Viable Cells /mL": row["viable_ml"],
        "Viable cells /mL": row["viable_ml"],
        "Average Diameter": row["diameter"],
        "Average total cell diameter μm": row["diameter"],
        "Average Circularity": row["circularity"],
        "Minimum Diameter": row["min_d"],
        "Maximum Diameter": row["max_d"],
        "Images": row["images"],
        "Notes": "synthetic",
    }
    return {header: values.get(header, "") for header in headers}


def current_csv(serial: str = "VC-XR-1042") -> bytes:
    return render_vicell_csv(CURRENT_ROWS, serial=serial)


def partial_csv() -> bytes:
    """Drops SYN-S-005 so completeness is below 100 percent. Still synthetic."""
    rows = [row for row in CURRENT_ROWS if row["sample_id"] != "SYN-S-005"]
    return render_vicell_csv(rows, serial="VC-XR-1042", extra_note="partial synthetic fixture")


def supported_parser_files() -> list[tuple[str, bytes]]:
    """Twenty supported Vi-CELL XR tabular files. Every one is synthetic."""
    files: list[tuple[str, bytes]] = []
    files.append(("vicell_current.csv", current_csv()))
    alias_headers = [
        "Sample identifier",
        "Viability %",
        "Total cell count",
        "Viable cells /mL",
        "Average total cell diameter μm",
    ]
    files.append(("vicell_alias_headers.csv", render_vicell_csv(CURRENT_ROWS[:2], serial="VC-XR-1042", headers=alias_headers)))
    bom = b"\xef\xbb\xbf" + current_csv()
    files.append(("vicell_bom.csv", bom))
    extra_headers = CANONICAL_HEADERS + ["Notes"]
    files.append(("vicell_extra_column.csv", render_vicell_csv(CURRENT_ROWS[:1], serial="VC-XR-1042", headers=extra_headers)))
    quoted = render_vicell_csv(CURRENT_ROWS[:1], serial="VC-XR-1042")
    files.append(("vicell_quoted.csv", quoted.replace(b"SYN-S-001", b'"SYN-S-001"')))
    for spec in historical_experiments(12):
        files.append(
            (
                f"vicell_hist_{spec['index']:02d}.csv",
                render_vicell_csv(spec["samples"], serial="VC-XR-1042"),
            )
        )
    # 5 explicit + 12 historical = 17. Add three more controlled variants.
    files.append(("vicell_single_sample.csv", render_vicell_csv(CURRENT_ROWS[:1], serial="VC-XR-2088")))
    files.append(("vicell_partial.csv", partial_csv()))
    lowercase = current_csv().replace(b"Sample ID", b"sample id").replace(b"Viability (%)", b"viability (%)")
    files.append(("vicell_lowercase.csv", lowercase))
    assert len(files) == 20, len(files)
    return files


def protocol_definitions(today: date | None = None) -> list[dict]:
    today = today or date.today()
    sop_common = (
        "SYNTHETIC TRAINING TEXT. This is not an approved laboratory standard. "
        "It exists so the demo can index a protocol, cite a section, and plan an experiment."
    )
    return [
        {
            "code": "SYN-CVP-001",
            "title": "Synthetic cell viability by trypan blue exclusion on Vi-CELL XR",
            "version": "1.2",
            "version_number": 2,
            "summary": "Synthetic CHO-K1 viability protocol used for the lab demo.",
            "parameters": DEFAULT_PARAMETERS,
            "criteria": SUCCESS_CRITERIA,
            "samples": SAMPLE_PANEL,
            "sections": [
                ("1. Purpose", f"{sop_common} Purpose: measure CHO-K1 viability after 24 hours.", "SYN-CVP-001 §1"),
                ("4.2 Readout", "Record viability percent, viable cells per mL, and average diameter from the Vi-CELL XR trypan blue exclusion export.", "SYN-CVP-001 §4.2"),
                ("6. Success", "Mean viability must be at least 85 percent and the coefficient of variation must be at most 10 percent.", "SYN-CVP-001 §6"),
            ],
        },
        {
            "code": "SYN-CVP-002",
            "title": "Synthetic seeding-density viability screen",
            "version": "1.0",
            "version_number": 1,
            "summary": "Synthetic screen that starts from a lower seeding density.",
            "parameters": {**DEFAULT_PARAMETERS, "seeding_density_cells_per_ml": 150000, "instrument_serial": "VC-XR-1042", "operator": "Priya Nair", "reagent_lot": "TB-LOT-778"},
            "criteria": SUCCESS_CRITERIA,
            "samples": SAMPLE_PANEL[:3],
            "sections": [
                ("1. Purpose", f"{sop_common} Compare viability across a lower seeding density.", "SYN-CVP-002 §1"),
            ],
        },
        {
            "code": "SYN-CVP-003",
            "title": "Synthetic post-thaw recovery viability",
            "version": "2.0",
            "version_number": 2,
            "summary": "Synthetic post-thaw recovery check.",
            "parameters": {**DEFAULT_PARAMETERS, "incubation_hours": 4, "passage_number": 8, "instrument_serial": "VC-XR-1042", "operator": "Priya Nair", "reagent_lot": "TB-LOT-778"},
            "criteria": SUCCESS_CRITERIA,
            "samples": SAMPLE_PANEL[:2],
            "sections": [
                ("1. Purpose", f"{sop_common} Measure viability four hours after thaw.", "SYN-CVP-003 §1"),
            ],
        },
    ]


def lot_dates(today: date | None = None) -> dict:
    today = today or date.today()
    return {
        "near_expiry": today + timedelta(days=7),
        "alternative": today + timedelta(days=400),
        "calibration_overdue": today - timedelta(days=3),
        "calibration_current": today + timedelta(days=180),
    }
