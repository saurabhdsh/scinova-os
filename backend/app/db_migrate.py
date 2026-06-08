"""Lightweight schema migrations for existing databases."""

import logging

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)

_USER_ID_TABLES = (
    "documents",
    "ingestion_jobs",
    "workflow_runs",
    "agent_runs",
    "scientific_reports",
)

_PROJECT_ID_TABLES = (
    "documents",
    "ingestion_jobs",
    "workflow_runs",
    "agent_runs",
    "scientific_reports",
)

_AGENT_TASK_COLS = ("user_id",)


def _add_column_if_missing(engine, table: str, column: str, col_type: str = "VARCHAR") -> None:
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns(table)}
    if column in existing:
        return
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
    logger.info("Added column %s.%s", table, column)


def run_migrations(engine) -> None:
    for table in _USER_ID_TABLES:
        _add_column_if_missing(engine, table, "user_id")

    for table in _PROJECT_ID_TABLES:
        _add_column_if_missing(engine, table, "project_id")

    _add_column_if_missing(engine, "agent_task_settings", "user_id")

    # Assign orphan rows to first admin user
    with engine.begin() as conn:
        admin = conn.execute(text("SELECT id FROM users WHERE role = 'admin' LIMIT 1")).fetchone()
        if not admin:
            return
        admin_id = admin[0]
        for table in _USER_ID_TABLES:
            conn.execute(
                text(f"UPDATE {table} SET user_id = :uid WHERE user_id IS NULL"),
                {"uid": admin_id},
            )
        conn.execute(
            text(
                "UPDATE agent_task_settings SET user_id = :uid "
                "WHERE user_id IS NULL AND id = 'default'"
            ),
            {"uid": admin_id},
        )
