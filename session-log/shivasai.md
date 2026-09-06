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

## 2026-09-06 — SHIVA-003: Conflict-Resolution & Verification Layer Design (F15/F16)

- **Ticket:** SHIVA-003
- **Status:** DESIGN COMPLETE (Implementation Pending in SHIVA-004)
- **Branch:** `feature/26167-SHIVA-003-verification-design`

**Did:**
- Performed rigorous architecture and contract investigation across repository contracts (`bck/app/contracts/schemas.py`), pipeline seams (`bck/app/pipeline/stages.py`, `bck/app/pipeline/pipeline.py`), `ARCHITECTURE.md`, `AGENTS.md`, and project specifications (`01-SatQuery-AI-PRD.md`, `02-SatQuery-AI-Features-Spec.md`, `03-SatQuery-AI-Technical-Implementation.md`).
- Confirmed `ToolResult` does not exist in `app.contracts` or anywhere in the repository; established `Evidence` as the sole canonical contract boundary for `app.verification`.
- Completely restructured and authored `bck/app/verification/DESIGN.md` into an implementation-ready 15-section architecture blueprint for F15 and F16.
- Formulated a 5-stage deterministic verification lifecycle: (1) Evidence Availability & Feasibility Gate, (2) Domain-Level Sensor Compatibility Gate, (3) Structured Claim Grounding, (4) Cross-Modal Relationship Classification, (5) Final Verification Decision Assembly.
- Defined a deterministic 8-rule table (RULE-VERIFY-01 to RULE-VERIFY-08) operating strictly on available contract data (`Evidence.payload`, `Evidence.type`, `ImageInput.modality`), eliminating invented geometry fields and unsupported assumptions.
- Formulated an explicit 5-state cross-modal relationship model (`AGREEMENT`, `DISAGREEMENT`, `COMPLEMENTARY`, `NOT_COMPARABLE`, `INSUFFICIENT_EVIDENCE`) to distinguish legitimate complementary sensor observations from genuine contradictions.
- Defined strict boundaries for structured claim grounding (counts, areas, percentages, structured identifiers) against `EvidenceType.STATS` payloads; explicitly excluded unconstrained semantic natural-language fact-checking from deterministic post-processing.
- Established a clean text mutation boundary: `app.verification` produces an immutable `VerificationDecision` reporting verified evidence, disagreement records, and penalties without mutating upstream inputs or constructing downstream `Answer` objects.
- Formulated typed abstention protocols with deterministic reason codes (`NO_EVIDENCE_PRODUCED`, `INSUFFICIENT_CONFIDENCE`, `SENSOR_PHYSICAL_LIMITATION`, `SEVERE_MODALITY_CONFLICT`, `UNVERIFIABLE_MANDATORY_CLAIM`), strictly enforcing `Answer` contract constraints (`abstained=True` requires `abstention_reason`).
- Verified 1:1 backward compatibility with the pipeline seam (`stub_verification(evidence: list[Evidence]) -> tuple[list[Evidence], bool, str | None]`) via `VerificationDecision.as_pipeline_tuple()`.
- Designed trace integration (`verification_trace_params`, `create_verification_trace_step`) using strictly JSON-serializable primitives for `TraceStep.params`.
- Outlined a concrete 9-point test suite specification for subsequent implementation in `SHIVA-004`.

