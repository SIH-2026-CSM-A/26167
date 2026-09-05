# Verification Layer Design

**Module:** `bck/app/verification`
**Owner:** Shivasai (`@adepushivasai901-ops`)
**Status:** Design Specification (Interface Sketches & Architecture Blueprint — Non-Production)
**Associated Ticket:** SHIVA-003
**Target Branch:** `feature/26167-SHIVA-003-verification-design`
**Implementation Ticket:** SHIVA-004

---

## 1. Purpose and Scope

This document specifies the architectural design, interface sketches, deterministic conflict-resolution rules, structured claim-grounding mechanisms, cross-modal relationship classifications, and typed abstention protocols for the **SatQuery AI Verification module** (`app.verification`, addressing features **F15** and **F16**).

The verification layer acts as the cognitive safety, grounding, and reconciliation gate in the SatQuery AI backend pipeline. It executes deterministically in pure Python without secondary LLM/VLM calls. Its responsibilities are:

1. **Hallucination Mitigation & Structured Claim Grounding (F15):** Mechanically verifies that asserted numeric quantities (counts, percentages, areas) and structured coordinates are backed by contract-valid `Evidence` payloads (such as `EvidenceType.STATS`). Any ungrounded or contradictory claim is stripped or penalized, while non-verifiable semantic claims are explicitly marked rather than falsely validated.
2. **Deterministic Cross-Modal Relationship Classification & Conflict Resolution (F16):** Evaluates independent tool outputs across sensors (notably Optical vs. SAR) against a deterministic rule table. Rather than forcing an artificial consensus or declaring arbitrary sensor superiority, it classifies modal relationships into explicit states (`AGREEMENT`, `DISAGREEMENT`, `COMPLEMENTARY`, `NOT_COMPARABLE`, `INSUFFICIENT_EVIDENCE`) and transparently records discrepancies.
3. **Explicit Typed Abstention (F15 / PRD §8):** Prevents speculative answers when evidence is absent, confidence is below a calibrated policy floor, or physical sensor limitations prevent answering the user's question (e.g. optical reflectance queried on SAR-only data). It emits typed, auditable abstentions adhering strictly to the `Answer` contract (`abstained=True`, `abstention_reason=...`).

---

## 2. Architectural Position

The verification layer is positioned downstream of tool execution and upstream of final answer assembly. It does **not** execute tools or models.

```text
User Request (QueryRequest: query + images)
      │
      ▼
┌──────────────┐
│  app.router  │  (Classifies intent, validates structural input feasibility F9-F11)
└──────┬───────┘
       │  DispatchPlan
       ▼
┌──────────────┐
│ app.pipeline │  (Orchestrates lifecycle stages per ARCHITECTURE.md)
└──────┬───────┘
       │  Invokes specialist tools
       ▼
┌──────────────┐
│  app.tools*  │  (Specialist models run: vqa_grounding, change_detection, fusion)
└──────┬───────┘
       │  Emits list[Evidence]
       ▼
┌──────────────────────┐
│   app.verification   │  ◄── [SHIVA-003 Design / SHIVA-004 Implementation]
│                      │  - Filters unviable evidence
│                      │  - Validates physical sensor compatibility
│                      │  - Grounds structured numeric claims
│                      │  - Classifies cross-modal relationships
│                      │  - Emits VerificationDecision (verified evidence, trace, abstention)
└──────────┬───────────┘
           │  VerificationDecision.as_pipeline_tuple() -> (verified_evidence, abstained, reason)
           ▼
┌──────────────────────┐
│     app.evidence     │  (Assembles final Answer, formats text, map overlays, PDF report F14/F23)
└──────────┬───────────┘
           │
           ▼
Final Answer (Answer contract returned to API)
```

### Key Position Constraints:
- **No Direct Tool Invocation:** `app.verification` never imports or calls `app.tools.*` or `app.models.*`.
- **Pure Leaf Isolation:** Per `.github/CODEOWNERS` and `pyproject.toml` (`[tool.importlinter]`), `app.verification` imports **only** from `app.contracts`, `app.core`, and internal `app.verification` modules. It does **not** import `app.router`, `app.pipeline`, or `app.evidence`.
- **Zero Second-LLM Calls:** Verification evaluates deterministic Python rules and regex/key-value scanners, introducing negligible latency (<5ms) and preserving offline compute boundaries.

---

## 3. Contract Inventory

