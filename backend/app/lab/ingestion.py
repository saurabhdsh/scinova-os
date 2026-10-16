"""FR-DC ingestion. Raw bytes are written once, then parsed and published."""

from __future__ import annotations

import app.lab.parsers  # noqa: F401  (registers Vi-CELL parser)
from sqlalchemy.orm import Session

from app.lab.adapters import data_lake, landing_zone
from app.lab.audit import record
from app.lab.errors import LabError
from app.lab.graph_bridge import link, publish
from app.lab.models import (
    LabDataQualityFlag,
    LabExperiment,
    LabInstrument,
    LabMeasurement,
    LabRawDataFile,
    LabReadinessIssue,
    LabRun,
    LabSample,
)
from app.lab.parsers.base import select_parser


def ingest_bytes(
    db: Session,
    *,
    content: bytes,
    filename: str,
    experiment_id: str,
    actor: str,
    enforce_readiness: bool = True,
    parser_id: str | None = None,
) -> dict:
    experiment = db.get(LabExperiment, experiment_id)
    if experiment is None:
        raise LabError("Experiment not found.", status_code=404, code="not_found")
    if experiment.status == "planned" and enforce_readiness:
        raise LabError(
            "Readiness has not been evaluated for this experiment.",
            status_code=409,
            code="readiness_required",
        )
    if enforce_readiness:
        blocking = (
            db.query(LabReadinessIssue)
            .filter(
                LabReadinessIssue.experiment_id == experiment_id,
                LabReadinessIssue.status == "open",
                LabReadinessIssue.severity == "blocking",
            )
            .count()
        )
        if blocking:
            raise LabError(
                "Open blocking readiness issues must be resolved before ingestion.",
                status_code=409,
                code="readiness_blocked",
                details={"open_blocking": blocking},
            )
    run = (
        db.query(LabRun)
        .filter(LabRun.experiment_id == experiment_id)
        .order_by(LabRun.created_at.asc())
        .first()
    )
    if run is None:
        raise LabError("Experiment has no run.", status_code=409, code="run_missing")

    zone = landing_zone()
    stored = zone.put_immutable(filename, content)
    if not zone.verify(stored.uri, stored.sha256):
        raise LabError("Checksum verification failed.", status_code=500, code="checksum_failed")

    existing = (
        db.query(LabRawDataFile)
        .filter(LabRawDataFile.sha256 == stored.sha256, LabRawDataFile.experiment_id == experiment_id)
        .first()
    )
    record(
        db,
        event_type="raw_ingested",
        actor=actor,
        resource_type="raw_data_file",
        resource_id=existing.id if existing else stored.sha256,
        action="Ingested raw instrument file into the immutable landing zone",
        details={
            "sha256": stored.sha256,
            "filename": filename,
            "landing_mode": stored.mode,
            "landing_external": stored.external,
            "simulation": stored.simulation,
            "experiment_id": experiment_id,
            "idempotent": existing is not None,
        },
    )
    if existing:
        db.flush()
        return _summary(db, existing, idempotent=True)

    try:
        parser = select_parser(filename, content, parser_id)
    except (LookupError, KeyError) as exc:
        raise LabError(str(exc), status_code=422, code="parser_rejected") from exc
    parsed = parser.parse(content, filename)
    record(
        db,
        event_type="parsed",
        actor=actor,
        resource_type="experiment",
        resource_id=experiment_id,
        action=f"Parsed instrument file with {parsed.parser_id} {parsed.parser_version}",
        details={
            "parser_id": parsed.parser_id,
            "parser_version": parsed.parser_version,
            "row_count": len(parsed.rows),
            "sha256": stored.sha256,
        },
    )

    instrument = db.get(LabInstrument, run.instrument_id) if run.instrument_id else None
    raw = LabRawDataFile(
        experiment_id=experiment_id,
        run_id=run.id,
        instrument_id=run.instrument_id,
        sha256=stored.sha256,
        byte_size=stored.byte_size,
        filename=filename,
        landing_uri=stored.uri,
        landing_mode=stored.mode,
        landing_external=stored.external,
        parser_id=parsed.parser_id,
        parser_version=parsed.parser_version,
        instrument_serial_observed=parsed.instrument_serial,
        checksum_verified=True,
        data_origin="synthetic" if (parsed.data_class or "").upper() == "SYNTHETIC" else "unspecified",
        created_by=actor,
    )
    db.add(raw)
    db.flush()

    samples = db.query(LabSample).filter(LabSample.experiment_id == experiment_id).all()
    by_code = {sample.sample_code: sample for sample in samples}
    flags = []
    unmatched_codes = set()
    measurements = []
    for row in parsed.rows:
        sample = by_code.get(row.sample_code)
        if sample is None:
            unmatched_codes.add(row.sample_code)
        for item in row.measurements:
            measurement = LabMeasurement(
                experiment_id=experiment_id,
                run_id=run.id,
                sample_id=sample.id if sample else None,
                raw_file_id=raw.id,
                readout_key=item.readout_key,
                value=item.value,
                unit=item.unit,
                ontology_id=item.ontology_id,
                ontology_label=item.ontology_label,
                unit_ontology_id=item.unit_ontology_id,
                mapping_confidence=item.mapping_confidence,
                mapping_method=item.mapping_method,
                sample_code_observed=row.sample_code,
                produced_by="LAB-A6",
                data_origin=raw.data_origin,
                raw_row_json={"header": item.header, "sample_code": row.sample_code},
                created_by=actor,
            )
            db.add(measurement)
            measurements.append(measurement)
    db.flush()

    for code in sorted(unmatched_codes):
        flag = LabDataQualityFlag(
            experiment_id=experiment_id,
            run_id=run.id,
            raw_file_id=raw.id,
            code="UNMATCHED_SAMPLE",
            message=f"Sample identifier {code} did not match a sample on the experiment.",
            sample_code=code,
            created_by=actor,
        )
        db.add(flag)
        flags.append(flag)
    if instrument and parsed.instrument_serial and parsed.instrument_serial != instrument.serial_number:
        flag = LabDataQualityFlag(
            experiment_id=experiment_id,
            run_id=run.id,
            raw_file_id=raw.id,
            code="INSTRUMENT_MISMATCH",
            message=(
                f"File serial {parsed.instrument_serial} does not match scheduled instrument {instrument.serial_number}."
            ),
            created_by=actor,
        )
        db.add(flag)
        flags.append(flag)
    db.flush()
    for flag in flags:
        record(
            db,
            event_type="quality_flag",
            actor=actor,
            resource_type="data_quality_flag",
            resource_id=flag.id,
            action=f"Raised {flag.code}",
            details={"code": flag.code, "sample_code": flag.sample_code, "run_id": run.id, "experiment_id": experiment_id},
        )

    completeness = _completeness(db, run, samples)
    run.completeness_percent = completeness
    run.status = "ingested"
    record(
        db,
        event_type="completeness_recorded",
        actor=actor,
        resource_type="run",
        resource_id=run.id,
        action="Recorded run completeness",
        details={"completeness_percent": completeness, "experiment_id": experiment_id},
    )

    dataset = {
        "data_origin": raw.data_origin,
        "experiment_id": experiment_id,
        "run_id": run.id,
        "raw_file_id": raw.id,
        "sha256": raw.sha256,
        "parser": {"id": parsed.parser_id, "version": parsed.parser_version},
        "completeness_percent": completeness,
        "measurements": [
            {
                "id": item.id,
                "sample_id": item.sample_id,
                "sample_code": item.sample_code_observed,
                "readout_key": item.readout_key,
                "value": item.value,
                "unit": item.unit,
                "ontology_id": item.ontology_id,
                "mapping_confidence": item.mapping_confidence,
            }
            for item in measurements
        ],
    }
    lake_ref = data_lake().write_harmonized(experiment_id, run.id, dataset)
    _publish_graph(db, experiment, run, instrument, samples, raw, measurements, flags)
    record(
        db,
        event_type="fabric_published",
        actor=actor,
        resource_type="raw_data_file",
        resource_id=raw.id,
        action="Published harmonized measurements to the lab fabric and data lake",
        details={"lake": lake_ref, "measurement_count": len(measurements), "experiment_id": experiment_id},
    )
    if experiment.status in {"ready_for_ingestion", "data_captured", "planned"}:
        experiment.status = "data_captured"
    db.flush()
    summary = _summary(db, raw, idempotent=False)
    summary["lake"] = lake_ref
    summary["completeness_percent"] = completeness
    summary["quality_flags"] = [{"id": flag.id, "code": flag.code, "sample_code": flag.sample_code} for flag in flags]
    summary["measurement_ids"] = [item.id for item in measurements]
    return summary


