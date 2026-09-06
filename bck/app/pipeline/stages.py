"""Pipeline-owned upload, trace, and failure types for cross-module composition."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.contracts import ExecutionTrace, Modality, TraceStep


@dataclass(frozen=True, slots=True)
class PipelineUpload:
    """Raw multipart asset passed from the API without losing its bytes."""

    id: str
    filename: str
    content_type: str
    content: bytes
    modality: Modality


class PipelineError(RuntimeError):
    """Safe user-facing pipeline failure carrying the trace recorded before failure."""

    def __init__(
        self,
        *,
        message: str,
        stage: str,
        status_code: int,
        trace: ExecutionTrace,
    ) -> None:
        """Store a sanitized message, failed stage, HTTP status, and partial trace."""
        super().__init__(message)
        self.message = message
        self.stage = stage
        self.status_code = status_code
        self.trace = trace


class TraceRecorder:
    """Append actual pipeline events and serialize them through canonical trace contracts."""

    def __init__(self) -> None:
        """Create one trace identity and an empty ordered step collection."""
        self._trace_id = str(uuid.uuid4())
        self._created_at = datetime.now(UTC)
        self._steps: list[TraceStep] = []

    def record(
        self,
        module: str,
        action: str,
        *,
        params: dict[str, Any] | None = None,
        confidence: float | None = None,
        evidence_ids: list[str] | None = None,
        started_at: datetime | None = None,
    ) -> None:
        """Append one completed event containing only supplied execution facts."""
        event_started = started_at or datetime.now(UTC)
        self._steps.append(
            TraceStep(
                module=module,
                action=action,
                params=params or {},
                confidence=confidence,
                started_at=event_started,
                completed_at=datetime.now(UTC),
                evidence_ids=evidence_ids or [],
            )
        )

    def build(self) -> ExecutionTrace:
        """Return an immutable canonical snapshot of all events recorded so far."""
        return ExecutionTrace(
            trace_id=self._trace_id,
            steps=list(self._steps),
            created_at=self._created_at,
        )
