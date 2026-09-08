"""GeoTIFF ingestion and deterministic visual-preview generation."""

from __future__ import annotations

import atexit
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import ColorInterp, Resampling
from rasterio.errors import RasterioIOError
from rasterio.io import MemoryFile

from app.contracts import ImageInput, Modality

SUPPORTED_TIFF_SUFFIXES = frozenset({".tif", ".tiff"})
PREVIEW_MAX_DIMENSION = 1024
LOWER_VISUAL_PERCENTILE = 2.0
UPPER_VISUAL_PERCENTILE = 98.0

# B4: metadata-only modality classification. Real-fixture-verified, not guessed —
# tests/fixtures/Bolivia_103757_S1Hand.tif carries band descriptions exactly
# ("VV", "VH"); Bolivia_103757_S2Hand.tif carries exactly ("B1", ..., "B8A", ...,
# "B12"). Band count alone is not used as a signal: a single-band optical
# panchromatic scene and a single-pol SAR scene are structurally indistinguishable
# by count, so trusting count here would be exactly the kind of guessed rule this
# ticket exists to avoid.
_SAR_POLARIZATION_PATTERN = re.compile(r"\b(VV|VH|HH|HV)\b", re.IGNORECASE)
_OPTICAL_BAND_NAME_PATTERN = re.compile(r"\bB(?:[0-9]|1[0-2]|8A)\b", re.IGNORECASE)
_OPTICAL_COLORS = frozenset({ColorInterp.red, ColorInterp.green, ColorInterp.blue})


class RasterIngestionError(ValueError):
    """Base error for user-correctable raster ingestion failures."""


class UnsupportedRasterError(RasterIngestionError):
    """Raised when an upload is not a supported TIFF asset."""


class InvalidRasterError(RasterIngestionError):
    """Raised when raster bytes cannot be decoded safely."""


@dataclass(frozen=True, slots=True)
class RasterUpload:
    """Raw uploaded raster retained until real decoding completes."""

    id: str
    filename: str
    content_type: str
    content: bytes
    modality: Modality | None
    """None means the client did not supply a modality: ingestion classifies it
    from raster metadata (see `classify_modality`). A concrete value is a
    client-supplied override, used as-is without re-classification.
    """


@dataclass(frozen=True, slots=True)
class IngestedRaster:
    """Canonical source descriptor paired with a model-ready RGB overview."""

    source: ImageInput
    visual: Image.Image


def classify_modality(dataset: rasterio.io.DatasetReader) -> Modality:
    """Classify sensor modality from raster metadata alone — no pixel values, no LLM call.

    Checks band descriptions and tags for SAR polarization tokens (VV/VH/HH/HV) or
    Sentinel-2-style optical band-name tokens (B1-B12/B8A) first, since those are
    unambiguous when present; falls back to GDAL color interpretation (declared
    Red/Green/Blue) for natural-color rasters that carry neither. Returns
    `Modality.UNKNOWN` rather than guessing when none of these signals are present.
    """
    band_texts: list[str] = []
    for index in range(1, dataset.count + 1):
        description = dataset.descriptions[index - 1]
        if description:
            band_texts.append(description)
        band_texts.extend(str(value) for value in dataset.tags(index).values())
    combined_text = " ".join(band_texts)

    if _SAR_POLARIZATION_PATTERN.search(combined_text):
        return Modality.SAR
    if _OPTICAL_BAND_NAME_PATTERN.search(combined_text):
        return Modality.OPTICAL
    if _OPTICAL_COLORS & set(dataset.colorinterp):
        return Modality.OPTICAL
    return Modality.UNKNOWN


def ingest_raster(upload: RasterUpload) -> IngestedRaster:
    """Decode a TIFF upload, preserve source metadata, and create an RGB overview."""
    _validate_upload(upload)
    try:
        with MemoryFile(upload.content) as memory_file, memory_file.open() as dataset:
            if dataset.driver != "GTiff":
                raise UnsupportedRasterError("uploaded asset is not a GeoTIFF/TIFF raster")
            if upload.modality is not None:
                modality = upload.modality
                modality_source = "client_override"
            else:
                modality = classify_modality(dataset)
                modality_source = "metadata_classifier"
            visual, band_indexes, visualization_method = _build_visual(dataset)
            metadata = _extract_metadata(
                dataset,
                upload,
                band_indexes=band_indexes,
                visualization_method=visualization_method,
            )
            metadata["modality_source"] = modality_source
            source = ImageInput(
                id=upload.id,
                modality=modality,
                format=dataset.driver,
                path=_persist_temp(upload),
                metadata=metadata,
            )
    except UnsupportedRasterError:
        raise
    except (RasterioIOError, ValueError, OSError) as error:
        raise InvalidRasterError(
            f"TIFF '{upload.filename}' could not be read as a raster"
        ) from error
    return IngestedRaster(source=source, visual=visual)


def _persist_temp(upload: RasterUpload) -> str:
    """Write the upload's raw bytes to disk so downstream tools (e.g. BIT) can load by path.

    INTERIM SAFETY NET: nothing downstream currently consumes ImageInput.path, so there
    is no lifecycle owner yet to delete this file at the right time (e.g. after a query
    completes). atexit cleanup here only guards against unbounded accumulation across a
    single process's lifetime -- it is NOT a substitute for real per-request cleanup once
    a consumer is wired up. Follow-up needed when a real consumer reads this path.
    """
    suffix = Path(upload.filename).suffix or ".tif"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(upload.content)
        atexit.register(_cleanup_temp, tmp.name)
        return tmp.name