def correct_measurement(db: Session, measurement_id: str, value: float, reason: str, actor: str) -> LabMeasurement:
    old = db.get(LabMeasurement, measurement_id)
    if old is None:
        raise LabError("Measurement not found.", status_code=404, code="not_found")
    if old.status != "active":
        raise LabError("Only the active measurement version can be corrected.", status_code=409, code="not_active")
    raw = db.get(LabRawDataFile, old.raw_file_id)
    before = raw.sha256 if raw else None
    revised = LabMeasurement(
        version=old.version + 1,
        status="active",
        supersedes_id=old.id,
        experiment_id=old.experiment_id,
        run_id=old.run_id,
        sample_id=old.sample_id,
        raw_file_id=old.raw_file_id,
        readout_key=old.readout_key,
        value=float(value),
        unit=old.unit,
        ontology_id=old.ontology_id,
        ontology_label=old.ontology_label,
        unit_ontology_id=old.unit_ontology_id,
        mapping_confidence=old.mapping_confidence,
        mapping_method="scientist_correction",
        sample_code_observed=old.sample_code_observed,
        produced_by="LAB-A6",
        data_origin=old.data_origin,
        raw_row_json={"correction_reason": reason, "previous_value": old.value, "previous_id": old.id},
        created_by=actor,
    )
    old.status = "superseded"
    db.add(revised)
    db.flush()
    if raw is not None and raw.sha256 != before:
        raise LabError("Raw checksum changed during correction.", status_code=500, code="raw_immutable")
    record(
        db,
        event_type="correction",
        actor=actor,
        resource_type="measurement",
        resource_id=revised.id,
        action="Corrected a measurement by creating a new version",
        details={
            "previous_id": old.id,
            "previous_value": old.value,
            "value": revised.value,
            "reason": reason,
            "raw_file_id": old.raw_file_id,
            "raw_sha256": before,
            "experiment_id": old.experiment_id,
        },
    )
    return revised


