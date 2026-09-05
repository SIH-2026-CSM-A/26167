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
- Mapped all design components directly against the six PS orchestration requirements from SIH26167 (ISRO/SAC).

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
