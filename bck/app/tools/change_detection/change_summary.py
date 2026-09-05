"""Human-readable summary of a binary change-detection mask."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ChangeSummary:
    """Textual description plus a pixel-space location reference.

    `bbox` is (row_min, col_min, row_max, col_max), inclusive, in pixel-space —
    there is no CRS or affine transform to project into, so no lat/lon is ever
    emitted. Both fields are None when no change is present.
    """

    changed: bool
    description: str
    bbox: tuple[int, int, int, int] | None
    relative_position: str | None


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


def summarize_change(mask: np.ndarray) -> ChangeSummary:
    """Describe a binary change mask: presence, extent, and pixel-space location.

    `mask` is a 2D array where any nonzero value means "changed".
    """
    mask = np.asarray(mask).astype(bool)
    if mask.ndim != 2:
        raise ValueError(f"mask must be 2D, got shape {mask.shape}")

    if not mask.any():
        return ChangeSummary(
            changed=False, description="No change detected.", bbox=None, relative_position=None
        )

    row_indices = np.where(np.any(mask, axis=1))[0]
    col_indices = np.where(np.any(mask, axis=0))[0]
    row_min, row_max = int(row_indices[0]), int(row_indices[-1])
    col_min, col_max = int(col_indices[0]), int(col_indices[-1])
    bbox = (row_min, col_min, row_max, col_max)

    centroid_row = (row_min + row_max) / 2
    centroid_col = (col_min + col_max) / 2
    relative_position = _relative_position(centroid_row, centroid_col, mask.shape)

    changed_fraction = float(mask.mean())
    description = (
        f"Change detected across {changed_fraction * 100:.1f}% of the scene, "
        f"located {relative_position}."
    )
    return ChangeSummary(
        changed=True, description=description, bbox=bbox, relative_position=relative_position
    )
