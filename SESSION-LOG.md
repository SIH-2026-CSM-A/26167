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

## 2026-09-07 - JASH-005: curated demo dataset package + offline cache - Codex

**Session and starting state**
- Ticket: `26167 / JASH-005 / F24`.
- Branch: `feature/26167-JASH-005-demo-dataset-package`.
- Integration base and starting HEAD: `12bbf2c` (`origin/main`). The branch was
  created from that clean integration base; no unrelated local modifications
  were discarded, stashed, reset, or overwritten.
- Agent/session identity: OpenAI Codex primary agent (`/root`), 2026-09-07.

**Files changed or packaged**
- `data/demo/README.md`
- `data/demo/manifest.json`
- `data/demo/assets/sen1floods11_bolivia_103757_s1_sar.tif`
- `data/demo/assets/sen1floods11_bolivia_103757_s2_optical.tif`
- `data/demo/assets/levir_cd_train_103_9_before.png`
- `data/demo/assets/levir_cd_train_103_9_after.png`
- `bck/app/core/demo_manifest.py`
- `bck/tests/core/test_demo_manifest.py`
- `bck/app/ingestion/raster.py` (explicitly authorized JASH-005 scope
  exception: one dtype-ordering line in `_normalize_band()` only)
- `SESSION-LOG.md`

**Final representative queries (PRD section 6 order, verbatim)**
1. `Describe the land-cover and major objects visible in this image.`
2. `Highlight the water body referred to in the query.`
3. `What changed between these two dates, and where did the change occur?`
4. `Use the optical and SAR images together to identify built-up and water-covered regions.`
5. `Has the built-up area increased, decreased, or remained unchanged?`

**Manifest design and LIKI-006 contract**
- Canonical path: `data/demo/manifest.json`; schema version: `1.0`.
- Top-level fields: `schema_version`, `presets`.
- Preset fields: `id`, `label`, `query`, `intent`, `tool`, `scenario`,
  `assets`.
- Asset fields: `id`, `path`, `modality`, `role`.
- `intent`: `vqa`, `grounding`, `change_vqa`, `fusion`.
- `tool`: `vqa_grounding`, `change_detection`, `fusion`.
- `scenario`: `single_image`, `flood_water`, `bi_temporal_change`,
  `cross_modal`.
- `modality`: `optical`, `sar`.
- `role`: `image`, `pre_image`, `post_image`, `optical_image`, `sar_image`.
- `preset.id` is the deterministic lookup key. Manifest array order is the PRD
  representative-query order. Asset roles, not array positions, are
  authoritative.
- Asset paths are relative POSIX paths resolved from `data/demo/`. Absolute,
  URL, drive, UNC-like, backslash, traversal, NUL-containing, out-of-root, and
  symlink-escape paths fail validation. Unknown fields and invalid workflow
  combinations fail validation.
- Frontend-display-safe fields are `label` and `query`; `id` is the lookup key.
  `intent`, `tool`, `scenario`, and asset fields are binding/internal workflow
  data.
- `schema_version: 1.0` field names and role semantics are frozen for LIKI-006
  unless JASH-005 is explicitly reopened.

**Imagery reuse, provenance, hashes, and raster metadata**
- `bck/tests/fixtures/Bolivia_103757_S1Hand.tif` ->
  `sen1floods11_bolivia_103757_s1_sar.tif`; Sen1Floods11 Sentinel-1 SAR
  VV/VH; 698748 bytes; SHA-256
  `d7c7630e6540b3d32b063ed079d73e55c95b1c0347f5d94257b2b7300befb4c8`;
  512x512, 2 bands, `float32`/`float32`, `EPSG:4326`.
- `bck/tests/fixtures/Bolivia_103757_S2Hand.tif` ->
  `sen1floods11_bolivia_103757_s2_optical.tif`; co-registered
  Sen1Floods11 Sentinel-2 optical; 908533 bytes; SHA-256
  `d16f68d9fffa6235b44cc31b186ec4ab5179420892fc59589d597717afeb19ad`;
  512x512, 13 `int16` bands, `EPSG:4326`.
