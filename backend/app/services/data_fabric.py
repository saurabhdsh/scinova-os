"""Legacy re-export — use ingestion_pipeline instead."""

from app.services.ingestion_pipeline import (
    INGESTION_STAGES,
    run_ingestion_pipeline,
    semantic_search,
    start_ingestion,
)

__all__ = [
    "INGESTION_STAGES",
    "run_ingestion_pipeline",
    "semantic_search",
    "start_ingestion",
]
