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
