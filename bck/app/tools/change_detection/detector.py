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
from types import SimpleNamespace

import numpy as np
import torch
from PIL import Image

from app.contracts import Evidence, EvidenceType, ImageInput
from app.tools.change_detection.change_summary import summarize_change
from app.tools.change_detection.confidence import compute_confidence
from app.tools.change_detection.registration_quality import require_registration_quality
from bit_vendor.networks import define_G

_TOOL_NAME = "change_detection.bit"
_NET_G = "base_transformer_pos_s4_dd8_dedim8"
_IMG_SIZE = 256
_NORMALIZE_MEAN = 0.5
_NORMALIZE_STD = 0.5


def _load_and_preprocess(path: str) -> torch.Tensor:
    """Load an RGB image from disk and prepare it as BIT expects: 256x256, [-1, 1]."""
    image = Image.open(path).convert("RGB").resize((_IMG_SIZE, _IMG_SIZE))
    array = np.asarray(image, dtype=np.float32) / 255.0
    normalized = (array - _NORMALIZE_MEAN) / _NORMALIZE_STD
    return torch.from_numpy(normalized).permute(2, 0, 1).unsqueeze(0).float()


def _load_bit_model(checkpoint_path: str) -> torch.nn.Module:
    """Build BIT's network and load its pretrained LEVIR-CD weights."""
    net = define_G(SimpleNamespace(net_G=_NET_G))
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    net.load_state_dict(checkpoint["model_G_state_dict"])
    net.eval()
    return net


def detect_change(image_a: ImageInput, image_b: ImageInput, checkpoint_path: str) -> list[Evidence]:
    """Run BIT on a co-registered bi-temporal pair and return change-detection Evidence.

    `checkpoint_path` is a required parameter, not an invented default — the
    pretrained weight file's location is a deployment concern, not something
    this function should guess.
    """
    started = time.perf_counter()

    require_registration_quality(image_a.path, image_b.path)

    tensor_a = _load_and_preprocess(image_a.path)
    tensor_b = _load_and_preprocess(image_b.path)
    net = _load_bit_model(checkpoint_path)

    with torch.no_grad():
        logits = net(tensor_a, tensor_b)
        probability_changed = torch.softmax(logits, dim=1)[0, 1].numpy()
        predicted_mask = torch.argmax(logits, dim=1)[0].numpy().astype(bool)

    confidence = compute_confidence(probability_changed, predicted_mask)
    summary = summarize_change(predicted_mask)

    evidence = Evidence(
        id=str(uuid.uuid4()),
        tool=_TOOL_NAME,
        type=EvidenceType.MASK,
        payload={
            "change_mask": predicted_mask,
            "description": summary.description,
            "bbox": summary.bbox,
            "relative_position": summary.relative_position,
            "status": summary.status,
            "changed_pixel_count": summary.changed_pixel_count,
            "changed_percentage": summary.changed_percentage,
            "source_image_a_id": image_a.id,
            "source_image_b_id": image_b.id,
        },
        confidence=confidence,
        timing=time.perf_counter() - started,
    )
    return [evidence]
