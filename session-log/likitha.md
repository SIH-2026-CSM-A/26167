## 2026-09-05 — LIKI-001: Frontend Scaffold (Vite/React/TS/Tailwind)

Built via Antigravity (single-agent, Windows).

**Did:**
- Initialized frontend root under `fnt/` using Vite, React 18, and TypeScript (strict mode).
- Configured Tailwind CSS v3 with PostCSS and Autoprefixer, extending custom theme colors for ISRO/SAC SatQuery styling.
- Configured React Router v6 with routes for `/upload` (ingestion dropzone shell), `/chat` (VQA & assistant shell), and `/map` (spatial evidence container shell).
- Implemented reusable `Navbar` component with active route indicators and a live Tailwind-styled telemetry status element (`animate-pulse`, border, badge).
- Preserved existing `fnt/src` structure (`components/`, `hooks/`, `pages/`, `services/`, `store/`, `utils/`, plus added `styles/`).
- Added ESLint config, tsconfig, and npm scripts (`dev`, `build`, `lint`, `preview`).
- Verified `npm ci`, `npm run lint`, `npm run build`, and `npm run dev` clean without warnings or errors.

**Important Decisions & Rationale:**
- Root path is strictly `fnt/` (never `frontend/`), adhering to `ARCHITECTURE.md`, `.github/CODEOWNERS`, and `.github/workflows/ci.yml`.
- Kept the `/map` page as a routed container shell for LIKI-001 rather than mounting a live MapLibre instance before tile endpoints (TiTiler in `infra/`) exist. This avoids stub layers or mock data, conforming to the `AGENTS.md` rule: "No fake data, no placeholders, no stubs."

**Rejected along the way:**
- Rejected creating a `frontend/` directory — all repository pipelines, ownership rules, and CI explicitly target `fnt/`.
- Rejected Next.js — rejected in `ARCHITECTURE.md` due to offline demo constraints and faster Vite HMR loop.
- Rejected mock backend API calls or simulated inference streams in the chat/upload views — contracts and backend integration will be wired strictly through typed API services in downstream tickets.

## 2026-09-06 — LIKI-002: Modular Upload & Query Form Implementation

- Architected modular subcomponents in `fnt/src/components/Upload/`:
  - `ConfigSelector.tsx` (58 lines): Single Image, Cross-Modal (optical/sar locked), and Bi-Temporal modes.
  - `SlotUploader.tsx` (116 lines): Drag-and-drop file uploader with client-side benchmark and GeoTIFF validation.
  - `QueryResultCard.tsx` (92 lines): Displays answer text, confidence metric, evidence payloads, and expandable trace step viewer.
  - `UploadPage.tsx` (128 lines): Orchestrates components and coordinates 1:1 positional `submitQuery` calls.
- Enforced zero mock data; connected directly to live backend endpoint via `submitQuery`.
- Verified 0 errors on `npm run lint` and `npm run build`.

### Review Fixes Applied (PR #16)
- Reverted all changes to `bck/app/api/main.py` back to `origin/main` to keep the branch pure frontend scope and eliminate CI formatting failures.
- Configured Vite dev-server proxy (`/query` -> `http://localhost:8000`) and alias resolution in `fnt/vite.config.ts`.
- Updated `fnt/src/services/api.ts` default `API_BASE_URL` to relative pathing (`''`).
- Deleted synthetic placeholder fixtures (`pair_*.png`, `single_*.png`, `t*.png`) from `fnt/test-fixtures/` pending real SEN12MS/LEVIR-CD samples from team members.
- Verified clean linter (`npm run lint`) and production build (`npm run build`).

## 2026-09-06 — LIKI-003: Map overlay + chat interface with evidence citations

Built via Antigravity (single-agent, Windows).

**Did:**
- Grounded frontend TypeScript contracts (`fnt/src/types/contracts.ts`, `fnt/src/types/geojson.ts`) 1:1 against backend models in `bck/app/contracts/schemas.py` (`Evidence`, `EvidenceType`, `TraceStep`, `ExecutionTrace`, `Answer`, `QueryRequest`, `Modality`, `ImageInput`). Zero fake or placeholder data.
- Created GeoJSON transformation and bounding calculation utilities (`fnt/src/utils/evidenceGeoJson.ts`) to turn raw evidence payloads (bounding boxes and vector masks) into MapLibre-compatible GeoJSON FeatureCollections with bounding box calculation.
- Built reusable MapLibre GL component (`fnt/src/components/Map/EvidenceMap.tsx`) importing `maplibre-gl/dist/maplibre-gl.css`, supporting ESRI Satellite raster basemap tiles, dark matter, and street tiles, with GeoJSON mask/bbox fill and stroke layers, animated selection halo (`evidence-selected-halo`), smooth viewport fitting (`map.fitBounds`), map controls (`MapControls.tsx`), and floating evidence details card (`EvidenceDetailCard.tsx`).
- Built chat interface subcomponents (`fnt/src/components/Chat/`):
  - `CitationChip.tsx`: Interactive clickable chips backing factual claims with tool names, confidence percentages, and map-zoom triggers.
  - `CitationText.tsx`: Inline citation tag parser and highlighter.
  - `ConfidenceBadge.tsx`: Visual confidence indicator with verification and abstention status.
  - `ChatMessageItem.tsx`: Conversational message layout with inline citations, confidence badges, evidence ribbon, and execution trace.
  - `ChatInput.tsx`: Natural language query input with image attachment and per-image modality selector (Optical / SAR).
