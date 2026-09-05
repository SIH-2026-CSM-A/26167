# Architecture — SatQuery AI (SIH26167)

## Stack

| Layer | Choice | Rejected | Why |
|---|---|---|---|
| Backend | Python 3.11, FastAPI, uv (never pip/venv) | Node/Express | Team's ML code is Python; one language end to end avoids a serialization boundary for tensors/arrays |
| Core VLM | InternVL3-2B (MIT/Apache-2.0), `transformers`, `trust_remote_code=True` | Qwen2-VL-2B, GeoChat | BigEarthNet.txt's own authors adapted InternVL on this exact dataset — direct precedent, not a popularity argument. GeoChat is Vicuna-7B, ~3.5× this project's compute budget, and optical-only (no SAR competence) |
| Model serving (day one) | Plain `transformers` + `bitsandbytes` 4-bit | `lmdeploy`/vLLM | Fewer install surprises under time pressure; revisit only if latency becomes a demo problem with the simple path already working |
| Adaptation | LoRA/QLoRA via `peft` on BigEarthNet.txt native annotations | Synthetic caption generation from classification labels | BigEarthNet.txt already ships 9.6M real captions/VQA/referring-expression pairs — no synthesis pipeline needed |
| Cross-modal fusion | Late fusion — independent optical/SAR analysis + deterministic rule-table reconciliation | Trained pixel-fusion network (FusAtNet-class) | Every reconciliation decision stays a readable rule, not a learned weight — matches the PS's own "combine textual and spatial outputs" language, lower-risk to build correctly in the time available |
| Change detection | BIT or ChangeFormer | Training a change model from scratch | Real, published, code-available — no reason to reinvent |
| Router | Hand-rolled schema-constrained classifier | LangGraph / free-form ReAct agent | The PS's own text specifies a narrow classifier ("predefined registry," "internal reasoning text is neither required nor evaluated"), not an open planner. A framework the team hasn't used before is a risk with no PS-mandated upside |
| Database | PostgreSQL (GCP Cloud SQL or a VM-hosted instance), JSONB for evidence/trace | Supabase free tier | Supabase free projects auto-pause after 7 days with no DB request — unacceptable for a project with gaps between working sessions and a live demo at the end |
| Tile serving | TiTiler (Cloud-Optimized GeoTIFF → XYZ tiles) | Shipping raw GeoTIFFs to the browser | Browser never touches multi-gigabyte files directly |
| Frontend | React + TypeScript + Vite + Tailwind, MapLibre GL JS | Next.js | No SSR/SEO need for an internal demo tool; Vite's dev loop is faster to iterate on under a deadline. MapLibre has no API-token dependency (unlike Mapbox GL) |
| Voice (optional, P2) | Bhashini API, Web Speech API fallback | — | Real Government of India NLP mission; behind a cost ceiling and never on the critical demo path |
| Reports | Server-side generation, ReportLab | Headless-browser HTML→PDF | Avoids shipping a browser instance just to render a PDF |
| Import boundaries | `import-linter` in CI | Code-review-only enforcement | A cross-module import fails the build before a PR exists — a norm in a document is not a fact, a failing check is |

Runs fully offline after model weights and demo data are staged locally. No live API call sits on the inference path — the only network-dependent piece is the optional Bhashini voice input, which has a documented fallback.

## Folder structure

```
26167/
├── .github/
│   ├── CODEOWNERS
│   └── workflows/ci.yml
├── bck/
│   ├── pyproject.toml            # uv-managed, ruff + import-linter + pytest config
│   ├── app/
│   │   ├── contracts/            # Pydantic schemas shared by every module — Yashwanth only
│   │   ├── core/                 # config, cost ceilings, DB session, logging — Yashwanth only
│   │   ├── pipeline/             # composes modules per request — the ONLY layer allowed to
│   │   │                         #   import more than one leaf module — Yashwanth only
│   │   ├── api/                  # FastAPI routes, thin, calls pipeline only — Yashwanth only
│   │   ├── models/                # InternVL3-2B load/inference wrapper — Aashritha
│   │   ├── training/               # LoRA fine-tuning on BigEarthNet.txt — Aashritha
│   │   ├── tools/
│   │   │   ├── vqa_grounding/         # F4/F5 — thin wrapper around models/ — Aashritha
│   │   │   ├── change_detection/      # F6 — BIT/ChangeFormer — Rohan
│   │   │   └── fusion/                # F7 — optical+SAR rule-based reconciliation — Rohan
│   │   ├── router/                # F9-F11 — intent classification, tool dispatch — Shivasai
│   │   ├── verification/          # F15/F16 — conflict resolution, abstention — Shivasai
│   │   ├── evidence/               # F14/F23 — evidence schema, trace, PDF reports — Likitha
│   │   └── ingestion/              # F1-F3 — upload, GeoTIFF/TIFF compatibility checks — Jashwanth
│   └── tests/                     # mirrors app/, each owner tests their own module
├── fnt/                            # React/Vite/Tailwind/MapLibre — Likitha
├── infra/                          # docker-compose, GCP config, TiTiler — Jashwanth
├── data/                           # dataset manifests only (real data is gitignored) — Aashritha
├── session-log/<name>.md           # per-person history, never shared — everyone
├── ARCHITECTURE.md · AGENTS.md · CLAUDE.md · TODO.md · SETUP.md · SESSION-LOG.md
```

