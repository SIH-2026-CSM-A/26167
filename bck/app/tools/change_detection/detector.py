"""BIT change-detection entry point: the Evidence-assembling tool for F6.

Loads two co-registered images from their `ImageInput.path` (already
persisted to disk by ingestion via `tempfile.NamedTemporaryFile(delete=False,
...)` — read now, do not delete; cleanup is a separate, not-yet-built
concern), runs the vendored BIT model (`bit_vendor/`) to produce a predicted
change mask, and constructs `list[Evidence]` directly — matching
`fusion/reconcile.py`'s exact construction pattern. There is no `stub_tool`
seam anywhere in this codebase to plug into instead (verified directly
against source, not assumed).
"""

import time
import uuid

import numpy as np
from PIL import Image

from app.contracts import Evidence, EvidenceType, ImageInput
from app.tools.change_detection.change_summary import summarize_change
from app.tools.change_detection.confidence import compute_confidence
from app.tools.change_detection.confounder_gate import evaluate_confounder_gate

_TOOL_NAME = "change_detection.bit"


def build_change_evidence(
    *,
    probability_changed: np.ndarray,
    predicted_mask: np.ndarray,
    image_a: ImageInput,
    image_b: ImageInput,
    started: float,
    cloud_mask: np.ndarray | None = None,
) -> list[Evidence]:
    """Gate, score and summarise BIT output into change-detection Evidence.

    Torch-free: the BIT forward pass may have run locally (bit_model) or remotely.
    `started` is the time.perf_counter() value taken before BIT ran, so Evidence.timing
    covers preprocessing, inference and this post-processing.
    """
    gate_result = evaluate_confounder_gate(
        raw_mask=predicted_mask,
        path_a=image_a.path,
        path_b=image_b.path,
        cloud_mask=cloud_mask,
    )
    effective_mask = (
        np.zeros_like(predicted_mask) if gate_result.suppressed else gate_result.filtered_mask
    )
    confidence = compute_confidence(probability_changed, effective_mask)
    summary = summarize_change(effective_mask)

    evidence = Evidence(
        id=str(uuid.uuid4()),
        tool=_TOOL_NAME,
        type=EvidenceType.MASK,
        payload={
            "change_mask": effective_mask,
            "raw_mask": predicted_mask,
            "label": "Changed area (BIT change mask)",
            "description": summary.description,
            "bbox": summary.bbox,
            "relative_position": summary.relative_position,
            "status": summary.status,
            "changed_pixel_count": summary.changed_pixel_count,
            "changed_percentage": summary.changed_percentage,
            "source_image_a_id": image_a.id,
            "source_image_b_id": image_b.id,
            "confounder_suppressed": gate_result.suppressed,
            "confounder_reason": gate_result.reason,
            "cloud_fraction": gate_result.cloud_fraction,
        },
        confidence=confidence,
        timing=time.perf_counter() - started,
    )
    return [evidence]


def detect_change(
    image_a: ImageInput,
    image_b: ImageInput,
    checkpoint_path: str,
    cloud_mask: np.ndarray | None = None,
) -> list[Evidence]:
    """Run BIT locally on a co-registered bi-temporal pair and return change-detection Evidence.

    `checkpoint_path` is a required parameter, not an invented default — the
    pretrained weight file's location is a deployment concern, not something
    this function should guess. Imports torch (via bit_model) only when called.
    """
    from app.tools.change_detection.bit_model import load_bit_model, run_bit

    started = time.perf_counter()
    image_pre = Image.open(image_a.path)
    image_post = Image.open(image_b.path)
    net = load_bit_model(checkpoint_path)
    probability_changed, predicted_mask = run_bit(net, image_pre, image_post)
    return build_change_evidence(
        probability_changed=probability_changed,
        predicted_mask=predicted_mask,
        image_a=image_a,
        image_b=image_b,
        started=started,
        cloud_mask=cloud_mask,
    )
