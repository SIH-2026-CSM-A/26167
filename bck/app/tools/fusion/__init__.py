"""Cross-modal optical and SAR fusion tools."""

from app.tools.fusion.calibration import calibrate_sigma0_db
from app.tools.fusion.cloud_detector import CloudDetectionResult, detect_clouds
from app.tools.fusion.despeckle import lee_filter
from app.tools.fusion.guards import ScaleError, require_db_scale
from app.tools.fusion.reconcile import reconcile_sar_optical
from app.tools.fusion.sar_scale import SarScale
from app.tools.fusion.sar_water_mask import otsu_water_mask
from app.tools.fusion.tool import execute_fusion

__all__ = [
    "CloudDetectionResult",
    "SarScale",
    "ScaleError",
    "calibrate_sigma0_db",
    "detect_clouds",
    "execute_fusion",
    "lee_filter",
    "otsu_water_mask",
    "reconcile_sar_optical",
    "require_db_scale",
]
