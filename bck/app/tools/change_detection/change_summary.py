"""Human-readable summary of a binary change-detection mask."""

from dataclasses import dataclass
from typing import Literal

import numpy as np

# Real self-comparison noise floor, measured directly via detector.py's actual
# pipeline (BIT model, not a synthetic mask): a real fixture image run against
# an exact copy of itself. Both real fixtures available in this repo
# (levir_test_1_t1, levir_train_103_9_t1) measured EXACTLY 0.0% changed pixels
# (0/65536) against themselves — not just "low", genuinely zero. The team
# lead's example ballpark (0.5% / 15px) was offered before this measurement
# existed; those two example figures are also inconsistent with each other
# for a 256x256=65536px frame (0.5% ~= 328px, not 15px). Given the real
# measured floor is exactly zero, 0.1% (~66px of 65536) is chosen as a
# threshold a full order of magnitude tighter than the lead's more
# conservative 0.5% example, while still comfortably above the true-zero
# floor to tolerate ordinary model noise on genuinely distinct (non-identical)
# real image pairs. This is provisional per PRD Section 8's "TBD from real
# testing" and based on only 2 real self-comparison points.
_NOISE_FLOOR_FRACTION = 0.001


@dataclass(frozen=True)
class ChangeSummary:
    """Textual description plus a pixel-space location reference.

    `bbox` is (row_min, col_min, row_max, col_max), inclusive, in pixel-space —
    there is no CRS or affine transform to project into, so no lat/lon or
    geographic-area (m^2) footprint is ever emitted for these fixtures; that
    would require real GSD/affine metadata this benchmark data doesn't carry.
    Both `bbox` and `relative_position` are None only when the raw mask has no
    flagged pixels at all.

    `changed` is the raw model signal (did BIT flag any pixel at all).
    `status` is the noise-floor-aware categorical judgment ("increased",
    "decreased", or "unchanged") described in this module's docstring — the
    two can disagree: a mask with a few scattered flagged pixels below the
    noise floor has `changed=True` but `status="unchanged"`.

    Defaulting "changed and not reversed" to "increased" (never inferring
    "decreased" from pixel content) is a LEVIR-CD-specific dataset-context
    assumption, not a general capability: LEVIR-CD is a documented
    building-construction/growth benchmark, so a detected change in this
    specific pipeline is assumed to be growth unless the caller explicitly
    states the image order is reversed. "decreased" is real, reachable code
    (see `reversed_order`), but is not validated against any real observed
    decrease in this repo's fixtures — LEVIR-CD contains no real decrease
    pairs to test it against.
    """

    changed: bool
    description: str
    bbox: tuple[int, int, int, int] | None
    relative_position: str | None
    status: Literal["increased", "decreased", "unchanged"]
    changed_pixel_count: int
    changed_percentage: float


def _relative_position(centroid_row: float, centroid_col: float, shape: tuple[int, int]) -> str:
    height, width = shape
    if centroid_row < height / 3:
        vert = "upper"
    elif centroid_row >= 2 * height / 3:
        vert = "lower"
    else:
        vert = "centre"

    if centroid_col < width / 3:
        horiz = "left"
    elif centroid_col >= 2 * width / 3:
        horiz = "right"
    else:
        horiz = "centre"

    if vert == "centre" and horiz == "centre":
        return "centre"
    return f"{vert}-{horiz}"


def summarize_change(mask: np.ndarray, reversed_order: bool = False) -> ChangeSummary:
    """Describe a binary change mask: presence, extent, direction, and location.

    `mask` is a 2D array where any nonzero value means "changed". Pass
    `reversed_order=True` when the caller knows the image pair was supplied
    as (t2, t1) rather than (t1, t2) — this is the only mechanism by which
    `status` can ever be "decreased"; it is never inferred from pixel content.
    """
    mask = np.asarray(mask).astype(bool)
    if mask.ndim != 2:
        raise ValueError(f"mask must be 2D, got shape {mask.shape}")

    changed_pixel_count = int(mask.sum())
    changed_fraction = float(mask.mean())
    changed_percentage = changed_fraction * 100.0

    if not mask.any():
        return ChangeSummary(
            changed=False,
            description="No change detected.",
            bbox=None,
            relative_position=None,
            status="unchanged",
            changed_pixel_count=0,
            changed_percentage=0.0,
        )

    row_indices = np.where(np.any(mask, axis=1))[0]
    col_indices = np.where(np.any(mask, axis=0))[0]
    row_min, row_max = int(row_indices[0]), int(row_indices[-1])
    col_min, col_max = int(col_indices[0]), int(col_indices[-1])
    bbox = (row_min, col_min, row_max, col_max)

    centroid_row = (row_min + row_max) / 2
    centroid_col = (col_min + col_max) / 2
    relative_position = _relative_position(centroid_row, centroid_col, mask.shape)

    if changed_fraction < _NOISE_FLOOR_FRACTION:
        status: Literal["increased", "decreased", "unchanged"] = "unchanged"
    elif reversed_order:
        status = "decreased"
    else:
        status = "increased"

    description = (
        f"Change detected ({status}) across {changed_percentage:.1f}% of the scene, "
        f"located {relative_position}."
    )
    return ChangeSummary(
        changed=True,
        description=description,
        bbox=bbox,
        relative_position=relative_position,
        status=status,
        changed_pixel_count=changed_pixel_count,
        changed_percentage=changed_percentage,
    )
