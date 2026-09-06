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
