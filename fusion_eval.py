"""
Fusion water-detection accuracy vs. Sen1Floods11 ground truth (full 512x512 scene).
"""

import sys
sys.path.insert(0, "bck")

import numpy as np
import rasterio

from app.tools.fusion.despeckle import lee_filter
from app.tools.fusion.sar_water_mask import otsu_water_mask
from app.tools.fusion.cloud_detector import detect_clouds
from app.tools.fusion.reconcile import reconcile_sar_optical
from app.tools.fusion.sar_scale import SarScale

FIXTURES = "bck/tests/fixtures"
S1_PATH = f"{FIXTURES}/Bolivia_103757_S1Hand.tif"
S2_PATH = f"{FIXTURES}/Bolivia_103757_S2Hand.tif"
LABEL_PATH = f"{FIXTURES}/Bolivia_103757_LabelHand.tif"
NOISE_VARIANCE = 0.005


def load_full_scene():
    with rasterio.open(S1_PATH) as src:
        vv = src.read(1).astype(np.float64)
    with rasterio.open(S2_PATH) as src:
        s2 = src.read()
    with rasterio.open(LABEL_PATH) as src:
        label = src.read(1)
    return vv, s2, label


def compute_metrics(predicted, ground_truth, valid_mask):
    pred = predicted[valid_mask]
    gt = ground_truth[valid_mask].astype(bool)

    tp = int((pred & gt).sum())
    fp = int((pred & ~gt).sum())
    fn = int((~pred & gt).sum())
    tn = int((~pred & ~gt).sum())

    iou = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else float("nan")
    precision = tp / (tp + fp) if (tp + fp) > 0 else float("nan")
    recall = tp / (tp + fn) if (tp + fn) > 0 else float("nan")
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else float("nan")
    accuracy = (tp + tn) / (tp + fp + fn + tn)

    return {
        "n_valid_pixels": int(valid_mask.sum()),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "iou": iou, "precision": precision, "recall": recall,
        "f1": f1, "accuracy": accuracy,
    }


def main():
    print("Loading full 512x512 Bolivia_103757 scene...")
    vv, s2, label = load_full_scene()

    sar_valid_mask = ~np.isnan(vv)
    label_valid_mask = label != -1
    eval_valid_mask = sar_valid_mask & label_valid_mask

    print(f"SAR valid pixels: {int(sar_valid_mask.sum())} / {vv.size} "
          f"({100*sar_valid_mask.mean():.1f}%)")
    print(f"Label valid pixels: {int(label_valid_mask.sum())} / {label.size} "
          f"({100*label_valid_mask.mean():.1f}%)")
    print(f"Pixels usable for eval (both valid): {int(eval_valid_mask.sum())} "
          f"({100*eval_valid_mask.mean():.1f}%)")
    print(f"Ground truth water fraction (of eval-valid pixels): "
          f"{(label[eval_valid_mask] == 1).mean():.4f}")

    print("\nRunning SAR despeckle + Otsu water classification (SAR-valid region only)...")
    despeckled = lee_filter(
        vv, SarScale.DB, noise_variance=NOISE_VARIANCE, valid_mask=sar_valid_mask
    )
    water_pred = otsu_water_mask(despeckled, SarScale.DB, valid_mask=sar_valid_mask)

    print("\n=== SAR-derived water mask vs. Sen1Floods11 ground truth (full scene) ===")
    metrics = compute_metrics(water_pred, label, eval_valid_mask)
    for k, v in metrics.items():
        print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

    print("\nRunning cloud detection + reconciliation...")
    reflectance = np.moveaxis(s2, 0, -1).astype(np.float32) / 10000.0
    cloud_result = detect_clouds(reflectance)
    evidence_list = reconcile_sar_optical(
        despeckled, water_pred, cloud_result, valid_mask=sar_valid_mask
    )

    print(f"\nReconciliation produced {len(evidence_list)} region(s):")
    for ev in evidence_list:
        print(f"  region={ev.payload['region']}, confidence={ev.confidence:.4f}, "
              f"optical_inconclusive={ev.payload['optical_inconclusive']}")

    if len(evidence_list) == 2:
        cloud_mask = cloud_result.mask
        clear_region_valid = eval_valid_mask & ~cloud_mask
        cloud_region_valid = eval_valid_mask & cloud_mask

        print("\n=== Accuracy split by region ===")
        print(f"\nClear region ({int(clear_region_valid.sum())} valid px):")
        for k, v in compute_metrics(water_pred, label, clear_region_valid).items():
            print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

        print(f"\nCloud-affected region ({int(cloud_region_valid.sum())} valid px):")
        for k, v in compute_metrics(water_pred, label, cloud_region_valid).items():
            print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")
    else:
        print("\nOnly one region (no cloud cover detected) -- no split to report.")


if __name__ == "__main__":
    main()
