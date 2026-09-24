# End-to-end run log: EO validation gates on the console-v2 UI

Live runs through the real stack: Vite dev server (`fnt/`, :5173) → Vite proxy → FastAPI
(`bck/`, uvicorn :8000) → Postgres and TiTiler (`infra/docker-compose.yml`). Nothing was mocked.
Browser: headed Chromium (Playwright 1.62.1) at a 1600×1000 viewport with `--disable-gpu`,
logged in with a throwaway local account.

- **Branch:** `feat/26167-demo-captures`, which is `feat/26167-console-v2-redesign` with
  `feat/26167-veto-trace-ui` merged in.
- **Runs A and D:** code under test is `4eeb122` (real per-stage trace timing and specific mask
  evidence labels). A ran at 2026-09-23 17:17:42 UTC and D at 17:14:27 UTC.
- **Runs B and C:** not re-run for this commit. Their figures are from `67c4a4a` at
  16:49–16:50 UTC, before step timing was fixed. Their totals are valid, but their per-step
  durations were all recorded as 0 ms.
- **CPU:** 13th Gen Intel(R) Core(TM) i5-13420H
- **Compute:** CPU only. InternVL3-2B was never loaded; neither the fusion nor the
  change-detection route calls it. BIT runs on CPU: `define_G` is called with `gpu_ids=[]`, and
  the checkpoint is loaded with `map_location="cpu"`.

## Results

All numbers below come from the `/query` HTTP response body (the `Answer`, or `detail` for
the 422).

- **Pipeline ms** = `trace.created_at` → last `step.completed_at`.
- **Round-trip ms** = measured in the browser from clicking Run to receiving the response. It
  is the only number here not taken from the response body.

| Run | Commit | HTTP | reason_code | Final confidence | Pipeline ms (trace) | Round-trip ms (browser) | EO gates (crs / overlap / gsd / order) |
|---|---|---|---|---|---|---|---|
| A. Veto: S2 optical + S1 SAR reprojected to EPSG:32720 | `4eeb122` | 422 | `EO_CRS_MISMATCH` (stage `validation`) | none (request blocked) | 836 | 1753 | FAIL / PASS / NOT_COMPARABLE / NOT_COMPARABLE |
| B. Healthy fusion: S2 optical + S1 SAR, both EPSG:4326 | `67c4a4a` | 200 | none | 0.875 | 2364 | 4961 | PASS / PASS / PASS / NOT_COMPARABLE |
| C. Bi-temporal change: LEVIR-CD train_103_9 before/after (PNG) | `67c4a4a` | 200 | none | 0.9522647214737191 | 1999 | 2961 | NOT_COMPARABLE ×4 |
| D. Hero: same inputs as B, trace left collapsed | `4eeb122` | 200 | none | 0.875 | 8165 | 12684 | PASS / PASS / PASS / NOT_COMPARABLE |

Timings vary noticeably from run to run on this machine. For example, fusion inference took
4.3 s in D, while the whole of B took 2.4 s. Read them as single samples, not benchmarks.

Evidence labels returned (`payload.label`, shown on the evidence cards):

- **B and D (`fusion.reconcile`):**
  - "Water extent — clear sky (optical + SAR agree)", confidence 1.0
  - "Water extent — cloud-covered (SAR only, reduced confidence)", confidence 0.75
- **C (`change_detection.bit`):** "Changed area (BIT change mask)" is set from `4eeb122` onward.
  C was not re-run, so its screenshot still shows the old generic label.

### Per-step durations (from each step's `started_at` → `completed_at`)

Steps named `*_started` are instant markers. Each completion step spans the work that
produced it.

**A. Veto (`4eeb122`):**

| # | Step | ms |
|---|---|---|
| 1 | `pipeline/request_received` | 0.004 |
| 2 | `api/asset_received` | 0.008 |
| 3 | `api/asset_received` | 0.002 |
| 4 | `ingestion/asset_ingestion_started` | 0.001 |
| 5 | `ingestion/asset_ingested` | 804.953 |
| 6 | `validation/eo_gates` crs_consistency: FAIL | 3.068 |
| 7 | `validation/eo_gates` geographic_overlap: PASS | 23.527 |
| 8 | `validation/eo_gates` gsd_match: NOT_COMPARABLE | 0.524 |
| 9 | `validation/eo_gates` acquisition_order: NOT_COMPARABLE | 0.034 |
| 10 | `validation/execution_failed` | 0.011 |

The request was blocked with message "Rasters are in different coordinate reference systems."
and suggested action "Reproject the rasters to a common CRS before uploading." No `router` step
ran.

