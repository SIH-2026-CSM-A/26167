"""Single-image VQA tool coordinating answer, claim-grounding, and bbox-grounding passes."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Protocol

import numpy as np
from PIL import Image
from skimage.filters import threshold_otsu
from skimage.measure import label, regionprops

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
    bbox: list[int] | None = None
    bbox_label: str | None = None
    bbox_source: str | None = None  # "internvl_native" | "otsu_fallback" | None
    raw_bbox_output: str | None = None


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

    bbox: list[int] | None = None
    bbox_label: str | None = None
    bbox_source: str | None = None
    raw_bbox_output: str | None = None
    if SPATIAL_TRIGGER_PATTERN.search(question):
        bbox_label = raw_answer
        bbox_prompt = BBOX_GROUNDING_PROMPT.format(expression=raw_answer)
        raw_bbox_output = model.generate(image, bbox_prompt).strip()
        bbox = _parse_native_bbox(raw_bbox_output, image.size)
        if bbox is not None:
            bbox_source = "internvl_native"
        else:
            bbox = _otsu_fallback_bbox(image)
            if bbox is not None:
                bbox_source = "otsu_fallback"

    return VqaToolResult(
        source_asset_id=source_asset_id,
        raw_answer=raw_answer,
        supporting_observations=observations,
        raw_grounding_output=raw_grounding_output,
        model_id=model.model_id,
        device=model.device,
        timing_seconds=time.perf_counter() - started,
        bbox=bbox,
        bbox_label=bbox_label,
        bbox_source=bbox_source,
        raw_bbox_output=raw_bbox_output,
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


def _otsu_fallback_bbox(image: Image.Image) -> list[int] | None:
    """Bbox of the largest Otsu-thresholded region, when native grounding fails.

    Reuses the same `skimage.filters.threshold_otsu` primitive as
    `app.tools.fusion.sar_water_mask` (ROHAN-003's SAR water segmentation), applied
    to grayscale intensity: an arbitrary optical query image carries no NIR band, so
    a true NDWI ratio cannot be computed here, and low intensity is used as the
    foreground heuristic in the same spirit as that module's "water = low
    backscatter" rule. This is a deliberately coarse fallback, not a calibrated
    detector — it locates the darkest coherent region, nothing more specific.
    """
    grayscale = np.asarray(image.convert("L"), dtype=np.float64)
    if grayscale.min() == grayscale.max():
        return None
    threshold = threshold_otsu(grayscale)
    mask = grayscale <= threshold
    labeled = label(mask)
    if labeled.max() == 0:
        return None
    largest = max(regionprops(labeled), key=lambda region: region.area)
    min_row, min_col, max_row, max_col = largest.bbox
    if max_col <= min_col or max_row <= min_row:
        return None
    return [int(min_col), int(min_row), int(max_col), int(max_row)]