def _cleanup_temp(path: str) -> None:
    """Best-effort removal of a persisted temp raster on process exit."""
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


def _validate_upload(upload: RasterUpload) -> None:
    """Reject missing identities, names, bytes, and unsupported suffixes early."""
    if not upload.id.strip():
        raise InvalidRasterError("uploaded asset id is required")
    if not upload.filename.strip():
        raise InvalidRasterError("uploaded filename is required")
    if Path(upload.filename).suffix.lower() not in SUPPORTED_TIFF_SUFFIXES:
        raise UnsupportedRasterError("only .tif or .tiff raster uploads are supported")
    if not upload.content:
        raise InvalidRasterError(f"TIFF '{upload.filename}' is empty")


def _build_visual(dataset: rasterio.io.DatasetReader) -> tuple[Image.Image, list[int], str]:
    """Read a bounded overview and convert its selected bands into RGB."""
    if dataset.width <= 0 or dataset.height <= 0 or dataset.count <= 0:
        raise InvalidRasterError("raster must contain at least one non-empty band")

    output_width, output_height = _preview_dimensions(dataset.width, dataset.height)
    band_indexes, natural_rgb = _select_visual_bands(dataset)
    raster = dataset.read(
        band_indexes,
        out_shape=(len(band_indexes), output_height, output_width),
        resampling=Resampling.bilinear,
        masked=True,
    )

    if natural_rgb and all(dataset.dtypes[index - 1] == "uint8" for index in band_indexes):
        rgb = np.ma.filled(raster, 0).clip(0, 255).astype(np.uint8)
        method = "native_rgb"
    else:
        normalized = [_normalize_band(raster[index]) for index in range(raster.shape[0])]
        rgb = np.stack(normalized)
        method = "percentile_normalized_preview"

    if rgb.shape[0] == 1:
        rgb = np.repeat(rgb, 3, axis=0)
    image_array = np.moveaxis(rgb[:3], 0, -1)
    return Image.fromarray(image_array, mode="RGB"), band_indexes, method


def _preview_dimensions(width: int, height: int) -> tuple[int, int]:
    """Bound preview dimensions while preserving the source aspect ratio."""
    largest_dimension = max(width, height)
    if largest_dimension <= PREVIEW_MAX_DIMENSION:
        return width, height
    scale = PREVIEW_MAX_DIMENSION / largest_dimension
    return max(1, round(width * scale)), max(1, round(height * scale))


def _select_visual_bands(dataset: rasterio.io.DatasetReader) -> tuple[list[int], bool]:
    """Prefer declared red/green/blue bands, then deterministic leading bands."""
    color_to_index = {
        color: index
        for index, color in enumerate(dataset.colorinterp, start=1)
        if color in {ColorInterp.red, ColorInterp.green, ColorInterp.blue}
    }
    if all(
        color in color_to_index for color in (ColorInterp.red, ColorInterp.green, ColorInterp.blue)
    ):
        return [
            color_to_index[ColorInterp.red],
            color_to_index[ColorInterp.green],
            color_to_index[ColorInterp.blue],
        ], True
    if dataset.count >= 3:
        return [1, 2, 3], False
    return [1], False


def _normalize_band(band: np.ma.MaskedArray) -> np.ndarray:
    """Scale one raster band into byte range using valid-data percentiles."""
    values = np.asarray(band.compressed(), dtype=np.float32)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return np.zeros(band.shape, dtype=np.uint8)

    lower, upper = np.percentile(values, [LOWER_VISUAL_PERCENTILE, UPPER_VISUAL_PERCENTILE])
    if upper <= lower:
        return np.zeros(band.shape, dtype=np.uint8)
    filled = band.astype(np.float32).filled(np.nan)
    scaled = np.clip((filled - lower) / (upper - lower), 0.0, 1.0)
    return np.nan_to_num(scaled * 255.0, nan=0.0).astype(np.uint8)


def _extract_metadata(
    dataset: rasterio.io.DatasetReader,
    upload: RasterUpload,
    *,
    band_indexes: list[int],
    visualization_method: str,
) -> dict[str, object]:
    """Extract only source facts reported by Rasterio and the actual upload."""
    dtypes = list(dataset.dtypes)
    dtype: str | list[str] = dtypes[0] if len(set(dtypes)) == 1 else dtypes
    transform = dataset.transform
    return {
        "filename": upload.filename,
        "size_bytes": len(upload.content),
        "content_type": upload.content_type,
        "width": dataset.width,
        "height": dataset.height,
        "band_count": dataset.count,
        "dtype": dtype,
        "crs": dataset.crs.to_string() if dataset.crs else None,
        "bounds": list(dataset.bounds),
        "transform": [
            transform.a,
            transform.b,
            transform.c,
            transform.d,
            transform.e,
            transform.f,
        ],
        "nodata": dataset.nodata,
        "file_format": dataset.driver,
        "visualization": {
            "band_indexes": band_indexes,
            "method": visualization_method,
        },
    }