The verification design depends **only** on contracts confirmed to exist in `bck/app/contracts/schemas.py`. It does not invent fields or assume unverified models.

| Contract | Fields Used in Verification | Verification Purpose |
| :--- | :--- | :--- |
| **`Evidence`** | `id: str`<br>`tool: str`<br>`type: EvidenceType`<br>`payload: dict[str, Any]`<br>`confidence: float`<br>`timing: float` | Primary input unit. Verification inspects `type`, `confidence`, and `payload` for grounding and conflict resolution. Filters weak evidence. |
| **`EvidenceType`** | `TEXT`, `BBOX`, `MASK`, `STATS`, `LAYER` | Payload kind discriminator. Used to route evidence to appropriate validation sub-routines (e.g. `STATS` for numbers, `TEXT` for claim checking). |
| **`ImageInput`** | `id: str`<br>`modality: Modality`<br>`format: str`<br>`metadata: dict[str, Any]` | Input image descriptor from `QueryRequest`. Used in domain-level sensor compatibility checks to verify if sensor modality matches query demands. |
| **`Modality`** | `Modality.OPTICAL`, `Modality.SAR` | Enum indicating sensor physics. Core anchor for cross-modal conflict and sensor limitation checks. |
| **`QueryRequest`** | `query: str`<br>`images: list[ImageInput]` | Contextual request metadata providing the raw user prompt and input image descriptors for physical compatibility checking. |
| **`TraceStep`** | `module: str`<br>`action: str`<br>`params: dict[str, Any]`<br>`confidence: float \| None`<br>`started_at: datetime`<br>`completed_at: datetime \| None`<br>`evidence_ids: list[str]` | Auditable execution hop. Verification serializes its decisions, disagreement records, and actions into `params`. |
| **`Answer`** | `text: str`<br>`evidence: list[Evidence]`<br>`trace: ExecutionTrace`<br>`confidence: float`<br>`abstained: bool`<br>`abstention_reason: str \| None` | Target pipeline contract. Verification ensures downstream `Answer` validity via explicit typed abstention flags and reason codes. |

> [!IMPORTANT]
> **Absence of ToolResult:** `ToolResult` does **not** exist in `app.contracts` or the repository. `Evidence` is the sole canonical contract emitted by tools and consumed by verification.

---

## 4. Responsibility Boundary

To avoid scope creep and preserve modularity, the responsibilities of `app.verification` are strictly bounded:

### Verification IS Responsible For:
1. **Evidence Feasibility & Confidence Gating:** Checking that evidence was produced and filtering evidence falling below configurable reliability thresholds.
2. **Domain-Level Physical Sensor Compatibility:** Intercepting requests where query demands conflict with fundamental sensor physics (e.g. optical spectral indices queried on SAR-only data).
3. **Structured Claim Grounding:** Validating that specific numeric quantities (counts, areas, percentages) asserted in text payloads are backed by structured values in `EvidenceType.STATS` payloads.
4. **Cross-Modal Relationship Classification:** Classifying relationships between multi-sensor outputs into explicit categories (`AGREEMENT`, `DISAGREEMENT`, `COMPLEMENTARY`, `NOT_COMPARABLE`, `INSUFFICIENT_EVIDENCE`).
5. **Conflict Resolution & Caveating:** Reconciling known physical sensor behaviors (such as optical cloud obstruction alongside SAR flood detection) and downgrading confidence when genuine contradictions occur.
6. **Typed Abstention Enforcement:** Forcing structured abstentions (`abstained=True`, `abstention_reason=...`) when evidence is unviable or sensor capability is fundamentally unsupported.
7. **Audit Trace Serialization:** Generating JSON-serializable diagnostic metadata for `TraceStep.params`.

### Verification IS NOT Responsible For:
1. **Running Tools or Models:** Verification never schedules, executes, or manages tools (`app.tools`) or model weights (`app.models`).
2. **Reclassifying User Intent:** Intent classification and tool dispatch belong solely to `app.router`. Verification only inspects the query for domain sensor compatibility.
3. **Generating Imagery or Rasters:** Ingestion and image preprocessing belong to `app.ingestion`.
4. **Inventing Missing Evidence:** Verification never extrapolates, synthesizes, or hallucinates missing data points.
5. **Unrestricted Natural-Language Fact-Checking:** Open-ended semantic claims outside contract-defined structured payloads cannot be mechanically validated without an LLM judge; they remain outside verification's deterministic post-processing scope.
6. **Constructing the Final Answer:** Rendering final natural language responses, map layers, and PDF reports belongs to `app.evidence`. Verification outputs a `VerificationDecision`.

