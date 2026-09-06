"""Single-image VQA tool coordinating answer and image-grounding inference passes."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Protocol

from PIL import Image

GROUNDING_PROMPT = """Review the candidate answer against the image itself.
Return only claims that are directly visible in the image, one claim per line.
Preserve the candidate claim wording exactly where it is supported.
Omit unsupported claims. Do not add explanations.

Original question: {question}
Candidate answer: {candidate_answer}
"""
BULLET_PREFIX = re.compile(r"^(?:[-*•]\s*|\d+[.)]\s*)")
SUPPORTED_PREFIX = re.compile(r"^supported\s*:\s*", re.IGNORECASE)
UNSUPPORTED_PREFIX = re.compile(r"^unsupported\s*:", re.IGNORECASE)


class VqaModel(Protocol):
    """Structural model interface that keeps the tool independent from app.models."""

    model_id: str
    device: str

    def generate(self, image: Image.Image, prompt: str) -> str:
        """Generate model text for one image and prompt."""
        ...


class VqaToolError(RuntimeError):
    """Raised when model output cannot form a valid VQA tool result."""


@dataclass(frozen=True, slots=True)
class VqaToolResult:
    """Raw VQA answer and grounded observations with actual execution provenance."""

    source_asset_id: str
    raw_answer: str
    supporting_observations: tuple[str, ...]
    raw_grounding_output: str
    model_id: str
    device: str
    timing_seconds: float


def execute_vqa(
    *,
    image: Image.Image,
    question: str,
    source_asset_id: str,
    model: VqaModel,
) -> VqaToolResult:
    """Run real answer and grounding passes and return structured tool output."""
    if not question.strip():
        raise ValueError("question is required")
    if not source_asset_id.strip():
        raise ValueError("source_asset_id is required")

    started = time.perf_counter()
    raw_answer = model.generate(image, question.strip()).strip()
    if not raw_answer:
        raise VqaToolError("VQA model returned an empty answer")
    grounding_prompt = GROUNDING_PROMPT.format(
        question=question.strip(), candidate_answer=raw_answer
    )
    raw_grounding_output = model.generate(image, grounding_prompt).strip()
    observations = _parse_supporting_observations(raw_grounding_output)
    return VqaToolResult(
        source_asset_id=source_asset_id,
        raw_answer=raw_answer,
        supporting_observations=observations,
        raw_grounding_output=raw_grounding_output,
        model_id=model.model_id,
        device=model.device,
        timing_seconds=time.perf_counter() - started,
    )


def _parse_supporting_observations(model_text: str) -> tuple[str, ...]:
    """Parse only affirmative grounded lines and discard explicit unsupported lines."""
    observations: list[str] = []
    for raw_line in model_text.splitlines():
        line = BULLET_PREFIX.sub("", raw_line.strip())
        if not line or UNSUPPORTED_PREFIX.match(line):
            continue
        line = SUPPORTED_PREFIX.sub("", line).strip()
        if line:
            observations.append(line)
    return tuple(observations)
