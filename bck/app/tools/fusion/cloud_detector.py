"""Cloud probability/mask via s2cloudless's pixel-based classifier.

Wraps sentinel-hub's `S2PixelCloudDetector` — purely local LightGBM
inference over the array handed to it. This module never imports
s2cloudless's `download_bands_and_valid_data_mask`, which is the only part
of the library that touches the network; the classifier itself does not.

Reflectance must already be scaled to Sentinel-2 TOA reflectance in [0, 1]
(raw digital numbers divided by 10000) — this function does not rescale.
"""

from dataclasses import dataclass

import numpy as np
from s2cloudless import S2PixelCloudDetector

_ALL_BANDS_COUNT = 13
_MODEL_BANDS_COUNT = 10


@dataclass(frozen=True)
class CloudDetectionResult:
    """Cloud probability map (float, [0, 1]) and binary cloud mask, both (H, W)."""

    probability: np.ndarray
    mask: np.ndarray


def detect_clouds(reflectance: np.ndarray, threshold: float = 0.4) -> CloudDetectionResult:
    """Run S2PixelCloudDetector on a single (H, W, 13) or (H, W, 10) reflectance array.

    `threshold` is s2cloudless's own documented default cloud-probability
    cutoff (0.4), passed straight through — not a value invented here.
    """
    if reflectance.ndim != 3:
        raise ValueError(f"reflectance must be (H, W, bands); got shape {reflectance.shape}")

    band_count = reflectance.shape[-1]
    if band_count == _ALL_BANDS_COUNT:
        all_bands = True
    elif band_count == _MODEL_BANDS_COUNT:
        all_bands = False
    else:
        raise ValueError(
            f"reflectance must have {_ALL_BANDS_COUNT} bands (all Sentinel-2 bands) or "
            f"{_MODEL_BANDS_COUNT} bands (B01,B02,B04,B05,B08,B8A,B09,B10,B11,B12); "
            f"got {band_count}"
        )

    detector = S2PixelCloudDetector(threshold=threshold, all_bands=all_bands)
    batched = reflectance[np.newaxis, ...].astype(np.float32)
    probability = detector.get_cloud_probability_maps(batched)[0]
    mask = detector.get_mask_from_prob(probability[np.newaxis, ...])[0]

    return CloudDetectionResult(probability=probability, mask=mask.astype(bool))
