# Latency benchmark: non-VLM `/query` paths (headless)

Repeatable latency figures for the three paths that do not use the VLM. Each request was a
direct HTTP `POST /query` to uvicorn. No browser, no Vite and no Playwright were running.
The raw per-request data is in [`latency_bench.csv`](latency_bench.csv): 69 rows, including
the warm-ups.

## Environment

| | |
|---|---|
| Commit | `67509dc` on `feat/26167-demo-captures` |
| Date | 2026-09-23, 17:27:27–17:28:42 UTC |
| CPU | 13th Gen Intel(R) Core(TM) i5-13420H, 12 logical CPUs (2 threads/core) |
| RAM | 7.6 GiB visible to WSL2 (`MemTotal` 7,939,452 kB) |
| OS | Ubuntu 26.04 LTS on WSL2, kernel 6.6.87.2-microsoft-standard-WSL2+ |
| Python | 3.12.13 (project `.venv`) |
| Server | single uvicorn process, `.venv/bin/python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000`, default log level |
| Backing services | Postgres + TiTiler via `infra/docker-compose.yml` (Docker 29.7.2) |
| Client | httpx 0.28.1, one `httpx.Client`, same host, sequential |
| GPU | Not used. InternVL3-2B was not loaded; no path in this benchmark calls it. BIT runs on CPU (`gpu_ids=[]`, `map_location="cpu"`). |

Other processes: an idle `chrome-devtools-mcp` MCP server (0.0 % CPU) and the Claude Code
session itself were running on the machine. Both are outside the request path.

## Method

- **Inputs:** the same as [`run_log.md`](run_log.md). Form fields match what the Upload page
  sends: `modality` per slot and `capture_order` 0/1.
  - **fusion:** `sen1floods11_bolivia_103757_s2_optical.tif` + `sen1floods11_bolivia_103757_s1_sar.tif`, modality optical/sar
  - **change:** `levir_cd_train_103_9_before.png` + `levir_cd_train_103_9_after.png`, modality optical/optical
  - **veto:** the S2 optical file + `/tmp/s1_sar_utm20s.tif` (EPSG:32720), modality optical/sar
  - All three use the same query text as `run_log.md`.
- **Order:** for each path, 3 warm-up requests (discarded), then 20 measured requests. The
  paths ran in the order fusion → change → veto, strictly one request at a time.
- **pipeline ms:** from `trace.created_at` to the last step's `completed_at`, taken from the
  response. For the 422, the trace comes from `detail.trace`.
- **client ms:** `time.perf_counter()` around the `httpx` POST. It covers upload, multipart
  parsing, the pipeline, persistence and history writes, and response serialisation and
  transfer.
- **Per-stage durations:** each step's `completed_at − started_at`.
  - ingestion = `asset_ingested`
  - eo_gates = the sum of the 4 `validation/eo_gates` steps
  - routing = `route_selected`
  - tool inference = `fusion_inference_completed` / `bit_inference_completed`
  - verification = `verification_completed`
- **Percentiles:** `numpy.percentile` with linear interpolation, over n = 20.
- **Correctness checks on every request, including warm-ups:**
  - fusion: HTTP 200, answer starting "SAR indicates 40.9% water coverage in the 95.2% of the
    valid area", confidence 0.875, not abstained.
  - change: HTTP 200, answer "Change detected (increased) across 41.3% of the scene, located
    centre.", confidence 0.9522647214737191, not abstained.
  - veto: HTTP 422 with `reason_code` `EO_CRS_MISMATCH`.

## Correctness

**All 69 requests (9 warm-up + 60 measured) returned the expected outcome. No deviations.**

- fusion: 23/23 returned 200, the expected answer and confidence, 17 trace steps.
- change: 23/23 returned 200, the expected answer and confidence, 17 trace steps.
- veto: 23/23 returned 422 `EO_CRS_MISMATCH`, 10 trace steps, and never reached the router.

## Results (n = 20 measured per path)

### End-to-end

| Path | Metric | n | P50 ms | P95 ms | min ms | max ms |
|---|---|---|---|---|---|---|
| fusion | pipeline | 20 | 1279.0 | 1571.0 | 1063.2 | 1768.4 |
| fusion | client round-trip | 20 | 1868.5 | 2709.6 | 1611.5 | 3217.8 |
| change | pipeline | 20 | 363.2 | 497.9 | 317.9 | 555.9 |
| change | client round-trip | 20 | 504.0 | 608.4 | 423.4 | 683.3 |
| veto | pipeline | 20 | 27.4 | 49.3 | 22.4 | 55.5 |
| veto | client round-trip | 20 | 34.3 | 61.8 | 28.4 | 71.2 |

### Per-stage P50 (P95) in ms

| Path | ingestion | eo_gates (4 gates) | routing | tool inference | verification | untraced inside pipeline¹ |
|---|---|---|---|---|---|---|
| fusion | 27.738 (41.891) | 0.130 (0.211) | 0.061 (0.087) | 701.428 (1024.501) | 0.129 (0.491) | 538.2 (667.0) |
| change | 3.158 (5.776) | 0.020 (0.094) | 0.051 (0.095) | 356.913 (493.873) | 0.110 (0.173) | 0.9 (1.3) |
| veto | 26.733 (48.844) | 0.316 (1.043) | not reached | not reached | not reached | 0.1 (0.2) |

¹ pipeline ms minus the traced stages above, per request. In fusion this is real work that no
step spans yet: the per-optical-input cloud-cover precompute (a 13-band `detect_clouds` pass
between the EO gates and routing) and writing the two mask artifacts (`_enrich_mask_evidence`).
It is not measurement error.

### What sits between pipeline and client time (P50 client − pipeline)

| Path | P50 ms | P95 ms | Notes |
|---|---|---|---|
| fusion | 586.8 | 956.0 | Upload and multipart parsing (~1.6 MB), persistence and history writes, and serialisation of a response that still carries both 512×512 masks as JSON lists |
| change | 117.4 | 212.2 | Same overheads, with a smaller upload and a single mask |
| veto | 6.9 | 12.6 | No evidence and no persistence: the veto fails before `persist_trace` |

## Caveats

- **Warm-up was not fully enough for fusion.** The 20 measured requests still drift downward:
  the mean of requests 1–10 is 1,419.8 ms and of requests 11–20 is 1,207.0 ms. Change drifts
  similarly (407.0 → 359.4 ms), as does veto (38.0 → 25.3 ms). The P50s above include that
  drift. More warm-ups, or a longer run, would probably lower them slightly. The first
  warm-up of each path was far slower than the rest (fusion 5,132 ms, change 3,327 ms, veto
  83 ms). That is cold-start cost: the first BIT checkpoint load, and GDAL/rasterio warm-up.
- **This is one laptop under WSL2** with turbo boost and no CPU pinning. Treat the numbers as
  relative figures for this machine, not capacity planning. Earlier single runs in
  `run_log.md` (fusion 2.4 s and 8.2 s pipeline) fall outside this benchmark's range, which
  shows how much single samples vary here.
- **BIT reloads its checkpoint on every request.** `detect_change` calls `_load_bit_model`
  each time, so the change path's inference time includes the model load. This benchmark
  measures current behaviour; it does not optimise it.
- **The client round-trip for fusion includes serialising and transferring the full mask
  arrays.** That payload size is a known cost the frontend now truncates for display. The
  API still returns the arrays.
- **Sequential only.** Concurrency and throughput were not measured.