- Built `ExecutionTracePanel` (`fnt/src/components/Trace/`): Expandable audit panel rendering real trace fields (trace ID, timing duration, module pipeline stages, action parameters, confidence, and linked evidence).
- Created `SatQueryContext` and `useSatQuery` hook to unify chat conversation state, active answers, evidence lists, and selected feature IDs across pages.
- Integrated the live map view into `ChatPage.tsx` (responsive side-by-side / toggle view with citation click-to-zoom) and updated `MapPage.tsx` with dedicated full-screen geospatial workstation and evidence feature sidebar filter.
- Strictly complied with T3-Coding-Standards: all files under 300 lines, all functions under 48 lines, max <= 4 parameters, 1 primary export per file, zero fake/placeholder data, zero TODO comments.
- Verified `npm run build` and `npm run lint` clean (exit code 0, zero warnings).

**Important Decisions & Rationale:**
- Used named ESM imports from `maplibre-gl` to match Vite/Rollup module resolution.
- Integrated ESRI World Imagery raster tiles for the satellite basemap — no token dependency, high-resolution global coverage, with toggleable Dark and Street modes.
- Decomposed React functional components into atomic sub-components (all <= 48 lines) to strictly comply with T3-Coding-Standards.
- Separated `SatQueryContext` from `SatQueryProvider` into distinct files to strictly comply with the ESLint `react-refresh/only-export-components` rule.

**Rejected along the way:**
- Rejected mock or placeholder data in production components — strict grounding against backend Answer/Evidence schema.
- Rejected Mapbox GL due to token dependency; MapLibre GL is token-free and offline/self-hosting compatible per `ARCHITECTURE.md`.

### 2026-09-06 — added downloadable PDF report — PowerShell & Antigravity

**Done**
- Implemented `bck/app/evidence/report.py` using ReportLab to stream structured PDF evidence reports matching on-screen pipeline data.
- Added `/api/evidence/export-pdf` POST streaming endpoint in `bck/app/api/main.py`.
- Added unit and endpoint tests in `bck/tests/evidence/test_report.py` (2 passed).
- Added `downloadEvidencePdf` service in `fnt/src/services/api.ts` and wired the trigger button into `fnt/src/components/Upload/QueryResultCard.tsx`.

**Decided**
- Server-side ReportLab document streaming instead of client-side/headless HTML-to-PDF rendering to guarantee identical evidence representation between report and UI without browser overhead.

**Incomplete**
- None.

## 2026-09-07 — LIKI-005: Render BBOX evidence on map (FS grounding)

Built via Antigravity (single-agent, Windows).

**Did:**
- Implemented BBOX evidence rendering and synchronization for ClickUp ticket 26167 - LIKI-005.
- Extended `fnt/src/utils/evidenceGeoJson.ts`:
  - Handled `EvidenceType = 'bbox'` and evidence carrying `payload.bbox: [minLon, minLat, maxLon, maxLat]`.
  - Implemented 5-point closed GeoJSON Polygon conversion in `bboxToPolygonCoordinates`.
  - Added robust payload extraction from `payload.geojson` supporting `Feature`, `FeatureCollection`, and raw `Geometry`.
  - Enhanced `getFeatureBounds` and `getCollectionBounds` with finite-coordinate guards for `Polygon`, `MultiPolygon`, and `Point` geometries to prevent runtime errors.
  - Added `isOutsideViewport` helper to detect when a feature bounding box is outside or partially outside the current viewport.
  - Added `normalizeBoundsForFit` helper to expand zero-area or point bounding boxes with an epsilon offset to prevent MapLibre camera fit crashes.
- Updated `fnt/src/components/Map/EvidenceMap.tsx`:
  - Rendered BBOX evidence through existing `satquery-evidence` source and layers (`evidence-mask-fill`, `evidence-boundary-line`, `evidence-selected-halo`).
  - Synced selection highlighting via the existing `['==', ['get', 'id'], selectedId ?? '']` halo filter.
  - Safely framed bounding boxes via `map.fitBounds` with padding when the selected feature is out of view or partially outside the viewport.
  - Preserved file size strictly under the 300-line hard limit (270 lines total) and kept all functions under 50 lines.
- Enhanced `fnt/src/components/Map/EvidenceDetailCard.tsx`:
  - Displayed label and description for BBOX evidence alongside coordinates, confidence, timing, and tool.