- `bck/tests/fixtures/levir_train_103_9_t1.png` ->
  `levir_cd_train_103_9_before.png`; real LEVIR-CD before chip; 162163
  bytes; SHA-256
  `4153eb70e037c724dbddc5886de715953aacbcd97065590cc7e2f78f72aed12c`;
  256x256, 3 `uint8` bands, no CRS.
- `bck/tests/fixtures/levir_train_103_9_t2.png` ->
  `levir_cd_train_103_9_after.png`; real LEVIR-CD after chip; 154055 bytes;
  SHA-256
  `8d1e8ea0ed0aa4caf6fc45558546deefd359c48fe7f531944ac14758c02743d5`;
  256x256, 3 `uint8` bands, no CRS.
- Direct hash comparisons confirmed every packaged file is byte-for-byte equal
  to its named source fixture. No imagery or model data was downloaded. The
  repository evidence did not establish a specific fixture license, so no new
  licensing claim was made.

**Decisions and rejected alternatives**
- Kept five presets even when assets are reused so the frontend contract maps
  one-to-one to the five representative queries.
- Used explicit role-bound asset objects so temporal and cross-modal bindings
  do not depend on list positions.
- Reused the smallest verified Sen1Floods11 and LEVIR-CD fixtures. Synthetic
  samples, labels, unreadable NPZ data, external downloads, symlinks, a generic
  cache layer, endpoints, database changes, model changes, and frontend work
  were rejected as unnecessary or out of scope.
- Full validation reads raster width, height, band count, and dtypes inside a
  Rasterio environment with remote directory scans disabled and PROJ networking
  off. LEVIR PNG `NotGeoreferencedWarning` messages are expected and accepted.
- The real cached 13-band `int16` TIFF exposed a pre-existing dtype-ordering bug
  in ingestion: filling an integer masked array with NaN raised before the cast.
  With explicit user authorization, `_normalize_band()` now casts the masked
  array to `float32` before `.filled(np.nan)`. No other ingestion code changed.

**TDD and verification evidence**
- RED: `uv run pytest tests/core/test_demo_manifest.py -q` failed during
  collection with `ModuleNotFoundError: No module named 'app.core.demo_manifest'`.
- A later required offline pipeline test exposed the integer masked-array
  failure: `TypeError: Cannot convert fill_value nan to dtype int16` in
  `_normalize_band()`.
- After the authorized one-line fix, the exact test
  `test_single_image_cached_tiff_reaches_executable_pipeline_offline` passed:
  `1 passed`.
- Review RED: an embedded NUL asset path raised raw `ValueError: stat: embedded
  null character in path`. The validator now rejects NUL before filesystem
  resolution. Focused GREEN: `7 passed` for all unsafe-path cases.
- Final targeted command:
  `uv run pytest tests/core/test_demo_manifest.py -q -p no:cacheprovider
  --basetemp <workspace>/.pytest-tmp-jash005-target-final` ->
  `36 passed, 1 skipped, 36 warnings in 3.06s`. The one skip is the
  permission-bit unreadable-file case on Windows, where `os.access()` cannot
  create the intended unreadable condition; production read/open failures are
  still hard errors. The symlink-escape case executed and passed.
- Ingestion regression command:
  `uv run pytest tests/ingestion/test_raster.py -q -p no:cacheprovider
  --basetemp <workspace>/.pytest-tmp-jash005-ingestion-final` ->
  `3 passed, 2 warnings in 0.69s`.
- Full backend command:
  `uv run pytest -q -p no:cacheprovider --basetemp
  <workspace>/.pytest-tmp-jash005-full-final` ->
  `172 passed, 9 skipped, 47 warnings in 24.87s`.
- `uv run ruff check .` -> `All checks passed!`.
- `uv run ruff format --check .` -> `106 files already formatted`.
- `uv run lint-imports` -> analyzed 102 files / 219 dependencies; 3 contracts
  kept, 0 broken.
