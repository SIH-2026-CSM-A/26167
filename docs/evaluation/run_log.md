# End-to-end run log: EO validation gates on the console-v2 UI

Live runs through the real stack: Vite dev server (`fnt/`, :5173) → Vite proxy → FastAPI
(`bck/`, uvicorn :8000) → Postgres and TiTiler (`infra/docker-compose.yml`). Nothing was mocked.
Browser: headed Chromium (Playwright 1.62.1) at a 1600×1000 viewport with `--disable-gpu`,
logged in with a throwaway local account.

- **Branch:** `feat/26167-demo-captures`, which is `feat/26167-console-v2-redesign` with
  `feat/26167-veto-trace-ui` merged in.
- **Code under test:** `67c4a4a`, the port of the veto trace and raw-evidence truncation.
  Screenshots and this log are committed on top of it.
- **Date / time (UTC):** 2026-09-23, runs from 16:49:27 to 16:50:07 (times taken from the trace timestamps)
- **CPU:** 13th Gen Intel(R) Core(TM) i5-13420H
- **Compute:** CPU only. InternVL3-2B was never loaded; neither the fusion nor the
  change-detection route calls it. BIT ran on CPU: `define_G` is called with `gpu_ids=[]`, and
  the checkpoint is loaded with `map_location="cpu"`.

## Results

All numbers below come from the `/query` HTTP response body (the `Answer`, or `detail` for
the 422).

- **Pipeline ms** = `trace.created_at` → last `step.completed_at`.
- **Round-trip ms** = measured in the browser from clicking Run to receiving the response. It
  is the only number here not taken from the response body.

| Run | HTTP | reason_code | Final confidence | Pipeline ms (trace) | Round-trip ms (browser) | EO gates (crs / overlap / gsd / order) |
|---|---|---|---|---|---|---|
| A. Veto: S2 optical + S1 SAR reprojected to EPSG:32720 | 422 | `EO_CRS_MISMATCH` (stage `validation`) | none (request blocked) | 266 | 1143 | FAIL / PASS / NOT_COMPARABLE / NOT_COMPARABLE |
| B. Healthy fusion: S2 optical + S1 SAR, both EPSG:4326 | 200 | none | 0.875 | 2364 | 4961 | PASS / PASS / PASS / NOT_COMPARABLE |
| C. Bi-temporal change: LEVIR-CD train_103_9 before/after (PNG) | 200 | none | 0.9522647214737191 | 1999 | 2961 | NOT_COMPARABLE ×4 |
| D. Hero: same inputs as B, trace left collapsed | 200 | none | 0.875 | 2235 | 4586 | PASS / PASS / PASS / NOT_COMPARABLE |

Evidence returned:

- **B and D:** two `mask` items from `fusion.reconcile`, region `clear` at confidence 1.0 and
  region `cloud_affected` at 0.75.
- **C:** one `mask` item from `change_detection.bit` at confidence 0.9522647214737191.

### Trace steps (module/action, in order)

Every run starts with the same 9 steps:

1. `pipeline/request_received`
2. `api/asset_received`
3. `api/asset_received`
4. `ingestion/asset_ingestion_started`
5. `ingestion/asset_ingested`
6. `validation/eo_gates` (crs_consistency)
7. `validation/eo_gates` (geographic_overlap)
8. `validation/eo_gates` (gsd_match)
9. `validation/eo_gates` (acquisition_order)

**A. Veto (10 steps):** the 9 above, then 10. `validation/execution_failed`. No `router` step
ran.

- Message: "Rasters are in different coordinate reference systems."
- Suggested action: "Reproject the rasters to a common CRS before uploading."
- Check results:
  - crs_consistency: FAIL (EPSG:4326 vs EPSG:32720)
  - geographic_overlap: PASS ("Footprints overlap by at least 100.0%.")
  - gsd_match: NOT_COMPARABLE ("Rasters are in different CRSs; pixel sizes are in different units.")
  - acquisition_order: NOT_COMPARABLE ("Not a bi-temporal request.")

**B and D. Fusion (17 steps):** the 9 above, then:

10. `router/routing_started`
11. `router/route_selected`
12. `tools.fusion/fusion_started`
13. `models.fusion.despeckle_otsu/fusion_inference_completed`
14. `verification/verification_started`
15. `verification/verification_completed`
16. `evidence/evidence_created`
17. `pipeline/response_completed`

Acquisition order is NOT_COMPARABLE with "Not a bi-temporal request."

**C. Bi-temporal change (17 steps):** the 9 above, then:

10. `router/routing_started`
11. `router/route_selected`
12. `tools.change_detection/change_detection_started`
13. `models.change_detection.bit/bit_inference_completed`
14. `verification/verification_started`
15. `verification/verification_completed`
16. `evidence/evidence_created`
17. `pipeline/response_completed`

All four checks are NOT_COMPARABLE because the PNGs have no CRS. Acquisition order reads
"Order declared by upload slot, not verified: no readable TIFFTAG_DATETIME on one or both
rasters."

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

| File | Capture method |
|---|---|
| `veto_crs_mismatch.png` / `_panel.png` | Playwright full-page capture after scrolling to the top and waiting 4 s for the globe texture. The panel is the error alert, cropped with a 16 px margin, with the trace and the four `eo_gates` parameter blocks expanded. |
| `fusion_healthy_trace.png` / `_panel.png` | Full-page capture; the panel is the result card with the trace expanded, cropped with a 16 px margin |
| `change_bitemporal_trace.png` / `_panel.png` | Full-page capture; the panel is the result card with the trace expanded, cropped with a 16 px margin |
| `hero_upload_fusion.png` / `_panel.png` | Full-page capture. The panel is a single 1600×1000 viewport frame with the result card scrolled into view and the trace collapsed. |

All pages were short enough (1,136–2,621 px) for a single native full-page capture; no
stitching was needed. The globe is a WebGL canvas and rendered under `--disable-gpu` through
Chromium's software GL. The capture context does *not* set reduced motion: under
`prefers-reduced-motion`, `RotatingEarthBackdrop` renders one frame before its texture has
loaded, and the globe comes out dark.

## Observations (open)

1. **Fusion and change evidence cards read "Spatial mask layer".** `EvidenceSummaryCard`
   labels `mask` evidence with `payload.label`, which neither tool sets. The tools' readable
   sentence (`note` for fusion, `description` for change detection) and their coverage figures
   are not shown on the card, only in the answer text and the raw data.
2. **Trace step durations all read 0 ms.** `TraceRecorder.record` stamps `started_at` and
   `completed_at` at the same moment for each event, so the per-step clock in `TraceStepItem`
   is not a real timing. The totals above come from the trace span instead.
3. **The globe is hidden once a result is shown.** The planet sits centred behind the content
   column, and the result card is opaque, so the hero frame shows the starfield and atmosphere
   glow but not the planet. The translucent veto alert in run A does show the planet.
