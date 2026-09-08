"""Scale guards for fusion tools.

These guards trust the caller's declaration, not the pixel values. Guessing a
scale from array statistics is exactly the bug this module exists to prevent.
"""

import numpy as np

from app.tools.fusion.sar_scale import SarScale


class ScaleError(ValueError):
    """Raised when an array's declared scale doesn't match what an operation requires."""


class InsufficientValidSupportError(ValueError):
    """Raised when a valid-support mask has too few finite pixels to compute anything.

    A raster's nodata footprint can leave zero (or near-zero) finite pixels inside
    the area of interest. Below `MIN_VALID_PIXELS` there is no statistically
    meaningful Otsu threshold or fraction to compute — this is an abstention
    signal, not a value to silently zero-fill or divide-by-zero through.
    """


# The literal floor from the spec this guard implements: 0 finite pixels must
# raise. 1 is not a tuned accuracy threshold — it is the smallest count for
# which "a pixel exists to reason about" is true; a scene with exactly one
# valid pixel is a degenerate case callers should already be routing around
# (e.g. via a real footprint check upstream), but this guard exists so that
# case fails loudly here rather than propagating NaN/nonsense downstream.
MIN_VALID_PIXELS = 1


def require_db_scale(array: np.ndarray, declared_scale: SarScale) -> np.ndarray:
    """Return `array` unchanged if `declared_scale` is DB, else raise.

    Does not inspect `array`'s values. A caller that mislabels a LINEAR array
    as DB will not be caught here — that's a contract violation upstream, not
    something this guard can detect from numbers alone.
    """
    if declared_scale is not SarScale.DB:
        raise ScaleError(
            f"expected SarScale.DB, got {declared_scale!r}: "
            "convert to dB and pass SarScale.DB explicitly"
        )
    return array
