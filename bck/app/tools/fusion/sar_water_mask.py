"""Binary water mask from despeckled SAR backscatter via Otsu's threshold.

Source: Otsu, N. (1979), "A threshold selection method from gray-level
histograms," IEEE Transactions on Systems, Man, and Cybernetics, SMC-9(1).

Standing/open water produces single-bounce (specular) reflection of the radar
signal away from the sensor, so it appears as LOW backscatter relative to land
(Esri, "Interpret SAR data for flood mapping," ArcGIS Pro documentation).
Pixels at or below the Otsu threshold are classified as water.
"""

import numpy as np
from skimage.filters import threshold_otsu

from app.tools.fusion.guards import (
    MIN_VALID_PIXELS,
    InsufficientValidSupportError,
    require_db_scale,
)
from app.tools.fusion.sar_scale import SarScale


def otsu_water_mask(
    sigma0_db: np.ndarray, declared_scale: SarScale, valid_mask: np.ndarray | None = None
) -> np.ndarray:
    """Binary water mask (True = water) from a despeckled, dB-scale SAR array.

    Without `valid_mask`, expects the input to already be NaN-free (e.g.
    nodata masked out by the caller); raises rather than silently
    thresholding around missing data. This is the legacy behavior.

    With `valid_mask` (co-registered boolean array, True = valid data), the
    Otsu threshold is computed only from valid, finite pixels, and only
    those pixels are classified — pixels outside `valid_mask` come back
    False in the returned array, but that False means "not classified", not
    "not water": callers must AND the result with `valid_mask` (or check it
    directly) before treating a False as a real "not water" observation, the
    same as everywhere else nodata and the water class must stay separate.
    Raises `InsufficientValidSupportError` if fewer than `MIN_VALID_PIXELS`
    valid, finite pixels are available to threshold.
    """
    require_db_scale(sigma0_db, declared_scale)
    sigma0_db = np.asarray(sigma0_db, dtype=np.float64)

    if valid_mask is None:
        if np.isnan(sigma0_db).any():
            raise ValueError("sigma0_db contains NaN; mask nodata before thresholding")
        threshold = threshold_otsu(sigma0_db)
        return sigma0_db <= threshold

    valid_mask = np.asarray(valid_mask, dtype=bool)
    if valid_mask.shape != sigma0_db.shape:
        raise ValueError(
            f"valid_mask must share sigma0_db's shape {sigma0_db.shape}; got {valid_mask.shape}"
        )
    finite_valid = valid_mask & np.isfinite(sigma0_db)
    valid_values = sigma0_db[finite_valid]
    if valid_values.size < MIN_VALID_PIXELS:
        raise InsufficientValidSupportError(
            f"only {valid_values.size} valid, finite pixel(s) available; at least "
            f"{MIN_VALID_PIXELS} required to compute an Otsu threshold"
        )

    threshold = threshold_otsu(valid_values)
    water_mask = np.zeros(sigma0_db.shape, dtype=bool)
    water_mask[finite_valid] = sigma0_db[finite_valid] <= threshold
    return water_mask
