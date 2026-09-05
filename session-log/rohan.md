# ROHAN-001 — env/SAR spike

## What was done

- **Environment check**: RTX 3050 6GB (driver present, no system CUDA toolkit needed —
  bck's torch wheel bundles its own), 7.6GB RAM, 933GB free disk, rsync/wget/curl present.
- **SEN12MS**: `mediatum.ub.tum.de/1474000`'s page is behind an Anubis JS anti-bot
  challenge — couldn't read the rsync password off the rendered page directly. Verified
  the standard TUM dataserv convention (`m1474000`/`m1474000`) against a live
  `rsync --list-only`, which is a real authenticated listing, not a guess. No per-scene
  files exist; smallest S1 archive is `ROIs2017_winter_s1.tar.gz` (14.4GB, whole season
  bundle) — downloading into `data/` per team lead approval, one scene will be extracted
  and the archive + all other scenes deleted afterward. `SupportingDocument.txt` (fetched
  from the same rsync source) states S1 channels are already sigma-nought dB, 16-bit
  GeoTIFFs — the numeric check (dtype/min/max/percentiles) against the real scene is
  pending the download and will confirm or contradict this.
- **LEVIR-CD**: downloaded the ChangeFormer-linked preprocessed 256×256 zip (2.3GB),
  extracted exactly one real A/B/label triplet (`train_103_9.png`, 256×256), then deleted
  the zip and all other extracted files.
- **BIT environment** (`~/spikes/bit/`, outside the repo): venv created with `uv`, torch
  2.14.0+cu130 / torchvision 0.29.0 / einops installed there only — never touched `bck`.
  Cloned `justchenhao/BIT_CD`, fetched its pretrained LEVIR-CD checkpoint (57.3MB).
- **BIT run on the real LEVIR-CD pair**: ran successfully end to end, produced a real
  256×256 binary change mask (41.3% pixels flagged changed) for `train_103_9.png`. Getting
  there required three real compatibility fixes against the torch/torchvision version gap
  the team lead flagged as a risk — all in the `~/spikes/bit` clone, never in `bck`:
  - `torchvision.models.utils.load_state_dict_from_url` was removed from modern
    torchvision — repointed the import to `torch.hub.load_state_dict_from_url`.
  - Two undocumented runtime deps the README never lists: `opencv-python-headless` and
    `tifffile`. Installed into the spike venv only.
  - `np.str` was removed from numpy (deprecated since 1.20) — the dataset-list loader
    used it as a dtype; changed to `str`.
  - **The flagged one**: `torch.load` defaults to `weights_only=True` since PyTorch 2.6,
    and BIT's checkpoint pickles a `numpy.core.multiarray.scalar` global that isn't on
    the safe list — load failed with `_pickle.UnpicklingError`. Fixed by passing
    `weights_only=False` (checkpoint is BIT's own published, trusted release asset).
  This is the real, reproducible failure mode against a current PyTorch — reported here
  rather than silently worked around.
- **Fusion module** (`bck/app/tools/fusion/`): `sar_scale.py` (`SarScale` enum: DB,
  LINEAR) and `guards.py` (`require_db_scale` — raises unless the caller explicitly
  declares DB; never inspects pixel values to guess the scale) plus
  `tests/test_fusion_guards.py`. All four gates green
  (`ruff check`, `ruff format --check`, `lint-imports`, `pytest`). Committed as two
  conventional commits (`feat:`, `test:`).

## Blocked / deferred

- **`despeckle.py` (Lee filter) — not written.** `05-Research-And-References` §3.1a
  (the Lee/MMSE formula citation) isn't in this repo or filesystem; it lives in
  external project knowledge I can't reach from this environment. Per the ticket's own
  instruction, stopping rather than reconstructing the formula from memory. Team lead is
  fetching the exact text to paste in; `despeckle.py` and its test follow once that
  lands. No stub, no placeholder, no TODO left in its place.
- **SEN12MS numeric check (dtype/min/max/percentile/metadata) and despeckle evidence
  (Step 4)** — pending the archive download, which stalled once (dead connection, silent
  for 2+ hours) and is currently crawling at ~150-250 KB/s (ETA 20+ hrs) even after
  resuming with `--partial --append-verify`. Confirmed this machine's general bandwidth
  is fine (~5MB/s to an unrelated host) — the slowness is on TUM dataserv's end, not
  fixable from here. Will complete and report the verbatim numbers once it lands.

## Decisions

- **BIT over ChangeFormer**: BIT's pretrained LEVIR-CD checkpoint is 57.3MB vs
  ChangeFormer's 940MB — meaningfully cheaper to ship and iterate on. BIT also has one
  fewer pinned dependency (no `timm`). With only 6GB of VRAM on this machine, the smaller
  model leaves more headroom to run alongside everything else in the pipeline.
  ChangeFormer was not tested further for this reason, not because it doesn't work.
- **DN→dB calibration deferred to a follow-up ticket** (per team lead, already reflected
  in this ticket's amended scope): SEN12MS's own `SupportingDocument.txt` states its
  Sentinel-1 channels ship as sigma-nought dB already — there is nothing to convert from
  DN for this dataset. The scale guard (`require_db_scale`) exists precisely so a future
  caller can't skip declaring which scale a given SAR source actually uses.

## Agent

Claude Code (Sonnet 5), session
https://claude.ai/code/session_01Mcufc5gSdGYGxKZp4R1H94.