---

## 5. Verification Lifecycle

Verification executes sequentially across five deterministic stages:

```text
Inputs: list[Evidence], raw_query: str | None, images: list[ImageInput] | None, policy: VerificationPolicy
                                  │
                                  ▼
 ┌─────────────────────────────────────────────────────────────────┐
 │ Stage 1: Evidence Availability & Feasibility Gate               │
 ├─────────────────────────────────────────────────────────────────┤
 │ Input:   list[Evidence], policy.min_confidence_floor            │
 │ Process: Verify evidence list is non-empty. Filter items below  │
 │          confidence floor. Check if surviving items exist.      │
 │ Output:  valid_evidence: list[Evidence]                         │
 │ Failure: If empty -> ABSTAIN (NO_EVIDENCE_PRODUCED)            │
 │          If all below floor -> ABSTAIN (INSUFFICIENT_CONFIDENCE)│
 └────────────────────────────────┬────────────────────────────────┘
                                  │
                                  ▼
 ┌─────────────────────────────────────────────────────────────────┐
 │ Stage 2: Domain-Level Sensor Compatibility Gate                 │
 ├─────────────────────────────────────────────────────────────────┤
 │ Input:   raw_query, images (list[ImageInput])                   │
 │ Process: Scan query for optical-specific spectral requests     │
 │          (NDVI, RGB color, true color) when inputs are SAR-only.│
 │ Output:  Compatibility status (PASS or CONFLICT)                │
 │ Failure: If incompatible -> ABSTAIN (SENSOR_PHYSICAL_LIMITATION)│
 └────────────────────────────────┬────────────────────────────────┘
                                  │
                                  ▼
 ┌─────────────────────────────────────────────────────────────────┐
 │ Stage 3: Structured Claim Grounding                             │
 ├─────────────────────────────────────────────────────────────────┤
 │ Input:   valid_evidence (TEXT vs STATS payloads)                │
 │ Process: Extract structured numbers from TEXT evidence. Check   │
 │          existence against numeric values in STATS payloads.    │
 │ Output:  grounding_records: list[DisagreementRecord], penalty   │
 │ Failure: Unsupported numbers recorded; penalty deducted.        │
 └────────────────────────────────┬────────────────────────────────┘
                                  │
                                  ▼
 ┌─────────────────────────────────────────────────────────────────┐
 │ Stage 4: Cross-Modal Relationship Classification                │
 ├─────────────────────────────────────────────────────────────────┤
 │ Input:   valid_evidence across distinct tools/modalities        │
 │ Process: Classify pair relationships: AGREEMENT, DISAGREEMENT,  │
 │          COMPLEMENTARY, NOT_COMPARABLE, INSUFFICIENT_EVIDENCE.  │
 │          Reconcile optical cloud vs SAR water transparently.    │
 │ Output:  relationship_records: list[DisagreementRecord]         │
 │ Failure: Severe irreconcilable conflict -> ABSTAIN or downgrade │
 └────────────────────────────────┬────────────────────────────────┘
                                  │
                                  ▼
 ┌─────────────────────────────────────────────────────────────────┐
 │ Stage 5: Final Verification Decision Assembly                   │
 ├─────────────────────────────────────────────────────────────────┤
 │ Input:   Accumulated records, retained evidence, total penalty  │
 │ Process: Compute final effective confidence, assemble           │
 │          VerificationDecision, format pipeline tuple.           │
 │ Output:  VerificationDecision                                   │
 └─────────────────────────────────────────────────────────────────┘
```

---

## 6. Deterministic Rule Table

Every rule is deterministic, operates strictly on available contract data, and specifies its trace and abstention effects. Thresholds are drawn from a configurable `VerificationPolicy` object rather than hard-coded magic numbers.