**Key Architectural Decisions:**
- **Evidence as Canonical Verification Boundary:** Verification operates strictly on `list[Evidence]`. If `AASH-003` introduces tool-internal objects, they must be adapted to `Evidence` upstream before reaching verification; `app.verification` never imports `app.tools`.
- **Configurable Policy Over Hardcoded Magic Numbers:** Replaced arbitrary universal thresholds (such as 0.30 confidence floor or IoU 0.30) with an explicit `VerificationPolicy` model. Documented that defaults are baseline implementation policies requiring empirical calibration against benchmark slices (VRSBench, RSVQA, BigEarthNet.txt).
- **Conditional Spatial Geometry Consistency:** Eliminated assumptions about universal polygon/mask intersection. Spatial contradiction and extent comparison rules execute conditionally only when compatible, contract-defined coordinate reference systems and geometries are present in payloads; otherwise, the relationship is recorded as `NOT_COMPARABLE`.
- **Complementary Sensor Physics Over Forced Sensor Superiority:** Rejected blanket rules declaring SAR superior to Optical during clouds. The verification layer surfaces both facts transparently: optical cloud limitation alongside independent radar observations, preserving physical nuance and uncertainty.
- **Conservative Radar Scattering Physics:** Replaced claims of universal SAR canopy penetration with conservative physical characterization: differing returns are classified as distinct scattering mechanisms (volume/dielectric vs. spectral) rather than asserting penetration without sensor frequency/polarization metadata.
- **Bounded Deterministic Grounding:** Restricted claim grounding strictly to numeric quantities and coordinates cross-referenced against structured `STATS` payloads. Descriptive qualitative prose is preserved without false claims of mathematical verification.
- **Leaf Module Isolation (Zero Cross-Leaf Imports):** `app.verification` imports solely from `app.contracts`, `app.core`, and internal modules. No dependencies on `app.router`, `app.pipeline`, `app.tools`, or `app.models`.

**Rejected Along the Way:**
- **Inventing Unverified Contracts / ToolResult:** Rejected defining local duplicate schemas or assuming `ToolResult` exists.
- **Second-LLM Verification / Evaluator LLM:** Explicitly rejected per Technical Implementation §2.6 to eliminate latency spikes, compute costs, and non-determinism.
- **Arbitrary Threshold Claims:** Rejected presenting uncalibrated numbers as scientific facts.
- **Direct Edits to `app.contracts`:** Preserved ownership boundaries for `@ybaddam8-png`.
- **Premature Production Code in Design Ticket:** Maintained SHIVA-003 strictly as a design deliverable; implementation deferred to SHIVA-004.

**Constraints Followed:**
- Leaf module isolation verified via import-linter.
- No changes to `app.contracts/` or other teammate modules.
- No commit or push performed prior to explicit user approval.

**Validation Evidence:**
- `uv run ruff check .` $\rightarrow$ PASS (0 errors)
- `uv run ruff format --check .` $\rightarrow$ PASS (50 files already formatted)
- `uv run lint-imports` $\rightarrow$ PASS (Contracts: 3 kept, 0 broken)
- `uv run pytest` $\rightarrow$ PASS (50 passed in 12.51s)

---

### Session: 2026-09-06 — SHIVA-004: Adversarial Abstention Path Implementation

**Branch:** `feature/26167-SHIVA-004-abstention-path`

