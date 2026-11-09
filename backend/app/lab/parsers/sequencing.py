"""Synthetic targeted-sequencing summary parser.

The file is a lab-demo summary, not a FASTQ, BAM, or VCF export.
"""

from __future__ import annotations

import csv
import io

from app.lab.parsers.base import InstrumentParser, ParsedMeasurement, ParsedRow, ParseResult, register

_COLUMNS = {
    "mean coverage (x)": ("mean_coverage_x", "x"),
    "on-target (%)": ("on_target_percent", "percent"),
}


def _decode(content: bytes) -> str:
    return content.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")


class SequencingSummaryParser(InstrumentParser):
    parser_id = "sequencing-summary"
    version = "1.0"
    instrument_family = "targeted-sequencer"

    def sniff(self, filename: str, content: bytes) -> bool:
        text = _decode(content).lower()
        return "mean coverage" in text and "on-target" in text and "sample id" in text

    def parse(self, content: bytes, filename: str) -> ParseResult:
        meta = {}
        table_lines = []
        for line in _decode(content).split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                body = stripped[1:].strip()
                if ":" in body:
                    key, value = body.split(":", 1)
                    meta[key.strip().lower().replace(" ", "_")] = value.strip()
                continue
            table_lines.append(stripped)
        reader = csv.DictReader(io.StringIO("\n".join(table_lines)))
        rows = []
        for raw in reader:
            sample = (raw.get("Sample ID") or raw.get("sample id") or "").strip()
            if not sample:
                continue
            measurements = []
            for header, value in raw.items():
                if not header:
                    continue
                mapped = _COLUMNS.get(header.strip().lower())
                if mapped is None or value in (None, ""):
                    continue
                key, unit = mapped
                measurements.append(
                    ParsedMeasurement(
                        readout_key=key,
                        value=float(str(value).replace(",", "")),
                        unit=unit,
                        ontology_id=None,
                        ontology_label=key,
                        unit_ontology_id=None,
                        mapping_confidence=1,
                        mapping_method="sequencing_summary",
                        header=header,
                    )
                )
            if measurements:
                rows.append(ParsedRow(sample_code=sample, measurements=measurements))
        return ParseResult(
            parser_id=self.parser_id,
            parser_version=self.version,
            instrument_model="Synthetic sequencer",
            instrument_serial=meta.get("instrument_serial"),
            software_version=None,
            data_class=meta.get("data_class"),
            rows=rows,
        )


register(SequencingSummaryParser())
