"""AASH-004 verification: GSD-conditioning embedding (Fourier over log-GSD + FiLM).

Standalone check, not the training loop. The structural checks are model-free and
run anywhere; the final section additionally loads InternVL3-2B to print the live
`mlp1` input dimension the training script reads.

Run: `python -m app.training.verify_gsd_conditioning`.
"""

from __future__ import annotations

import torch

from app.training.gsd_conditioning import (
    GSDFiLMConditioner,
    attach_gsd_film,
    mlp1_input_dim,
    sinusoidal_encoding,
)

DEMO_DIM = 64
# Metres. 0.5-2 m is the Cartosat/RISAT range never seen in training (the
# extrapolation case); 12-28 m is inside the augmentation's 10-30 m band.
IN_RANGE_GSDS = [12.0, 18.0, 24.0, 28.0]
EXTRAPOLATION_GSDS = [0.5, 1.0, 2.0]


def check_encoding_is_not_collapsing() -> None:
    print("=== encoding: distinct per GSD (vs. a lookup that would collapse) ===")
    gsds = torch.tensor(IN_RANGE_GSDS + EXTRAPOLATION_GSDS)
    enc = sinusoidal_encoding(torch.log(gsds), DEMO_DIM)
    assert enc.shape == (len(gsds), DEMO_DIM), enc.shape
    assert torch.isfinite(enc).all(), "non-finite encoding values"
    pdist = torch.cdist(enc, enc)
    off_diag_min = pdist[~torch.eye(len(gsds), dtype=torch.bool)].min().item()
    print(f"encoding shape           : {tuple(enc.shape)}")
    print(f"min pairwise L2 distance : {off_diag_min:.4f}  (must be > 0)")
    assert off_diag_min > 1e-6, "two GSDs produced the same encoding"


def check_identity_at_init() -> None:
    print("\n=== FiLM: exact identity at initialisation ===")
    conditioner = GSDFiLMConditioner(DEMO_DIM)
    for gsd in IN_RANGE_GSDS + EXTRAPOLATION_GSDS:
        scale, shift = conditioner.film_params(torch.tensor([gsd]))
        assert torch.allclose(scale, torch.ones_like(scale)), (gsd, scale)
        assert torch.allclose(shift, torch.zeros_like(shift)), (gsd, shift)
    conditioner.set_gsd(torch.tensor([15.0]))
    features = torch.randn(1, 8, DEMO_DIM)
    out = conditioner(features)
    assert out.shape == features.shape, out.shape
    assert torch.allclose(out, features, atol=1e-6), "not identity at init"
    print("scale == 1, shift == 0, output == input for every tested GSD")


def check_conditioning_signal_after_a_step() -> None:
    print("\n=== FiLM: a single optimiser step makes it GSD-dependent ===")
    torch.manual_seed(0)
    conditioner = GSDFiLMConditioner(DEMO_DIM)
    opt = torch.optim.SGD(conditioner.parameters(), lr=0.1)
    target = torch.randn(1, 8, DEMO_DIM)
    conditioner.set_gsd(torch.tensor([20.0]))
    features = torch.randn(1, 8, DEMO_DIM)
    loss = ((conditioner(features) - target) ** 2).mean()
    opt.zero_grad()
    loss.backward()
    grad_norm = torch.cat([p.grad.flatten() for p in conditioner.parameters()]).norm().item()
    opt.step()
    print(f"gradient norm through FiLM generator : {grad_norm:.4f}  (must be > 0)")
    assert grad_norm > 0.0, "no gradient reached the FiLM generator"

    s_lo, _ = conditioner.film_params(torch.tensor([IN_RANGE_GSDS[0]]))
    s_hi, _ = conditioner.film_params(torch.tensor([EXTRAPOLATION_GSDS[0]]))
    spread = (s_lo - s_hi).abs().max().item()
    print(f"max |scale(12 m) - scale(0.5 m)|    : {spread:.4f}  (must be > 0)")
    assert spread > 1e-6, "scale does not vary with GSD after training"


def check_pre_hook_wiring() -> None:
    print("\n=== pre-hook: modifies mlp1 input, leaves child param names intact ===")
    mlp1 = torch.nn.Sequential(
        torch.nn.LayerNorm(DEMO_DIM),
        torch.nn.Linear(DEMO_DIM, DEMO_DIM),
        torch.nn.GELU(),
        torch.nn.Linear(DEMO_DIM, DEMO_DIM),
    )
    names_before = [n for n, _ in mlp1.named_parameters()]
    assert mlp1_input_dim(mlp1) == DEMO_DIM
    conditioner = GSDFiLMConditioner(DEMO_DIM)
    handle = attach_gsd_film(mlp1, conditioner)
    conditioner.set_gsd(torch.tensor([25.0]))
    x = torch.randn(2, 8, DEMO_DIM)
    _ = mlp1(x)  # runs without error through the hook
    names_after = [n for n, _ in mlp1.named_parameters()]
    handle.remove()
    print(f"param names unchanged by hook : {names_before == names_after}")
    assert names_before == names_after, (names_before, names_after)


def inspect_live_model() -> None:
    print("\n=== live InternVL3-2B mlp1 input dimension ===")
    try:
        from transformers import AutoModel

        model = AutoModel.from_pretrained(
            "OpenGVLab/InternVL3-2B", trust_remote_code=True, torch_dtype=torch.float32
        )
    except Exception as exc:  # noqa: BLE001 - report why, do not fail the check run
        print(f"model not loaded here ({type(exc).__name__}: {exc}); run on the training box")
        return
    dim = mlp1_input_dim(model.mlp1)
    conditioner = GSDFiLMConditioner(dim)
    n_params = sum(p.numel() for p in conditioner.parameters())
    print(f"mlp1 input dim (live)      : {dim}")
    print(f"conditioner params at dim  : {n_params}")


def main() -> None:
    check_encoding_is_not_collapsing()
    check_identity_at_init()
    check_conditioning_signal_after_a_step()
    check_pre_hook_wiring()
    inspect_live_model()
    print("\nAll structural checks passed.")


if __name__ == "__main__":
    main()