def reject_raw_mutation() -> None:
    raise LabError(
        "Raw instrument data cannot be modified. Corrections create a new derived version. BR-DR-001.",
        status_code=409,
        code="raw_immutable",
    )


def _completeness(db: Session, run: LabRun, samples: list[LabSample]) -> float:
    readouts = list(run.expected_readouts_json or [])
    expected = len(samples) * len(readouts)
    if expected == 0:
        return 0.0
    matched = 0
    for sample in samples:
        for readout in readouts:
            found = (
                db.query(LabMeasurement)
                .filter(
                    LabMeasurement.run_id == run.id,
                    LabMeasurement.sample_id == sample.id,
                    LabMeasurement.readout_key == readout,
                    LabMeasurement.status == "active",
                )
                .first()
            )
            if found:
                matched += 1
    return round(100.0 * matched / expected, 2)


def _publish_graph(db, experiment, run, instrument, samples, raw, measurements, flags):
    document_id = experiment.source_document_id
    exp_node = publish(db, experiment, entity_type="Experiment", label=experiment.title, document_id=document_id)
    run_node = publish(db, run, entity_type="Run", label=run.run_code, document_id=document_id)
    link(db, exp_node, run_node, "HAS_RUN")
    raw_node = publish(
        db,
        raw,
        entity_type="RawDataFile",
        label=raw.filename,
        document_id=document_id,
        extra={"sha256": raw.sha256, "data_origin": raw.data_origin},
    )
    link(db, run_node, raw_node, "CAPTURED_FILE")
    inst_node = None
    if instrument is not None:
        inst_node = publish(db, instrument, entity_type="Instrument", label=instrument.serial_number, document_id=document_id)
        link(db, run_node, inst_node, "USES_INSTRUMENT")
    sample_nodes = {}
    for sample in samples:
        sample_nodes[sample.id] = publish(
            db,
            sample,
            entity_type="Sample",
            label=sample.sample_code,
            document_id=document_id,
            ontology_id=sample.cell_line_ontology,
        )
        link(db, exp_node, sample_nodes[sample.id], "HAS_SAMPLE")
    for measurement in measurements:
        node = publish(
            db,
            measurement,
            entity_type="Measurement",
            label=f"{measurement.sample_code_observed} {measurement.readout_key}",
            document_id=document_id,
            ontology_id=measurement.ontology_id,
            confidence=measurement.mapping_confidence or 1.0,
            extra={"value": measurement.value, "unit": measurement.unit, "data_origin": measurement.data_origin},
        )
        link(db, run_node, node, "PRODUCED_MEASUREMENT")
        link(db, node, raw_node, "DERIVED_FROM")
        if measurement.sample_id and measurement.sample_id in sample_nodes:
            link(db, node, sample_nodes[measurement.sample_id], "OF_SAMPLE")
    for flag in flags:
        flag_node = publish(db, flag, entity_type="DataQualityFlag", label=flag.code, document_id=document_id)
        link(db, run_node, flag_node, "HAS_QUALITY_FLAG")


def _summary(db: Session, raw: LabRawDataFile, *, idempotent: bool) -> dict:
    count = db.query(LabMeasurement).filter(LabMeasurement.raw_file_id == raw.id, LabMeasurement.status == "active").count()
    flags = db.query(LabDataQualityFlag).filter(LabDataQualityFlag.raw_file_id == raw.id).count()
    run = db.get(LabRun, raw.run_id)
    return {
        "raw_file_id": raw.id,
        "sha256": raw.sha256,
        "checksum_verified": raw.checksum_verified,
        "landing_uri": raw.landing_uri,
        "landing_mode": raw.landing_mode,
        "landing_external": raw.landing_external,
        "simulation": False,
        "parser_id": raw.parser_id,
        "parser_version": raw.parser_version,
        "data_origin": raw.data_origin,
        "measurement_count": count,
        "quality_flag_count": flags,
        "completeness_percent": run.completeness_percent if run else None,
        "idempotent": idempotent,
    }
