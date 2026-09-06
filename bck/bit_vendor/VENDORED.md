# Vendored: BIT (Bitemporal Image Transformer)

**Source**: https://github.com/justchenhao/BIT_CD.git
**Commit**: `adcd7aea6f234586ffffdd4e9959404f96271711`
**License**: as published in the upstream repository (no LICENSE file was present at
this commit; treat as all-rights-reserved by the original authors pending clarification).

## What's vendored and why

Only the pure model-definition files needed to construct BIT's network and run a
forward pass — no training loop, no CLI/demo plumbing, no dataset loader. That
plumbing (`main_cd.py`, `demo.py`, `datasets/`, `misc/`) pulls in `opencv-python`,
`tifffile`, and `matplotlib`, none of which `bck` needs; `detector.py` reimplements the
minimal preprocessing (resize, [-1, 1] normalize) and postprocessing (argmax/softmax)
directly instead.

| File (originally under `models/`) | Purpose |
|---|---|
| `__init__.py` | Re-exports `resnet` so `networks.py`'s `models.resnet18(...)`-style calls resolve. |
| `resnet.py` | ResNet18/34/50 backbone. |
| `networks.py` | `BASE_Transformer` (BIT's actual architecture) + `define_G` factory. |
| `help_funcs.py` | Transformer/TransformerDecoder/TwoLayerConv2d building blocks `networks.py` needs. |
| `losses.py` | Loss functions — not used by `detector.py` (inference only), kept so this mirrors a complete, coherent subset of the original `models/` package rather than an arbitrary partial cherry-pick. |

`basic_model.py` (the original `CDEvaluator` wrapper) was deliberately **not** vendored —
it imports `misc.imutils.save_image`, which would have pulled in `opencv-python` and
`tifffile` as new `bck` dependencies for a side effect (saving prediction PNGs to disk)
`detector.py` doesn't need. `detector.py` reimplements the same load-checkpoint /
forward-pass / argmax logic directly against `networks.define_G`, verified against
`basic_model.py`'s actual source to make sure it matches exactly (same
`model_G_state_dict` checkpoint key, same `torch.argmax(..., dim=1)` postprocessing).

## Deliberate edits from upstream

- `networks.py`: `import models` / `from models.help_funcs import ...` renamed to
  `import bit_vendor as models` / `from bit_vendor.help_funcs import ...` — the only
  change needed to make the self-referencing package import resolve under this new
  location. No logic changed.
- `resnet.py`: `from torchvision.models.utils import load_state_dict_from_url` (removed
  in modern torchvision) repointed to `from torch.hub import load_state_dict_from_url` —
  this fix was already applied and verified during ROHAN-001's BIT environment spike.

## Pretrained weights

Not vendored here (binary, 57.3MB) — expected at `bck/checkpoints/BIT_LEVIR/best_ckpt.pt`
(gitignored, matching the repo's existing `checkpoints/` ignore rule). Source: BIT's own
published LEVIR-CD release asset (Google Drive link in the upstream README), fetched and
verified during ROHAN-001.

## Ruff

Excluded from linting/formatting via `[tool.ruff] extend-exclude` — this is upstream
third-party code we did not write and should not reformat.
