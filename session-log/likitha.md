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
- MapLibre GL map layer rendering and bounding box overlay will be implemented in ticket LIKI-002 once tile and evidence endpoints are ready.
- Backend API client bindings (`fnt/src/services/`) will be wired in the vertical slice ticket.

## LIKI-002: Modular Upload & Query Form Implementation
- Architected modular subcomponents in `fnt/src/components/Upload/`:
  - `ConfigSelector.tsx` (58 lines): Single Image, Cross-Modal (optical/sar locked), and Bi-Temporal modes.
  - `SlotUploader.tsx` (116 lines): Drag-and-drop file uploader with client-side benchmark and GeoTIFF validation.
  - `QueryResultCard.tsx` (92 lines): Displays answer text, confidence metric, evidence payloads, and expandable trace step viewer.
  - `UploadPage.tsx` (128 lines): Orchestrates components and coordinates 1:1 positional `submitQuery` calls.
- Enforced zero mock data; connected directly to live backend endpoint via `submitQuery`.
- Verified 0 errors on `npm run lint` and `npm run build`.
## Review Fixes Applied (PR #16)
- Reverted all changes to `bck/app/api/main.py` back to `origin/main` to keep the branch pure frontend scope and eliminate CI formatting failures.
- Configured Vite dev-server proxy (`/query` -> `http://localhost:8000`) and alias resolution in `fnt/vite.config.ts`.
- Updated `fnt/src/services/api.ts` default `API_BASE_URL` to relative pathing (`''`).
- Deleted synthetic placeholder fixtures (`pair_*.png`, `single_*.png`, `t*.png`) from `fnt/test-fixtures/` pending real SEN12MS/LEVIR-CD samples from team members.
- Verified clean linter (`npm run lint`) and production build (`npm run build`).