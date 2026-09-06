"""Confidence score for a change-detection prediction."""

import numpy as np


def compute_confidence(probability: np.ndarray, predicted_mask: np.ndarray) -> float:
    """Mean, over all pixels, of P where predicted "changed" else (1 - P).

    `probability` is BIT's per-pixel sigmoid probability of "changed";
    `predicted_mask` is the already-binarized predicted mask (nonzero means
    changed). Binarizing a raw probability map is the caller's decision — this
    function takes no threshold and invents no default for one.
    """
    probability = np.asarray(probability, dtype=np.float64)
    predicted_mask = np.asarray(predicted_mask).astype(bool)
    if probability.shape != predicted_mask.shape:
        raise ValueError(
            f"probability shape {probability.shape} != predicted_mask shape {predicted_mask.shape}"
        )

    per_pixel_confidence = np.where(predicted_mask, probability, 1.0 - probability)
    return float(per_pixel_confidence.mean())