**Objective:**
Implement the minimal production verification module (`app.verification`) and adversarial abstention path based on `DESIGN.md` (approved in PR #14). Ensure the system explicitly abstains on unanswerable and adversarial queries, grounds structured numeric claims, reconciles cloud-obscured optical with SAR radar observations, and makes abstentions structurally distinguishable from low-confidence verified answers in execution traces.

**Work Completed:**
- Created `bck/app/verification/schemas.py`: Implemented typed Pydantic models and Enums (`VerificationStatus`, `DisagreementCategory`, `CrossModalRelationship`, `AbstentionReasonCode`, `DisagreementRecord`, `VerificationPolicy`, `VerificationDecision`) with `as_pipeline_tuple()` backward-compatibility seam and clamped `effective_confidence` property.
- Created `bck/app/verification/rules.py`: Implemented pure deterministic rule evaluators:
  - `evaluate_empty_evidence` (RULE-VERIFY-01: forces `NO_EVIDENCE_PRODUCED` abstention).
  - `evaluate_confidence_floor` (RULE-VERIFY-02: filters sub-floor items, forces `INSUFFICIENT_CONFIDENCE` if all fail).
  - `evaluate_sensor_compatibility` (RULE-VERIFY-03: forces `SENSOR_PHYSICAL_LIMITATION` when optical spectral properties like NDVI/color are queried on SAR-only data).
  - `evaluate_cloud_sar_reconciliation` (RULE-VERIFY-04: records `COMPLEMENTARY_OBSERVATION` and preserves SAR evidence when optical is cloud-affected; does NOT abstain).
  - `evaluate_structured_numeric_grounding` (RULE-VERIFY-06: cross-references explicit numeric assertions in TEXT against STATS payloads; flags `UNSUPPORTED_NUMERIC_CLAIM` and applies confidence penalties).
  - `evaluate_cross_modal_conflict` (RULE-VERIFY-CONFLICT: forces `SEVERE_MODALITY_CONFLICT` abstention when optical asserts 0% water under 0% cloud while SAR asserts standing water on the identical region).
- Created `bck/app/verification/verifier.py`: Implemented master `verify(...)` evaluation pipeline and JSON-serializable trace parameter generators (`verification_trace_params`, `create_verification_trace_step`).
- Created `bck/app/verification/__init__.py`: Clean public module exports.
- Integrated into `bck/app/pipeline/stages.py`: Updated `stub_verification` to delegate to `verify(...).as_pipeline_tuple()`.
- Integrated into `bck/app/pipeline/pipeline.py`: Wired real verification hop calling `verify(...)` directly, recording full `verification_trace_params(decision)` and `decision.effective_confidence` into the execution trace step.
- Configured `bck/pyproject.toml`: Added `ignore_imports = ["app.api.main -> app.pipeline.pipeline"]` under Contract 1 so the top-level API caller composing through the pipeline preserves module independence while satisfying the layers contract.
- Created `bck/tests/verification/__init__.py` and `bck/tests/verification/test_verification.py`: 21 comprehensive unit tests covering all schemas, individual rule evaluators, trace formatting, and policy overrides.
- Created `bck/tests/verification/test_adversarial_abstention.py`: 11 adversarial tests fulfilling all acceptance criteria:
  - AC 1A: Absent-object queries against real Bolivia scene fixture (`Bolivia_103757_S2Hand.tif`) produce explicit typed abstentions (`NO_EVIDENCE_PRODUCED` / `INSUFFICIENT_CONFIDENCE`) without claiming verification evaluates raw imagery.
  - AC 1B & AC 4: Real cloudy crop from Sen1Floods11 scene through real fusion pipeline preserves SAR water evidence under `COMPLEMENTARY_OBSERVATION` and does NOT abstain.
  - AC 1C: Contradictory optical/SAR observations on the same region trigger typed abstention (`SEVERE_MODALITY_CONFLICT`).
  - AC 2: Structured numeric claims in TEXT grounded against STATS payloads; unsupported claims are downgraded.
  - AC 3: Explicit typed abstention triggers enforced across all four codes.
  - AC 5: Abstention (`status="abstained"`, `abstained=True`, `confidence=0.0`) is structurally distinguishable from low-confidence verified answers (`status="verified"`, `abstained=False`, `confidence_penalty > 0.0`) in trace params.
  - AC 6: End-to-end `pipeline.run(request)` execution produces an auditable trace with verification step parameters.

**Key Architectural Decisions:**
- **Epistemic Limitation Maintained:** Verification does not inspect raw pixels; absent-object abstention operates deterministically on upstream tool output signals (empty evidence or sub-floor confidence).
- **No Second LLM/VLM Call:** All verification rules are deterministic, pure functions operating in microseconds without non-determinism, hallucinations, or GPU compute overhead.
- **Auditable Trace Distinction:** Preserved full `VerificationDecision` in `pipeline.py` and serialized all disagreement records, filtered evidence IDs, penalties, and reasons into `TraceStep.params`.
- **Offline Multi-Modal Fixtures:** All tests run 100% offline using committed Sentinel-1/Sentinel-2 GeoTIFF fixtures (`Bolivia_103757_S1Hand.tif`, `Bolivia_103757_S2Hand.tif`).

**Deferred Rules:**
- Complex geometry IoU / polygon overlap (RULE-VERIFY-05).
- Canopy penetration physics (RULE-VERIFY-07).
- Mask-to-bounding-box geometric consistency (RULE-VERIFY-08).

**Validation Evidence:**
- `git diff --check` $\rightarrow$ PASS (0 whitespace errors)
- `uv run ruff check .` $\rightarrow$ PASS (All checks passed!)
- `uv run ruff format --check .` $\rightarrow$ PASS (69 files already formatted)
- `uv run lint-imports` $\rightarrow$ PASS (Contracts: 3 kept, 0 broken)
- `uv run pytest` $\rightarrow$ PASS (98 passed, 2 warnings in 6.47s)