| Rule ID | Name | Trigger Condition | Required Contract Data | Action Taken | Trace Effect | Abstention Effect |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **RULE-VERIFY-01** | **Empty Evidence Gate** | `len(evidence) == 0` | `evidence: list[Evidence]` | Terminate verification; emit abstention decision. | Record `status="abstained"`, `action="empty_evidence_gate"`. | **Forces Abstention:** `NO_EVIDENCE_PRODUCED`. |
| **RULE-VERIFY-02** | **Confidence Floor Gate** | Item has `confidence < policy.min_confidence_floor` | `Evidence.confidence` | Filter item out of retained evidence. If all items are filtered, terminate. | Record filtered evidence IDs in `filtered_evidence_ids`. | **Forces Abstention:** `INSUFFICIENT_CONFIDENCE` if surviving count is 0. |
| **RULE-VERIFY-03** | **Sensor Physical Incompatibility Gate** | Query asks for optical spectral properties (e.g. NDVI, RGB color) but all input images are `Modality.SAR`. | `QueryRequest.query`, `ImageInput.modality` | Terminate verification; reject physical incompatibility. | Record `rule_id="RULE-VERIFY-03"`, `category="sensor_physical_limitation"`. | **Forces Abstention:** `SENSOR_PHYSICAL_LIMITATION`. |
| **RULE-VERIFY-04** | **Optical Cloud vs. SAR Radar Reconciliation** | Optical evidence reports cloud cover limitation while SAR evidence reports surface/flood observation. | `Evidence.payload` containing recognized cloud and flood indicators | Reconcile: Retain both observations; surface cloud limitation and SAR independence transparently. | Record `category="complementary"`, `action_taken="reconciled"`. | **No Abstention.** Both observations reported. |
| **RULE-VERIFY-05** | **Scattering Mechanism Divergence** | Optical and SAR report different surface characteristics over vegetation or built structures. | `Evidence.payload` across distinct tools | Do not assume penetration; record modality divergence due to physical scattering differences. | Record `category="complementary"`, `action_taken="caveated"`. | **No Abstention.** Discrepancy noted in trace. |
| **RULE-VERIFY-06** | **Structured Numeric Claim Grounding** | `TEXT` payload contains numeric quantities (count, area, percentage) not found in any `STATS` payload. | `EvidenceType.TEXT`, `EvidenceType.STATS`, `Evidence.payload` | Flag ungrounded numeric claim; apply configurable confidence penalty `policy.unsupported_numeric_penalty`. | Record `category="unsupported_numeric_claim"`, `action_taken="downgraded"`. | **No Abstention** unless confidence drops below floor. |
| **RULE-VERIFY-07** | **Conditional Spatial Geometry Consistency** | Terrestrial detection and water mask geometries overlap beyond threshold in a shared, verified coordinate frame. | Compatible geometry fields in `Evidence.payload` (CRS, bbox/polygon) | If compatible geometries exist and conflict, apply `policy.spatial_contradiction_penalty`. If geometries are missing or incompatible, record `NOT_COMPARABLE`. | Record `category="spatial_contradiction"` or `not_comparable`. | **No Abstention.** Confidence penalized or marked non-comparable. |
| **RULE-VERIFY-08** | **Cross-Modal Spatial Extent Comparison** | Optical and SAR segmentation masks exist for the same target in a compatible coordinate frame. | Compatible raster/polygon geometries in `Evidence.payload` | If spatial IoU is low in a shared frame, apply `policy.extent_divergence_penalty`. If incompatible or absent, record `NOT_COMPARABLE`. | Record `category="cross_modal_conflict"` or `not_comparable`. | **No Abstention.** Retain both extents with caveat. |

---

## 7. Cross-Modal Relationship Model

In multi-sensor remote sensing (particularly Optical and SAR), observations often differ without being contradictory. Verification evaluates evidence pairs against five mutually exclusive relationship states:

```python
class CrossModalRelationship(StrEnum):
    AGREEMENT = "agreement"
    DISAGREEMENT = "disagreement"
    COMPLEMENTARY = "complementary"
    NOT_COMPARABLE = "not_comparable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
```

### Deterministic Classification Criteria:

1. **`AGREEMENT`**:
   - Both modalities evaluate the same physical attribute or target area and produce mutually consistent results (e.g. both confirm standing water or both confirm urban expansion).
2. **`DISAGREEMENT`**:
   - Both modalities evaluate the exact same spatial feature under comparable observing conditions but assert diametrically opposing conclusions (e.g. Optical confirms dry bare ground with high confidence under clear skies, while SAR asserts deep standing water on the identical footprint).
3. **`COMPLEMENTARY`**:
   - The modalities provide differing observations that are explained by distinct sensor physics rather than error (e.g. Optical observes cloud cover $\ge 50\%$, while SAR microwave pulses penetrate clouds to map surface water; or Optical detects tree canopy while SAR backscatter indicates ground surface roughness). Both findings are preserved.
