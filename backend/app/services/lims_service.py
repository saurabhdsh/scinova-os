"""LIMS connector — fetch assay plates and ingest into Data Fabric."""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models.db_models import AuditEvent, DataSource, Document
from app.services.task_queue import enqueue_ingestion
from app.services.ingestion_pipeline import start_ingestion

logger = logging.getLogger(__name__)

# Demo plates when no external LIMS is configured
DEMO_PLATES = [
    {
        "plate_id": "PLT-2025-041",
        "assay": "JAK1 biochemical IC50",
        "wells": 96,
        "status": "completed",
        "project_code": "RA-JAK1",
    },
    {
        "plate_id": "PLT-2025-038",
        "assay": "hERG patch clamp",
        "wells": 48,
        "status": "qc_review",
        "project_code": "SN-2847",
    },
    {
        "plate_id": "PLT-2025-033",
        "assay": "Cell viability MTT",
        "wells": 384,
        "status": "completed",
        "project_code": "LC-891",
    },
]


def _fetch_remote_plates() -> list[dict] | None:
    if not settings.lims_api_url:
        return None
    headers = {}
    if settings.lims_api_key:
        headers["Authorization"] = f"Bearer {settings.lims_api_key}"
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(f"{settings.lims_api_url.rstrip('/')}/plates", headers=headers)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
            return data.get("plates") or data.get("results") or []
    except Exception as exc:
        logger.warning("LIMS API fetch failed: %s", exc)
        return None


def list_lims_plates(db: Session) -> dict:
    remote = _fetch_remote_plates()
    source = db.query(DataSource).filter(DataSource.source_type == "lims_export").first()
    return {
        "connector": "lims",
        "mode": "api" if settings.lims_api_url else "demo",
        "api_url": settings.lims_api_url or None,
        "data_source": source.name if source else "LIMS Bridge",
        "plates": remote if remote is not None else DEMO_PLATES,
    }


def _plate_to_csv(plate: dict) -> bytes:
    plate_id = plate.get("plate_id") or plate.get("id") or "PLATE"
    assay = plate.get("assay") or plate.get("assay_name") or "assay"
    wells = int(plate.get("wells") or 96)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["well", "sample_id", "compound_id", "concentration_uM", "response", "assay", "plate_id"])
    for i in range(min(wells, 96)):
        row = i // 12
        col = i % 12
        well = f"{chr(65 + row)}{col + 1}"
        writer.writerow([
            well,
            f"SMP-{plate_id}-{i + 1:03d}",
            f"CMP-{1000 + i}",
            round(0.001 * (10 ** (i % 5)), 4),
            round(0.55 + (i % 7) * 0.05, 3),
            assay,
            plate_id,
        ])
    return buf.getvalue().encode("utf-8")


def sync_lims_plate(
    db: Session,
    *,
    user_id: str,
    plate_id: str,
    project_id: str | None = None,
) -> dict:
    catalog = list_lims_plates(db)
    plate = next((p for p in catalog["plates"] if (p.get("plate_id") or p.get("id")) == plate_id), None)
    if not plate:
        raise ValueError(f"Plate '{plate_id}' not found")

    if settings.lims_api_url:
        try:
            headers = {"Authorization": f"Bearer {settings.lims_api_key}"} if settings.lims_api_key else {}
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(
                    f"{settings.lims_api_url.rstrip('/')}/plates/{plate_id}/results",
                    headers=headers,
                )
                resp.raise_for_status()
                content = resp.content
                filename = f"lims_{plate_id}.csv"
        except Exception as exc:
            raise ValueError(f"LIMS fetch failed: {exc}") from exc
    else:
        content = _plate_to_csv(plate)
        filename = f"lims_{plate_id}.csv"

    job = start_ingestion(
        db,
        filename,
        content,
        source_type="lims_export",
        user_id=user_id,
        project_id=project_id,
    )
    if project_id and job.document_id:
        doc = db.query(Document).filter(Document.id == job.document_id).first()
        if doc:
            doc.metadata_json = {
                **(doc.metadata_json or {}),
                "lims_plate_id": plate_id,
                "lims_assay": plate.get("assay"),
                "imported_at": datetime.utcnow().isoformat(),
            }
            db.commit()

    enqueue_ingestion(job.id)

    db.add(AuditEvent(
        event_type="lims_sync",
        actor=user_id,
        resource_type="document",
        resource_id=job.document_id,
        action=f"LIMS plate {plate_id} imported",
        details_json={"plate_id": plate_id, "project_id": project_id},
    ))
    db.commit()

    return {
        "plate_id": plate_id,
        "job_id": job.id,
        "document_id": job.document_id,
        "status": "ingestion_started",
    }