- Added test suites:
  - `fnt/src/utils/__tests__/evidenceGeoJson.test.ts` (17 tests covering conversion, geojson payloads, selection filtering, bounds calculation, out-of-view viewport detection, and bounds normalization).
  - `fnt/src/components/Map/__tests__/EvidenceMap.test.tsx` (5 tests covering layer initialization, BBOX feature loading, selection halo filter, fitBounds viewport framing, and detail card display).
- Verified full suite:
  - Frontend: `npm test` (all 26 tests passed), `npm run lint` (0 errors), `npm run build` (clean production build).
  - Backend: `uv run ruff check .`, `uv run ruff format --check .`, `uv run lint-imports`, `uv run pytest` (136 passed).

**Rejected along the way:**
- Rejected creating separate layer pipelines or parallel selection state for BBOX vs Mask evidence; both feed the unified `satquery-evidence` GeoJSON layer stack.
- Rejected unconditional `map.fitBounds` calls when a feature is already completely visible within the viewport, preventing disorienting camera jumps on click.
- Rejected modifying contracts (`fnt/src/types/contracts.ts` and `bck/app/contracts/`), strictly respecting module ownership rules.

## 2026-09-07 — LIKI-006: One-click demo preset selector wired to manifest (F24)

Built via Antigravity (single-agent, Windows).

**Did:**
- Grounded frontend manifest models in `fnt/src/types/manifest.ts` matching `data/demo/manifest.json` schema v1.0 (`DemoManifest`, `DemoPreset`, `DemoAsset`, `DemoAssetRole`, `PresetSlotData`, `PresetApplyPayload`). Zero fake data.
- Built reusable preset loading and mapping utilities in `fnt/src/utils/demoPresets.ts`:
  - `resolveAssetUrl`: Deterministically joins relative POSIX asset paths to manifest base directory.
  - `fetchManifestData`: Retrieves and validates manifest preset array.
  - `loadPresetAssetFiles`: Asynchronously retrieves preset assets as live browser `File` objects with extension-appropriate MIME types.
  - `mapPresetToSlotsAndMode`: Explicitly binds role-tagged imagery into target upload slots:
    - `"image"` -> Single image slot (`Primary Imagery`, optical, unlocked).
    - `"pre_image"` & `"post_image"` -> Bi-temporal slots (`Slot 1 (T1 Pass)` and `Slot 2 (T2 Pass)`).
    - `"optical_image"` & `"sar_image"` -> Cross-modal slots (`Slot 1 (Optical)` and `Slot 2 (SAR)` locked to optical and sar).
- Implemented `DemoPresetSelector.tsx` (`fnt/src/components/DemoPresetSelector.tsx`):
  - Renders curated preset cards with scenario tags, natural language query preview, and asset count telemetry.
  - Handles one-click preset activation, loading assets and triggering slot population.
  - Implements resilient error handling: displays honest inline banner `"Demo preset unavailable. Please use manual upload or verify dataset path."` if manifest fetch fails or asset fetch returns 404, preventing blank screen or unhandled exceptions.
  - Strictly adheres to React Refresh guidelines by keeping component exports pure.
- Updated `UploadPage.tsx` (`fnt/src/pages/UploadPage.tsx`):
  - Added opt-in segmented toggle (`Manual Upload` vs `Demo Presets`), keeping default manual upload intact.
  - When demo preset chip is selected, automatically sets pipeline configuration mode, fills query text box, and populates upload slots with authentic raster files.
- Configured Vite dev/preview server middleware in `fnt/vite.config.ts` to serve real `data/demo/` rasters and manifest without copying or mock layers.
- Added comprehensive unit test suite in `fnt/src/components/__tests__/DemoPresetSelector.test.tsx` (6 tests):
  - Renders available presets from manifest data.
  - Selecting a preset updates query and slot states.
  - Displays honest fallback banner if manifest fetch fails.
  - Displays honest fallback banner if an asset path returns a 404.
  - Manual upload remains untouched when toggle is off.
  - Selecting preset in `UploadPage` populates query, mode, and slots.
- Maintained file limits: all files under 225 lines (< 300 lines limit), all functions under 45 lines, max parameters <= 2.
- Verified test & quality gates:
  - Frontend: `npm test` (all 32 tests passed), `npm run lint` (0 errors, 0 warnings), `npm run build` (clean exit 0).
  - Backend: `uv run ruff check .`, `uv run ruff format --check .`, `uv run lint-imports`, `uv run pytest` (210 passed, 10 skipped).

**Important Decisions & Rationale:**
- Extracted utility functions into `fnt/src/utils/demoPresets.ts` and types into `fnt/src/types/manifest.ts` to satisfy ESLint's `react-refresh/only-export-components` rule.
- Added Vite dev server middleware to stream genuine `data/demo` rasters directly, guaranteeing offline demonstration fidelity without duplicated asset storage.
- Kept manual upload active by default with explicit toggle to prevent disruption to existing manual workflows.

**Rejected along the way:**
- Rejected hardcoded/mocked manifest payloads in frontend source — directly wired to manifest JSON fetch and offline dev proxy.
- Rejected altering backend contract files (`bck/app/contracts/`), strictly respecting module ownership boundaries.

