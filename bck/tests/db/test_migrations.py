"""Regression tests for the JASH-004 Alembic migration chain."""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from alembic.config import Config

from alembic import command
from app.core.config import get_settings


def test_upgrade_repairs_existing_nullable_evidence_trace_id(monkeypatch) -> None:
    """The migration chain upgrades deployed evidence.trace_id columns to NOT NULL."""
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://satquery:satquery_local_dev@127.0.0.1:5432/satquery",
    )
    monkeypatch.setenv("COST_CEILING", "1")
    get_settings.cache_clear()
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    sql_output = StringIO()

    try:
        with redirect_stdout(sql_output):
            command.upgrade(config, "head", sql=True)
    finally:
        get_settings.cache_clear()

    assert "ALTER TABLE evidence ALTER COLUMN trace_id SET NOT NULL" in sql_output.getvalue()
