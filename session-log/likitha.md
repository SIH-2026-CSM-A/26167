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

**Incomplete:**
- MapLibre GL map layer rendering and bounding box overlay will be implemented in ticket LIKI-003 once tile and evidence endpoints are ready.
- Backend API client bindings (`fnt/src/services/`) will be wired in the vertical slice ticket.

## 2026-09-05 — LIKI-002: Upload UI + Query Form (POST /query integration)

Built via Antigravity (single-agent, Windows).

**Did:**
- Created typed TypeScript contracts in `fnt/src/services/types.ts` mirroring backend schemas from `bck/app/contracts/schemas.py` (`Answer`, `Evidence`, `EvidenceType`, `TraceStep`, `ExecutionTrace`, `Modality`, `InputConfiguration`).
- Implemented `fnt/src/services/api.ts` with `submitQuery` for real `POST /query` calls sending `multipart/form-data` with exact fields: `query` (form text), `images` (repeated file fields), and `modality` (repeated form fields in matching 1:1 order). Added typed `ApiError` handling parsing FastAPI 422 validation details, HTTP errors, and network failures.
- Implemented `fnt/src/utils/fileValidation.ts` enforcing Problem Statement rules: GeoTIFF/TIFF (`.tif`, `.tiff`) for geospatial imagery and PNG/JPEG (`.png`, `.jpg`, `.jpeg`) for public benchmark datasets, rejecting empty files and unsupported extensions.
- Implemented reusable `ImageUploadSlot` component (`fnt/src/components/ImageUploadSlot.tsx`) supporting drag-and-drop, file browsing, format validation alerts, format badges, image preview thumbnails, and modality controls (`optical` / `sar`).
- Decomposed upload layout into focused components per engineering standards (max 300 lines per file): `ConfigurationSelector` (`fnt/src/components/ConfigurationSelector.tsx`), `ConfigurationUploadSection` (`fnt/src/components/ConfigurationUploadSection.tsx`), `QueryInputField` (`fnt/src/components/QueryInputField.tsx`), `UploadFormActions` (`fnt/src/components/UploadFormActions.tsx`), and `UploadSidebar` (`fnt/src/components/UploadSidebar.tsx`).
- Implemented `QueryResultCard` component (`fnt/src/components/QueryResultCard.tsx`) rendering actual backend `Answer` objects with synthesized text, confidence score, explicit abstention alerts (`abstained` + `abstention_reason` per F15/F16), grounded evidence items with tool details and payload viewer, and auditable pipeline execution trace timeline.
- Updated `UploadPage` (`fnt/src/pages/UploadPage.tsx`, 268 lines, under the 300-line repository limit) supporting exactly three input configurations:
  1. Single image (exactly 1 image, user-selectable optical/sar modality)
  2. Cross-modal pair (exactly 1 optical image + 1 SAR image)
  3. Bi-temporal pair (two spatially corresponding images represented as T1 and T2)
  Added text query input with contextual remote-sensing suggestions, submission gating when configuration is incomplete or invalid, active loading states with spinners, and backend error alerts.
- Maintained production-grade visual design and accessible keyboard/screen-reader semantics adhering to existing Tailwind design direction.
- Verified all source files strictly adhere to the 300-line coding standard ceiling, and TypeScript compilation and ESLint (`npm run lint` and `npm run build`) pass with zero errors and zero warnings.

**Important Decisions & Rationale:**
- Module ownership strictly respected: changes restricted to `fnt/src/components/**`, `fnt/src/pages/**`, `fnt/src/services/**`, and `fnt/src/utils/**`. No backend files touched.
- No fake/mock responses: `UploadPage` and `QueryResultCard` consume real `Answer` objects from `POST /query`.
- Enforced configuration validation client-side before form dispatch to prevent unnecessary invalid requests to the inference backend.
- Cross-modal configuration strictly separates optical and SAR slots with fixed modality indicators to prevent invalid combinations.

**Rejected along the way:**
- Rejected embedding fetch logic directly in `UploadPage.tsx` — created dedicated API service `fnt/src/services/api.ts` to preserve separation of concerns and maintainable architecture.
- Rejected inventing arbitrary file format rules beyond the Problem Statement requirements (GeoTIFF/TIFF + benchmark PNG/JPEG).
- Rejected inventing additional metadata form fields: backend endpoint only takes `query`, `images`, and `modality`.
- Rejected adding large testing dependencies outside the existing setup per ticket instructions.

**Checks:**
- `npm run lint`: clean, 0 errors, 0 warnings.
- `npm run build` (`tsc && vite build`): clean, built successfully without TypeScript errors.

