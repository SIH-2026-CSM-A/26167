# SHIVA-001: Router Design — Intent Schema and Veto-Layer Specification

**Module:** `bck/app/router`  
**Owner:** Shivasai (`@adepushivasai901-ops`)  
**Status:** Design Specification (Interface Sketches & Architecture Blueprint — Non-Production)  
**Associated Ticket:** SHIVA-001  
**Target Branch:** `feature/26167-SHIVA-001-router-design`  

---

## 1. Purpose and Scope

This document specifies the architectural design, interface sketches, and deterministic veto logic for the **SatQuery AI Router module** (`app.router`, F9–F11). 

The router acts as the cognitive dispatch decision-maker in the SatQuery AI backend pipeline. It consumes a `QueryRequest` (user natural language text and an inventory of uploaded image descriptors), determines the user's operational intent via a fixed, schema-constrained task taxonomy, validates whether the uploaded image inventory can physically support the intent, and emits an actionable dispatch plan for execution by `app.pipeline`.

### Core Architectural Mandates & Constraints
- **Design-Only Scope:** All Python models and functions presented here are design interface sketches and architectural pseudocode. They define the contract and behavior for subsequent implementation tickets and are **not** production code.
- **Isolated Leaf Module:** In strict adherence to `.github/CODEOWNERS` and `ARCHITECTURE.md`, `app.router` is an isolated leaf module. It imports only from `app.contracts`, `app.core`, and itself.
- **No Direct Tool Execution:** The router **never** imports `app.tools` or `app.models`, and **never** calls or executes tools directly. It only produces deterministic routing decisions and parameter bindings for `app.pipeline` to execute.
- **Zero Free-Form Agents / CoT:** Strictly **no** LangGraph-style agent graphs, **no** free-form ReAct loops, **no** unconstrained LLM "free text routing", and **no** chain-of-thought (CoT) token scoring or probabilistic confidence thresholding.
- **Single Source of Truth:** `TaskType` is the sole authority for intent. Redundant boolean requirement flags are eliminated so contradictory states cannot exist.
- **Feasibility Separation:** Router veto logic is strictly limited to deterministic structural and inventory feasibility derived from `TaskType`, `InputInventory`, registry capability availability, and raw query structural validation (`query.strip()`). The veto layer does not perform semantic keyword parsing on raw query text; domain-specific physical incompatibilities (e.g. asking for optical spectral reflectance on SAR data) are handled downstream by verification and abstention mechanisms (`app.verification`, F15/F16).

---

## 2. Fixed Task-Type Registry

The problem statement (ISRO/SAC SIH26167) specifies discrete remote-sensing operational workflows. The router classifies queries into a closed, fixed enum:

```python
from enum import StrEnum


class TaskType(StrEnum):
    """Fixed task registry matching PS-specified operational capabilities."""

    VQA = "vqa"
    """Single-image Visual Question Answering over Optical or SAR imagery."""

    GROUNDING = "grounding"
    """Single-image referring expression segmentation or bounding-box localization."""

    CHANGE_VQA = "change_vqa"
    """Bi-temporal change detection, change description, and change-VQA across pre- and post-event scenes."""

    FUSION = "fusion"
    """Cross-modal joint analysis and rule-based reconciliation across co-registered Optical + SAR pairs."""

    ARCHIVE_SEARCH_BONUS = "archive_search_bonus"
    """Catalog semantic search and historical archive retrieval (PRD §11 bonus capability)."""
```

---

## 3. Schema-Constrained Intent Classification (Interface Sketch)

> [!NOTE]
> The following schema is a design sketch illustrating the narrow, constrained structure of the intent output.

The intent classification step strictly maps raw query semantics to `TaskType`. It avoids open-ended text, reasoning traces, and probabilistic confidence scores.

```python
from pydantic import BaseModel, ConfigDict


class IntentClassification(BaseModel):
    """Narrow, schema-constrained candidate intent.

    TaskType is the sole source of truth; no redundant boolean flags
    (e.g., requires_grounding, requires_cross_modal) are permitted.
    """

    model_config = ConfigDict(frozen=True)

    task_type: TaskType
```

### Deterministic Derivation of Requirements from `TaskType`
Because `TaskType` is the single source of truth, all downstream input inventory requirements and tool target bindings are derived deterministically:

