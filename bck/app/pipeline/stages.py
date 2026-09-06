"""The five pipeline stages, as a Protocol plus stub implementations.

Every stub here is a placeholder seam: real work lands as `app.ingestion`, `app.router`,
`app.tools.*`, `app.verification`, and `app.evidence` are built out, and `pipeline.py` swaps
the corresponding stub for the real module. Each stub is named `stub_<stage>` so a grep for
"stub_" finds every seam still open.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol, TypeVar

from app.contracts import (
    Answer,
    Evidence,
    EvidenceType,
    ExecutionTrace,
    ImageInput,
    TraceStep,
)

T_in = TypeVar("T_in", contravariant=True)
T_out = TypeVar("T_out", covariant=True)


class Stage(Protocol[T_in, T_out]):
    """A pipeline stage: takes one input, produces one output. No shared state between calls."""

    def __call__(self, data: T_in) -> T_out: ...


def stub_ingestion(images: list[ImageInput]) -> list[ImageInput]:
    """Placeholder for `app.ingestion` (F1-F3).

    Real ingestion validates modality/format compatibility and rejects bad input; this stub
    passes images through unchanged since there is nothing yet to validate against.
    """
    return list(images)


def stub_router(query: str, images: list[ImageInput]) -> str:
    """Placeholder for `app.router` (F9-F11).

    Real router classifies intent from query + input inventory and selects a tool from the
    fixed registry. This stub always returns the same hardcoded intent regardless of input.
    """
    del query, images
    return "vqa_grounding"


def stub_tool(intent: str, query: str, images: list[ImageInput]) -> Evidence:
    """Placeholder for `app.tools.*` / `app.models` (F4-F7).

    Real tools run the selected model/tool and return real evidence. This stub returns one
    Evidence object whose payload is explicitly marked as a stub value, but whose content
    (query text, image count/ids) reflects the actual request rather than a static fixture.
    """
    started = time.perf_counter()
    payload = {
        "stub": True,
        "note": f"stub_tool ran for intent={intent!r}",
        "query": query,
        "image_ids": [image.id for image in images],
    }
    timing = time.perf_counter() - started
    return Evidence(
        id=str(uuid.uuid4()),
        tool=intent,
        type=EvidenceType.TEXT,
        payload=payload,
        confidence=0.5,
        timing=timing,
    )


def stub_verification(
    evidence: list[Evidence],
    raw_query: str | None = None,
    images: list[ImageInput] | None = None,
) -> tuple[list[Evidence], bool, str | None]:
    """Verification stage calling app.verification.verify (F15/F16).

    Preserves backward-compatible tuple signature (verified_evidence, abstained, abstention_reason).
    """
    import importlib

    verifier_mod = importlib.import_module("app.verification")
    decision = verifier_mod.verify(evidence=evidence, raw_query=raw_query, images=images)
    return decision.as_pipeline_tuple()


def stub_evidence(
    query: str,
    evidence: list[Evidence],
    abstained: bool,
    abstention_reason: str | None,
    trace: ExecutionTrace,
) -> Answer:
    """Placeholder for `app.evidence` (F14/F23).

    Real assembly renders text + visual evidence + confidence + trace + optional PDF report.
    This stub builds a real Answer from what the prior stages actually produced: the text
    names the query and how many evidence items backed it, and confidence is the mean of the
    evidence confidences (0.0 with no evidence, matching the abstention case).
    """
    confidence = sum(item.confidence for item in evidence) / len(evidence) if evidence else 0.0
    text = (
        f"[stub] Answered {len(evidence)} evidence item(s) for query: {query!r}"
        if evidence
        else f"[stub] No evidence produced for query: {query!r}"
    )
    return Answer(
        text=text,
        evidence=evidence,
        trace=trace,
        confidence=confidence,
        abstained=abstained,
        abstention_reason=abstention_reason,
    )


def new_trace_step(
    module: str,
    action: str,
    started_at: datetime,
    params: dict[str, Any] | None = None,
    confidence: float | None = None,
    evidence_ids: list[str] | None = None,
) -> TraceStep:
    """Shared helper so pipeline.py doesn't repeat the same TraceStep construction five times."""
    return TraceStep(
        module=module,
        action=action,
        params=params or {},
        confidence=confidence,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        evidence_ids=evidence_ids or [],
    )
