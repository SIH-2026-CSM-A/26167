"""Public GeoTIFF ingestion boundary used by the integration pipeline."""

from app.ingestion.eo_gates import (
    EoGate,
    EoGateResult,
    EoGateStatus,
    evaluate_eo_gates,
)
from app.ingestion.raster import (
    IngestedRaster,
    InvalidRasterError,
    RasterIngestionError,
    RasterUpload,
    UnsupportedRasterError,
    classify_modality,
    ingest_raster,
)

__all__ = [
    "EoGate",
    "EoGateResult",
    "EoGateStatus",
    "IngestedRaster",
    "InvalidRasterError",
    "RasterIngestionError",
    "RasterUpload",
    "UnsupportedRasterError",
    "classify_modality",
    "evaluate_eo_gates",
    "ingest_raster",
]