| `TaskType` | Derived Image Inventory Requirement | Derived Modality Requirement | Target Tool Binding in Pipeline |
| :--- | :--- | :--- | :--- |
| `VQA` | Exactly 1 image | Optical or SAR | `vqa_grounding` (mode: VQA) |
| `GROUNDING` | Exactly 1 image | Optical or SAR | `vqa_grounding` (mode: Grounding/Localization) |
| `CHANGE_VQA` | Exactly 2 images (bi-temporal pair) | Optical pair or SAR pair (with pre/post order) | `change_detection` (BIT / ChangeFormer) |
| `FUSION` | At least 2 images (co-registered) | Must contain $\ge 1$ Optical **and** $\ge 1$ SAR | `fusion` (Optical + SAR late fusion) |
| `ARCHIVE_SEARCH_BONUS` | 0 or more images (catalog query) | Any | `archive_search` (if enabled in registry) |

---

## 4. Input Inventory Model (Interface Sketch)

The router extracts deterministic structural facts from the incoming `QueryRequest.images: list[ImageInput]` without mutating shared contracts:

```python
from pydantic import BaseModel, ConfigDict


class InputInventory(BaseModel):
    """Deterministic structural summary of the QueryRequest image payload."""

    model_config = ConfigDict(frozen=True)

    total_images: int
    has_optical: bool
    has_sar: bool
    optical_ids: list[str]
    sar_ids: list[str]
```

---

## 5. Deterministic Veto Layer

The veto layer sits between intent classification and dispatch planning. It evaluates whether the candidate `TaskType` is executable given the actual `InputInventory`, active registry capabilities, and raw query structural validity.

The veto layer is strictly restricted to structural feasibility:
- **`CHANGE_VQA`** requires the bi-temporal inventory (exactly 2 images).
- **`FUSION`** requires co-registered cross-modal inventory ($\ge 1$ Optical and $\ge 1$ SAR).
- **`VQA` and `GROUNDING`** enforce single-image inventory (exactly 1 image) as defined by `TaskType`.
- **`ARCHIVE_SEARCH_BONUS`** checks active capability availability in the registry.
- **Empty query validation** is a direct structural validation using `query.strip()`.

Any domain-level modality incompatibility that cannot be determined purely from `TaskType` and `InputInventory` is evaluated downstream by `app.verification` (F15/F16), consistent with `ARCHITECTURE.md`.

### Veto Reason Codes and Decision Schema
```python
class VetoReasonCode(StrEnum):
    """Deterministic veto codes consumed by pipeline and verification layers."""

    EMPTY_QUERY = "EMPTY_QUERY"
    INSUFFICIENT_IMAGES = "INSUFFICIENT_IMAGES"
    EXCESS_IMAGES = "EXCESS_IMAGES"
    CROSS_MODAL_PAIR_MISSING = "CROSS_MODAL_PAIR_MISSING"
    CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"


class VetoDecision(BaseModel):
    """Deterministic veto payload explaining why an intent cannot be executed."""

    model_config = ConfigDict(frozen=True)

    reason_code: VetoReasonCode
    message: str
    suggested_action: str
```

### Deterministic Veto Rules

1. **Rule VETO-01 (Raw Query Structural Validity Gate):**
   - The raw query string is directly inspected using `query.strip()`.
   - If `not query or not query.strip()`, veto immediately with `EMPTY_QUERY`.
2. **Rule VETO-02 (Registry Availability Gate):**
   - If the selected `TaskType` is not registered or disabled in the active registry configuration (e.g. `ARCHIVE_SEARCH_BONUS` when search infrastructure is unconfigured), veto with `CAPABILITY_UNAVAILABLE`.
3. **Rule VETO-03 (Change-VQA Bi-temporal Inventory Gate):**
   - If `TaskType.CHANGE_VQA`: requires exactly 2 images.
   - If `total_images < 2`: veto with `INSUFFICIENT_IMAGES`.
   - If `total_images > 2`: veto with `EXCESS_IMAGES`.
4. **Rule VETO-04 (Cross-Modal Fusion Inventory Gate):**
   - If `TaskType.FUSION`: requires co-registered optical and SAR imagery.
   - If `not (has_optical and has_sar)`: veto with `CROSS_MODAL_PAIR_MISSING`.
