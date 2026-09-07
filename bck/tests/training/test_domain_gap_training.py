"""Focused AASH-004 tests for GSD conditioning and multi-scale transforms."""

from __future__ import annotations

import importlib
import math
import random
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import torch
from PIL import Image, ImageChops
from transformers import AutoModel, AutoTokenizer

from app.training.gsd_augment import GSDAugmentConfig, MultiScaleGSDAugment
from app.training.gsd_conditioning import (
    GSDConditionedProjector,
    GSDConditioner,
    GSDConditioningConfig,
    attach_gsd_output_conditioning,
    condition_on,
    load_gsd_conditioner,
    save_gsd_conditioner,
    validate_gsd_m,
)
from app.training.train_lora_mlp1_vision import (
    attach_sample_gsd,
    build_transform,
    preprocess_image_for_split,
)


def test_valid_gsd_is_normalized_and_embedded_to_requested_width() -> None:
    """A finite positive sample GSD produces one embedding of configured width."""
    conditioner = GSDConditioner(GSDConditioningConfig(output_dim=8, hidden_dim=4))

    embedding = conditioner(torch.tensor([10.0]))

    assert embedding.shape == (1, 8)


def test_different_gsd_values_produce_different_embeddings() -> None:
    """Changing the physical GSD changes the learned conditioning representation."""
    torch.manual_seed(7)
    conditioner = GSDConditioner(GSDConditioningConfig(output_dim=8, hidden_dim=4))

    embeddings = conditioner(torch.tensor([1.0, 20.0]))

    assert not torch.allclose(embeddings[0], embeddings[1])


def test_conditioning_changes_projected_tokens_and_receives_gradient() -> None:
    """The projector path adds GSD to visual tokens and trains the conditioner."""
    torch.manual_seed(11)
    projector = torch.nn.Sequential(
        torch.nn.LayerNorm(4),
        torch.nn.Linear(4, 8),
        torch.nn.GELU(),
        torch.nn.Linear(8, 8),
    )
    conditioned_projector = GSDConditionedProjector(
        projector,
        GSDConditioningConfig(output_dim=8, hidden_dim=4),
    )
    hidden_states = torch.randn(1, 3, 4)

    with conditioned_projector.condition_on(torch.tensor([5.0])):
        low_resolution_tokens = conditioned_projector(hidden_states)
    with conditioned_projector.condition_on(torch.tensor([20.0])):
        high_resolution_tokens = conditioned_projector(hidden_states)

    loss = high_resolution_tokens.square().mean()
    loss.backward()

    assert not torch.allclose(low_resolution_tokens, high_resolution_tokens)
    assert conditioned_projector.conditioner.network[0].weight.grad is not None


def test_hook_conditions_existing_projector_without_renaming_lora_layers() -> None:
    """The production hook changes projected tokens while preserving projector parameter names."""
    projector = torch.nn.Sequential(torch.nn.Linear(4, 8))
    names_before = [name for name, _ in projector.named_parameters()]
    conditioner = GSDConditioner(GSDConditioningConfig(output_dim=8, hidden_dim=4))
    handle = attach_gsd_output_conditioning(projector, conditioner)

    with condition_on(conditioner, [5.0]):
        low_resolution_tokens = projector(torch.zeros(1, 2, 4))
    with condition_on(conditioner, [20.0]):
        high_resolution_tokens = projector(torch.zeros(1, 2, 4))
    handle.remove()

    assert not torch.allclose(low_resolution_tokens, high_resolution_tokens)
    assert names_before == [name for name, _ in projector.named_parameters()]


def test_conditioned_projector_requires_gsd_metadata() -> None:
    """A missing GSD cannot silently create an unconditioned visual forward pass."""
    projector = torch.nn.Linear(4, 8)
    conditioned_projector = GSDConditionedProjector(
        projector,
        GSDConditioningConfig(output_dim=8, hidden_dim=4),
    )

    with pytest.raises(ValueError, match="GSD conditioning requires"):
        conditioned_projector(torch.zeros(1, 3, 4))


@pytest.mark.parametrize(
    "value",
    [None, 0, -1, math.nan, math.inf, -math.inf, "10", True],
)
def test_invalid_gsd_metadata_is_rejected(value: object) -> None:
    """Missing, non-finite, non-positive, and non-numeric GSD values fail explicitly."""
    with pytest.raises((TypeError, ValueError), match="gsd_m"):
        validate_gsd_m(value)


