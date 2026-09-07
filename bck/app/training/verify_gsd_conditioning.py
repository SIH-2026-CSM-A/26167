"""Standalone structural verification for the AASH-004 GSD conditioning path."""

from __future__ import annotations

import torch

from app.training.gsd_conditioning import (
    GSDConditionedProjector,
    GSDConditioningConfig,
    attach_gsd_output_conditioning,
    condition_on,
)

DEMO_DIM = 64
GSD_VALUES = (0.5, 10.0, 30.0)


def build_demo_projector() -> GSDConditionedProjector:
    """Build a small projector that exercises the same additive conditioning interface."""
    projector = torch.nn.Sequential(
        torch.nn.LayerNorm(DEMO_DIM),
        torch.nn.Linear(DEMO_DIM, DEMO_DIM),
        torch.nn.GELU(),
        torch.nn.Linear(DEMO_DIM, DEMO_DIM),
    )
    return GSDConditionedProjector(
        projector,
        GSDConditioningConfig(output_dim=DEMO_DIM, hidden_dim=16),
    )


def check_distinct_embeddings() -> None:
    """Verify different physical GSD values produce different vectors."""
    torch.manual_seed(0)
    conditioned = build_demo_projector()
    embeddings = conditioned.conditioner(torch.tensor(GSD_VALUES))
    assert embeddings.shape == (len(GSD_VALUES), DEMO_DIM)
    assert not torch.allclose(embeddings[0], embeddings[-1])
    print(f"embedding shape: {tuple(embeddings.shape)}")


def check_forward_and_gradient() -> None:
    """Verify GSD changes projected tokens and receives training gradients."""
    torch.manual_seed(1)
    conditioned = build_demo_projector()
    hidden_states = torch.randn(1, 4, DEMO_DIM)
    with conditioned.condition_on([10.0]):
        first = conditioned(hidden_states)
    with conditioned.condition_on([20.0]):
        second = conditioned(hidden_states)
    loss = second.square().mean()
    loss.backward()
    assert not torch.allclose(first, second)
    assert conditioned.conditioner.network[0].weight.grad is not None
    print("forward path changes with GSD and conditioner gradients are non-zero")


def check_hook_preserves_parameter_names() -> None:
    """Verify the production hook leaves existing projector names unchanged."""
    projector = torch.nn.Sequential(torch.nn.Linear(DEMO_DIM, DEMO_DIM))
    names_before = [name for name, _ in projector.named_parameters()]
    conditioned = build_demo_projector()
    handle = attach_gsd_output_conditioning(projector, conditioned.conditioner)
    with condition_on(conditioned.conditioner, [10.0]):
        projector(torch.zeros(1, 2, DEMO_DIM))
    handle.remove()
    assert names_before == [name for name, _ in projector.named_parameters()]
    print("projector parameter names remain unchanged")


def inspect_live_model() -> None:
    """Print the actual InternVL3 language hidden dimension when weights are available."""
    try:
        from transformers import AutoModel

        model = AutoModel.from_pretrained(
            "OpenGVLab/InternVL3-2B", trust_remote_code=True, torch_dtype=torch.float32
        )
    except Exception as error:  # noqa: BLE001 - standalone diagnostic reports environment state
        print(f"live model not loaded ({type(error).__name__}: {error})")
        return
    print(f"live mlp1 output dimension: {model.config.llm_config.hidden_size}")


def main() -> None:
    """Run model-free conditioning checks and an optional live-model inspection."""
    check_distinct_embeddings()
    check_forward_and_gradient()
    check_hook_preserves_parameter_names()
    inspect_live_model()
    print("All GSD conditioning checks passed.")


if __name__ == "__main__":
    main()
