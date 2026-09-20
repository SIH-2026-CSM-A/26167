"""SQLAlchemy model for the query_history table.

A separate DeclarativeBase from app.db.models.Base and app.auth.models.Base: app.history
cannot import either (leaf modules never import each other), so it owns its own Base.
alembic/env.py registers all three Bases' metadata for migrations/autogenerate.

`user_id` is a plain, nullable String(64) column with no `ForeignKey(...)` declared here —
matching users.id's actual type (a UUID string, not an Integer). The FK constraint to
users.id is added at the DB layer only, via the migration's own op.create_foreign_key, so
this module's Python code never imports app.auth.models.User.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base declarative class for history models."""


class QueryHistory(Base):
    """One persisted /query request+answer, scoped to the user who made it (if any)."""

    __tablename__ = "query_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    query_text: Mapped[str] = mapped_column(String, nullable=False)
    answer_text: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    modality: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