5. **Rule VETO-05 (Single-Image Tasks Inventory Gate):**
   - If `TaskType.VQA` or `TaskType.GROUNDING`: requires exactly 1 image per the inventory requirements derived from `TaskType`.
   - If `total_images == 0`: veto with `INSUFFICIENT_IMAGES`.
   - If `total_images > 1`: veto with `EXCESS_IMAGES`.
6. **Domain-Level Modality Feasibility Boundary (Downstream Verification):**
   - Single-image tasks (`VQA`, `GROUNDING`) validly dispatch to `vqa_grounding` for either optical or SAR inputs based on `TaskType`.
   - The router veto layer does **not** perform semantic interpretation or keyword parsing of raw query text to guess domain-specific physical constraints.
   - Any domain-level modality incompatibility that cannot be determined purely from `TaskType` and `InputInventory` (e.g., asking for optical spectral reflectance on SAR data) is handled downstream by `app.verification` (F15/F16), which is architecturally responsible for stripping unsupported claims and producing typed abstentions (`Answer.abstained = True`, `Answer.abstention_reason = ...`) when sensor evidence cannot support the query.

---

## 6. Veto Evaluation Pseudocode

```python
def evaluate_veto(
    raw_query: str,
    intent: IntentClassification,
    inventory: InputInventory,
    registry_capabilities: dict[TaskType, bool],
) -> VetoDecision | None:
    """Evaluates deterministic structural feasibility rules. Returns VetoDecision on failure, None on success."""

    # 1. Direct raw query structural emptiness check
    if not raw_query or not raw_query.strip():
        return VetoDecision(
            reason_code=VetoReasonCode.EMPTY_QUERY,
            message="Query text is empty or whitespace-only.",
            suggested_action="Provide a specific geospatial question or command.",
        )

    # 2. Tool registry capability availability check
    if not registry_capabilities.get(intent.task_type, False):
        return VetoDecision(
            reason_code=VetoReasonCode.CAPABILITY_UNAVAILABLE,
            message=f"Capability '{intent.task_type.value}' is currently unavailable or disabled in the tool registry.",
            suggested_action="Use single-image VQA, change detection, or cross-modal fusion workflows.",
        )

    # 3. TaskType-derived structural inventory feasibility rules
    task = intent.task_type

    if task == TaskType.CHANGE_VQA:
        if inventory.total_images < 2:
            return VetoDecision(
                reason_code=VetoReasonCode.INSUFFICIENT_IMAGES,
                message=f"Change detection requires 2 temporal images (pre- and post-event), but {inventory.total_images} was provided.",
                suggested_action="Upload both pre-event and post-event satellite scenes.",
            )
        if inventory.total_images > 2:
            return VetoDecision(
                reason_code=VetoReasonCode.EXCESS_IMAGES,
                message=f"Change detection currently supports bi-temporal pairs (2 images), but {inventory.total_images} were provided.",
                suggested_action="Select exactly two scenes (pre- and post-event) to compare.",
            )

    elif task == TaskType.FUSION:
        if not (inventory.has_optical and inventory.has_sar):
            return VetoDecision(
                reason_code=VetoReasonCode.CROSS_MODAL_PAIR_MISSING,
                message="Cross-modal fusion requires both Optical and SAR imagery.",
                suggested_action="Upload a co-registered pair containing at least one Optical and one SAR scene.",
            )

    elif task in (TaskType.VQA, TaskType.GROUNDING):
        if inventory.total_images == 0:
            return VetoDecision(
                reason_code=VetoReasonCode.INSUFFICIENT_IMAGES,
                message=f"Single-image {task.value} requires an uploaded satellite image.",
                suggested_action="Upload an optical or SAR image to inspect.",
            )
        if inventory.total_images > 1:
            return VetoDecision(
                reason_code=VetoReasonCode.EXCESS_IMAGES,
                message=f"Single-image {task.value} received {inventory.total_images} images.",
                suggested_action="Provide a single image, or select bi-temporal / cross-modal workflows.",
            )
        # Note: Domain-level physical capability constraints (e.g. asking for optical-only facts on a SAR image)
        # are evaluated downstream by app.verification (F15/F16), not by query keyword parsing here.

    elif task == TaskType.ARCHIVE_SEARCH_BONUS:
        # If capability is enabled in registry, archive search accepts text query with 0 or more reference rasters
        pass

    return None
```

---

## 7. Supported vs. Rejected Input Combinations Matrix

