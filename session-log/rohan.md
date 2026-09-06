# ROHAN-001 — change-detection env + SAR calibration spike

### 2026-09-05 — Claude Code

## Done

- **Environment**: RTX 3050 6GB (driver present; no system CUDA toolkit needed, bck's torch wheel bundles its own), 7.6GB RAM, 933GB free disk, rsync/wget/curl present.
- **LEVIR-CD**: downloaded the ChangeFormer-linked preprocessed 256x256 zip (2.3GB), extracted exactly one real A/B/label triplet (`train_103_9.png`, 256x256), then deleted the zip and all other extracted files.
- **BIT environment** (`~/spikes/bit/`, outside the repo): venv created with `uv`; torch 2.14.0+cu130, torchvision 0.29.0 and einops installed there only, never in `bck`. Cloned `justchenhao/BIT_CD` and fetched its pretrained LEVIR-CD checkpoint (57.3MB).
- **BIT run on the real LEVIR-CD pair**: ran end to end and produced a real 256x256 binary change mask, 41.3% of pixels flagged changed. Four compatibility fixes were needed against the torch version gap the team lead flagged as a risk — all in the spike clone, nothing in `bck`:
  - `torchvision.models.utils.load_state_dict_from_url` was removed from modern torchvision — repointed to `torch.hub.load_state_dict_from_url`.
  - `np.str` was removed from numpy — the dataset-list loader used it as a dtype; changed to `str`.
  - Two undocumented runtime deps the README never lists, `opencv-python-headless` and `tifffile`, installed into the spike venv only.
  - The flagged one: `torch.load` defaults to `weights_only=True` since PyTorch 2.6, and BIT's checkpoint pickles a `numpy.core.multiarray.scalar` global that isn't on the safe list — load failed with `_pickle.UnpicklingError`. Resolved with `weights_only=False`; the checkpoint is BIT's own published release asset.
- **Fusion module** (`bck/app/tools/fusion/`): `sar_scale.py` (`SarScale` enum: DB, LINEAR) and `guards.py` (`require_db_scale`, which raises unless the caller explicitly declares DB and never inspects pixel values to guess scale), plus `bck/tests/test_fusion_guards.py`.
- **`calibration.py`** (`calibrate_sigma0_db`): the verified §3.2 formula, `10*log10(DN^2) - K_cal + 10*log10(sin(theta_inc))`. DN cast to float64 before squaring (integer arrays would overflow otherwise); `DN <= 0` returns NaN per element rather than emitting `-inf`; `incidence_angle_deg` outside the open interval (0, 90) raises `ValueError`; array-like `k_cal` or `incidence_angle_deg` raises `TypeError`. `bck/tests/test_fusion_calibration.py` covers a normal case, DN=0, negative DN, invalid angles, an int16 array that would overflow if squared in place, and the scalar-only enforcement — every expected dB value hand-computed via Python's `math` module in a comment so it is independently checkable.
- All four gates green throughout: `ruff check`, `ruff format --check`, `lint-imports`, `pytest`.

## Decided

- **BIT over ChangeFormer.** 57.3MB pretrained LEVIR-CD checkpoint vs ChangeFormer's 940MB, one fewer pinned dependency (no `timm`), and a ResNet18 backbone leaving far more headroom on this machine's 6GB VRAM. The bar for this ticket was "it runs", and BIT was likelier to clear it. ChangeFormer is generally reported to score better on LEVIR-CD and pins its dependencies properly — a real point against BIT — and swapping later is contained behind the same tool interface. ChangeFormer was not tested further for this reason, not because it doesn't work.
- **Acceptance criterion 2 re-scoped into two parts by the team lead; only part 1 is built here.** SEN12MS ships sigma-nought dB already, so there was never raw DN in it to calibrate from and the formula could not be verified end to end against this ticket's own dataset. `calibrate_sigma0_db` implements the verified §3.2 formula standalone, correct by construction and by its hand-computed test cases, independent of which dataset eventually supplies real DN.
- **K_cal is scalar by design, valid for single-patch/fixed-geometry inputs per this ticket's scope — full-scene per-pixel LUT calibration is a separate future function, not a defect in this one.**
- **The scale guard does not infer scale from pixel values.** Any "values above X are DN" rule would have been an invented threshold. Callers declare scale explicitly or the guard raises.

## Rejected

- **A placeholder or simplified despeckle filter**, suggested to unblock the ticket. AGENTS.md is explicit: no stubs, no placeholders, no TODOs in shipped code. A stand-in for the real Lee/MMSE formula quietly becomes load-bearing for ROHAN-002/003 the moment anything imports `app.tools.fusion` expecting *something* called despeckle — worse than leaving the gap visible. Waiting cost nothing, since despeckle was already agreed non-blocking.
- **QXS-SAROPT as a substitute SAR source.** Its DN-vs-calibrated pixel format is not documented in any verified source, so switching would have traded a slow download for an unverified assumption.
- **Reconstructing the Lee/MMSE formula from memory** when §3.1a proved unreachable. Stopped and escalated instead.

## Incomplete / blocked

- **`despeckle.py` — not written.** `05-Research-And-References` §3.1a lives in external project knowledge that this environment cannot read. The team lead is supplying the exact text; the filter and its test follow once it lands. No stub, no placeholder, no TODO left in its place.
- **SEN12MS Sentinel-1 numeric check and despeckle evidence.** `mediatum.ub.tum.de/1474000` sits behind an Anubis JS anti-bot challenge, so the rsync password could not be read off the rendered page; the standard TUM dataserv convention was confirmed against a live authenticated `rsync --list-only`, not guessed. No per-scene files exist — the smallest S1 archive is `ROIs2017_winter_s1.tar.gz` at 14.4GB. `SupportingDocument.txt`, fetched from the same rsync source, states the S1 channels are already sigma-nought dB as 16-bit GeoTIFFs; the numeric confirmation against real pixels is still pending. The transfer stalled once and is crawling at 70-290 KB/s despite `--partial --append-verify`. This machine's general bandwidth is fine (~5MB/s to an unrelated host), so the constraint is on TUM's end.

## Agent

Claude Code (Sonnet 5), session https://claude.ai/code/session_01Mcufc5gSdGYGxKZp4R1H94

---

### 2026-09-05 — ROHAN-003: environment note — missing libgomp1 for lightgbm/s2cloudless — Claude Code

`app/tools/fusion/cloud_detector.py` wraps `s2cloudless`, which depends on `lightgbm`.
`lightgbm`'s native binary is linked against `libgomp.so.1` (the GNU OpenMP runtime), a
system library — not something `uv`/pip can install. This machine doesn't have it
(`dpkg -s libgomp1` → not installed, no `gcc`/`g++` either, and no already-installed
Python package in `bck/.venv` bundles a copy), so `import s2cloudless` fails with
`OSError: libgomp.so.1: cannot open shared object file`.

No root access available, so instead of `sudo apt-get install libgomp1`:

```
apt download libgomp1
dpkg-deb -x libgomp1_*.deb bck/.system-libs
```

Both commands work without root — `apt download` only fetches the `.deb` (needs apt's
package lists already populated, which they are here), and `dpkg-deb -x` extracts
without installing. This pulls the real, correctly-versioned Ubuntu package
(`14.2.0-4ubuntu2~24.04.1`) into a project-local directory instead of system-wide.
`bck/.system-libs/` is gitignored — it's a local runtime workaround, not something to
commit.

**Anyone running this branch's tests locally who hits the same `libgomp.so.1` error**
needs to either `sudo apt-get install libgomp1` (if they have root) or run the two
commands above, then prefix every `uv run` that touches `cloud_detector.py` /
`s2cloudless` / `lightgbm` with:

```
LD_LIBRARY_PATH=bck/.system-libs/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH
```

This belongs in `SETUP.md` as a real, reproducible environment gap — flagging for
Yashwanth (its owner) rather than adding it myself.

---

### 2026-09-06 — ROHAN-002: BIT change detection tool (detector.py) — Claude Code

## Done
- Confirmed `a04b865` (#28) landed on `main` before starting: `ImageInput.path`
  is real (`path: str`, populated by `ingest_raster()`'s
  `tempfile.NamedTemporaryFile(delete=False, ...)`). `stub_tool` is NOT
  real — checked the actual diff of a04b865 and grepped the whole tree for
  `stub_tool`/`StubTool`/`ToolStub`: zero matches anywhere. The commit
  message's second bullet doesn't correspond to any real code.
- Vendored BIT (5 files: `__init__.py`, `resnet.py`, `networks.py`,
  `help_funcs.py`, `losses.py`) from `justchenhao/BIT_CD` @
  `adcd7aea6f234586ffffdd4e9959404f96271711` (verified against the local
  clone's actual git log, not GitHub's web UI) into `bit_vendor/`,
  inference-only — no training/CLI/dataset-loader plumbing, so no new
  `opencv-python`/`tifffile`/`matplotlib` dependencies. Documented the two
  deliberate upstream edits in `bit_vendor/VENDORED.md`.
- Built `detector.py`: loads two `ImageInput`s via `.path`, runs vendored
  BIT, constructs `list[Evidence]` directly — following `fusion/reconcile.py`'s
  real, already-merged pattern, since no `stub_tool` exists to build into.
- Verified against two real LEVIR-CD pairs: `levir_test_1_*` (already
  committed for the frontend; ground truth genuinely all-zero, predicted
  0.0% — exact match) and `levir_train_103_9_*` (the same pair ROHAN-001
  verified via BIT's CLI demo; IoU=0.8945, pixel accuracy=95.48%,
  changed-pixel fraction 0.4132843017578125 — cross-checked byte-for-byte
  against the original CLI run's actual saved output PNG, not just
  re-asserted from a prior note).
- All four gates green: `ruff check`, `ruff format --check`, `lint-imports`
  (91 files, 176 deps, 3/3 contracts kept), `pytest` (93 passed).

## Decided
- Vendored only pure model-definition files, not `basic_model.py` — its
  `CDEvaluator` wrapper pulls in `opencv-python`/`tifffile` as new deps
  `detector.py` doesn't need. Reimplemented the same load-checkpoint/
  forward/argmax logic directly, verified against `basic_model.py`'s real
  source (same `model_G_state_dict` key, same `torch.argmax(..., dim=1)`).
- `checkpoint_path` is a required parameter, not a hardcoded default,
  matching this codebase's established convention.
- Used the already-committed `levir_test_1_*` pair as the primary fixture
  (not `~/spikes/bit/`, outside the repo) paired with `levir_train_103_9_*`
  for a real-change case.

## Rejected
- Rebuilding BIT's preprocessing from memory or blog conventions. Read
  `datasets/data_utils.py` directly to confirm real normalization
  (`mean=[0.5]*3, std=[0.5]*3`, not ImageNet stats).
- Inventing a `stub_tool` wrapper to match a04b865's commit message at
  face value. Verified it doesn't exist before building around it.

## Incomplete
- Temp files at `ImageInput.path` are never cleaned up — known, explicitly
  flagged by the lead as a separate follow-up, not this ticket's scope.

## Agent
Claude Code (Sonnet 5), session
https://claude.ai/code/session_01Mcufc5gSdGYGxKZp4R1H94.

---

### 2026-09-06 — ROHAN-002 follow-up: change_summary.py/confidence.py missing from branch, fixed via cherry-pick — Claude Code

**Root cause**: `change_summary.py` and `confidence.py` (originally added on
this branch, commits `d49480e`, `95829a9`, `fcad9b5`) were deliberately moved
onto a separate branch (`feature/26167-ROHAN-004-mask-hardening`) during an
earlier git-scoping cleanup, based on an incorrect assessment that they were
ROHAN-004-only work unrelated to ROHAN-002 — without first checking whether
detector.py (built afterward) actually depends on them. It does.

**How it was caught**: Yashwanth ran CI himself against the pushed branch
rather than trusting a "no failing checks" claim at face value — CI surfaced
the missing imports as a collection failure.

**The fix**: three commits cherry-picked back onto the branch —
`d924ba9` (`feat(change-detection): add summarize_change for binary masks`),
`6ec513a` (`feat(change-detection): add compute_confidence for predicted
masks`), and `edaceb7` (`test(change-detection): cover summarize_change and
compute_confidence`) — restoring both modules and their tests.

**Verified after the fix**: `detector.py`'s imports
(`from app.tools.change_detection.change_summary import summarize_change`,
`from app.tools.change_detection.confidence import compute_confidence`)
resolve against real files again. All four gates green, and `pytest -v`
confirms real collection — 93 items collected and passed, including both
restored test files (`tests/change_detection/test_change_summary.py`,
`tests/change_detection/test_confidence.py`) and `tests/test_detector.py` —
not just a summary line claiming so.

---

### 2026-09-06 — ROHAN-004 (first half): registration-quality gate derivation — Claude Code

**Method chosen, and why**: `skimage.registration.phase_cross_correlation`
(global phase correlation), not ORB/SIFT + RANSAC keypoint matching — that
approach was tried first and abandoned after real testing showed it produces
physically implausible fitted transforms (rotations of ±30–132°, scale
factors of 0.19–0.62, 100+ px translations) even on genuinely well-registered
real LEVIR-CD pairs, because these 256x256 patches don't have enough
distinctive, stable texture for reliable keypoint correspondence. Confirmed
independently with both ORB and SIFT, and with both a full 6-DOF affine and a
restricted 4-DOF similarity transform — same failure mode every time.

**Canonical phase-correlation pipeline** (fixed after diagnostics, do not vary
without re-deriving): PIL `.convert("RGB")` -> float32 array / 255.0 ->
`skimage.color.rgb2gray` -> multiply by a 2D Hann window
(`np.outer(np.hanning(h), np.hanning(w))`) ->
`phase_cross_correlation(..., upsample_factor=100)`. Shift-vector Euclidean
norm is the sole gating scalar.

**`error` is deliberately unused**: a self-vs-self control (a real image
against a byte-identical copy of itself — zero shift, zero difference) still
returned `error=0.9999999982747276` in this environment (skimage 0.26.0).
Since the shift computation on that same control is separately verified
correct (exactly `[0, 0]`, norm `0.0`), `error` is not a meaningful signal at
all here — it doesn't approach zero even for a literally identical pair.

**Real-pair sample — every genuine bi-temporal pair in `bck/tests/fixtures/`,
n=2** (searched the whole directory including inside both `.npz` archives;
everything else is single-timepoint SAR/optical/cloud data, not a second real
timepoint of the same modality):
| Pair | Shift norm |
|---|---|
| `levir_test_1` | 1.93px |
| `levir_train_103_9` | 12.04px |

**Threshold set: 40.0px** — roughly 3x the maximum observed real-pair shift
norm (12.04px), rounded up. Deliberately generous over a sample of only 2
real pairs already showing ~6x variance between them — the goal is to never
falsely refuse a real, correctly co-registered pair that happens to contain
large real scene change (`levir_train_103_9`'s 12.04px is exactly that: real
content change, not misregistration). Provisional per PRD §8's "TBD from real
testing"; a future ticket should widen the real-pair sample before this is
treated as final.

**Synthetic shift sweep** (reference only, NOT used to set the threshold —
`scipy.ndimage.shift`, `mode="reflect"`, never `np.roll`: an earlier attempt
using `np.roll` introduced a wraparound seam that measurably distorted the
shift estimate at larger offsets, confirmed by comparing measured/injected
ratio drifting from 0.98 at 1px to 1.37 at 32px):
1px→1.41px, 2px→2.83px, 4px→5.66px, 8px→11.31px, 16px→22.63px, 32px→45.25px.

**Known v1 limitation, deliberately deferred**: this is global phase
correlation over the whole frame. Bi-temporal change-detection pairs contain
large real content change by definition, which can inflate the global shift
estimate independent of true misregistration — this gate catches gross
global misalignment, not subtle misregistration on a pair with major scene
change. A more robust future approach (patch-based/block-voting phase
correlation, median shift across sub-tiles) is a known, deliberately-deferred
improvement, not built here due to time constraints.

**Built**: `bck/app/tools/change_detection/registration_quality.py`
(`require_registration_quality`, `RegistrationQualityError` — mirrors
`fusion/guards.py`'s refusal style exactly: explicit exception, no silent
pass-through, no fabricated fallback). Wired as a precondition at the very
start of `detector.py`'s `detect_change()`, before any BIT loading/inference.
Tests: `bck/tests/test_registration_quality.py` — both real pairs pass, plus
two clearly-labeled synthetic cases (shape-mismatch via a resized copy;
gross-misregistration via the same 32px `scipy.ndimage.shift` methodology as
the reference sweep, measured at shift_norm_px=45.25, correctly refused).

**Note on branch state**: this work was done with `main` checked out, not
`feature/26167-ROHAN-004-directional-change-vqa` as expected — flagged
directly to the user, not resolved via a write git command per this
session's git rules.
