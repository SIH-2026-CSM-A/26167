## 2026-09-05 — SHIVA-001: Router Design — Intent Schema and Veto-Layer Specification

Built via Antigravity CLI (Gemini 3.8 Flash, Windows / PowerShell).

**Ticket:** SHIVA-001  
**Branch:** `feature/26167-SHIVA-001-router-design`  

**Did:**
- Drafted complete architectural design specification in `bck/app/router/DESIGN.md` for the SatQuery AI router module (`app.router`, F9–F11).
- Defined fixed `TaskType` enum covering `VQA`, `GROUNDING`, `CHANGE_VQA`, `FUSION`, and `ARCHIVE_SEARCH_BONUS`.
- Defined narrow, schema-constrained `IntentClassification` interface sketch with `TaskType` as the single source of truth (no redundant boolean requirement flags).
- Formulated deterministic input inventory model (`InputInventory`) to extract image counts, modality types (Optical vs. SAR), and image IDs from `QueryRequest`.
- Specified deterministic veto layer logic (`evaluate_veto`) with typed `VetoReasonCode` (`EMPTY_QUERY`, `INSUFFICIENT_IMAGES`, `EXCESS_IMAGES`, `CROSS_MODAL_PAIR_MISSING`, `CAPABILITY_UNAVAILABLE`).
- Formulated comprehensive supported vs. rejected input combinations matrix.
- Established strict responsibility boundaries separating intent classification, inventory validation, veto evaluation, dispatch planning, and pipeline execution.
- Mapped all design components directly against the verbatim six PSD §2 orchestration requirements from SIH26167 (ISRO/SAC), explicitly defining router ownership for bullets 1–3, split parameter configuration/execution for bullet 4, and documenting downstream ownership by verification/evidence layers for bullets 5–6 per lead review feedback.

**Key Architectural Decisions:**
- **TaskType as Single Source of Truth:** Downstream requirements (temporal pairs for change detection, cross-modal optical+SAR for fusion, localization for grounding) are deterministically derived from `TaskType` rather than maintaining auxiliary boolean flags, preventing contradictory states.
- **Direct Raw Query Validation:** Empty/whitespace query checks are performed directly using `query.strip()`, avoiding any reliance on classifier inference or heuristics.
- **Capability-Driven Archive Search:** `ARCHIVE_SEARCH_BONUS` is maintained as a first-class valid `TaskType` with availability gated by the active tool registry configuration (`CAPABILITY_UNAVAILABLE` veto if unconfigured), rather than treating it as permanently deferred.
- **Strict Separation of Dispatch and Execution:** The router only emits a `DispatchPlan` with bound image IDs; it never imports or executes tools directly. Tool invocation remains solely with `app.pipeline`.
- **Abstention Alignment:** Veto outputs map directly into the core `Answer` contract (`abstained=True`, `abstention_reason=veto.message`) for seamless integration with `app.verification`.

**Rejected Along the Way:**
- **Probabilistic Confidence Scoring:** Completely rejected confidence scores and confidence thresholds in routing and veto evaluation. The PS requires deterministic classification and registry routing, not probabilistic routing heuristics.
- **Keyword Scoring / Detected Keywords in Schema:** Rejected `detected_keywords` in the public `IntentClassification` schema to keep the contract narrow, clean, and strictly schema-constrained.
- **Semantic Raw-Query Keyword Parsing in Veto Layer:** Rejected keyword-based substring checks (e.g. searching raw queries for "ndvi", "true color", "natural color", or "rgb reflectance") in the veto layer. Semantic interpretation belongs strictly to the schema-constrained classifier or downstream verification, while the router veto layer remains restricted to deterministic structural feasibility derived from `TaskType`, `InputInventory`, and capability availability.
- **Redundant Requirement Flags:** Rejected boolean flags (`requires_grounding`, `requires_cross_modal`, `requires_temporal_pair`) inside `IntentClassification` to prevent invalid states where flags might contradict `task_type`.
- **LangGraph / Free-form ReAct Loops:** Explicitly rejected per `ARCHITECTURE.md` and problem statement instructions; internal reasoning text is neither evaluated nor required.
- **Editing `app/contracts/` Directly:** Maintained strict module ownership boundaries; all schemas in this ticket remain design interface sketches within `bck/app/router/DESIGN.md`.

**Constraints Followed:**
- Leaf module isolation enforced (zero imports from other leaf modules).
- No production code modified or stubs introduced during this design-only ticket.
- No commit or push performed prior to explicit user review.

## 2026-09-05 — SHIVA-002: Router Implementation (F9–F12)

**Ticket:** SHIVA-002  
**Branch:** `feature/26167-SHIVA-002-router-implementation`  

**Did:**
- Implemented production router module adhering strictly to `bck/app/router/DESIGN.md` across seven files:
  - `schemas.py`: Frozen Pydantic models and enums (`TaskType`, `IntentClassification`, `InputInventory`, `VetoReasonCode`, `VetoDecision`, `DispatchPlan`, `RouterDecision`).
  - `classifier.py`: Pure deterministic pattern-based classifier mapping queries to `TaskType`.
  - `inventory.py`: Deterministic structural summary of input image descriptors.
  - `veto.py`: Deterministic structural feasibility gates (`EMPTY_QUERY`, `CAPABILITY_UNAVAILABLE`, `INSUFFICIENT_IMAGES`, `EXCESS_IMAGES`, `CROSS_MODAL_PAIR_MISSING`).
  - `planner.py`: Immutable dispatch parameter binding mapping to target tools (`vqa_grounding`, `change_detection`, `fusion`, `archive_search`).
  - `router.py`: Central `route(...)` orchestrator and trace metadata adapters.
  - `__init__.py`: Clean public package exports.
- Implemented unit test suite in `bck/tests/router/test_router.py` (17/17 tests passing).
- Verified routing for all five representative problem statement queries (verbatim PS §0 / PRD §6).
- Validated structural veto paths, including the deliberately malformed case where `CHANGE_VQA` receives 1 image.
- Implemented trace adapters (`router_trace_params`, `create_router_trace_step`) confirming seamless integration into `TraceStep` and `ExecutionTrace` without modifying `app.contracts`.

**Key Architectural Decisions:**
- **Request Order Preservation for Change Detection:** Preserved request image order (`images[0]` as `pre_image`, `images[1]` as `post_image`) rather than attempting heuristic parsing of arbitrary metadata timestamp strings not guaranteed by the contract.
- **Structural Feasibility Separation:** Kept router veto logic strictly focused on structural feasibility (counts, modalities, query emptiness). Downstream physical sensor incompatibilities remain cleanly isolated to `app.verification` (F15/F16).
- **Zero Cross-Module Pollution:** Maintained leaf module purity (imports strictly from `app.contracts`, `app.core`, and `app.router`).

**Validation Evidence:**
- `uv run ruff check .` $\rightarrow$ PASS (0 errors)
- `uv run ruff format --check .` $\rightarrow$ PASS (44 files already formatted)
- `uv run lint-imports` $\rightarrow$ PASS (Leaf modules never import each other: KEPT, Only pipeline composes modules: KEPT, Contracts import nothing of ours: KEPT)
- `uv run pytest` $\rightarrow$ PASS (37/37 tests passed)
