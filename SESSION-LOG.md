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
