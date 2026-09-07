"""AASH-004: multi-scale ground-sample-distance (GSD) crop/degrade augmentation.

Simulates viewing the same real scene at a coarser ground resolution than the
source imagery by low-pass degradation -- downsample to fewer real pixels, then
resample back up to the model input size. The vision projector (mlp1) then sees
each real Sentinel-2 scene across a range of effective GSDs during LoRA
fine-tuning, widening the resolution distribution it is adapted to.

Scope (AASH-004 -- GSD-conditioning + augmentation half; augmentation part only):
- This module is the augmentation mechanism only. The explicit GSD *conditioning
  embedding* at training time, and any §3.3-specified random-crop scale
  schedule, are held for 03-SatQuery-AI-Technical-Implementation.md §3.3, which
  is not available to this ticket. Nothing here encodes a resolution boundary,
  bin edge, or sampling rule from that section.
- Coarsening only. The wired Sentinel-2 training imagery (EuroSAT,
  `Honaker/eurosat_dataset`) is 10 m GSD for its RGB bands; degrading toward a
  coarser GSD is a physically faithful low-pass. Simulating a *finer* GSD than
  the source (the 0.5 m end of the range named in the ticket) cannot be produced
  by resampling and is left to the real Cartosat/RISAT imagery follow-up.
- `max_gsd_m` defaults to 30.0 -- the resolution-range upper bound named in the
  AASH-004 ticket. `min_gsd_m` defaults to the source GSD; no finer bound is
  invented here.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from PIL import Image

# EuroSAT is Sentinel-2 L2A surface reflectance; its RGB bands (B04/B03/B02) are
# 10 m GSD. Documented property of the sensor/dataset, not a project-chosen value.
EUROSAT_NATIVE_GSD_M = 10.0

# Upper bound of the simulated resolution range, per the AASH-004 ticket.
DEFAULT_MAX_SIM_GSD_M = 30.0


@dataclass(frozen=True)
class GSDAugmentConfig:
    """Bounds and output size for one augmentation pass.

    `min_gsd_m` left as None means "start from the source GSD" -- the finest
    resolution that can be simulated without inventing detail.
    """

    source_gsd_m: float = EUROSAT_NATIVE_GSD_M
    max_gsd_m: float = DEFAULT_MAX_SIM_GSD_M
    min_gsd_m: float | None = None
    output_size: int = 448

    def resolved_min_gsd_m(self) -> float:
        return self.source_gsd_m if self.min_gsd_m is None else self.min_gsd_m

    def __post_init__(self) -> None:
        if self.source_gsd_m <= 0:
            raise ValueError(f"source_gsd_m must be > 0, got {self.source_gsd_m}")
        if self.output_size <= 0:
            raise ValueError(f"output_size must be > 0, got {self.output_size}")
        low = self.resolved_min_gsd_m()
        if low < self.source_gsd_m:
            raise ValueError(
                f"min_gsd_m ({low}) is finer than source_gsd_m ({self.source_gsd_m}); "
                "resampling cannot synthesise detail the source does not contain"
            )
        if self.max_gsd_m < low:
            raise ValueError(
                f"max_gsd_m ({self.max_gsd_m}) is coarser-bound below min_gsd_m ({low})"
            )


class MultiScaleGSDAugment:
    """Callable: a source PIL image -> (degraded image at `output_size`, GSD in metres).

    The returned GSD is the effective ground-sample-distance the degraded image
    now represents -- the value a GSD-conditioning embedding would consume once
    §3.3 defines it.
    """

    def __init__(self, config: GSDAugmentConfig | None = None) -> None:
        self.config = config or GSDAugmentConfig()

    def sample_gsd_m(self, rng: random.Random) -> float:
        """Draw a target GSD uniformly across the configured range.

        Uniform-in-metres is this module's default over the narrow 10-30 m span;
        §3.3 may specify a different distribution once available.
        """
        return rng.uniform(self.config.resolved_min_gsd_m(), self.config.max_gsd_m)

    def degrade_to_gsd(self, image: Image.Image, target_gsd_m: float) -> Image.Image:
        """Low-pass `image` so it represents `target_gsd_m`, sized to `output_size`."""
        cfg = self.config
        if target_gsd_m < cfg.source_gsd_m:
            raise ValueError(
                f"target_gsd_m ({target_gsd_m}) is finer than source_gsd_m "
                f"({cfg.source_gsd_m}); nothing to simulate in that direction"
            )
        src = image if image.mode == "RGB" else image.convert("RGB")
        width, height = src.size
        # Fraction of native detail retained: <= 1, smaller = coarser GSD.
        retained = cfg.source_gsd_m / target_gsd_m
        low_width = max(1, round(width * retained))
        low_height = max(1, round(height * retained))
        low = src.resize((low_width, low_height), Image.Resampling.BILINEAR)
        return low.resize((cfg.output_size, cfg.output_size), Image.Resampling.BICUBIC)

    def __call__(
        self, image: Image.Image, rng: random.Random | None = None
    ) -> tuple[Image.Image, float]:
        active_rng = rng if rng is not None else random.Random()
        target_gsd_m = self.sample_gsd_m(active_rng)
        return self.degrade_to_gsd(image, target_gsd_m), target_gsd_m
