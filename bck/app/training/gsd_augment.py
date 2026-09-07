"""Configurable multi-scale crop and resolution degradation for training images."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from PIL import Image

EUROSAT_NATIVE_GSD_M = 10.0
DEFAULT_MAX_SIM_GSD_M = 30.0
DEFAULT_MIN_SIM_GSD_M = 0.5


@dataclass(frozen=True)
class GSDAugmentConfig:
    """Physical source/target GSD bounds and model output settings."""

    source_gsd_m: float = EUROSAT_NATIVE_GSD_M
    max_gsd_m: float = DEFAULT_MAX_SIM_GSD_M
    min_gsd_m: float = DEFAULT_MIN_SIM_GSD_M
    output_size: int = 448
    min_crop_pixels: int = 2
    sampling: str = "log_uniform"

    def resolved_min_gsd_m(self) -> float:
        """Return the configured lower target-GSD bound."""
        return self.min_gsd_m

    def __post_init__(self) -> None:
        """Validate augmentation bounds and output dimensions."""
        for name, value in (
            ("source_gsd_m", self.source_gsd_m),
            ("min_gsd_m", self.min_gsd_m),
            ("max_gsd_m", self.max_gsd_m),
        ):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be positive and finite, got {value}")
        if self.max_gsd_m < self.min_gsd_m:
            raise ValueError("max_gsd_m must be greater than or equal to min_gsd_m")
        if self.output_size <= 0 or self.min_crop_pixels <= 0:
            raise ValueError("output_size and min_crop_pixels must be positive")
        if self.sampling != "log_uniform":
            raise ValueError("sampling must be 'log_uniform'")


class MultiScaleGSDAugment:
    """Apply a seeded scale proxy for fine targets and low-pass degradation for coarse targets."""

    def __init__(self, config: GSDAugmentConfig | None = None) -> None:
        self.config = config or GSDAugmentConfig()

    def sample_gsd_m(self, rng: random.Random) -> float:
        """Sample a target GSD uniformly in log space across configured bounds."""
        low = math.log(self.config.resolved_min_gsd_m())
        high = math.log(self.config.max_gsd_m)
        return math.exp(rng.uniform(low, high))

    def _crop_for_finer_scale(
        self, image: Image.Image, target_gsd_m: float, rng: random.Random
    ) -> Image.Image:
        """Crop a source-proportional window to proxy finer apparent spatial scale."""
        source = image if image.mode == "RGB" else image.convert("RGB")
        width, height = source.size
        fraction = min(1.0, target_gsd_m / self.config.source_gsd_m)
        crop_width = max(self.config.min_crop_pixels, round(width * fraction))
        crop_height = max(self.config.min_crop_pixels, round(height * fraction))
        crop_width = min(width, crop_width)
        crop_height = min(height, crop_height)
        left = rng.randint(0, width - crop_width)
        top = rng.randint(0, height - crop_height)
        return source.crop((left, top, left + crop_width, top + crop_height)).resize(
            (self.config.output_size, self.config.output_size), Image.Resampling.BICUBIC
        )

    def degrade_to_gsd(
        self, image: Image.Image, target_gsd_m: float, rng: random.Random | None = None
    ) -> Image.Image:
        """Transform an image to the target GSD proxy and configured model dimensions."""
        if not math.isfinite(target_gsd_m) or target_gsd_m <= 0:
            raise ValueError("target_gsd_m must be positive and finite")
        cfg = self.config
        if target_gsd_m < cfg.min_gsd_m or target_gsd_m > cfg.max_gsd_m:
            raise ValueError("target_gsd_m is outside the configured GSD range")
        active_rng = rng if rng is not None else random.Random(0)
        if target_gsd_m < cfg.source_gsd_m:
            return self._crop_for_finer_scale(image, target_gsd_m, active_rng)

        source = image if image.mode == "RGB" else image.convert("RGB")
        width, height = source.size
        retained = cfg.source_gsd_m / target_gsd_m
        low_width = max(1, round(width * retained))
        low_height = max(1, round(height * retained))
        low = source.resize((low_width, low_height), Image.Resampling.BILINEAR)
        return low.resize((cfg.output_size, cfg.output_size), Image.Resampling.BICUBIC)

    def __call__(
        self, image: Image.Image, rng: random.Random | None = None
    ) -> tuple[Image.Image, float]:
        """Return a transformed image and the derived effective GSD used for conditioning."""
        active_rng = rng if rng is not None else random.Random()
        target_gsd_m = self.sample_gsd_m(active_rng)
        return self.degrade_to_gsd(image, target_gsd_m, active_rng), target_gsd_m
