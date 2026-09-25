# Composite query: change detection → VQA on the changed region

This closes the problem statement's orchestration requirement: the system must "select, **sequence**, and execute" specialist tools. Until now exactly one tool ran per query (`architecture_findings.md` §2). One fixed two-tool sequence now exists. It is not a general planner.

- **Branch:** `feat/26167-composite-orchestration`, not pushed.
- **Base:** `594324d` on `feat/26167-hf-zerogpu-inference` (draft PR #77). Step 2's VQA uses that branch's remote inference path, so `pipeline.py` is not edited on two diverging bases. #77 sits on #76, which sits on `origin/main` `78bd9ef`, the latest descendant of `feat/26167-console-v2-redesign`.
- **Code under test:** `4de1a1e`.
- **Inference:** the Space `ybaddam8/satquery-inference` on `cpu-upgrade`, fp32, InternVL3-2B@`89915501` plus adapter `796d3c25`, BIT `c159ba76`. The Space's startup log shows both sha256 checks passing.

| Commit | What |
|---|---|
| `dc6f01c` | The sequence: router, planner, pipeline, tests |
| `df1d6a2` | First version of this report, with the Step 5 capture |
| `8f88ea2` | `planned_sequence` on `route_selected`, including vetoed requests |
| `b0fad73` | LEVIR-CD **test**-split demo pair (fixture plus provenance) |
| `04d48c9` | The step-2 prompt no longer triggers the VQA bbox pass |
| `95cb85e` | Verification: claims split at line breaks; markdown markers dropped |
| `4de1a1e` | Step 2 asks what the crop contains, not what is new |

## Status

| Step | Status |
|---|---|
| 0: safety | Done. Uncommitted files stashed as `stash@{0}` "pre-composite-orchestration-2026-09-25" |
| 1: design | Done. The requested change→fusion scenario has no fixture; change→VQA was approved |
| 2: implementation plus unit tests | Done |
| 3: CI | Green (below) |
| 4: live positive path | Done, live on the Space (below) |
| 5: live negative case | Done, re-captured on `4de1a1e` (below) |

## Step 1: design decision

**The requested scenario is not backed by fixtures.** "Change detection on an optical pair, then fusion on an optical+SAR pair" needs a bi-temporal pair in which one date is also a co-registered optical+SAR pair:
- LEVIR-CD is bi-temporal but optical RGB only, with no CRS.
- Sen1Floods11 Bolivia_103757 has optical and SAR, but for one date only.

Two further problems:
- **BIT is out of domain.** It is a LEVIR building-change model (0.5 m); water change on 10 m Sentinel-2 would give meaningless numbers.
- **The available second date doesn't fit the pipeline.** A second real date exists on Planetary Computer (a live STAC query found 126 S2 L2A dates and 165 S1 RTC dates over the footprint). But L2A has no B10 band for s2cloudless, and RTC gamma0 is not the σ0 dB the fusion tool expects.

**Approved alternative:** `change_detection → vqa_grounding`.

| Decision | What was built |
|---|---|
| Schema | `DispatchPlan.followups: tuple[ToolStep, ...] = ()`. The single-tool fields are unchanged, so every existing caller and test is untouched. There is a `tool_sequence` property. `ToolStep.input_from_previous` has one allowed value, `"largest_change_component"` |
| Routing rule | `TaskType.CHANGE_DESCRIBE` requires a change cue (the CHANGE_VQA patterns) **and** a cue asking what the changed area contains: "new structures/buildings", "what kind/type of", "what was built/demolished", "identify the new", "in the changed area". It is evaluated after fusion and before CHANGE_VQA; "Describe what changed …" stays CHANGE_VQA |
| Threading | The largest **8-connected component** of the post-gate change mask (BIT's 256×256 space) is scaled to post-image pixels, padded to at least 128 px per side (centred, clamped to the image), and cropped. VQA runs on that crop, and its box is shifted back to full-frame pixels. If the gate leaves no component, step 2 is skipped and recorded as `sequence_short_circuit` |
| Step-2 prompt | A fixed, content-only prompt: "Describe the structures and land cover visible in this image." VQA sees one post-image crop, so it isn't asked what is *new*; that comes from BIT. The prompt has no spatial trigger word, so there is no bbox pass (see "Fixes found by the live run") |
| Trace | One trace. `route_selected` has `tool_sequence` and `planned_sequence`. There are `sequence_step_started` / `sequence_step_completed` steps around each tool's own steps, and a `sequence_handoff` step (component area, mask bbox, crop box, crop size) |
| One answer, one confidence | One `verify()` over both tools' evidence. The text is the change narrative plus "In the largest changed region: {verified VQA answer}". Confidence is the **minimum** over the surviving evidence, a **design choice** labelled as such in code, not a sourced rule |
| Loop-proofing | `MAX_TOOL_CALLS = 2`: a `DispatchPlan` validator, a call counter in the pipeline, and only `["change_detection","vqa_grounding"]` is accepted as a sequence |
| Vetoes | The CHANGE_VQA structural checks (2 images, capture order 0/1), run in the router before either tool. `planned_sequence` still shows what would have run |

**Demo pair:** `levir_cd_test_102_2`, from the LEVIR-CD **test** split, via `ericyu/LEVIRCD_Cropped256` at `b5a9ebf`, row 40. How it was chosen (full provenance in `bck/tests/fixtures/README.md`):
- All 2,048 test pairs were run through local BIT and the real gate. 283 were rejected by the registration check, 1,195 suppressed by the 2% gate, 570 passed, and 315 passed with a largest component of at least 2% of the frame on its own.
- The top three by IoU with the ground-truth label:
  - `test_16_4`: 68.09% change, bbox [0,34,256,256], IoU 0.988. It covers most of the frame, so its crop would be nearly the whole image.
  - **`test_102_2`**: 20.91% change, component 13,704 px (20.91%), bbox [79,0,256,176], IoU 0.974.
  - `test_102_8`: 31.86% change, component 22.47%, bbox [55,91,256,256], IoU 0.966.

## Step 3: CI (`bck/`, at `4de1a1e`)

`uv sync --all-extras --dev && uv run ruff check . && uv run ruff format --check . && uv run lint-imports && uv run pytest -q` (exit 0):

```
Resolved 152 packages in 8ms
Checked 142 packages in 22ms
All checks passed!
206 files already formatted
Analyzed 160 files, 504 dependencies.
Leaf modules never import each other KEPT
Only pipeline composes modules KEPT
API and pipeline never load local models or torch KEPT
Contracts import nothing of ours KEPT
Contracts: 4 kept, 0 broken.
516 passed, 1 skipped, 114 warnings in 29.69s
```

Earlier, one full run had a single failure in `tests/pipeline/test_trace_timing.py::test_stage_step_spans_its_work`, a wall-clock timing flake that passes alone and in every later run. It is reported, not edited.

## Step 4: positive path, live (no mocks)

**Stack:**
- Vite dev server (:5173) → FastAPI (uvicorn :8000) at `4de1a1e` → the real Space through `remote.py` (`INFERENCE_TIMEOUT_S=180`), plus Postgres and TiTiler (`infra/docker-compose.yml`).
- Headed Chromium (Playwright 1.62.1) at 1600×1000 with `--disable-gpu`, a throwaway account generated at run time, the Upload page's **Bi-Temporal Pair** slots (T1 = `levir_cd_test_102_2_t1.jpg`, T2 = `_t2.jpg`), and the query "What changed between these dates, and what are the new structures in the changed area?".
- Captured 2026-09-25T23:52:44Z; trace `6c39976b-9006-4f27-9a48-6466eb55c0f3`.

| Field | Value |
|---|---|
| HTTP | **200**, `served_from: live` |
| Ordered `tool_sequence` | **`["change_detection", "vqa_grounding"]`** (`planned_sequence` is the same) |
| Handoff | **component 13,704 px** (20.91% of 256×256), mask bbox **[79, 0, 256, 176]**, crop box **[79, 0, 256, 176]**, crop 177×176 (already ≥128, so no padding) |
| Total pipeline ms (`trace.created_at` → last `completed_at`) | **113,605.2** |
| Round trip (browser, click → response) | 114,355 ms |
| Final confidence (min rule) | **0.9911** = min(BIT 0.9911, VQA text 1.0) |
| Verification | verified, 0 claims rejected |

**Per-step timings** (real; the pass durations are measured inside the Space):

| # | Step | ms | Notes |
|---|---|---|---|
| 11 | `router.route_selected` | 0.17 | intent `change_describe` |
| 12 | `pipeline.sequence_step_started` | 0.00 | 1 of 2, `change_detection` |
| 14 | `inference.remote.remote_change_detect_call` | 4,485.4 | Space 0.284 s, network and queue 4.20 s |
| 15 | `models.change_detection.bit.bit_forward_pass` | 271.0 | |
| 16 | `…bit_inference_completed` | 4,610.0 | gate passed, 20.91% changed |
| 17 | `pipeline.sequence_step_completed` | 4,610.1 | 1 of 2 |
| 18 | `pipeline.sequence_handoff` | 0.01 | see above |
| 19 | `pipeline.sequence_step_started` | 0.00 | 2 of 2, `vqa_grounding` |
| 22 | `inference.remote.remote_vqa_call` | 108,953.3 | Space 106.45 s, network and queue 2.50 s |
| 23 | `models.internvl.internvl_answer_pass` | 51,983.7 | |
| 24 | `models.internvl.internvl_grounding_pass` | 54,471.0 | no bbox pass (non-spatial prompt) |
| 26 | `pipeline.sequence_step_completed` | 108,958.2 | 2 of 2 |
| 28 | `verification.verification_completed` | 1.78 | effective confidence 0.9955, 0 rejected |

**Evidence 1: `change_detection.bit`** (mask, confidence 0.9911).
- Description: "Change detected (increased) across 20.9% of the scene, located centre." 13,704 changed px; `confounder_suppressed: false` ("Change detected (20.91%) exceeds confounder precision threshold (2.0%).").

**Evidence 2: `internvl_vqa`** (text, confidence 1.0, `OpenGVLab/InternVL3-2B + yash004-mlp1-vision-lora`, grounded to `levir_cd_test_102_2_t2.jpg`):
> The image shows an aerial view of a large industrial or commercial area. The dominant feature is a long, white-roofed building, likely a warehouse or large facility, which occupies a significant portion of the image. Surrounding this building are several parking lots filled with cars, indicating the presence of employees or visitors. The land cover includes a mix of paved areas for parking and the expansive roof of the building. There are also patches of grass and possibly some trees or vegetation near the edges of the parking lots. The overall layout suggests a functional, organized space designed for industrial or commercial activities.

The VQA text's 1.0 is a **self-consistency** score. The grounding pass returned the whole answer back as one observation, so every claim is "supported" by the same model's restatement. This is how RULE-VERIFY-09 is designed, but it is not independent verification of the content.

**Screenshots** (`docs/evaluation/screenshots/`, from the capture above):

| File | Content |
|---|---|
| `composite_success_levir_test_102_2.png` | Full page, result card, trace collapsed |
| `composite_success_levir_test_102_2_panel.png` | Tight crop of the result card: answer plus both evidence items |
| `composite_success_levir_test_102_2_trace.png` | Full page, trace expanded, with every step's parameters open except the ingestion/received steps (large raster metadata) |
| `composite_success_levir_test_102_2_trace_panel.png` | Tight crop of the card with the expanded trace (896×6899) |

### Fixes found by the live runs
There were three live browser runs; only the third is the Step 4 result.

- **Run 1** (trace `819fa21c`, code `04d48c9`) ran both tools, but **VQA's evidence was dropped**: RULE-VERIFY-09 rejected all 8 claims (confidence 0.0). There were two causes, both fixed with tests:
  1. `95cb85e`: claims only split at sentence punctuation and conjunctions, so a markdown heading line was glued to the list item under it and matched no single grounded line. Line breaks are now claim boundaries, and list numbering and emphasis markers are dropped. The real answer from that run is a regression fixture: 4 of 10 claims are now grounded, and the prompt echo and partial claims are still rejected.
  2. `4de1a1e`: step 2 had asked the user's "what are the new structures" question of one post-image crop, so VQA asserted novelty it can't see ("a new large building … has been constructed"). It now asks only what the crop contains.

  Also, before any run, `04d48c9` fixed the step-2 prefix: it contained "where", a VQA spatial trigger, which added a bbox pass (45–60 s) to every composite query.
- **Run 2** (trace `98bf46c7`, code `4de1a1e`) returned the correct answer: both evidence items, confidence 0.991, pipeline 170.2 s. But the browser round trip was 351.2 s. **180.5 s passed before `run()` started**, and the VQA call spent 56.7 s in network and queue.
  - The backend log shows a single `/query`.
  - A direct `curl` straight afterwards took 114.2 s end to end, with `run()` starting 0.01 s after send and 2.5 s of network and queue.
  - Run 3 in the browser had a 0.7 s gap.

  The run-2 delay was on the browser → Vite-proxy path and at the Space's queue at that moment. **It is not explained and did not recur.**

## Step 5: negative case, live (no mocks)

Same stack, re-captured on `4de1a1e` at 2026-09-25T23:53:46Z, trace `11e076b2-f9e1-42f1-beef-deda51a98df7`. Input: Single Image mode, one post-date image (`levir_cd_test_102_2_t2.jpg`), the composite query.

| Field | Value |
|---|---|
| HTTP | **422** |
| `reason_code` | **`INSUFFICIENT_IMAGES`** (stage `routing`) |
| message | "Change detection requires 2 temporal images (pre- and post-event), but 1 was provided." |
| `route_selected` | intent `change_describe`, `tool: null`, `tool_sequence: []`, **`planned_sequence: ["change_detection", "vqa_grounding"]`**, `supported: false` |
| Trace steps | **7**, with no `sequence_*`, `change_detection_*`, `remote_*`, `bit_*`, `vqa_*` or `internvl_*` step |
| Pipeline ms | 17.8 |
| Round trip | 753 ms |

The request was vetoed at routing, before either tool ran.

Screenshots:
- `composite_veto_single_image.png` / `_panel.png`: full page and the veto alert.
- `composite_veto_single_image_trace.png` / `_trace_panel.png`: full page and the alert with the trace expanded.

Capture method for both steps follows `run_log.md`: scroll to the top and wait 4 s for the globe texture before each full-page capture. Panels are clipped in document coordinates at scroll position 0.

## Open items
- **Latency:** step 2 takes about 106–108 s on `cpu-upgrade`, which fits under the 180 s timeout. On `cpu-basic` it would not fit.
- **Confidence meaning:** the VQA text's confidence reflects self-consistency (see Evidence 2).
- **Map overlay:** served through TiTiler, which Render doesn't run. This is the follow-up ticket in PR #77.
