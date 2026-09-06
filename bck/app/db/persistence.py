"""Trace and evidence persistence module.

Provides write-once persistence for completed execution traces and their associated evidence.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.contracts import Evidence, ExecutionTrace
from app.db.models import EvidenceModel, ExecutionTraceModel
from app.db.session import get_sync_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class TracePersistenceError(Exception):
    """Raised when writing the execution trace to persistent storage fails."""


def persist_trace(
    trace: ExecutionTrace,
    evidence: list[Evidence],
    session: Session | None = None,
) -> None:
    """Persist a completed execution trace and its associated evidence in a single transaction.

    Args:
        trace: The auditable ExecutionTrace instance built by TraceRecorder.
        evidence: The list of Evidence items produced during pipeline execution.
        session: Optional existing database session. If None, creates a new session.

    Raises:
        TracePersistenceError: If database persistence fails for any reason.
    """
    try:
        trace_model = ExecutionTraceModel(
            trace_id=trace.trace_id,
            created_at=trace.created_at,
            steps=[step.model_dump(mode="json") for step in trace.steps],
        )

        evidence_models = [
            EvidenceModel(
                id=ev.id,
                trace_id=trace.trace_id,
                tool=ev.tool,
                type=ev.type.value if hasattr(ev.type, "value") else str(ev.type),
                payload=ev.model_dump(mode="json")["payload"],
                confidence=ev.confidence,
                timing=ev.timing,
            )
            for ev in evidence
        ]

        if session is not None:
            session.add(trace_model)
            for ev_model in evidence_models:
                session.add(ev_model)
            session.flush()
        else:
            with get_sync_session() as sess:
                sess.add(trace_model)
                for ev_model in evidence_models:
                    sess.add(ev_model)
                sess.commit()
    except Exception as error:
        raise TracePersistenceError(f"Database persistence failed: {error}") from error
