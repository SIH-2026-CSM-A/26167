"""Continuous numeric GSD conditioning for the InternVL vision projector."""

from __future__ import annotations

import json
import math
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from numbers import Real
from pathlib import Path

import torch
from torch import nn

CONDITIONER_STATE_FILENAME = "gsd_conditioner.pt"
CONDITIONER_CONFIG_FILENAME = "gsd_conditioner.json"


def validate_gsd_m(value: object, field_name: str = "gsd_m") -> float:
    """Return a positive finite GSD in metres or raise an explicit validation error."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a numeric value in metres")
    gsd_m = float(value)
    if not math.isfinite(gsd_m) or gsd_m <= 0:
        raise ValueError(f"{field_name} must be positive and finite, got {value!r}")
    return gsd_m


def _gsd_tensor(values: object, device: torch.device | None = None) -> torch.Tensor:
    """Convert scalar or one-dimensional GSD metadata into a validated tensor."""
    if isinstance(values, torch.Tensor):
        if values.dtype == torch.bool:
            raise TypeError("gsd_m must be a numeric value in metres, not boolean")
        tensor = values.detach().to(device=device, dtype=torch.float32)
    elif isinstance(values, (list, tuple)):
        tensor = torch.tensor(values, device=device)
        if tensor.dtype == torch.bool:
            raise TypeError("gsd_m must be a numeric value in metres, not boolean")
        tensor = tensor.to(dtype=torch.float32)
    else:
        tensor = torch.tensor([validate_gsd_m(values)], device=device, dtype=torch.float32)
    if tensor.ndim == 0:
        tensor = tensor.reshape(1)
    if tensor.ndim != 1 or tensor.numel() == 0:
        raise ValueError("gsd_m must be a non-empty scalar or one-dimensional sequence")
    if not torch.isfinite(tensor).all() or (tensor <= 0).any():
        raise ValueError("gsd_m must contain only positive finite values")
    return tensor


@dataclass(frozen=True)
class GSDConditioningConfig:
    """Configuration for log-space GSD normalization and the learnable encoder."""

    output_dim: int
    min_gsd_m: float = 0.5
    max_gsd_m: float = 30.0
    hidden_dim: int = 64

    def __post_init__(self) -> None:
        """Validate conditioning bounds and dimensions at configuration creation."""
        min_gsd_m = validate_gsd_m(self.min_gsd_m, "min_gsd_m")
        max_gsd_m = validate_gsd_m(self.max_gsd_m, "max_gsd_m")
        if max_gsd_m <= min_gsd_m:
            raise ValueError("max_gsd_m must be greater than min_gsd_m")
        if self.hidden_dim <= 0 or self.output_dim <= 0:
            raise ValueError("hidden_dim and output_dim must be positive")


class GSDConditioner(nn.Module):
    """Encode validated GSD values into vectors with the configured output width."""

    def __init__(self, config: GSDConditioningConfig) -> None:
        super().__init__()
        self.config = config
        self._active_gsd: object | None = None
        self.network = nn.Sequential(
            nn.Linear(1, config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.output_dim),
        )

    def normalize(self, values: object) -> torch.Tensor:
        """Normalize GSD values to approximately [-1, 1] in natural-log space."""
        tensor = _gsd_tensor(values)
        minimum = math.log(self.config.min_gsd_m)
        maximum = math.log(self.config.max_gsd_m)
        if (tensor < self.config.min_gsd_m).any() or (tensor > self.config.max_gsd_m).any():
            raise ValueError(
                f"gsd_m must be within {self.config.min_gsd_m:g}-{self.config.max_gsd_m:g} metres"
            )
        return ((tensor.log() - minimum) / (maximum - minimum) * 2.0 - 1.0).unsqueeze(-1)

    def forward(self, values: object) -> torch.Tensor:
        """Return one learnable conditioning vector per validated GSD value."""
        normalized = self.normalize(values).to(self.network[0].weight.device)
        return self.network(normalized)


class GSDConditionedProjector(nn.Module):
    """Add a GSD embedding to projected visual tokens during an explicit context."""

    def __init__(self, projector: nn.Module, config: GSDConditioningConfig) -> None:
        super().__init__()
        self.projector = projector
        self.conditioner = GSDConditioner(config)
        self._active_gsd: object | None = None

    @contextmanager
    def condition_on(self, values: object) -> Iterator[None]:
        """Set GSD metadata for one forward pass and restore prior state afterward."""
        previous = self._active_gsd
        self._active_gsd = values
        try:
            yield
        finally:
            self._active_gsd = previous

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        """Project visual tokens and add one GSD vector to every token in each sample."""
        if self._active_gsd is None:
            raise ValueError("GSD conditioning requires gsd_m metadata via condition_on()")
        projected = self.projector(hidden_states)
        conditioning = self.conditioner(self._active_gsd).to(
            device=projected.device, dtype=projected.dtype
        )
        if conditioning.shape[0] == 1 and projected.shape[0] > 1:
            conditioning = conditioning.expand(projected.shape[0], -1)
        if conditioning.shape[0] != projected.shape[0]:
            raise ValueError("one gsd_m value is required for each projected image batch item")
        return projected + conditioning.unsqueeze(1)


def attach_gsd_output_conditioning(
    target: nn.Module, conditioner: GSDConditioner
) -> torch.utils.hooks.RemovableHandle:
    """Add conditioning after an existing projector without changing LoRA module names."""

    def _hook(
        _module: nn.Module, _inputs: tuple[object, ...], output: torch.Tensor
    ) -> torch.Tensor:
        if conditioner._active_gsd is None:
            raise ValueError("GSD conditioning requires gsd_m metadata via condition_on()")
        conditioning = conditioner(conditioner._active_gsd).to(
            device=output.device, dtype=output.dtype
        )
        if conditioning.shape[0] == 1 and output.shape[0] > 1:
            conditioning = conditioning.expand(output.shape[0], -1)
        if conditioning.shape[0] != output.shape[0]:
            raise ValueError("one gsd_m value is required for each projected image batch item")
        return output + conditioning.unsqueeze(1)

    return target.register_forward_hook(_hook)


@contextmanager
def condition_on(conditioner: GSDConditioner, values: object) -> Iterator[None]:
    """Set GSD metadata for a hook-based model forward and restore prior state afterward."""
    previous = conditioner._active_gsd
    conditioner._active_gsd = values
    try:
        yield
    finally:
        conditioner._active_gsd = previous


def save_gsd_conditioner(conditioner: GSDConditioner, output_dir: str | Path) -> None:
    """Persist conditioner weights and normalization metadata beside the LoRA adapter."""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    torch.save(conditioner.state_dict(), path / CONDITIONER_STATE_FILENAME)
    (path / CONDITIONER_CONFIG_FILENAME).write_text(
        json.dumps(asdict(conditioner.config), indent=2) + "\n", encoding="utf-8"
    )


def load_gsd_conditioner(output_dir: str | Path) -> GSDConditioner:
    """Restore a conditioner from the state and configuration saved beside an adapter."""
    path = Path(output_dir)
    config_data = json.loads((path / CONDITIONER_CONFIG_FILENAME).read_text(encoding="utf-8"))
    conditioner = GSDConditioner(GSDConditioningConfig(**config_data))
    state = torch.load(path / CONDITIONER_STATE_FILENAME, map_location="cpu", weights_only=True)
    conditioner.load_state_dict(state)
    return conditioner
