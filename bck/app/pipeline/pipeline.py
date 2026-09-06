"""Orchestrates the five pipeline stages, in order, for one request.

Every stage called here is currently a stub (see stages.py); this function's shape — the
order, the trace it builds — is what stays fixed as each stub is swapped for its real module.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.contracts import Answer, ExecutionTrace, QueryRequest
from app.pipeline.stages import (
    new_trace_step,
    stub_evidence,
    stub_ingestion,
    stub_router,
    stub_tool,
    stub_verification,
)


def run(request: QueryRequest) -> Answer:
    steps = []

    started = datetime.now(UTC)
    images = stub_ingestion(request.images)
    steps.append(new_trace_step("ingestion", "stub_ingestion", started))

    started = datetime.now(UTC)
    intent = stub_router(request.query, images)
    steps.append(new_trace_step("router", "stub_router", started, params={"intent": intent}))

    started = datetime.now(UTC)
    evidence_items = stub_tool(intent, request.query, images)
    steps.append(
        new_trace_step(
            "tool",
            "stub_tool",
            started,
            confidence=min(item.confidence for item in evidence_items),
            evidence_ids=[item.id for item in evidence_items],
        )
    )

    started = datetime.now(UTC)
    verified_evidence, abstained, abstention_reason = stub_verification(evidence_items)
    steps.append(
        new_trace_step(
            "verification",
            "stub_verification",
            started,
            params={"abstained": abstained},
            evidence_ids=[item.id for item in verified_evidence],
        )
    )

    trace = ExecutionTrace(trace_id=str(uuid.uuid4()), steps=steps, created_at=datetime.now(UTC))

    return stub_evidence(request.query, verified_evidence, abstained, abstention_reason, trace)