**D. Hero fusion (`4eeb122`):**

| # | Step | ms |
|---|---|---|
| 1 | `pipeline/request_received` | 0.001 |
| 2 | `api/asset_received` | 0.001 |
| 3 | `api/asset_received` | 0.001 |
| 4 | `ingestion/asset_ingestion_started` | 0.001 |
| 5 | `ingestion/asset_ingested` | 134.933 |
| 6 | `validation/eo_gates` crs_consistency: PASS | 0.353 |
| 7 | `validation/eo_gates` geographic_overlap: PASS | 0.128 |
| 8 | `validation/eo_gates` gsd_match: PASS | 3.563 |
| 9 | `validation/eo_gates` acquisition_order: NOT_COMPARABLE | 0.028 |
| 10 | `router/routing_started` | 0.016 |
| 11 | `router/route_selected` | 9.646 |
| 12 | `tools.fusion/fusion_started` | 0.034 |
| 13 | `models.fusion.despeckle_otsu/fusion_inference_completed` | 4328.572 |
| 14 | `verification/verification_started` | 0.061 |
| 15 | `verification/verification_completed` | 5.840 |
| 16 | `evidence/evidence_created` | 32.757 |
| 17 | `pipeline/response_completed` | 0.003 |

**What the step durations do not cover.** The pipeline span includes some work that no step
spans:

- Cloud-cover precompute: the optical-cloud pass that runs between the EO gates and routing.
- Mask artifact writing (`_enrich_mask_evidence`).
- Everything before step 1 or after the last step, such as persistence and history.

That is why, in D, the step durations add up to less than the 8,165 ms pipeline span.

**B and C (`67c4a4a`) step sequences:** the same as D after step 9, with C using
`tools.change_detection/change_detection_started` and
`models.change_detection.bit/bit_inference_completed`. In C, acquisition order reads "Order
declared by upload slot, not verified: no readable TIFFTAG_DATETIME on one or both rasters."

## Inputs

| Role | Path |
|---|---|
| Optical (S2) | `data/demo/assets/sen1floods11_bolivia_103757_s2_optical.tif` (EPSG:4326) |
| SAR (S1) | `data/demo/assets/sen1floods11_bolivia_103757_s1_sar.tif` (EPSG:4326) |
| SAR, CRS-mismatch copy | `/tmp/s1_sar_utm20s.tif` (EPSG:32720, "WGS 84 / UTM zone 20S", band descriptions VV/VH) |
| LEVIR-CD before | `data/demo/assets/levir_cd_train_103_9_before.png` |
| LEVIR-CD after | `data/demo/assets/levir_cd_train_103_9_after.png` |

The CRS-mismatch copy was made with `rio warp --dst-crs EPSG:32720`, rasterio's CLI equivalent
of `gdalwarp -t_srs`, because the GDAL command-line tools are not installed here. `rio warp`
dropped the `VV`/`VH` band descriptions, so they were copied back from the source. The file was
still valid for this run and was reused without being regenerated.

## Screenshots (`docs/evaluation/screenshots/`)

| File | Commit | Capture method |
|---|---|---|
| `veto_crs_mismatch.png` / `_panel.png` | `4eeb122` | Playwright full-page capture after scrolling to the top and waiting 4 s for the globe texture. The panel is the error alert, cropped with a 16 px margin, with the trace and the four `eo_gates` parameter blocks expanded. It shows the real per-step durations. |
| `fusion_healthy_trace.png` / `_panel.png` | `67c4a4a` | Full-page capture; the panel is the result card with the trace expanded. It predates the timing and label fixes. |
| `change_bitemporal_trace.png` / `_panel.png` | `67c4a4a` | Full-page capture; the panel is the result card with the trace expanded. It predates the timing and label fixes. |
| `hero_upload_fusion.png` / `_panel.png` | `4eeb122` | Full-page capture. The panel is a single 1600×1000 viewport frame with the result card scrolled into view and the trace collapsed. It shows the new fusion evidence labels. |

All pages were short enough for a single native full-page capture. The globe is a WebGL canvas
and rendered under `--disable-gpu` through Chromium's software GL. The capture context does
*not* set reduced motion: under `prefers-reduced-motion`, `RotatingEarthBackdrop` renders one
frame before its texture has loaded, and the globe comes out dark.

## Observations (open)

1. **The globe is hidden once a result is shown.** The planet sits centred behind the content
   column, and the result card is opaque, so the hero frame shows the starfield and atmosphere
   glow but not the planet. The translucent veto alert in run A does show the planet.
