"""SQLAlchemy DeclarativeBase models for trace and evidence persistence.

Mirrors Pydantic contracts from app.contracts.schemas.
JSONB is used for variable tool payloads and trace steps per Technical Implementation §4/§5.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

# Dialect-safe JSON type: uses JSONB on PostgreSQL, JSON on SQLite/others
JsonType = JSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    """Base declarative class for all SatQuery database models."""


class ExecutionTraceModel(Base):
    """Persisted record of an auditable pipeline execution trace."""

    __tablename__ = "execution_traces"

    trace_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, nullable=False, default=list)

    evidence: Mapped[list[EvidenceModel]] = relationship(
        "EvidenceModel",
        back_populates="trace",
        cascade="all, delete-orphan",
        order_by="EvidenceModel.created_at",
    )


class EvidenceModel(Base):
    """Persisted record of uniform tool-generated evidence."""

    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trace_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("execution_traces.trace_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    tool: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False, default=dict)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    timing: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    trace: Mapped[ExecutionTraceModel | None] = relationship(
        "ExecutionTraceModel", back_populates="evidence"
    )