4. **`NOT_COMPARABLE`**:
   - Tools produced outputs that cannot be mathematically or physically juxtaposed (e.g. one output is an image-level caption, while the other is an unreferenced bounding box; or geometries lack a common coordinate reference system). Verification records `NOT_COMPARABLE` rather than manufacturing a false conflict.
5. **`INSUFFICIENT_EVIDENCE`**:
   - One or both modalities failed to produce evidence, or surviving evidence has confidence below the policy threshold.

---

## 8. Structured Claim Grounding

Acceptance criteria require that claims not backed by actual payload data are stripped or downgraded. Because unrestricted natural-language semantic parsing cannot be performed deterministically without an LLM judge, the verification layer strictly bounds its scope to **structurally verifiable claims**.

### Supported Claim Categories:
1. **Integer Counts:** Discrete quantities (e.g. "detected 14 storage tanks", "3 bridges").
2. **Percentage Ratios:** Proportions (e.g. "cloud cover 42%", "built-up area increased by 15%").
3. **Physical Areas:** Measured extents (e.g. "flooded area 12.5 km²", "45.2 ha").
4. **Structured Identifiers:** Named class labels or category tags explicitly listed in payloads.

### Claim Evaluation States:
- **`SUPPORTED`:** The numeric value extracted from the text payload matches a numeric value present in an associated `EvidenceType.STATS` payload within a relative tolerance $\epsilon = 0.01$. No penalty applied.
- **`UNSUPPORTED`:** The numeric value in the text payload cannot be located in any `STATS` payload. Action taken: The claim is recorded in `DisagreementRecord(action_taken="downgraded")` and a confidence penalty is applied.
- **`NOT_VERIFIABLE`:** The claim is descriptive prose (e.g. "the region appears moderately vegetated") without corresponding quantitative metrics in the evidence. Verification marks the claim as ungrounded qualitative text; it does **not** alter the text or claim mathematical verification.

---

## 9. Typed Abstention

The verification layer replaces speculative answers with auditable, typed abstentions. An abstention directly populates `Answer.abstained = True` and requires a non-empty `Answer.abstention_reason`.

### Abstention Reason Codes:

```python
class AbstentionReasonCode(StrEnum):
    NO_EVIDENCE_PRODUCED = "NO_EVIDENCE_PRODUCED"
    """Specialist tools returned zero evidence items."""

    INSUFFICIENT_CONFIDENCE = "INSUFFICIENT_CONFIDENCE"
    """All evidence items failed the configurable minimum confidence floor."""

    SENSOR_PHYSICAL_LIMITATION = "SENSOR_PHYSICAL_LIMITATION"
    """Query demands physical properties (e.g. optical reflectance/NDVI) absent in the sensor modality (e.g. SAR)."""

    SEVERE_MODALITY_CONFLICT = "SEVERE_MODALITY_CONFLICT"
    """Optical and SAR assert direct contradictions with equal high confidence and no reconciling physical explanation."""

    UNVERIFIABLE_MANDATORY_CLAIM = "UNVERIFIABLE_MANDATORY_CLAIM"
    """The central quantitative answer demanded by the query cannot be grounded in evidence."""
```

### Abstention vs. Caveating Policy:
- **Abstain:** Triggered when the system *cannot responsibly answer* (e.g. no evidence, sub-floor confidence, or physical impossibility).
- **Caveat (Do NOT Abstain):** Triggered when evidence is complementary or uncertain but meaningful observations exist (e.g. optical clouds present, but SAR flood detection is reliable; or extents differ across modalities). Both facts are surfaced to the user.

---

## 10. Verification Decision Contract

The following models represent the conceptual schema designed for implementation in `bck/app/verification/schemas.py` during ticket `SHIVA-004`:

