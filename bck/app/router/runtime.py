"""Minimal schema-constrained router runtime for single-image VQA."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.contracts import QueryRequest


class RouterIntent(StrEnum):
    """Closed intent subset implemented by the first vertical slice."""

    VQA = "vqa"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class RouterDecision:
    """Structured route result consumed only by the composing pipeline."""

    supported: bool
    intent: RouterIntent
    tool_name: str | None
    reason: str


def route_request(request: QueryRequest) -> RouterDecision:
    """Select InternVL VQA only for one image and a non-empty visual question."""
    if not request.query.strip():
        return RouterDecision(
            supported=False,
            intent=RouterIntent.UNSUPPORTED,
            tool_name=None,
            reason="A non-empty natural-language question is required.",
        )
    if len(request.images) != 1:
        return RouterDecision(
            supported=False,
            intent=RouterIntent.UNSUPPORTED,
            tool_name=None,
            reason="The current vertical slice supports exactly one uploaded image.",
        )
    return RouterDecision(
        supported=True,
        intent=RouterIntent.VQA,
        tool_name="internvl_vqa",
        reason="A natural-language visual question with a single uploaded image selects VQA.",
    )