def test_conditioner_state_can_be_persisted() -> None:
    """Conditioner weights and normalization metadata are written beside an adapter."""
    conditioner = GSDConditioner(GSDConditioningConfig(output_dim=8, hidden_dim=4))

    with TemporaryDirectory(dir=Path.cwd()) as output_dir:
        save_gsd_conditioner(conditioner, output_dir)

        assert Path(output_dir, "gsd_conditioner.pt").is_file()
        assert Path(output_dir, "gsd_conditioner.json").is_file()
        restored = load_gsd_conditioner(output_dir)
        assert restored.config == conditioner.config
        torch.testing.assert_close(
            conditioner(torch.tensor([10.0])), restored(torch.tensor([10.0]))
        )


def test_multiscale_transform_returns_model_size() -> None:
    """Every sampled scale produces the configured model input dimensions."""
    image = Image.new("RGB", (64, 64), "white")
    augment = MultiScaleGSDAugment(
        GSDAugmentConfig(source_gsd_m=10.0, min_gsd_m=0.5, max_gsd_m=30.0, output_size=32)
    )

    transformed, effective_gsd_m = augment(image, rng=random.Random(3))

    assert transformed.size == (32, 32)
    assert 0.5 <= effective_gsd_m <= 30.0


def test_multiscale_transform_reaches_multiple_effective_scales() -> None:
    """Configured multi-scale sampling exercises more than one effective GSD."""
    augment = MultiScaleGSDAugment(
        GSDAugmentConfig(source_gsd_m=10.0, min_gsd_m=0.5, max_gsd_m=30.0, output_size=32)
    )

    sampled = {augment.sample_gsd_m(random.Random(seed)) for seed in range(8)}

    assert len(sampled) > 1


def test_multiscale_transform_is_reproducible_for_a_fixed_seed() -> None:
    """The same seeded RNG gives the same target and transformed pixels."""
    image = Image.effect_noise((64, 64), 32).convert("RGB")
    augment = MultiScaleGSDAugment(
        GSDAugmentConfig(source_gsd_m=10.0, min_gsd_m=0.5, max_gsd_m=30.0, output_size=32)
    )

    first, first_gsd = augment(image, rng=random.Random(17))
    second, second_gsd = augment(image, rng=random.Random(17))

    assert first_gsd == second_gsd
    assert ImageChops.difference(first, second).getbbox() is None


def test_different_seeds_can_select_different_multiscale_paths() -> None:
    """Independent seeds can reach different configured target GSDs or crops."""
    image = Image.effect_noise((64, 64), 32).convert("RGB")
    augment = MultiScaleGSDAugment(
        GSDAugmentConfig(source_gsd_m=10.0, min_gsd_m=0.5, max_gsd_m=30.0, output_size=32)
    )

    first, first_gsd = augment(image, rng=random.Random(1))
    second, second_gsd = augment(image, rng=random.Random(2))

    assert first_gsd != second_gsd or ImageChops.difference(first, second).getbbox() is not None


def test_training_preprocessing_augments_without_changing_sample_targets() -> None:
    """Training preprocessing changes only the image and leaves label/text targets intact."""
    image = Image.effect_noise((64, 64), 32).convert("RGB")
    sample = {"image": image, "label": 3, "answer": "PermanentCrop"}
    enriched = attach_sample_gsd(sample, 10.0)
    transform = build_transform(32)
    augmenter = MultiScaleGSDAugment(
        GSDAugmentConfig(source_gsd_m=10.0, min_gsd_m=0.5, max_gsd_m=30.0, output_size=32)
    )

    pixels, effective_gsd_m = preprocess_image_for_split(
        enriched["image"], "train", transform, augmenter, random.Random(3)
    )

    assert pixels.shape == (1, 3, 32, 32)
    assert effective_gsd_m is not None
    assert enriched["label"] == sample["label"]
    assert enriched["answer"] == sample["answer"]


@pytest.mark.parametrize("split", ["validation", "test"])
def test_evaluation_preprocessing_does_not_augment(split: str) -> None:
    """Validation and test preprocessing retain the baseline transform without an augmenter."""
    image = Image.effect_noise((64, 64), 32).convert("RGB")
    transform = build_transform(32)

    pixels, effective_gsd_m = preprocess_image_for_split(image, split, transform)

    expected = transform(image).unsqueeze(0)
    assert torch.equal(pixels, expected)
    assert effective_gsd_m is None


def test_training_module_import_does_not_load_or_train(monkeypatch) -> None:
    """Importing training utilities must not trigger a model download or training run."""

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("model loading during module import")

    monkeypatch.setattr(AutoModel, "from_pretrained", fail_if_called)
    monkeypatch.setattr(AutoTokenizer, "from_pretrained", fail_if_called)

    module = importlib.import_module("app.training.train_lora_mlp1_vision")

    assert callable(module.main)