| Input Inventory | Candidate TaskType | Registry Enabled? | Decision | Result / Reason Code | Bound Tool / Slots |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `""` (Empty string) | Any | Any | **VETO** | `EMPTY_QUERY` | None |
| 1 Optical | `VQA` | Yes | **DISPATCH** | None | `vqa_grounding` (`image: opt_id`) |
| 1 Optical | `GROUNDING` | Yes | **DISPATCH** | None | `vqa_grounding` (`image: opt_id`, `grounding: True`) |
| 1 SAR | `VQA` | Yes | **DISPATCH** | None | `vqa_grounding` (`image: sar_id`)\* |
| 1 SAR | `GROUNDING` | Yes | **DISPATCH** | None | `vqa_grounding` (`image: sar_id`, `grounding: True`)\* |
| 1 Optical | `CHANGE_VQA` | Yes | **VETO** | `INSUFFICIENT_IMAGES` | None |
| 1 SAR | `FUSION` | Yes | **VETO** | `CROSS_MODAL_PAIR_MISSING` | None |
| 2 Optical (T1, T2) | `CHANGE_VQA` | Yes | **DISPATCH** | None | `change_detection` (`pre_image: t1_id`, `post_image: t2_id`) |
| 2 SAR (T1, T2) | `CHANGE_VQA` | Yes | **DISPATCH** | None | `change_detection` (`pre_image: t1_id`, `post_image: t2_id`) |
| 1 Optical + 1 SAR | `FUSION` | Yes | **DISPATCH** | None | `fusion` (`optical_image: opt_id`, `sar_image: sar_id`) |
| >2 Images | `VQA` / `GROUNDING` / `CHANGE_VQA` | Yes | **VETO** | `EXCESS_IMAGES` | None |
| 0 Images | `VQA` / `GROUNDING` / `CHANGE_VQA` / `FUSION` | Yes | **VETO** | `INSUFFICIENT_IMAGES` | None |
| 0 Images | `ARCHIVE_SEARCH_BONUS` | **No** | **VETO** | `CAPABILITY_UNAVAILABLE` | None |
| 0 Images | `ARCHIVE_SEARCH_BONUS` | **Yes** | **DISPATCH** | None | `archive_search` (`query: raw_query`) |

\* *Domain-level modality incompatibilities (e.g. asking for visual color or optical spectral indices on SAR imagery) are not parsed via keyword heuristics in the router; they are dispatched to the tool and verified downstream by `app.verification` (F15/F16), which issues a typed abstention (`Answer.abstained = True`, `Answer.abstention_reason = ...`) if sensor evidence cannot support the query.*

---

## 8. Dispatch Plan Schema & Responsibility Boundaries

### Dispatch Plan and Router Decision (Interface Sketches)
```python
class DispatchPlan(BaseModel):
    """Parameter binding emitted for pipeline tool execution. Router does not run tools."""

    model_config = ConfigDict(frozen=True)

    tool_name: str  # "vqa_grounding" | "change_detection" | "fusion" | "archive_search"
    image_bindings: dict[
        str, str
    ]  # {"image": id} | {"pre_image": id1, "post_image": id2} | {"optical_image": id1, "sar_image": id2}
    task_parameters: dict[str, str | bool]  # {"prompt": query, "grounding": True}


class RouterDecision(BaseModel):
    """Final output emitted by app.router to app.pipeline."""

    model_config = ConfigDict(frozen=True)

    status: str  # "dispatched" | "vetoed"
    intent: IntentClassification
    dispatch_plan: DispatchPlan | None = None
    veto: VetoDecision | None = None
```

### Responsibility Breakdown
The router workflow strictly separates five lifecycle phases:

```text
+-------------------------+      +---------------------------+      +-----------------------+
|  1. Classification      | ---> |  2. Inventory Validation  | ---> |  3. Veto Layer        |
|  (TaskType from query)  |      |  (extract structural facts|      |  (deterministic gate) |
+-------------------------+      +---------------------------+      +-----------------------+
                                                                                |
                                         +--------------------------------------+
                                         |
                                         +---> VETO: Return VetoDecision (abort dispatch)
                                         |
                                         +---> PASS:
                                                 |
                                                 v
                                 +-------------------------------+
                                 |  4. Dispatch Plan             |
                                 |  (bind IDs to tool slots)     |
                                 +-------------------------------+
                                                 |
                                                 v  (emits RouterDecision to pipeline)
                                 +-------------------------------+
                                 |  5. Pipeline Execution        |
                                 |  (app.pipeline runs tools)    |
                                 +-------------------------------+
```