## The import rule

A module imports from `app.contracts`, `app.core`, and itself. Nothing else. Two leaf modules
never import each other. `app.pipeline` composes modules; modules never compose each other.
Enforced by `import-linter` in CI (`bck/pyproject.toml`, `[tool.importlinter]`) — a cross-module
import fails the build before it reaches a pull request.

## Data flow, end to end

```
User uploads image(s) + types a query (fnt/)
        │  POST /query  (multipart: files + query text)
        ▼
api/  — validates request shape only, calls pipeline
        ▼
pipeline/  — orchestrates the call, in this order:
        │
        ├─▶ ingestion/     — modality/format/compatibility check (F1-F3)
        │                    fails fast with a typed error if incompatible
        │
        ├─▶ router/        — classifies intent from query + input inventory,
        │                    selects tool(s) from the fixed registry (F9-F11)
        │
        ├─▶ tools/*  or  models/   — the selected tool(s) run:
        │       vqa_grounding  → models/ (InternVL3-2B forward pass)
        │       change_detection → BIT/ChangeFormer on the bi-temporal pair
        │       fusion            → independent optical + SAR analysis,
        │                           reconciled via a rule table
        │     Every tool returns the same shape: {id, tool, type, payload,
        │     confidence, timing} — the uniform evidence schema (contracts/)
        │
        ├─▶ verification/  — strips unsupported numeric/spatial claims,
        │                    surfaces modality disagreement, forces an
        │                    explicit abstention where evidence is insufficient
        │
        └─▶ evidence/      — assembles the final answer: text + visual
                             evidence + confidence + the auditable execution
                             trace + (on request) a downloadable PDF report
        ▼
api/ returns the assembled response
        ▼
fnt/  — renders chat answer, map overlay, trace panel, evidence citations
```

Training-time data flow (offline, not on the request path): BigEarthNet.txt →
`training/` (LoRA fine-tune) → adapter weights staged into `models/` → evaluated against
held-out slices of VRSBench/RSVQA/CDVQA/BigEarthNet.txt's own benchmark split.

## Decisions expensive to reverse (and why now)

1. **InternVL3-2B as the core VLM.** Every VRAM/timeline estimate in this project is sized for a
   2B model with this exact architecture. Switching mid-build re-derives the whole compute plan,
   not just a config value. Locking it now means the training pipeline in `training/` can be
   built against a known model shape from day one.
2. **Rule-based late fusion over a trained fusion network.** This shapes `verification/`'s
   contract, the evidence schema, and the demo script itself — every reconciliation decision is
   a readable rule. Reversing it late means rebuilding the reasoning stage, not swapping a model
   file.
3. **Schema-constrained router over a free-planning agent.** This is the PS's own specified
   controller shape. Abandoning it isn't a refactor — it risks disqualification against explicit
   PS text ("internal reasoning text is neither required nor evaluated").
4. **PostgreSQL over Supabase.** Decided now specifically to avoid the 7-day auto-pause trap
   biting during a lull between build sessions or, worse, right before the demo.
5. **`import-linter` contracts from commit one, not added later.** Retrofitting import
   boundaries onto code five people have already written means untangling real imports, not
   writing a config file. Cheaper to never let the violation happen.

## Deliberately deferred (and what it costs later)

- **Feature-level (learned) optical–SAR fusion** — stretch goal only, if late fusion is solid
  early. Cost of deferring: none if late fusion ships; if it doesn't, this was never realistic
  anyway given the timeline.
- **Frontend import-boundary enforcement (eslint-plugin-boundaries or similar).** `import-linter`
  covers the backend; the frontend has one owner (Likitha) so a cross-boundary import inside
  `fnt/` has no second person to protect from. Cost of deferring: none while frontend stays
  single-owned; revisit only if a second person ever touches `fnt/`.
- **Archive semantic search (F26) and everything folded in from SIH26227 (F26-F29).** Cut first
  under time pressure per the PRD's own risk table. Cost of deferring: none against the PS's
  mandatory scope — these were always bonus.
- **lmdeploy/vLLM model serving.** Plain `transformers` ships first. Cost of deferring: possibly
  slower inference at demo time; mitigated by keeping the demo script's timeout expectations
  generous and testing latency early (build order, day one).
- **GSD-conditioning training run and Cartosat/RISAT domain-gap characterization** — not deferred
  in scope, but flagged here because it's the largest unresolved risk in the whole project (see
  Technical Implementation §3.3). Owned by Aashritha, scheduled explicitly, never silently cut.
