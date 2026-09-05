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

from app.tools.fusion.guards import require_db_scale
from app.tools.fusion.sar_scale import SarScale


def otsu_water_mask(sigma0_db: np.ndarray, declared_scale: SarScale) -> np.ndarray:
    """Binary water mask (True = water) from a despeckled, dB-scale SAR array.

    Expects the input to already be NaN-free (e.g. nodata masked out by the
    caller); raises rather than silently thresholding around missing data.
    """
    require_db_scale(sigma0_db, declared_scale)
    sigma0_db = np.asarray(sigma0_db, dtype=np.float64)
    if np.isnan(sigma0_db).any():
        raise ValueError("sigma0_db contains NaN; mask nodata before thresholding")

    threshold = threshold_otsu(sigma0_db)
    return sigma0_db <= threshold
