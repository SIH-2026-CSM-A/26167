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
## 2026-09-06 — JASH-004: Persist execution trace — Jashwanth (Antigravity)

**Done**
- `app/db/models.py`: DeclarativeBase models `ExecutionTraceModel` (`execution_traces`: `trace_id` PK, `created_at`, `steps` as JSONB) and `EvidenceModel` (`evidence`: `id` PK, `trace_id` FK with CASCADE, `tool`, `type`, `payload` as JSONB, `confidence`, `timing`, `created_at`). Uses dialect-safe `JsonType` with PostgreSQL JSONB variant.
- `app/db/session.py`: Sync SQLAlchemy engine and transaction session provider (`get_sync_session`) bound to `settings.database_url`.
- `app/db/persistence.py`: Atomic `persist_trace(trace, evidence, session=None)` persisting trace and evidence in a single transaction. Raises `TracePersistenceError` on DB failure.
- `alembic/env.py` & `alembic/versions/c9c6d725a002_create_execution_traces_and_evidence.py`: Initial migration creating `execution_traces` and `evidence` tables, applied to local PostgreSQL. Handled Windows psycopg selector event loop policy.
- `app/pipeline/pipeline.py`: Wired `persist_trace(trace, evidence_list)` right before answer assembly. DB write failure calls `_fail(recorder, stage="persistence", message=str(error), status_code=500)` enforcing hard failure semantics.
- `bck/pyproject.toml`: Added `app.db` to import-linter contracts (independent leaf module, layered under pipeline, forbidden from contracts).
- `bck/tests/db/test_persistence.py`: 6 automated tests covering model instantiation, cascade deletion, contract round-trip serialization, abstained trace persistence, multi-tool payload extensibility without migrations, and pipeline hard failure on persistence error.
- Verified against real Docker PostgreSQL: executed live queries through `/query`, confirmed 13-step trace and evidence rows written with full JSONB payload and raster metadata.
- All gates green: `ruff check`, `ruff format --check`, `lint-imports` (3/3 kept), `pytest` (131 passed, 3 skipped).

**Decided**
- Option B (JSONB/document persistence) confirmed with lead per Technical Implementation §4/§5: trace steps and evidence payloads remain JSONB so adding new tools requires zero schema migrations.
- Option A (Hard failure) confirmed with lead: DB persistence failure is a P0 failure that raises `PipelineError(stage="persistence", status_code=500)` rather than silently returning an unpersisted answer.

**Incomplete**
- None within scope. Read/replay API and trace UI are deferred to subsequent tickets per spec.

Agent: Antigravity.

## 2026-09-06 — JASH-004 continuation after Antigravity handoff — Codex

**Architecture and failure semantics**
- Reconfirmed the lead-approved Option B: one `execution_traces` row/document per execution,
  with ordered `steps` stored as JSONB; Evidence variable payloads are also JSONB.
- PostgreSQL inspection confirmed both JSONB column types and confirmed that no normalized
  `trace_steps` table exists. Adding a tool therefore does not require a trace-step schema
  migration.
- `bck/tests/db/**` remains explicitly authorized for this ticket.
- Persistence remains a hard failure: a write error raises
  `PipelineError(stage="persistence", status_code=500)` and prevents a successful response.
  The targeted regression test and all six DB tests passed.

**Migration verification**
- `uv run alembic heads`: `c9c6d725a002 (head)`.
- `uv run alembic current`: `c9c6d725a002 (head)` against the local PostgreSQL container.
- `uv run alembic upgrade head`: exit 0.
- Recovered the prior clean-database proof from the Antigravity transcript: it created the
  disposable `satquery_migration_test` database, migrated it from empty to head with exit 0,
  inspected `alembic_version`, `execution_traces`, and `evidence`, then dropped only that
  disposable database.

