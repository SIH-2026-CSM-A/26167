"""Scale guards for fusion tools.

These guards trust the caller's declaration, not the pixel values. Guessing a
scale from array statistics is exactly the bug this module exists to prevent.
"""

import numpy as np

from app.tools.fusion.sar_scale import SarScale


class ScaleError(ValueError):
    """Raised when an array's declared scale doesn't match what an operation requires."""


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
