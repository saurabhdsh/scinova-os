"""Vi-CELL XR tabular parser.

Column names follow the publicly documented Vi-CELL XR export fields used by the
Beckman instrument software and the Benchling Vi-CELL XR connector (Sample ID,
Viability, cell counts, diameter, circularity, dilution). This module does not
claim a Beckman-validated single canonical CSV schema. Numeric fixtures in this
repository are synthetic.
"""

from __future__ import annotations

import csv
import io
import re

from app.lab.errors import LabError
from app.lab.ontology import map_header
from app.lab.parsers.base import InstrumentParser, ParsedMeasurement, ParsedRow, ParseResult, register

_NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def _decode(content: bytes) -> str:
    text = content.decode("utf-8-sig")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _comments_and_table(text: str) -> tuple[dict, str]:
    meta: dict[str, str] = {}
    table_lines: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            body = stripped[1:].strip()
            if ":" in body:
                key, value = body.split(":", 1)
                meta[key.strip().lower().replace(" ", "_")] = value.strip()
            continue
        table_lines.append(line)
    return meta, "\n".join(table_lines)


def _parse_number(raw: str) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip().replace(",", "")
    if text == "":
        return None
    match = _NUMBER.search(text)
    if not match:
        return None
    return float(match.group(0))


class ViCellXrTabularParser(InstrumentParser):
    parser_id = "vicell-xr-tabular"
    version = "v1"
    instrument_family = "Vi-CELL XR"

    def sniff(self, filename: str, content: bytes) -> bool:
        try:
            text = _decode(content)
        except UnicodeDecodeError:
            return False
        meta, table = _comments_and_table(text)
        blob = f"{filename}\n{text[:1500]}".lower()
        if "vi-cell" in blob or "vicell" in blob or meta.get("schema", "").startswith("vicell-xr"):
            return "viability" in table.lower() and "sample" in table.lower()
        header = table.split("\n", 1)[0].lower() if table else ""
        return "sample" in header and "viability" in header

    def parse(self, content: bytes, filename: str) -> ParseResult:
        if not self.sniff(filename, content):
            raise LabError(
                "File is not a supported Vi-CELL XR tabular export.",
                status_code=422,
                code="parser_rejected",
                details={"parser_id": self.parser_id, "parser_version": self.version},
            )
        meta, table = _comments_and_table(_decode(content))
        reader = csv.DictReader(io.StringIO(table))
        if not reader.fieldnames:
            raise LabError("Vi-CELL file has no header row.", status_code=422, code="parser_rejected")
        column_map = []
        sample_header = None
        for header in reader.fieldnames:
            mapped = map_header(header)
            mapped["header"] = header
            column_map.append(mapped)
            if mapped["role"] == "sample_id":
                sample_header = header
        if sample_header is None:
            raise LabError("Vi-CELL file is missing a Sample ID column.", status_code=422, code="parser_rejected")
        if not any(item["readout_key"] == "viability_percent" for item in column_map):
            raise LabError("Vi-CELL file is missing a Viability column.", status_code=422, code="parser_rejected")

        rows: list[ParsedRow] = []
        warnings: list[str] = []
        for raw in reader:
            if not any((value or "").strip() for value in raw.values()):
                continue
            sample_code = (raw.get(sample_header) or "").strip()
            measurements: list[ParsedMeasurement] = []
            for item in column_map:
                if item["role"] != "measurement":
                    continue
                value = _parse_number(raw.get(item["header"]))
                if value is None:
                    continue
                measurements.append(
                    ParsedMeasurement(
                        readout_key=item["readout_key"],
                        value=value,
                        unit=item.get("unit"),
                        ontology_id=item.get("ontology_id"),
                        ontology_label=item.get("ontology_label"),
                        unit_ontology_id=item.get("unit_ontology_id"),
                        mapping_confidence=item["confidence"],
                        mapping_method=item["method"],
                        header=item["header"],
                    )
                )
            if not sample_code:
                warnings.append("Skipped a row with an empty Sample ID.")
                continue
            rows.append(ParsedRow(sample_code=sample_code, measurements=measurements, extras={"source": raw}))
        if not rows:
            raise LabError("Vi-CELL file contained no data rows.", status_code=422, code="parser_rejected")
        return ParseResult(
            parser_id=self.parser_id,
            parser_version=self.version,
            instrument_model=meta.get("instrument_model") or "Vi-CELL XR",
            instrument_serial=meta.get("instrument_serial"),
            software_version=meta.get("software_version"),
            data_class=meta.get("data_class"),
            rows=rows,
            warnings=warnings,
        )


register(ViCellXrTabularParser())
