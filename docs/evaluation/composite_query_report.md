# Composite query: change detection → VQA on the changed region

This closes the problem statement's orchestration requirement: the system must "select, **sequence**, and execute" specialist tools. Until now exactly one tool ran per query (`architecture_findings.md` §2). One fixed two-tool sequence now exists. It is not a general planner.

- **Branch:** `feat/26167-composite-orchestration`, not pushed.
- **Base:** `d22a692`, the tip of `feat/26167-hf-zerogpu-inference` (draft PR #77). Step 2's VQA uses that branch's remote inference path, so `pipeline.py` is not edited on two diverging bases. That branch sits on #76, which sits on `origin/main` `78bd9ef`, the latest descendant of `feat/26167-console-v2-redesign`.
- **Code under test:** `563da23`.

## Status

| Step | Status |
|---|---|
| 0: safety | Done. Uncommitted files stashed as `stash@{0}` "pre-composite-orchestration-2026-09-25" |
| 1: design | Done. The requested scenario has no fixture; an alternative was approved (below) |
| 2: implementation plus unit tests | Done (`563da23`) |
| 3: CI | Green (below) |
| 4: live positive-path capture | **Blocked.** It needs the inference Space `ybaddam8/satquery-inference` deployed and answering `/vqa_ground` and `/change_detect` |
| 5: live negative-case capture | Done (below) |

## Step 1: design decision

**The requested scenario is not backed by fixtures.** "Change detection on an optical pair, then fusion on an optical+SAR pair" needs a bi-temporal pair in which one date is also a co-registered optical+SAR pair. What exists:

| Fixture | Bi-temporal | Optical + SAR | CRS |
|---|---|---|---|
| LEVIR-CD `levir_test_1`, `levir_train_103_9` | yes | optical RGB PNG only | none |
| Sen1Floods11 Bolivia_103757 (S1 VV/VH, S2 13-band) | one date only | yes | EPSG:4326 |

Two further problems:
- **BIT is out of domain.** It is a LEVIR building-change model (0.5 m). Using it for water change on 10 m Sentinel-2 would produce meaningless numbers.
- **The available second date doesn't fit the pipeline.** A second real date exists on Planetary Computer (a live STAC query found 126 S2 L2A dates and 165 S1 RTC dates over the fixture's footprint, 2018–2019). But L2A has no B10 band, so s2cloudless can't run on it, and RTC gamma0 is not the σ0 dB the fusion tool assumes. Using it would need new data acquisition and preprocessing.

**Approved alternative:** `change_detection → vqa_grounding` on the LEVIR pair. Example query: "What changed between these dates, and what are the new structures in the changed area?" Both models run in their own domain, and step 2 genuinely consumes step 1's output.

