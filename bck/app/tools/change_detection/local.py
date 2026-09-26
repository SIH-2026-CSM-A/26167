"""Run BIT in this process: bit_model's forward pass + detector's evidence building.

Needs the `inference` extra (torch). Used by evaluation scripts and the model tests; the
deployed API calls the inference Space instead (app.pipeline -> app.inference.remote).
"""

import time

import numpy as np
from PIL import Image

from app.contracts import Evidence, ImageInput
from app.tools.change_detection.bit_model import load_bit_model, run_bit
from app.tools.change_detection.detector import build_change_evidence


def detect_change(
    image_a: ImageInput,
    image_b: ImageInput,
    checkpoint_path: str,
    cloud_mask: np.ndarray | None = None,
) -> list[Evidence]:
    """Run BIT locally on a co-registered bi-temporal pair and return change-detection Evidence.

    `checkpoint_path` is a required parameter, not an invented default — the
    pretrained weight file's location is a deployment concern, not something
    this function should guess.
    """
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
