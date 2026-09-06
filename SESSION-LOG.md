## 2026-09-06 — ROHAN-002: BIT change detection tool — Rohan (Claude Code)

**Done**
- `app/tools/change_detection/detector.py`: Evidence-assembling entry
  point. Takes two `ImageInput`s, loads from `.path`, runs vendored BIT,
  returns `list[Evidence]`.
- BIT vendored into `bit_vendor/` (5 files, from `justchenhao/BIT_CD` @
  `adcd7aea6f234586ffffdd4e9959404f96271711` — verified against the local
  clone's actual git log; see `bit_vendor/VENDORED.md`).
- Verified against two real LEVIR-CD pairs: exact match on the all-zero
  no-change pair; IoU=0.8945/pixel accuracy=0.9548 on a real-change pair,
  cross-checked byte-for-byte against the original CLI run's saved output
  (identical changed-pixel fraction, 0.4132843017578125).
- All four gates green (`ruff check`, `ruff format --check`, `lint-imports`,
  `pytest` — 93 passed).

**Decided**
- Vendored only pure model-definition files to avoid new dependencies;
  detector.py reimplements load/forward/argmax directly, verified against
  `basic_model.py`'s actual source.
- `detector.py` builds `Evidence` directly, matching `fusion/reconcile.py`'s
  pattern — **`stub_tool` does not exist anywhere in this codebase.**
  `a04b865`'s commit message claims it was widened to `list[Evidence]`, but
  the actual diff never touches any such function, and a full-tree grep
  found zero matches. Flagging this so nobody else goes looking for it.

**Rejected**
- N/A this ticket — the open questions (ImageInput.path shape, stub_tool
  existence) were verification stops, not design rejections.

**Incomplete**
- Temp files at `ImageInput.path` are never cleaned up (known follow-up,
  not this ticket's scope).

Agent: Claude Code (Sonnet 5).

## 2026-09-06 — ROHAN-004: registration-quality gate + directional change classification — Rohan (Claude Code)

**Done**
- `app/tools/change_detection/registration_quality.py`: global
  phase-correlation registration-quality gate
  (`skimage.registration.phase_cross_correlation`, Hann-windowed,
  `upsample_factor=100`). Shift-magnitude norm is the sole gating scalar
  (`error` deliberately unused — a self-vs-self control on a real image
  still returned `error≈0.9999999982747276`, not a usable signal). Threshold
  40.0px, ~3x the max of the only 2 real bi-temporal pairs in this repo's
  fixtures (1.93px, 12.04px). Wired as a precondition at the top of
  `detector.py`'s `detect_change()`.
- `app/tools/change_detection/change_summary.py`: `ChangeSummary` gains
  `status` (`"increased"|"decreased"|"unchanged"`), `changed_pixel_count`,
  `changed_percentage` — all exposed through `detector.py`'s existing
  `Evidence.payload`. Noise-floor threshold (0.1%) derived from a real
  self-comparison measuring exactly 0.0% changed pixels on both real pairs.
- Both guards mirror `fusion/guards.py`'s refusal style exactly — explicit
  exceptions (`RegistrationQualityError`), no silent pass-through, no
  fabricated fallback result.
- All four gates green throughout both halves (`ruff check`,
  `ruff format --check`, `lint-imports`, `pytest` — 144 passed on the final
  run).

**Decided**
- ORB/SIFT + RANSAC keypoint matching was tried first for the registration
  gate and rejected after real-data testing: on real LEVIR-CD 256x256
  patches it produced physically implausible fitted transforms (rotations of
  ±30–132°, scale factors of 0.19–0.62) even on genuinely well-registered
  real pairs — confirmed with both feature detectors and both a 6-DOF affine
  and a restricted 4-DOF similarity transform. Switched to global phase
  correlation, which measures cleanly on the same real data.
- A changed pair defaults to `"increased"`, never inferred from pixel
  content, because LEVIR-CD is a documented building-construction/growth
  benchmark — explicitly a dataset-context assumption, not a general
  capability. `"decreased"` is reachable only via an explicit
  `reversed_order` flag, tested against one clearly-labeled synthetic
  reversed-order case (real predicted mask, relabeled), since LEVIR-CD has
  no real decrease pairs.
- PR #37 was closed unmerged (deliberate) — both halves of this ticket
  landed as unmerged commits on `feature/26167-ROHAN-004-directional-change-vqa`
  and are going up as a single combined follow-up PR from the same branch,
  not two separate PRs.

**Incomplete**
- Registration-quality gate is v1/coarse: global phase correlation over the
  whole frame can have its shift estimate inflated by large real content
  change (which bi-temporal change-detection pairs have by definition) —
  it catches gross global misalignment, not subtle misregistration on a
  pair with major scene change. A patch-based/block-voting approach (median
  shift across sub-tiles) is a known, deliberately-deferred improvement.
- Both thresholds (40.0px registration gate, 0.1% noise floor) are derived
  from only 2 real bi-temporal pairs — provisional per PRD §8's "TBD from
  real testing"; a future ticket should widen the real-pair sample.
- Temp files at `ImageInput.path` are still never cleaned up (pre-existing,
  not this ticket's scope).

Agent: Claude Code (Sonnet 5).