1. **Classification Responsibility (`app.router.classifier`):**
   - Identifies candidate `TaskType` from `QueryRequest.query`.
   - Strictly schema-constrained without probabilistic confidence scores or CoT scratchpads.
2. **Inventory Feasibility Responsibility (`app.router.inventory`):**
   - Inspects `QueryRequest.images` and builds `InputInventory`.
   - Summarizes counts, modalities (Optical vs. SAR), and image IDs.
3. **Veto Responsibility (`app.router.veto`):**
   - Strictly limited to deterministic structural and inventory feasibility derived from `TaskType`, `InputInventory`, and registry capability availability.
   - Evaluates raw query structural validity (`query.strip()`) without performing semantic keyword interpretation of the query text.
   - If invalid or incompatible, generates a structured `VetoDecision` with an explicit reason code and terminates the dispatch attempt.
4. **Dispatch-Plan Responsibility (`app.router.planner`):**
   - Reached only if the veto layer passes.
   - Binds specific image IDs to semantic input slots required by the downstream tool.
   - Emits a frozen `DispatchPlan`.
5. **Pipeline Execution Responsibility (`app.pipeline` — Lead-Owned):**
   - The router **does not execute tools**.
   - `app.pipeline` evaluates `RouterDecision`:
     - If `status == "vetoed"`: pipeline routes directly to `app.verification` to construct a typed `Answer(abstained=True, abstention_reason=decision.veto.message)`.
     - If `status == "dispatched"`: pipeline invokes the bound tool in `app.tools` or `app.models`, collects `Evidence`, and passes it forward.
     - Domain-level physical incompatibilities that cannot be determined purely from `TaskType` and `InputInventory` are evaluated by `app.verification` (F15/F16), which forces an explicit typed abstention if evidence is insufficient.

---

## 9. Mapping Against the Six PSD §2 Orchestration Requirements

| # | PSD §2 Orchestration Requirement (Verbatim) | Responsibility Boundary & Fulfillment in SHIVA-001 Router Design |
| :--- | :--- | :--- |
| **1** | **interpret the query and classify the requested task** | **Owned by `app.router`.** The router uses a fixed `TaskType` taxonomy (`vqa`, `grounding`, `change_vqa`, `fusion`, `archive_search_bonus`) and schema-constrained `IntentClassification`. Free-form routing, ReAct loops, LangGraph orchestration, and unconstrained routing text are excluded. |
| **2** | **check number, modality, format, metadata, compatibility of input images** | **Owned by `app.router` (structural feasibility) & `app.ingestion` (format/metadata).** The router performs deterministic structural feasibility checks using `TaskType` and `InputInventory`, validating image count and required modality combinations. Unsupported structural combinations produce typed `VetoDecision`s. Domain-level sensor interpretation and downstream evidence compatibility remain outside the router boundary. |
| **3** | **select model(s)/tool(s) from a predefined registry** | **Owned by `app.router`.** The router maps the selected task to a predefined dispatch target (`vqa_grounding`, `change_detection`, `fusion`, `archive_search`). It does not import, instantiate, or execute tools; tool execution remains outside the isolated router leaf module. |
| **4** | **configure only permitted task parameters and execute the workflow** | **Configuration owned by `app.router`; Execution owned by `app.pipeline`.** The router emits a constrained `DispatchPlan` with permitted parameter bindings (`image_bindings`, `task_parameters`). Workflow execution is owned solely by `app.pipeline`; the router does not execute the workflow directly. |
| **5** | **combine textual and spatial outputs, estimate confidence, return visual evidence** | **Not owned by `app.router` (Downstream).** Output combination, confidence estimation, abstention handling, and visual evidence assembly are handled downstream by `app.verification` and the evidence-assembly layer. The router only supplies the dispatch plan and typed veto information that feed into those stages. |
| **6** | **provide an auditable execution summary (task, model/tool names, key parameters)** | **Not owned by `app.router` (Downstream).** The final execution summary is assembled and recorded by `app.pipeline`. The router supplies the auditable routing facts: task type, selected tool names, parameter bindings, and veto/dispatch information needed for the execution summary. |
