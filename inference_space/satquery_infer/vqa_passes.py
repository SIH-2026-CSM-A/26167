"""VQA model passes, copied from bck/app/tools/vqa_grounding/tool.py (see README provenance).

Only the parts that need the model: prompts, the pass runner, and native <box> parsing.
Otsu fallback and observation parsing stay on Render.
"""

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

# Trigger words for spatial-ask questions ("Where is the flooding?", "Highlight the
# river"). Deliberately narrow — bbox grounding costs an extra model pass, so it only
# runs when the question actually asks for a location, not on every query.
SPATIAL_TRIGGER_PATTERN = re.compile(r"\b(highlight|locate|where|point out)\b", re.IGNORECASE)

# InternVL's own documented grounding prompt (model card / FAQ): "Please provide the
# bounding box coordinate(s) of the region this sentence describes: <ref>{}</ref>".
# Native output echoes back "<ref>{expression}</ref><box>[[x1,y1,x2,y2]]</box>" with
# coordinates on InternVL's normalized 0-1000 scale, not raw pixels.
BBOX_GROUNDING_PROMPT = (
    "Please provide the bounding box coordinate of the region this sentence describes: "
    "<ref>{expression}</ref>"
)
BOX_TAG_PATTERN = re.compile(
    r"<box>\s*\[\s*\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,"
    r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]\s*\]\s*</box>"
)
_INTERNVL_BOX_SCALE = 1000

class VqaModel(Protocol):
    """Structural model interface that keeps the tool independent from app.models."""

    model_id: str
    device: str
    active_model_identity: str | None

    def generate(self, image: Image.Image, prompt: str) -> str:
        """Generate model text for one image and prompt."""
        ...


class VqaToolError(RuntimeError):
    """Raised when model output cannot form a valid VQA tool result."""


@dataclass(frozen=True, slots=True)
class VqaPasses:
    """Raw model text from each VQA pass, with that pass's own wall-clock timing.

    This is the only part of VQA that needs the model; it is what a remote inference service
    returns. Everything derived from it (parsing, bbox scaling, Otsu fallback) runs in
    build_vqa_result against the original image.
    """

    raw_answer: str
    raw_grounding_output: str
    raw_bbox_output: str | None
    answer_seconds: float
    grounding_seconds: float
    bbox_seconds: float | None


def run_vqa_passes(*, image: Image.Image, question: str, model: VqaModel) -> VqaPasses:
    """Run the answer, claim-grounding and (for spatial questions) bbox passes."""
    if not question.strip():
        raise ValueError("question is required")

    started = time.perf_counter()
    raw_answer = model.generate(image, question.strip()).strip()
    if not raw_answer:
        raise VqaToolError("VQA model returned an empty answer")
    answer_done = time.perf_counter()
    grounding_prompt = GROUNDING_PROMPT.format(
        question=question.strip(), candidate_answer=raw_answer
    )
    raw_grounding_output = model.generate(image, grounding_prompt).strip()
    grounding_done = time.perf_counter()

    raw_bbox_output: str | None = None
    bbox_seconds: float | None = None
    if SPATIAL_TRIGGER_PATTERN.search(question):
        bbox_prompt = BBOX_GROUNDING_PROMPT.format(expression=raw_answer)
        raw_bbox_output = model.generate(image, bbox_prompt).strip()
        bbox_seconds = time.perf_counter() - grounding_done

    return VqaPasses(
        raw_answer=raw_answer,
        raw_grounding_output=raw_grounding_output,
        raw_bbox_output=raw_bbox_output,
        answer_seconds=answer_done - started,
        grounding_seconds=grounding_done - answer_done,
        bbox_seconds=bbox_seconds,
    )


def _parse_native_bbox(grounding_output: str, image_size: tuple[int, int]) -> list[int] | None:
    """Parse exactly one <box>[[x1,y1,x2,y2]]</box> and scale it to image pixels.

    Refuses to guess on empty, malformed, or multi-box output (falls back instead
    of picking an arbitrary one of several candidate boxes).
    """
    matches = BOX_TAG_PATTERN.findall(grounding_output)
    if len(matches) != 1:
        return None
    x1_raw, y1_raw, x2_raw, y2_raw = (float(v) for v in matches[0])
    width, height = image_size
    x1 = round(x1_raw / _INTERNVL_BOX_SCALE * width)
    y1 = round(y1_raw / _INTERNVL_BOX_SCALE * height)
    x2 = round(x2_raw / _INTERNVL_BOX_SCALE * width)
    y2 = round(y2_raw / _INTERNVL_BOX_SCALE * height)
    if x2 <= x1 or y2 <= y1:
        return None
    return [x1, y1, x2, y2]