```python
from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.contracts import Evidence


class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    ABSTAINED = "abstained"


class DisagreementCategory(StrEnum):
    CROSS_MODAL_CONFLICT = "cross_modal_conflict"
    SPATIAL_CONTRADICTION = "spatial_contradiction"
    UNSUPPORTED_NUMERIC_CLAIM = "unsupported_numeric_claim"
    SENSOR_PHYSICAL_LIMITATION = "sensor_physical_limitation"
    COMPLEMENTARY_OBSERVATION = "complementary_observation"
    NOT_COMPARABLE = "not_comparable"


class DisagreementRecord(BaseModel):
    """Auditable log of a detected discrepancy or claim evaluation."""

    model_config = ConfigDict(frozen=True)

    rule_id: str
    category: DisagreementCategory
    description: str
    action_taken: str  # "downgraded" | "reconciled" | "caveated" | "abstained"
    conflicting_evidence_ids: list[str] = Field(default_factory=list)


class VerificationPolicy(BaseModel):
    """Configurable verification thresholds and penalty weights.
    Per Features Spec F15 and F22, these are implementation defaults
    subject to empirical calibration against benchmark slices.
    """

    model_config = ConfigDict(frozen=True)

    min_confidence_floor: float = 0.30
    unsupported_numeric_penalty: float = 0.15
    spatial_contradiction_penalty: float = 0.40
    extent_divergence_penalty: float = 0.20
    max_total_penalty: float = 0.50


class VerificationDecision(BaseModel):
    """Output emitted by app.verification."""

    model_config = ConfigDict(frozen=True)

    status: Literal["verified", "abstained"]
    abstained: bool
    abstention_reason: str | None = None
    verified_evidence: list[Evidence] = Field(default_factory=list)
    disagreements: list[DisagreementRecord] = Field(default_factory=list)
    confidence_penalty: float = Field(default=0.0, ge=0.0, le=1.0)
    filtered_evidence_ids: list[str] = Field(default_factory=list)

    @property
    def is_abstained(self) -> bool:
        return self.abstained

    @property
    def is_verified(self) -> bool:
        return not self.abstained

    def as_pipeline_tuple(self) -> tuple[list[Evidence], bool, str | None]:
        """Direct backward-compatibility unpack for pipeline seam in app.pipeline.stages."""
        return self.verified_evidence, self.abstained, self.abstention_reason
```

---

## 11. Pipeline Integration

In `bck/app/pipeline/stages.py`, the existing verification seam authored by Yashwanth (`YASH-002`) is:

```python
def stub_verification(evidence: list[Evidence]) -> tuple[list[Evidence], bool, str | None]:
    return list(evidence), False, None
```

The verification design provides **100% type and signature compatibility**:
- Calling `decision.as_pipeline_tuple()` produces the exact `tuple[list[Evidence], bool, str | None]` expected by `pipeline.py`.
- During pipeline migration, `app.pipeline.stages.run_verification` will invoke:

```python
decision = verify(
    evidence=evidence_items,
    raw_query=request.query,
    images=request.images,
    policy=VerificationPolicy(),
)
verified_evidence, abstained, abstention_reason = decision.as_pipeline_tuple()
```

---

## 12. Trace Integration

Verification produces structured, JSON-serializable parameters for `TraceStep.params`. No non-serializable objects or custom classes are placed in trace storage.

```python
def verification_trace_params(decision: VerificationDecision) -> dict[str, Any]:
    """Generate auditable parameter dictionary for contracts.TraceStep.params."""
    return {
        "status": decision.status,
        "abstained": decision.abstained,
        "abstention_reason": decision.abstention_reason,
        "retained_evidence_count": len(decision.verified_evidence),
        "filtered_evidence_count": len(decision.filtered_evidence_ids),
        "filtered_evidence_ids": decision.filtered_evidence_ids,
        "disagreement_count": len(decision.disagreements),
        "disagreements": [
            {
                "rule_id": d.rule_id,
                "category": str(d.category.value),
                "description": d.description,
                "action_taken": d.action_taken,
                "conflicting_evidence_ids": d.conflicting_evidence_ids,
            }
            for d in decision.disagreements
        ],
        "confidence_penalty": decision.confidence_penalty,
    }


def create_verification_trace_step(
    decision: VerificationDecision,
    started_at: datetime,
    completed_at: datetime | None = None,
) -> TraceStep:
    """Build a valid TraceStep contract representing the verification hop."""
    return TraceStep(
        module="verification",
        action="verify",
        params=verification_trace_params(decision),
        started_at=started_at,
        completed_at=completed_at,
        evidence_ids=[e.id for e in decision.verified_evidence],
    )
```

---

## 13. AASH-003 Integration Boundary

ClickUp ticket notes reference a potential `ToolResult` concept from `AASH-003`. However, inspection of the actual repository confirms:
- **`ToolResult` does NOT exist in `bck/app/contracts/`.**
- Per `ARCHITECTURE.md` §Data Flow, every specialist tool emits the uniform `Evidence` schema (`{id, tool, type, payload, confidence, timing}`).
- `app.verification` strictly consumes `list[Evidence]` as its canonical boundary.

