"""Parser contract. Implementations are registered by id and version."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParsedMeasurement:
    readout_key: str
    value: float
    unit: str | None
    ontology_id: str | None
    ontology_label: str | None
    unit_ontology_id: str | None
    mapping_confidence: float
    mapping_method: str
    header: str


@dataclass
class ParsedRow:
    sample_code: str
    measurements: list[ParsedMeasurement] = field(default_factory=list)
    extras: dict = field(default_factory=dict)


@dataclass
class ParseResult:
    parser_id: str
    parser_version: str
    instrument_model: str | None
    instrument_serial: str | None
    software_version: str | None
    data_class: str | None
    rows: list[ParsedRow]
    warnings: list[str] = field(default_factory=list)


class InstrumentParser:
    parser_id = ""
    version = ""
    instrument_family = ""

    def sniff(self, filename: str, content: bytes) -> bool:
        raise NotImplementedError

    def parse(self, content: bytes, filename: str) -> ParseResult:
        raise NotImplementedError


REGISTRY: dict[str, InstrumentParser] = {}


def register(parser: InstrumentParser) -> None:
    REGISTRY[parser.parser_id] = parser


def get_parser(parser_id: str) -> InstrumentParser:
    if parser_id not in REGISTRY:
        known = ", ".join(sorted(REGISTRY)) or "none"
        raise KeyError(f"Unknown parser {parser_id}. Registered: {known}")
    return REGISTRY[parser_id]


def select_parser(filename: str, content: bytes, parser_id: str | None = None) -> InstrumentParser:
    if parser_id:
        return get_parser(parser_id)
    for parser in REGISTRY.values():
        if parser.sniff(filename, content):
            return parser
    raise LookupError("No registered parser recognized this file.")
