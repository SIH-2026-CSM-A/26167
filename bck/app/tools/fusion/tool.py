"""Cross-modal optical and SAR fusion execution tool."""

from __future__ import annotations

import time

import numpy as np
import rasterio
from PIL import Image

from app.contracts import Evidence, ImageInput
from app.tools.fusion.cloud_detector import CloudDetectionResult, detect_clouds
from app.tools.fusion.despeckle import lee_filter
from app.tools.fusion.reconcile import reconcile_sar_optical
from app.tools.fusion.sar_scale import SarScale
from app.tools.fusion.sar_water_mask import otsu_water_mask

_NOISE_VARIANCE = 0.005


def execute_fusion(
    optical_source: ImageInput,
    sar_source: ImageInput,
    *,
    noise_variance: float = _NOISE_VARIANCE,
    sar_scale: SarScale = SarScale.DB,
    cloud_result: CloudDetectionResult | None = None,
) -> list[Evidence]:
    """Execute end-to-end cross-modal fusion between co-registered optical and SAR imagery.

    1. Load SAR VV backscatter from disk.
    2. Apply 7x7 Lee despeckle filter.
    3. Compute Otsu water mask.
    4. Compute or reuse optical cloud detection result.
    5. Reconcile optical and SAR into region-specific Evidence items.
    """
    started = time.perf_counter()

    with rasterio.open(sar_source.path) as src:
        sar_arr = src.read(1).astype(np.float64)

    # Handle NaNs in SAR backscatter (e.g. chipped margins / nodata)
    has_nans = np.isnan(sar_arr).any()
    if has_nans:
        valid_sar = ~np.isnan(sar_arr)
        if not valid_sar.any():
            raise ValueError(f"SAR asset '{sar_source.id}' contains only NaN values.")
        fill_val = float(np.nanmedian(sar_arr))
        clean_sar = np.where(valid_sar, sar_arr, fill_val)
        despeckled = lee_filter(clean_sar, sar_scale, noise_variance=noise_variance)
        water_mask = otsu_water_mask(despeckled, sar_scale)
        # Re-mask NaNs so nodata is not labeled as water
        water_mask = water_mask & valid_sar
    else:
        despeckled = lee_filter(sar_arr, sar_scale, noise_variance=noise_variance)
        water_mask = otsu_water_mask(despeckled, sar_scale)

    if cloud_result is None:
        with rasterio.open(optical_source.path) as src:
            opt_arr = src.read()

        band_count = opt_arr.shape[0]
        if band_count in (10, 13):
            reflectance = np.moveaxis(opt_arr, 0, -1).astype(np.float32) / 10000.0
            cloud_result = detect_clouds.get(reflectance)
        else:
            cached_fraction = optical_source.metadata.get("cloud_fraction")
            if cached_fraction is not None:
                cf = float(cached_fraction)
                prob = np.full(despeckled.shape, cf, dtype=np.float32)
                c_mask = prob >= 0.4 if cf > 0.0 else np.zeros(despeckled.shape, dtype=bool)
                cloud_result = CloudDetectionResult(probability=prob, mask=c_mask)
            else:
                prob = np.zeros(despeckled.shape, dtype=np.float32)
                c_mask = np.zeros(despeckled.shape, dtype=bool)
                cloud_result = CloudDetectionResult(probability=prob, mask=c_mask)

    # Ensure optical cloud mask matches SAR dimensions if co-registered
    # rasters differ in grid resolution
    if cloud_result.mask.shape != despeckled.shape:
        pil_mask = Image.fromarray(cloud_result.mask).resize(
            (despeckled.shape[1], despeckled.shape[0]), resample=Image.Resampling.NEAREST
        )
        pil_prob = Image.fromarray(cloud_result.probability).resize(
            (despeckled.shape[1], despeckled.shape[0]), resample=Image.Resampling.BILINEAR
        )
        cloud_result = CloudDetectionResult(
            probability=np.asarray(pil_prob, dtype=np.float32),
            mask=np.asarray(pil_mask, dtype=bool),
        )

    evidence_list = reconcile_sar_optical(despeckled, water_mask, cloud_result)

    # Attach image provenance to evidence payloads
    augmented_list: list[Evidence] = []
    for ev in evidence_list:
        payload = dict(ev.payload)
        payload["source_optical_id"] = optical_source.id
        payload["source_sar_id"] = sar_source.id
        payload["source_asset_ids"] = [optical_source.id, sar_source.id]
        payload["source_asset_id"] = sar_source.id
        augmented_list.append(
            ev.model_copy(
                update={
                    "payload": payload,
                    "timing": round(time.perf_counter() - started, 4),
                }
            )
        )

    return augmented_list