- Direct production `load_demo_manifest()` validation reported schema `1.0`,
  five presets, every declared binding resolved below the package root, and all
  four unique raster assets opened successfully with the metadata above.

**Offline/network-blocking evidence**
- Focused offline command for the all-preset routing test and executable
  single-image boundary -> `2 passed, 2 warnings in 3.50s`.
- Automated tests replace both `socket.create_connection` and
  `socket.socket.connect` with a loud `AssertionError`, then load and fully
  validate the canonical manifest, resolve assets, construct the existing
  `QueryRequest`, and execute the real router/classifier/planner handoff for all
  five presets. The declared intent, tool, and role-to-asset bindings matched
  for every preset with no attempted connection.
- With the same network blocker active, the current executable single-image
  pipeline consumed the actual cached 13-band optical TIFF and completed using
  an injected deterministic/local VQA model boundary. Raster ingestion, routing,
  and answer/evidence assembly therefore operated without an external data or
  model fetch in that tested boundary.
- Manifest runtime paths are local package-relative paths only. Rasterio runs
  with `GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR` and `PROJ_NETWORK=OFF` during
  validation.

**Limitations and YASH-008 handoff**
- JASH-005 does **not** prove all five presets through full production-model
  end-to-end execution. InternVL3 weights were not present in the detected local
  Hugging Face cache, and the production loader may otherwise fetch remotely.
- A local BIT checkpoint was absent.
- The current main application pipeline does not execute multi-image
  change-detection or fusion dispatch plans end to end.
- YASH-008 must first ensure locally available InternVL3 weights, a locally
  available BIT checkpoint, and implemented main-pipeline change/fusion
  execution; then run all five judged presets with networking disabled and
  verify no model, metadata, STAC, tile, or other external fetch occurs.
- Consequently, local package/validation, all-preset routing/planning, and the
  injected-model single-image boundary are verified; judge-level all-preset
  production inference remains partial pending those preconditions.

**Review fix (PR #40 send-back)**
- PR #40 reviewed by ybaddam8-png with two blockers:
  1. Missing direct regression test for _normalize_band() int16 masked-array handling in test_raster.py.
  2. Manifest contract / field shape unblock comment for LIKI-006 needed on handoff surface.
- Added direct unit regression test_normalize_band_handles_int16_masked_array() in bck/tests/ingestion/test_raster.py.
- Verified RED reproduction against pre-fix code order np.asarray(band.filled(np.nan), dtype=np.float32): raised TypeError: Cannot convert fill_value nan to dtype int16.
- Verified GREEN with production line band.astype(np.float32).filled(np.nan) (1 passed in 0.36s).
- Targeted suites: tests/ingestion/test_raster.py 4 passed; tests/core/test_demo_manifest.py 36 passed, 1 skipped.
- Full backend gates: Ruff check PASS, Ruff format PASS (106 files), import-linter 3 kept, 0 broken, full pytest 173 passed, 9 skipped in 11.92s.
- Manifest contract handoff documented and posted for LIKI-006.
- Manifest JSON and asset binaries remain untouched.

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

### 2026-09-07 — Render BBOX evidence on map (LIKI-005) — Antigravity

**Done**
- Converted BBoxPayload [minLon, minLat, maxLon, maxLat] tuples into closed 5-point GeoJSON Polygon rings.
- Integrated BBOX rendering into satquery-evidence across evidence-mask-fill, evidence-boundary-line, and evidence-selected-halo layers.
- Wired highlight selection to useFeatureHighlight to keep CitationChip interaction unified without parallel state logic.
- Implemented camera fitBounds with padding when selected bounding boxes fall outside the active viewport.
- Added 22 unit and component tests across evidenceGeoJson.test.ts and EvidenceMap.test.tsx.

**Decided**
- Reused existing MapLibre layers and selection filter instead of creating separate BBOX layers to avoid pipeline divergence.
- Guarded zero-area/point degenerate bounding boxes with an epsilon offset to prevent MapLibre camera crashes.

**Incomplete**
- None. Ready for backend integration with ticket AASH-005.
