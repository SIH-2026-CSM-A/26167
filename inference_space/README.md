---
title: SatQuery Inference
emoji: 🛰️
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 5.50.0
python_version: "3.12"
app_file: app.py
pinned: false
---

# SatQuery inference Space

Model inference for SatQuery AI (SIH26167). The Render backend keeps ingestion, EO validation
gates, routing, verification, evidence building, georeferencing and fusion. This Space runs
only the two torch models and returns their raw outputs:

| Endpoint | Inputs (files via `gradio_client.handle_file`) | Returns |
|---|---|---|
| `/vqa_ground` | 448×448 RGB PNG, question | raw answer, raw grounding text, raw `<box>` text, box in sent-image pixels, per-pass timings, model identity |
| `/change_detect` | pre and post 256×256 RGB PNGs | 16-bit probability PNG (value = round(p·65535), fixed scale), 8-bit mask PNG, stats, timings, model identity |

Inputs are `gr.File`, not `gr.Image`, so the uploaded bytes reach the model without being
re-encoded. Render pre-resizes images with the same functions the local path uses.
`bck/tests/tools/test_inference_equivalence.py` proves the model input is identical.

## Hardware

Written to run unchanged on **CPU Basic** (2 vCPU, 16 GB) and **ZeroGPU**. Switch in the Space
settings only; this README deliberately has no `hardware` line.

- Device is `cuda` if `torch.cuda.is_available()`, otherwise `cpu`. InternVL uses bf16 on cuda
  and fp32 on CPU.
- `vqa_ground` is decorated with `@spaces.GPU(duration=VQA_GPU_DURATION_S)`. It's a no-op off
  ZeroGPU. `VQA_GPU_DURATION_S` in `app.py` is a **placeholder** until measured on this Space.
- BIT always runs on CPU (small, and keeps parity with the local path). `change_detect` holds
  no GPU allocation.
- Models load once at module level (`low_cpu_mem_usage=True`),
  `torch.set_num_threads(os.cpu_count())`, and the queue allows one request at a time.

## Configuration

| Name | Kind | Purpose |
|---|---|---|
| `HF_TOKEN` | Secret | Fine-grained token with **read access to `ybaddam8/satquery-weights` only** |
| `WEIGHTS_REVISION` | Variable | Commit hash of the weights repo to load (default `main`; pin it) |
| `WEIGHTS_REPO` | Variable | Default `ybaddam8/satquery-weights` |
| `MAX_NEW_TOKENS` | Variable | Cap on generated tokens per VQA pass (default `128`) |

The weights repo layout is `lora-adapter/adapter_config.json`,
`lora-adapter/adapter_model.safetensors` and `bit/best_ckpt.pt`. At startup the Space logs whether the sha256 of each file matches
the expected values:

- adapter `796d3c25d883d7798c3d7634f855c86f5ae2c0107922c7d5d80f216298dde405`
- BIT `c159ba76143447f58c9f367ce8126a0014f2e4ba218cdb97cca173952c38cb3b`

The InternVL3-2B base model is pinned to revision
`899155015275a9b7338c7f4677e19c784e0e5a21` (`trust_remote_code=True` executes the repo's code).

## Provenance of copied code

Copied from `SIH-2026-CSM-A/26167` at commit `16b990d496ddb66e8b4da826dd5538457563dc4d`.

| File here | Source in the main repo | Changes |
|---|---|---|
| `satquery_infer/internvl.py` | `bck/app/models/internvl.py` | `MAX_NEW_TOKENS` read from env. dtype is bf16 on any cuda device, fp32 on CPU |
| `satquery_infer/vqa_passes.py` | `bck/app/tools/vqa_grounding/tool.py` | Only prompts, `VqaModel`, `VqaToolError`, `VqaPasses`, `run_vqa_passes`, `_parse_native_bbox`. Parsing helpers and Otsu fallback are left out (they run on Render) |
| `satquery_infer/bit_model.py` | `bck/app/tools/change_detection/bit_model.py` | Import path of `bit_io` only |
| `satquery_infer/bit_io.py` | `bck/app/tools/change_detection/bit_io.py` | None |
| `bit_vendor/{__init__,help_funcs,networks,resnet}.py`, `VENDORED.md` | `bck/bit_vendor/` | None (upstream BIT_CD, see `VENDORED.md`) |

When any source file changes in the main repo, re-copy it and update the commit above.

## Local run

```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install gradio==5.50.0 -r requirements.txt
HF_TOKEN=<read token for the weights repo> python app.py
```

InternVL3-2B has 2,088,957,440 parameters (counted from the pinned `model.safetensors` header), so the fp32 weights alone are 7.78 GiB of RAM on CPU, before activations and the Python process.
