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
