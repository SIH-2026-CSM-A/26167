"""AASH-004 verification: multi-scale GSD augmentation against real EuroSAT imagery.

Standalone check, not the training loop. Streams real Sentinel-2 EuroSAT scenes
(`Honaker/eurosat_dataset`, the same source the mlp1 vision LoRA trains on), runs
`MultiScaleGSDAugment` over them, and reports the simulated-GSD distribution plus
a before/after montage written to `data/` for visual inspection.

Run: `python -m app.training.verify_gsd_augment`.
"""

from __future__ import annotations

import random
import statistics

from datasets import load_dataset
from PIL import Image

from app.training.gsd_augment import (
    EUROSAT_NATIVE_GSD_M,
    GSDAugmentConfig,
    MultiScaleGSDAugment,
)

DATASET_ID = "Honaker/eurosat_dataset"
N_SAMPLES = 200
MONTAGE_ROWS = 4
MONTAGE_TILE = 160
MONTAGE_PATH = "data/aash004_gsd_augment_sample.png"
SEED = 42


def build_montage(pairs: list[tuple[Image.Image, Image.Image]]) -> Image.Image:
    """Source (left) beside its degraded counterpart (right), one pair per row."""
    tile = MONTAGE_TILE
    canvas = Image.new("RGB", (tile * 2, tile * len(pairs)), (16, 16, 16))
    for row, (src_img, degraded_img) in enumerate(pairs):
        canvas.paste(src_img, (0, row * tile))
        canvas.paste(degraded_img, (tile, row * tile))
    return canvas


def main() -> None:
    cfg = GSDAugmentConfig(source_gsd_m=EUROSAT_NATIVE_GSD_M, output_size=MONTAGE_TILE)
    augment = MultiScaleGSDAugment(cfg)
    rng = random.Random(SEED)

    print(f"Streaming {DATASET_ID} (real Sentinel-2 EuroSAT)...")
    ds = load_dataset(DATASET_ID, split="train", streaming=True)
    ds = ds.shuffle(seed=SEED, buffer_size=5000)
    samples = list(ds.take(N_SAMPLES))
    print(f"Pulled {len(samples)} real scenes.")

    gsds: list[float] = []
    montage_pairs: list[tuple[Image.Image, Image.Image]] = []
    montage_gsds: list[float] = []
    native_sizes: set[tuple[int, int]] = set()

    for i, ex in enumerate(samples):
        src = ex["image"]
        native_sizes.add(src.size)
        degraded, gsd_m = augment(src, rng)
        gsds.append(gsd_m)
        if i < MONTAGE_ROWS:
            src_tile = src.convert("RGB").resize(
                (MONTAGE_TILE, MONTAGE_TILE), Image.Resampling.BICUBIC
            )
            montage_pairs.append((src_tile, degraded))
            montage_gsds.append(gsd_m)

    print("\n=== source ===")
    print(f"native pixel sizes seen : {sorted(native_sizes)}")
    print(f"native GSD (documented) : {EUROSAT_NATIVE_GSD_M} m")

    print("\n=== simulated GSD distribution ===")
    print(f"n               : {len(gsds)}")
    print(f"min / max       : {min(gsds):.2f} m / {max(gsds):.2f} m")
    print(f"mean / median   : {statistics.mean(gsds):.2f} m / {statistics.median(gsds):.2f} m")
    print(f"configured band : {cfg.resolved_min_gsd_m():.1f}-{cfg.max_gsd_m:.1f} m")
    below = [g for g in gsds if g < cfg.resolved_min_gsd_m() - 1e-9]
    above = [g for g in gsds if g > cfg.max_gsd_m + 1e-9]
    print(f"out-of-band     : {len(below)} below min, {len(above)} above max")

    montage = build_montage(montage_pairs)
    montage.save(MONTAGE_PATH)
    montage_labels = ", ".join(f"{g:.1f} m" for g in montage_gsds)
    print(f"\nBefore/after montage written: {MONTAGE_PATH} ({montage.width}x{montage.height})")
    print(f"montage rows simulate: {montage_labels}")


if __name__ == "__main__":
    main()
