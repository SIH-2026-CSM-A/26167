"""Cross-modal SAR+optical reconciliation into per-region Evidence answers.

Rule: where the optical cloud mask flags cloud cover, that region's optical
contribution is inconclusive — the SAR-derived water assessment is still
reported there, but confidence is discounted and a disagreement flag is set.
Elsewhere, the SAR result is reported at full confidence with no flag.

No confidence formula is specified anywhere in the project docs at this
granularity (ARCHITECTURE.md and the contracts' Evidence schema describe the
{id, tool, type, payload, confidence, timing} shape, not how to compute a
value for a cross-modal disagreement case like this one). This module's own
choice, not something specified in any doc:

Region-split, not one global scalar. SAR is not blocked by cloud cover — that
is the entire reason to fuse it with optical — so a single scene-wide
confidence computed from the *overall* cloud fraction would drag down
confidence in pixels that have zero actual disagreement, while under-flagging
the pixels that genuinely do. Both `water_mask` and `cloud_result.mask` are
already full-resolution per-pixel arrays; this function uses that information
directly instead of collapsing it into one number first.

Concretely: when a scene has ANY cloud cover, this returns two Evidence
objects — one for the cloud-free region (confidence 1.0, no disagreement) and
one for the cloud-affected region (a fixed SAR-only confidence baseline,
_SAR_ONLY_CONFIDENCE — not scaled by how big that region is, since "missing
optical corroboration" is the same problem whether it affects 5% or 95% of
the frame). When a scene has zero cloud cover, it returns one Evidence object
at confidence 1.0, matching the original single-region behaviour exactly.
"""

import time
import uuid

import numpy as np

from app.contracts import Evidence, EvidenceType
from app.tools.fusion.cloud_detector import CloudDetectionResult

_TOOL_NAME = "fusion.reconcile"

# Confidence assigned to the cloud-affected region: SAR alone, with no optical
# corroboration. This is a fixed baseline, not scaled by how much of the
# scene happens to be cloudy — a region under cloud has the same "missing
# corroboration" problem whether it's 5% or 95% of the frame, so its
# confidence discount should not depend on that area fraction. 0.75 is this
# module's own invented choice (not specified in any project doc, same as
# the rest of this formula) — flagged for review alongside the region-split
# design itself.
_SAR_ONLY_CONFIDENCE = 0.75


def _region_water_fraction(water_mask: np.ndarray, region_mask: np.ndarray) -> float:
    """Water fraction within `region_mask`, or 0.0 if the region is empty."""
    if not region_mask.any():
        return 0.0
    return float(water_mask[region_mask].mean())


def reconcile_sar_optical(
    despeckled_sigma0_db: np.ndarray,
    water_mask: np.ndarray,
    cloud_result: CloudDetectionResult,
) -> list[Evidence]:
    """Combine an Otsu SAR water mask with an optical cloud-detection result.

    All three inputs must be co-registered and share one (H, W) shape.
    Returns one Evidence object per region (clear / cloud-affected) rather
    than one scene-wide average, so confidence reflects each pixel's actual
    cross-modal agreement instead of a scene-level dilution — see module
    docstring.
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

    if cloud_fraction == 0.0:
        # No disagreement anywhere — single evidence object, full confidence,
        # identical to the fully-clear case in the original implementation.
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
                "cloud_fraction": 0.0,
                "optical_inconclusive": False,
                "region": "full_scene",
                "note": note,
            },
            confidence=1.0,
            timing=time.perf_counter() - started,
        )
        return [evidence]

    clear_mask = ~cloud_mask
    clear_water_fraction = _region_water_fraction(water_mask, clear_mask)
    cloud_water_fraction = _region_water_fraction(water_mask, cloud_mask)

    evidence_list: list[Evidence] = []

    if clear_mask.any():
        clear_note = (
            f"SAR indicates {clear_water_fraction * 100:.1f}% water coverage in the "
            f"{(1 - cloud_fraction) * 100:.1f}% of the scene with no cloud cover; "
            "optical confirms no disagreement in this region."
        )
        evidence_list.append(
            Evidence(
                id=str(uuid.uuid4()),
                tool=_TOOL_NAME,
                type=EvidenceType.MASK,
                payload={
                    "water_mask": water_mask & clear_mask,
                    "region_mask": clear_mask,
                    "water_fraction": clear_water_fraction,
                    "cloud_fraction": 0.0,
                    "optical_inconclusive": False,
                    "region": "clear",
                    "region_area_fraction": 1.0 - cloud_fraction,
                    "note": clear_note,
                },
                confidence=1.0,
                timing=time.perf_counter() - started,
            )
        )

    if cloud_mask.any():
        # Fixed baseline, not scaled by this region's size — see
        # _SAR_ONLY_CONFIDENCE docstring above. The SAR answer for this
        # region is still reported, never silently dropped, just at a
        # discounted confidence reflecting the missing optical corroboration.
        cloud_region_confidence = _SAR_ONLY_CONFIDENCE
        cloud_note = (
            f"SAR indicates {cloud_water_fraction * 100:.1f}% water coverage in the "
            f"{cloud_fraction * 100:.1f}% of the scene under cloud cover; optical could "
            "not confirm this region, so the SAR-derived assessment is reported at "
            "reduced confidence."
        )
        evidence_list.append(
            Evidence(
                id=str(uuid.uuid4()),
                tool=_TOOL_NAME,
                type=EvidenceType.MASK,
                payload={
                    "water_mask": water_mask & cloud_mask,
                    "region_mask": cloud_mask,
                    "water_fraction": cloud_water_fraction,
                    "cloud_fraction": cloud_fraction,
                    "optical_inconclusive": True,
                    "region": "cloud_affected",
                    "region_area_fraction": cloud_fraction,
                    "note": cloud_note,
                },
                confidence=cloud_region_confidence,
                timing=time.perf_counter() - started,
            )
        )

    return evidence_list
