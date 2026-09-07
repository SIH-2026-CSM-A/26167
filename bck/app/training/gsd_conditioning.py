"""AASH-004: explicit GSD-conditioning embedding for the mlp1 vision projector.

Spec confirmed by the team lead (ybaddam8-png) on 2026-09-07 -- quoted here, not
invented:

1. Embedding form -- "sinusoidal/Fourier encoding of continuous log(GSD), not a
   binned lookup table -- a lookup collapses to one constant vector when
   training only ever sees discrete augmented values, giving zero real
   conditioning signal. Fourier over log-GSD extrapolates smoothly to unseen
   values (Cartosat 0.5-2m, RISAT) at eval time."
2. Injection point -- "FiLM-style per-channel scale+shift applied to mlp1's
   input, derived from the GSD embedding. Do not touch the vision tower (frozen
   InternViT, out of scope) and do not add a soft LLM token (too invasive this
   close to deadline). Reuses the same mlp1.1/mlp1.3 layers already
   LoRA-targeted."
3. Dimension -- "read mlp1's actual input feature dim live from the loaded
   InternVL3-2B model at startup (e.g. via the relevant Linear layer's
   .in_features) -- do not hardcode a number, since none is logged anywhere in
   this repo."
4. Sub-10m -- not simulated in training; the fine end (Cartosat/RISAT 0.5-2m) is
   deferred to real imagery in the separate domain-gap test.
5. Signal source -- consumes the per-step `sim_gsd_m` already produced by
   `MultiScaleGSDAugment` in `train_lora_mlp1_vision.py`; not recomputed here.

Formula choices (each cited or read live, nothing invented):
- Sinusoidal encoding uses the canonical geometric-wavelength schedule of
  Vaswani et al. 2017 ("Attention Is All You Need", base 10000). Its only free
  parameter is the encoding width, which is tied to mlp1's input dim (read live
  per point 3) -- so a single Linear maps encoding -> [scale, shift].
- `log` is the natural logarithm.
- Over the natural-log-GSD span the augmentation exercises (log 10 .. log 30
  ~= 2.30 .. 3.40) every schedule wavelength (>= 2 pi) exceeds the span, so the
  encoding is a smooth monotonic lift with no aliasing -- the smooth-
  extrapolation property point 1 asks for, carried down to log 0.5 ~= -0.69.
- FiLM generator is a single Linear, zero-initialised, with the scale read as
  `1 + gamma`; training therefore starts at exact identity (scale 1, shift 0),
  the standard identity-init for FiLM (Perez et al. 2018, "FiLM: Visual
  Reasoning with a General Conditioning Layer").
"""

from __future__ import annotations

import math

import torch
from torch import nn

SINUSOIDAL_BASE = 10000.0  # Vaswani et al. 2017


def sinusoidal_encoding(values: torch.Tensor, dim: int, base: float = SINUSOIDAL_BASE) -> torch.Tensor:
    """Vaswani et al. 2017 sinusoidal encoding of a 1-D tensor of scalars.

    `values` is shape (B,); returns (B, dim). `dim` must be even.
    """
    if dim % 2 != 0:
        raise ValueError(f"sinusoidal encoding dim must be even, got {dim}")
    half = dim // 2
    exponents = torch.arange(half, device=values.device, dtype=torch.float32) / half
    inv_freq = torch.exp(-exponents * math.log(base))  # (half,)
    angles = values.float().unsqueeze(1) * inv_freq.unsqueeze(0)  # (B, half)
    return torch.cat([torch.sin(angles), torch.cos(angles)], dim=1)  # (B, dim)


def mlp1_input_dim(mlp1: nn.Module) -> int:
    """The `.in_features` of the first Linear inside `mlp1` -- read live, never hardcoded.

    Call this on the raw model before any PEFT/LoRA wrapping, while the layer is
    still a plain `nn.Linear`.
    """
    for module in mlp1.modules():
        if isinstance(module, nn.Linear):
            return module.in_features
    raise ValueError("no nn.Linear found inside mlp1 to read an input dimension from")


class GSDFiLMConditioner(nn.Module):
    """Scalar GSD (metres) -> per-channel FiLM (scale, shift) for an mlp1-input feature vector.

    The current batch's GSD is supplied out-of-band via `set_gsd(...)`: it is not
    a model input, and InternVL3-2B's forward signature is fixed.
    """

    def __init__(self, num_channels: int) -> None:
        super().__init__()
        if num_channels % 2 != 0:
            raise ValueError(f"num_channels must be even for the encoding, got {num_channels}")
        self.num_channels = num_channels
        # encoding (num_channels) -> concat[scale, shift] (2 * num_channels).
        # Zero-init => identity modulation (scale = 1 + 0, shift = 0) at step 0.
        self.to_film = nn.Linear(num_channels, 2 * num_channels)
        nn.init.zeros_(self.to_film.weight)
        nn.init.zeros_(self.to_film.bias)
        self._gsd_m: torch.Tensor | None = None

    def set_gsd(self, gsd_m: torch.Tensor) -> None:
        """Register the GSD(s), in metres, for the next forward. Shape (B,) or scalar."""
        self._gsd_m = gsd_m

    def film_params(self, gsd_m: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        encoded = sinusoidal_encoding(torch.log(gsd_m.float()), self.num_channels)
        scale_shift = self.to_film(encoded.to(self.to_film.weight.dtype))
        gamma, beta = scale_shift.chunk(2, dim=-1)
        return 1.0 + gamma, beta

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        """Apply FiLM to `features` (shape (B, ..., num_channels)) using the registered GSD."""
        if self._gsd_m is None:
            raise RuntimeError("GSDFiLMConditioner.forward() called before set_gsd()")
        gsd_m = self._gsd_m
        if gsd_m.dim() == 0:
            gsd_m = gsd_m.reshape(1)
        if gsd_m.shape[0] == 1 and features.shape[0] > 1:
            gsd_m = gsd_m.expand(features.shape[0])
        scale, shift = self.film_params(gsd_m.to(features.device))
        while scale.dim() < features.dim():
            scale = scale.unsqueeze(1)
            shift = shift.unsqueeze(1)
        return features.to(scale.dtype) * scale + shift


def attach_gsd_film(
    mlp1: nn.Module, conditioner: GSDFiLMConditioner
) -> torch.utils.hooks.RemovableHandle:
    """Install `conditioner` on `mlp1`'s input via a forward pre-hook.

    A pre-hook (rather than replacing `mlp1`) keeps every LoRA parameter name
    under `mlp1` unchanged, so `save_pretrained` on the PEFT model is unaffected.
    The conditioner's own weights live outside the PEFT model and must be added
    to the optimizer and checkpointed separately.
    """

    def _pre_hook(_module: nn.Module, args: tuple[object, ...]) -> tuple[object, ...]:
        features, *rest = args
        return (conditioner(features), *rest)

    return mlp1.register_forward_pre_hook(_pre_hook)