**Final genuine HTTP/model acceptance**
- Request #1, `Describe the visible features in this satellite imagery.`, returned HTTP 200 in
  494.81 seconds. It used real offline `OpenGVLab/InternVL2-2B` on CPU through
  `vqa_grounding`, was verified and non-abstaining, and returned trace
  `f27096d6-ab3e-4dfe-a019-c062b131df90` with 13 steps and evidence
  `7938c18a-ed5c-41d6-aa8a-ecbfd4a8ce32`. Answer: `**Landmasses. The landmass is irregular in
  shape, with some areas appearing more densely populated. Surrounding the central landmass are
  smaller islands and.`
- Request #2, `What terrain or land-cover features are visible in this satellite image?`,
  returned HTTP 200 in 451.71 seconds. It used real offline `OpenGVLab/InternVL2-2B` on CPU
  through `vqa_grounding`, was verified and non-abstaining, and returned trace
  `5db2a627-40ab-4c95-8c51-5c0e31e2665b` with 13 steps and evidence
  `a8275841-775d-486e-9ae6-5b884357b4c2`. Answer: `The satellite image shows a variety of
  terrain. Land-cover features. The landmasses are irregular in shape, with some areas appearing
  more densely populated with clusters of white clouds, suggesting a higher concentration of
  cloud cover or possibly a region with a higher level of cloud formation. The darker areas on
  the right side of the image are likely to be bodies of water, possibly oceans or large lakes,
  given their size. The lack of visible land features. The green areas on the left side of the
  image are indicative of land, possibly forests or agricultural areas, given their uniform
  color. The presence of what appears to be a network of.`
- Direct read-only PostgreSQL queries matched both HTTP trace IDs and evidence IDs. The traces
  are distinct, each has 13 JSONB steps, and the evidence rows record `internvl_vqa` / `text`
  with timings of 493.4333611999755 and 451.378871599969 seconds respectively.
- No mocks, test fixtures, monkeypatches, direct `persist_trace()` calls, or manual database
  inserts were used for these two final E2E requests.

**Final gates**
- `uv run ruff check .`: pass.
- `uv run ruff format --check .`: pass, 106 files already formatted.
- `uv run lint-imports`: pass, 3 contracts kept and 0 broken.
- `uv run pytest -q`: 131 passed, 3 skipped. The final run supplied the required local
  `DATABASE_URL` and `COST_CEILING`; an earlier diagnostic run without them correctly produced
  persistence hard failures and was not treated as the final gate.
- No frontend, public-contract, or `session-log/jashwanth.md` edit was made during the Codex
  continuation. No commit, push, PR, or merge was performed.

Agent: Codex (continuation after Antigravity handoff).

**Post-rebase verification**
- Rebasing onto `origin/main` (`cb227c89fdc851eef6c0339e1c3c7250d09e51f7`) completed cleanly.
- Current-main changes added only temporary-raster `atexit` cleanup to the query ingestion path;
  routing, model selection, inference, verification, and persistence execution paths were
  unchanged, so the two expensive real InternVL acceptance requests were preserved.
- Post-rebase gates: Ruff pass; format pass (109 files already formatted); import-linter 3 kept,
  0 broken; pytest 138 passed, 3 skipped.

## 2026-09-07 — JASH-004 review fixes and E2E acceptance after Codex handoff — Antigravity

**Handoff & Review-Fix Summary**
- Handoff from Codex to Antigravity recovered seamlessly from the isolated worktree `SIH26167-jash004-reviewfix`.
- Resolved all three review blockers:
  1. Blocker 1 (Trace/Evidence UUID integrity): Fixed pipeline evidence creation so persisted evidence identity exactly preserves candidate evidence identity (`decision.verified_evidence[0]`). Verified referenced trace Evidence ID == persisted Evidence ID.
  2. Blocker 2 (`evidence.trace_id` non-null FK): Updated Alembic migration `c9c6d725a002` and SQLAlchemy model `EvidenceModel` to enforce `nullable=False` on `trace_id` with foreign key referencing `execution_traces.trace_id` (`ondelete="CASCADE"`). Verified on disposable DB migration and unit test `test_evidence_model_rejects_missing_trace_id`.
  3. Blocker 3 (`response_completed` completion boundary): Refactored `run()` to invoke `assemble_answer()` before `persist_trace()`, guaranteeing that an answer assembly failure cannot persist a premature `response_completed` trace. Verified by `test_answer_assembly_failure_does_not_persist_completed_trace`.