### Future Adapter Protocol:
If `AASH-003` later produces tool-internal objects, they must be converted into `Evidence` objects in `app.tools` or `app.pipeline` before reaching verification. `app.verification` will **never** import `app.tools`.

### Recommended Shared Fixture:
A shared test fixture `make_evidence(...)` should be utilized in unit tests to construct valid `Evidence` objects without coupling tests to tool implementations:

```python
def make_evidence(
    tool: str = "test_tool",
    evidence_type: EvidenceType = EvidenceType.TEXT,
    payload: dict[str, Any] | None = None,
    confidence: float = 0.85,
) -> Evidence:
    return Evidence(
        id=str(uuid.uuid4()),
        tool=tool,
        type=evidence_type,
        payload=payload or {},
        confidence=confidence,
        timing=0.05,
    )
```

---

## 14. Test Strategy for SHIVA-004

Implementation ticket `SHIVA-004` will implement a test suite in `bck/tests/verification/test_verification.py`. The suite must include test cases covering every designed behavior:

1. **Unsupported Structured Numeric Claim:**
   - *Input:* `Evidence(type=TEXT, payload={"text": "Detected 8 storage tanks."})` with no matching `STATS` payload.
   - *Expected:* Disagreement recorded (`UNSUPPORTED_NUMERIC_CLAIM`, `downgraded`), confidence penalized.
2. **SAR-Only Request for Optical-Only Property:**
   - *Input:* Query `"Compute NDVI vegetation index"`, `images=[ImageInput(modality=Modality.SAR)]`.
   - *Expected:* Abstention (`abstained=True`, `reason="SENSOR_PHYSICAL_LIMITATION"`).
3. **No Evidence Produced:**
   - *Input:* `evidence=[]`.
   - *Expected:* Abstention (`abstained=True`, `reason="NO_EVIDENCE_PRODUCED"`).
4. **Complementary Optical / SAR Outputs:**
   - *Input:* Optical evidence reporting cloud cover; SAR evidence reporting surface flood boundary.
   - *Expected:* Both evidence items retained; relationship classified as `COMPLEMENTARY`; no abstention.
5. **Deliberately Conflicting Optical / SAR Outputs:**
   - *Input:* Optical asserts clear bare ground; SAR asserts standing water over identical bounds without cloud obstruction.
   - *Expected:* Disagreement recorded (`CROSS_MODAL_CONFLICT`); confidence penalized.
6. **Non-Comparable Modalities:**
   - *Input:* Optical bounding box and SAR raster mask lacking shared coordinates or metadata.
   - *Expected:* Disagreement recorded as `NOT_COMPARABLE`; no invalid geometric calculations executed.
7. **Abstention Contract Validity:**
   - *Input:* Deliberately unanswerable input.
   - *Expected:* Generated `Answer` validates under `Answer._abstention_reason_matches_flag` (fails if `abstained=True` without reason).
8. **Trace Metadata Generation:**
   - *Input:* Any verification run.
   - *Expected:* `verification_trace_params` output is 100% JSON-serializable; contains counts, IDs, and statuses.
9. **Pipeline Tuple Compatibility:**
   - *Input:* Any verification run.
   - *Expected:* `decision.as_pipeline_tuple()` unpacks exactly into `(list[Evidence], bool, str | None)`.

---

## 15. Open Questions / Dependencies

The following dependencies remain open and require upstream alignment before production deployment:

1. **Tool Payload Standardization (AASH-003 / ROHAN-001):**
   - While `Evidence.payload` is `dict[str, Any]`, structured claim grounding requires specialist tools to emit standardized keys in `STATS` payloads (e.g. `{"count": int}`, `{"area_km2": float}`).
2. **Geometry Representation Schema:**
   - For `RULE-VERIFY-07` and `RULE-VERIFY-08` to perform spatial IoU or containment math in implementation, a standard representation for `MASK` (e.g. RLE, GeoJSON, binary array) and `BBOX` (`[ymin, xmin, ymax, xmax]` normalized vs pixel coordinates) must be agreed with tool authors.
3. **Empirical Confidence Calibration:**
   - Verification policy thresholds (`min_confidence_floor = 0.30`, penalties) are implementation baselines. Per PRD §10 and Features Spec F15/F22, these must be empirically tuned against the held-out BigEarthNet.txt, VRSBench, and RSVQA benchmark slices.
