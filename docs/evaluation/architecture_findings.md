# Architecture Findings — Implementation vs. Diagram

Read-only inspection of `bck/app/` on branch `feat/26167-console-v2-redesign` (2026-09-23).
Nothing was executed; every claim below cites the code it comes from. Paths are relative to
`bck/app/`.

## 1. EO validation gates

**Verdict:** No georeferenced validation gate exists. The "Co-registration / Spatial
Compatibility / Quality Check" steps in the diagram are only partly present: a pixel-level
registration check inside change detection, and a temporal-order check based on which upload
slot each image came from. CRS, AOI overlap and GSD are recorded but never compared.

Ingestion (`ingestion/raster.py::ingest_raster`, `_validate_upload`) validates each file on its
own: id, filename, suffix, non-empty bytes, and driver ∈ {GTiff, PNG, JPEG}. It never compares
one raster with another. `_extract_metadata` (lines 263–284) stores `crs`, `bounds` and
`transform`. Those fields are read only to project outputs (`evidence/builder.py:83–84`,
`core/raster_artifacts.py:31–32`), never to validate inputs. The pipeline
(`pipeline/pipeline.py::run`, lines 162–207) goes from ingestion straight to routing with no
cross-image step.

| Gate | Status | Where / evidence |
|---|---|---|
| CRS consistency between input rasters | **Not implemented** | `crs` is extracted (`ingestion/raster.py:272`) but never compared. `verification/rules.py::evaluate_spatial_geometry_consistency` (RULE-VERIFY-07) and `evaluate_spatial_extent_comparison` (RULE-VERIFY-08) state that no shared CRS is available, and always return `NOT_COMPARABLE` with a penalty of 0.0. Both run on output evidence, not inputs. |
| Spatial overlap / AOI compatibility | **Partially implemented (pixel-space only, change detection only)** | `tools/change_detection/registration_quality.py::require_registration_quality` (called from `confounder_gate.py::evaluate_confounder_gate`, line 180) rejects pairs whose shapes differ, then rejects a global phase-correlation shift above `_MAX_SHIFT_NORM_PX = 40.0` (line 58). This checks image alignment, not geographic footprint or `bounds` intersection. Fusion only has an array-shape equality check (`tools/fusion/reconcile.py::reconcile_sar_optical`, line 93). The router veto (`router/veto.py::evaluate_veto`, line 116) *asks* for "a co-registered pair" in its message but does not check for one. |
| GSD / resolution mismatch | **Not implemented** | The `transform` (pixel size) is stored but never compared. BIT resizes both inputs to 256×256 regardless (`tools/change_detection/detector.py::_load_and_preprocess`). The only GSD code is in training (`training/gsd_conditioning.py`, `gsd_augment.py`), which is not on the inference path. |
| Temporal order (T1 before T2) | **Partially implemented (declared order, not acquisition time)** | `router/planner.py::build_dispatch_plan` (lines 58–72) vetoes `CHANGE_VQA` with `TEMPORAL_ORDER_MISSING` unless the images' `capture_order` values are exactly `{0, 1}`. `capture_order` comes from the Upload page slot the user picked (`ingestion/raster.py::RasterUpload.capture_order`). No acquisition date/time is parsed from metadata, so a swapped upload (later scene in slot 0) is accepted. |

## 2. Multi-tool sequencing

**Verdict:** Exactly one specialist tool runs per query today. The router never chains tools.

- `router/schemas.py::DispatchPlan` (line 81) holds a single `tool_name: str`.
  `router/router.py::route` returns a `RouterDecision` with one `dispatch_plan`.
- `router/classifier.py::classify_intent` returns the first matching `TaskType`, checked in
  order: archive → fusion → change → grounding → VQA default.
  `router/planner.py::build_dispatch_plan` maps each `TaskType` to one `return DispatchPlan(tool_name=...)`.
- `pipeline/pipeline.py::run` (lines 248–264) runs one exclusive branch:

  ```python
  if dispatch_plan.tool_name == "vqa_grounding":
      ... = _run_vqa_tool(...)
  elif dispatch_plan.tool_name == "change_detection":
      candidate_evidence_list = _run_change_detection_tool(...)
  else:
      candidate_evidence_list = _run_fusion_tool(...)
  ```

- Nuances, so the answer is not overstated:
  - The fusion branch (`_run_fusion_tool`, lines 573–581) chains its own internal stages:
    `lee_filter → otsu_water_mask → detect_clouds → reconcile_sar_optical`. That is one
    specialist's internal pipeline, not router-level sequencing.
  - Before routing, `run` (lines 191–205) calls `detect_clouds` on every 10/13-band optical
    input and stores the result in `metadata["cloud_fraction"]`. This is a side computation,
    not a dispatched tool.
  - Verification (`verification/verifier.py::verify`) always runs after the tool. It is a
    gate, not a specialist.

## 3. Confidence definition per tool

**Verdict:** Only change detection produces a confidence derived from the model. Fusion and
bbox use fixed hand-set values. VQA text confidence is the share of the model's own claims that
match its own supporting observations. There is no spectral-indices tool.

| Specialist | What the number actually is | Citation |
|---|---|---|
| VQA / Grounding — text | Starts at `0.0` with `confidence_available: False`. RULE-VERIFY-09 then sets it to the **fraction of atomic claims in the answer that match one of the model's own `supporting_observations`** (a self-consistency score, not calibrated). Finally `run` overwrites it with `VerificationDecision.effective_confidence` = mean confidence of the surviving evidence minus the penalty. | `evidence/builder.py:42`; `verification/rules.py:423–424` (`evaluate_narrative_claim_grounding`); `pipeline/pipeline.py:313–315`; `verification/schemas.py:130–135` |
| VQA / Grounding — bbox | **Fixed values set by hand:** 0.75 for native InternVL grounding, 0.50 for the Otsu fallback. The code comments call them "authored" (not specified in any project doc). | `evidence/builder.py:57–58`, applied at line 136 (`build_bbox_evidence`) |
| Change Detection (BIT) | **Mean per-pixel agreement probability:** the mean over all pixels of P(changed) where the mask says changed and 1 − P where it does not. P is BIT's 2-class **softmax** probability for class 1. (The docstring says "sigmoid", which does not match the code.) When the confounder gate suppresses the result, the mask is all zeros, so the value becomes mean(1 − P). | `tools/change_detection/confidence.py:6–22` (`compute_confidence`); `tools/change_detection/detector.py:71, 83` |
| Optical–SAR Fusion | **Fixed rule-based values:** 1.0 for the cloud-free region (and for the whole scene when there is no cloud), and `_SAR_ONLY_CONFIDENCE = 0.75` for the cloud-covered, SAR-only region. The code comment says 0.75 is an "invented choice". | `tools/fusion/reconcile.py:50, 152, 187, 197` (`reconcile_sar_optical`) |
| Spectral Indices | **Not implemented.** There is no spectral-index tool under `tools/`, no `TaskType` for it (`router/classifier.py`), and nothing computes NDVI/NDWI at inference time. The only mentions are a keyword veto for spectral queries on SAR-only input (`verification/rules.py:47–56`, `evaluate_sensor_compatibility`) and a comment in the VQA Otsu fallback saying NDWI cannot be computed (`tools/vqa_grounding/tool.py:173`). | — |

The answer-level confidence is the mean of the verified evidence confidences
(`evidence/builder.py:164`, `assemble_answer`). It therefore mixes these differently-defined
numbers.