| Decision | What was built |
|---|---|
| Schema | `DispatchPlan.followups: tuple[ToolStep, ...] = ()`. `tool_name` / `image_bindings` / `task_parameters` are unchanged, so every single-tool caller and test is untouched. There is a `tool_sequence` property. `ToolStep.input_from_previous` has exactly one allowed value, `"largest_change_component"` |
| Routing rule | New `TaskType.CHANGE_DESCRIBE` requires a change cue (the existing CHANGE_VQA patterns) **and** a cue asking what the changed area contains: "new structures/buildings/…", "what kind/type of", "what was built/demolished/…", "identify the new …", "in the changed area". It is evaluated after fusion and before CHANGE_VQA. "Describe what changed between these images" stays CHANGE_VQA |
| Threading | The largest **8-connected component** of the post-gate change mask (BIT's 256×256 space) is scaled to post-image pixels, padded to at least 128 px per side (centred, clamped to the image), and cropped. VQA runs on that crop; its box is shifted back to full-frame pixels before georeferencing. With no component left after the confounder gate, step 2 is skipped and recorded as `sequence_short_circuit` |
| Trace | One trace. `route_selected.tool_sequence`. `sequence_step_started` / `sequence_step_completed` (timed) for each step, around each tool's own existing steps. `sequence_handoff` records the component's pixel area, its mask-space bbox, the crop box and the crop size |
| One answer, one confidence | A single `verify()` over both tools' evidence. The text is the change narrative plus "In the largest changed region: {verified VQA answer}". Confidence is the **minimum** over the surviving evidence, a **design choice** labelled as such in code (a chain is only as reliable as its weakest step), not a sourced rule |
| Loop-proofing | `MAX_TOOL_CALLS = 2`: a `DispatchPlan` validator rejects longer plans, the pipeline counts tool executions, and it refuses any sequence other than `["change_detection", "vqa_grounding"]` |
| Vetoes | Same structural checks as CHANGE_VQA (exactly 2 images, capture order 0/1). They run in the router, before either tool |

## Code changes (`563da23`)

| File | Change |
|---|---|
| `bck/app/router/schemas.py` | `CHANGE_DESCRIBE`, `ToolStep`, `DispatchPlan.followups` plus cap validator, `tool_sequence`, `MAX_TOOL_CALLS` |
| `bck/app/router/classifier.py` | `_CHANGE_CONTENT_PATTERNS`, and the change-plus-content rule before CHANGE_VQA |
| `bck/app/router/planner.py` | The CHANGE_DESCRIBE plan: change detection with a VQA followup on the post image |
| `bck/app/router/veto.py` | CHANGE_DESCRIBE gets the CHANGE_VQA inventory vetoes; registry entry added |
| `bck/app/router/router.py`, `__init__.py` | `tool_sequence` in router trace params; exports |
| `bck/app/pipeline/pipeline.py` | `_run_change_then_describe`, `_largest_change_component`, `_padded_region`, `_combine_change_and_vqa`; `region` crop support in `_run_vqa_tool` / `_run_remote_vqa`; `tool_sequence` in `route_selected` |
| `bck/app/evidence/builder.py` | `assemble_answer(confidence=...)` optional override. The default is still the mean |
| `bck/tests/router/test_change_describe.py` | 8 paraphrases, 6 near misses, the plan, the cap, 2 vetoes |
| `bck/tests/pipeline/test_change_describe_sequence.py` | Run order, handoff geometry, crop size equals the VQA input, trace order, min confidence, short-circuit, veto before any tool (×2), 5 padding and clamping cases |

In the pipeline tests the models are stand-ins (a known BIT probability map and the deterministic in-process VQA model); every other stage is real. One finding came from a real stage: a 1,200 px changed square (1.83% of the frame) was suppressed by the real confounder gate's 2.0% floor. The short-circuit did what it should, and the test now uses a 3,000 px (4.6%) region.

## Step 3: CI (`bck/`, at `563da23`)

`uv sync --all-extras --dev && uv run ruff check . && uv run ruff format --check . && uv run lint-imports && uv run pytest -q` (exit 0):

```
Resolved 152 packages in 28ms
Checked 142 packages in 38ms
All checks passed!
202 files already formatted
Analyzed 160 files, 504 dependencies.
Leaf modules never import each other KEPT
Only pipeline composes modules KEPT
API and pipeline never load local models or torch KEPT
Contracts import nothing of ours KEPT
Contracts: 4 kept, 0 broken.
509 passed, 1 skipped, 112 warnings in 27.12s
```

One earlier full run, before this one, had a single failure: `tests/pipeline/test_trace_timing.py::test_stage_step_spans_its_work`. That test asserts that a 0.05 s `time.sleep` shows up as at least 0.05 s of `datetime.now()` wall-clock. It passed alone and in both later full runs, and it doesn't touch any code changed here. It is a pre-existing timing flake (WSL2 wall-clock adjustment), reported, not edited.

## Step 5: negative case, live (no mocks)

**Stack:**
- Vite dev server (`fnt/`, :5173) → Vite proxy → FastAPI (`bck/`, uvicorn :8000) → Postgres and TiTiler (`infra/docker-compose.yml`), with `INFERENCE_SPACE` unset.
- Headed Chromium (Playwright 1.62.1) at 1600×1000 with `--disable-gpu`, logged in with a throwaway account whose email and password were generated at run time.
- Captured 2026-09-25T12:22:18Z.

**Input:** the Upload page in Single Image mode, one LEVIR post-date image (`bck/tests/fixtures/levir_test_1_t2.png`, optical), and the composite query "What changed between these dates, and what are the new structures in the changed area?". Uploading a single image is the only way the UI lets a user send this query with a missing input; the bi-temporal mode won't submit with an empty slot. The missing capture order case (`TEMPORAL_ORDER_MISSING`) is covered by unit tests, not by a live capture.

**API response (`POST /query`):**

| Field | Value |
|---|---|
| HTTP status | **422** |
| `reason_code` | **`INSUFFICIENT_IMAGES`** |
| stage | `routing` |
| message | "Change detection requires 2 temporal images (pre- and post-event), but 1 was provided." |
| suggested_action | "Upload both pre-event and post-event satellite scenes." |
| trace_id | `2c10285c-5d74-4b73-98c8-98783e4dde30` |
| Trace steps | **7** |
| Pipeline ms (`trace.created_at` → last `completed_at`) | 169.2 |
| Round trip ms (browser, click → response) | 10,354. This was the backend's first `/query` after start, so it includes importing the pipeline cold; in an earlier run on a backend that had already served a request it was 2,745 ms |

| # | Step | Duration | Notes |
|---|---|---|---|
| 1 | `pipeline.request_received` | 0.00 ms | `image_count: 1` |
| 2 | `api.asset_received` | 0.01 ms | |
| 3 | `ingestion.asset_ingestion_started` | 0.00 ms | |
| 4 | `ingestion.asset_ingested` | 168.23 ms | |
| 5 | `router.routing_started` | 0.00 ms | |
| 6 | `router.route_selected` | 0.20 ms | `intent: change_describe`, `tool: null`, `tool_sequence: []`, `supported: false` |
| 7 | `routing.execution_failed` | 0.00 ms | |

**Vetoed before any tool ran:**
- The trace has no `sequence_step_*`, `change_detection_started`, `remote_change_detect_call`, `bit_forward_pass`, `vqa_started` or `internvl_*` step.
- The uvicorn log for the run has no change-detection, VQA or gradio call.
- The router recognised the composite intent (`change_describe`) and refused it on inventory, the same path single-tool CHANGE_VQA uses.

**Screenshots** (`docs/evaluation/screenshots/`):

| File | Content |
|---|---|
| `composite_veto_single_image.png` | Full page, veto message, trace collapsed |
| `composite_veto_single_image_panel.png` | Tight crop of the veto alert (16 px margin) |
| `composite_veto_single_image_trace.png` | Full page, trace expanded, every step's parameters open |
| `composite_veto_single_image_trace_panel.png` | Tight crop of the alert with the expanded trace |

Capture method follows `run_log.md`: scroll to the top and wait 4 s for the globe texture before each full-page capture. Panels are clipped in document coordinates at scroll position 0. A first attempt clipped after scrolling the alert into view, which painted the sticky nav bar over the top of the tall trace panel; that capture was discarded.

## Step 4: positive path, pending

This is blocked until `ybaddam8/satquery-inference` is deployed and answering both endpoints. With the Space up and `INFERENCE_SPACE` / `HF_TOKEN` set, the same capture runs the LEVIR pair through the bi-temporal slots. It should record: the ordered `tool_sequence`, the handoff (component area, bbox, crop), real per-step timings for both tools, both evidence items, the final (min) confidence and the total pipeline ms.
