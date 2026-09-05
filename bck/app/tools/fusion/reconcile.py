"""Cross-modal SAR+optical reconciliation into a single Evidence answer.

Rule: where the optical cloud mask flags cloud cover, that region's optical
contribution is inconclusive — the SAR-derived water assessment is still
reported there, but confidence is scaled down and a disagreement flag is set.
Elsewhere, the SAR result is reported at full confidence with no flag.

No confidence formula is specified anywhere in the project docs at this
granularity (ARCHITECTURE.md and the contracts' Evidence schema describe the
{id, tool, type, payload, confidence, timing} shape, not how to compute a
value for a cross-modal disagreement case like this one). The rule below is
this module's own choice, not something specified in any doc: confidence
starts at 1.0 (full confidence in the SAR-only result) and scales down
linearly by the region's cloud-covered fraction.
"""

import time
import uuid

import numpy as np

from app.contracts import Evidence, EvidenceType
from app.tools.fusion.cloud_detector import CloudDetectionResult

_TOOL_NAME = "fusion.reconcile"


def reconcile_sar_optical(
    despeckled_sigma0_db: np.ndarray,
    water_mask: np.ndarray,
    cloud_result: CloudDetectionResult,
) -> list[Evidence]:
    """Combine an Otsu SAR water mask with an optical cloud-detection result.

    All three inputs must be co-registered and share one (H, W) shape.
    """
    started = time.perf_counter()

    if not (despeckled_sigma0_db.shape == water_mask.shape == cloud_result.mask.shape):
        raise ValueError(
            "despeckled_sigma0_db, water_mask, and cloud_result.mask must share one "
            f"shape; got {despeckled_sigma0_db.shape}, {water_mask.shape}, "
            f"{cloud_result.mask.shape}"
        )

    water_mask = np.asarray(water_mask).astype(bool)
    cloud_mask = np.asarray(cloud_result.mask).astype(bool)

    cloud_fraction = float(cloud_mask.mean())
    water_fraction = float(water_mask.mean())
    optical_inconclusive = cloud_fraction > 0.0
    confidence = 1.0 - cloud_fraction if optical_inconclusive else 1.0

    if optical_inconclusive:
        note = (
            f"SAR indicates {water_fraction * 100:.1f}% water coverage. Optical could "
            f"not confirm {cloud_fraction * 100:.1f}% of the region due to cloud cover; "
            "the SAR-derived assessment is reported there regardless."
        )
    else:
        note = (
            f"SAR indicates {water_fraction * 100:.1f}% water coverage. No cloud cover "
            "detected; optical raised no disagreement."
        )

    evidence = Evidence(
        id=str(uuid.uuid4()),
        tool=_TOOL_NAME,
        type=EvidenceType.MASK,
        payload={
            "water_mask": water_mask,
            "water_fraction": water_fraction,
            "cloud_fraction": cloud_fraction,
            "optical_inconclusive": optical_inconclusive,
            "note": note,
        },
        confidence=confidence,
        timing=time.perf_counter() - started,
    )
    return [evidence]