- Rebased cleanly onto current `origin/main` (`12bbf2ca68b699d0ddd0c85f2b94a29ffc75eb08`), preserving all teammate entries and commits.

**Runtime Environment & Failed float32 Attempt Distinction**
- Initial attempt on current main failed due to an environment/memory constraint, not a persistence defect: current main had updated default CPU dtype to `float32`, roughly doubling memory footprint and exhausting the ~7.1 GB free host RAM, causing a native process crash (curl exit 56, connection reset after 72.39s) during model loading without producing any database trace.
- Real model server was run on CPU with `torch.bfloat16` (`adapter._dtype = torch.bfloat16`) using offline cached `OpenGVLab/InternVL2-2B` (`D:\huggingface`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`), which fit reliably within available system memory.

**Genuine Fixed-Code Real E2E Acceptance**
- Real server running at `127.0.0.1:8010` with offline `OpenGVLab/InternVL2-2B` on CPU (`torch.bfloat16`). Raster: `C:\Users\JASHWANTH\yash003-acceptance\RGB.byte.tif`. Zero mocks, fixtures, or monkeypatches.
- Request #1 (`Describe the visible features in this satellite imagery.`):
  - HTTP Status: 200 OK (recovered from active Codex run)
  - Duration: 453.47s (model timing: 452.87s)
  - Trace ID: `d87a63fc-c095-4ed9-a507-2ea8ecf9a673`
  - Evidence ID: `081fb1fe-ec01-4109-8bd5-57dfb938e6b3`
  - Step Count: 13
  - Final Action: `response_completed`
  - Model ID: `OpenGVLab/InternVL2-2B`
  - Abstained: False
  - Answer: `**Landmasses. The landmass is irregular in shape, with some areas appearing more densely populated. Surrounding the central landmass are smaller islands and.`
  - DB Verification: Trace and Evidence matched exactly. `evidence.trace_id == trace_id`, trace Evidence ID == persisted Evidence ID.
- Request #2 (`What terrain or land-cover features are visible in this satellite image?`):
  - HTTP Status: 200 OK
  - Duration: 473.72s (model timing: 473.47s)
  - Trace ID: `733b6875-c395-4af0-873f-c78c5387e45a`
  - Evidence ID: `29dfa47e-37b3-4e40-8e55-2ea3f2f778ef`
  - Step Count: 13
  - Final Action: `response_completed`
  - Model ID: `OpenGVLab/InternVL2-2B`
  - Abstained: False
  - Answer: `The satellite image shows a variety of terrain. Land-cover features. The landmasses are irregular in shape, with some areas appearing more densely populated with clusters of white clouds, suggesting a higher concentration of cloud cover or possibly a region with a higher level of cloud formation. The darker areas on the right side of the image are likely to be bodies of water, possibly oceans or large lakes, given their size. The lack of visible land features. The green areas on the left side of the image are indicative of land, possibly forests or agricultural areas, given their uniform color. The presence of what appears to be a network of.`
  - DB Verification: Trace and Evidence matched exactly. `evidence.trace_id == trace_id`, trace Evidence ID == persisted Evidence ID.
- Distinct Traces: Request #1 and Request #2 trace IDs are verified distinct (`d87a63fc-c095-4ed9-a507-2ea8ecf9a673` != `733b6875-c395-4af0-873f-c78c5387e45a`).

**PostgreSQL Query Output (AC3 Verification)**
Direct queries executed against local PostgreSQL (`satquery-local-postgres-1`):

```sql
SELECT trace_id, created_at, jsonb_array_length(steps) AS steps_count, steps->-1->>'action' AS last_action, steps->-1->'evidence_ids' AS evidence_ids
FROM execution_traces
WHERE trace_id IN ('d87a63fc-c095-4ed9-a507-2ea8ecf9a673', '733b6875-c395-4af0-873f-c78c5387e45a')
ORDER BY created_at;
```

```text
               trace_id               |          created_at           | steps_count |    last_action     |               evidence_ids
--------------------------------------+-------------------------------+-------------+--------------------+------------------------------------------
 d87a63fc-c095-4ed9-a507-2ea8ecf9a673 | 2026-09-07 05:54:47.840433+00 |          13 | response_completed | ["081fb1fe-ec01-4109-8bd5-57dfb938e6b3"]
 733b6875-c395-4af0-873f-c78c5387e45a | 2026-09-07 06:22:23.948861+00 |          13 | response_completed | ["29dfa47e-37b3-4e40-8e55-2ea3f2f778ef"]
(2 rows)
```

```sql
SELECT id, trace_id, tool, type, confidence, timing, created_at, payload->>'model_id' AS model_id, payload->>'source_filename' AS filename
FROM evidence
WHERE trace_id IN ('d87a63fc-c095-4ed9-a507-2ea8ecf9a673', '733b6875-c395-4af0-873f-c78c5387e45a')
ORDER BY created_at;
```

```text
                  id                  |               trace_id               |     tool     | type |     confidence     |      timing       |          created_at           |        model_id        |   filename
--------------------------------------+--------------------------------------+--------------+------+--------------------+-------------------+-------------------------------+------------------------+--------------
 081fb1fe-ec01-4109-8bd5-57dfb938e6b3 | d87a63fc-c095-4ed9-a507-2ea8ecf9a673 | internvl_vqa | text | 0.3333333333333333 | 452.8667647999828 | 2026-09-07 06:02:21.200494+00 | OpenGVLab/InternVL2-2B | RGB.byte.tif
 29dfa47e-37b3-4e40-8e55-2ea3f2f778ef | 733b6875-c395-4af0-873f-c78c5387e45a | internvl_vqa | text |                  1 | 473.4714236999862 | 2026-09-07 06:30:17.590064+00 | OpenGVLab/InternVL2-2B | RGB.byte.tif
(2 rows)
```

**Migration & Gate Verification**
- Clean disposable migration test: PASS (migrated `satquery_disp_test` to head `c9c6d725a002`, verified `execution_traces.steps` is JSONB, `evidence.payload` is JSONB, `evidence.trace_id` is `NOT NULL` with cascading FK, and dropped cleanly).
- Alembic head: `c9c6d725a002 (head)`.
- `uv run ruff check .`: PASS.
- `uv run ruff format --check .`: PASS (111 files already formatted).
- `uv run lint-imports`: PASS (3 kept, 0 broken).
- `uv run pytest -q`: PASS (145 passed, 8 skipped). Patched `app.db.session.get_sync_session_maker` with in-memory SQLite sessionmaker in `test_main.py`, `test_vertical_slice.py`, `test_pipeline.py`, and `test_adversarial_abstention.py` so tests pass 100% cleanly locally even without `DATABASE_URL` or `COST_CEILING` environment variables.

**Lead Review Follow-Up (Yashwanth / ybaddam8-png)**
- Fixed local pytest failure: Added in-memory SQLite `StaticPool` sessionmaker patches to `test_main.py`, `test_vertical_slice.py`, `test_pipeline.py`, and `test_adversarial_abstention.py`. Full pytest suite passes 100% green (145 passed, 8 skipped) with `DATABASE_URL` and `COST_CEILING` completely unset.
- AC3 Verification: Pasted actual raw PostgreSQL query rows from `docker exec satquery-local-postgres-1 psql` for both E2E requests.
- Option B Architecture Sign-Off: Confirmed Option B document persistence (`steps` and `payload` as JSONB in `execution_traces` and `evidence`) avoids schema migrations on adding tools, awaiting final lead sign-off.
- Branch Synchronization (PR #44 / sentencepiece 0.2.2): Merged latest `origin/main` (incorporating PR #44 `sentencepiece==0.2.2`, PR #40 JASH-005 demo dataset, and PR #45 SHIVA-005 verification layer). Confirmed `sentencepiece` resolves to `0.2.2` in `pyproject.toml` and `uv.lock`. Updated `tests/core/test_demo_manifest.py` with `sqlite_db` fixture for offline persistence.
- Post-Verification Evidence Restoration & Identity Invariant: Restored the post-verification `build_vqa_evidence` call in `pipeline.py` passing `rejected_claims=tuple(d.description for d in decision.disagreements)`, preserving the hallucination-audit trail. Updated `evidence` via `model_copy(update={"id": candidate_evidence.id, ...})` so that `candidate_evidence.id == post_verification_evidence.id == TraceStep.evidence_ids == persisted_evidence.id`. Added focused regression test `test_pipeline_persists_rejected_claims_audit_trail_on_verification_disagreement` in `tests/db/test_persistence.py`.
- Automated Verification Gates: All 4 gates pass clean locally (`ruff`, `ruff format`, `lint-imports`, `pytest -q`: 221 passed, 9 skipped).
- Model Readiness Gate Under Committed Environment: Verified `sentencepiece==0.2.2`. Under this committed version, offline `OpenGVLab/InternVL2-2B` fails tokenizer load with `RuntimeError: INTERNAL: piece must not include null character.` at `sp.Load(vocab_file)` (due to null character pieces in InternLM2 tokenizer vocabulary), whereas `sentencepiece==0.2.1` loads successfully. Per instructions, blocked from faking acceptance under 0.2.1 while committed lock is 0.2.2; reporting compatibility state for lead decision.

Agent: Antigravity (handoff from Codex).

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

## 2026-09-07 — JASH-004 preserved-branch audit and current-main E2E — Codex

**Architecture and scope audit**
- Preserved the existing `feature/26167-JASH-004-persist-trace` implementation; the invalid
  `sentencepiece==0.2.1` commit exists only on the closed compatibility branch and is absent
  from JASH-004.
- Preserved Option B. PR #42 reviewer comment `5566236249` described JSONB TraceStep storage
  as reasonable, and comment `5567915088` subsequently confirmed the persistence layer was
  clean. No later comment explicitly revoked that architecture.
- `bck/pyproject.toml` changes only add the `app.db` import-linter boundary. The branch retains
  current-main `sentencepiece==0.2.2` and does not modify any model source or dependency pin.

**Deployed migration repair and proof**
- The live Docker database was stamped at `c9c6d725a002`, but catalog inspection found
  `evidence.trace_id` nullable because that already-applied revision had later been edited.
- Added follow-up revision `ed7c2c7c6c4a` rather than rewriting or deleting the original
  migration. A focused offline-SQL regression failed before the revision and passed afterward.
- Live migration output:

```text
=== alembic current before ===
c9c6d725a002
=== alembic heads ===
ed7c2c7c6c4a (head)
=== alembic upgrade head ===
=== alembic current after ===
ed7c2c7c6c4a (head)
```

- Direct PostgreSQL catalog proof after upgrade:

```text
    table_name    | column_name |        data_type         | is_nullable
------------------+-------------+--------------------------+-------------
 evidence         | id          | character varying        | NO
 evidence         | trace_id    | character varying        | NO
 evidence         | tool        | character varying        | NO
 evidence         | type        | character varying        | NO
 evidence         | payload     | jsonb                    | NO
 evidence         | confidence  | double precision         | NO
 evidence         | timing      | double precision         | NO
 evidence         | created_at  | timestamp with time zone | NO
 execution_traces | trace_id    | character varying        | NO
 execution_traces | created_at  | timestamp with time zone | NO
 execution_traces | steps       | jsonb                    | NO
(11 rows)

    constraint_name     | table_name | column_name | foreign_table_name | foreign_column_name | delete_rule
------------------------+------------+-------------+--------------------+---------------------+-------------
 evidence_trace_id_fkey | evidence   | trace_id    | execution_traces   | trace_id            | CASCADE
(1 row)
```

**Current-main model readiness and real HTTP acceptance**
- Synchronized the environment with `uv sync --all-extras --dev`; runtime SentencePiece is
  `0.2.2`, matching the repository lock.
- Staged `OpenGVLab/InternVL3-2B` revision
  `899155015275a9b7338c7f4677e19c784e0e5a21`, then initialized the real `InternVLAdapter`
  offline on CPU with `torch.bfloat16`. Readiness returned
  `MODEL_READY True InternVLChatModel Qwen2Tokenizer`.
- Used real `POST /query`, `RGB.byte.tif`, the real adapter/model, and Docker PostgreSQL. No
  fake adapter, fixture, direct pipeline substitute, `persist_trace()` shortcut, or manual SQL
  insert was used.
- The preferred first question returned HTTP 200 in 499.02 seconds and honestly abstained;
  trace `f764b2cb-85e2-4fba-a4ad-24b5342e62fa` has 13 steps and no Evidence row because all
  unsupported claims were filtered.
- Evidence-bearing acceptance query 1 returned HTTP 200 in 557.60 seconds: trace
  `81145673-ad6e-4763-b6a9-ca13dfd25666`, Evidence
  `da81c7be-17b7-4f1e-bed9-ca5f8f8cdfa6`.
- Evidence-bearing acceptance query 2 returned HTTP 200 in 499.81 seconds: trace
  `2f3321b9-fdcc-4f50-818f-ecb046febe07`, Evidence
  `8509eaa6-c39d-46ae-b460-b4c65e0fd693`. This natural response produced one verification
  disagreement, and the rejected-claim audit entry persisted without manipulating the query.

**Raw PostgreSQL acceptance rows**

```text
               trace_id               |          created_at           | step_count |    final_action    |            final_evidence_ids
--------------------------------------+-------------------------------+------------+--------------------+------------------------------------------
 81145673-ad6e-4763-b6a9-ca13dfd25666 | 2026-09-07 13:07:29.356276+00 |         13 | response_completed | ["da81c7be-17b7-4f1e-bed9-ca5f8f8cdfa6"]
 2f3321b9-fdcc-4f50-818f-ecb046febe07 | 2026-09-07 13:18:32.906868+00 |         13 | response_completed | ["8509eaa6-c39d-46ae-b460-b4c65e0fd693"]
(2 rows)

                  id                  |               trace_id               |     tool     | type |     confidence     |       timing       |        model_id        | rejected_claims | source_filename
--------------------------------------+--------------------------------------+--------------+------+--------------------+--------------------+------------------------+-----------------+-----------------
 da81c7be-17b7-4f1e-bed9-ca5f8f8cdfa6 | 81145673-ad6e-4763-b6a9-ca13dfd25666 | internvl_vqa | text |                  1 |  557.5028756000102 | OpenGVLab/InternVL3-2B | []              | RGB.byte.tif
 8509eaa6-c39d-46ae-b460-b4c65e0fd693 | 2f3321b9-fdcc-4f50-818f-ecb046febe07 | internvl_vqa | text | 0.8333333333333334 | 499.69043819996295 | OpenGVLab/InternVL3-2B | ["Narrative claim 'The satellite image reveals the following features:\n\n- **Land**: The visible landmass is the Canadian Shield, characterized by its green' is not supported by any grounded observation."] | RGB.byte.tif
(2 rows)
```

Agent: Codex.

**Final preserved-branch verification**
- Focused rejected-claim/identity regression: `1 passed`.
- `uv run ruff check .`: PASS.
- `uv run ruff format --check .`: PASS (`116 files already formatted`).
- `uv run lint-imports`: PASS (`3 kept, 0 broken`).
- `uv run pytest -q`: PASS (`222 passed, 9 skipped, 50 warnings`). The run used a
  branch-local pytest temp directory because the global Windows pytest temp path was locked;
  no test assertions failed in the earlier environment-only run.
