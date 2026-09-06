"""Unit tests for SatQuery AI Router module (SHIVA-002, F9–F12)."""

from datetime import UTC, datetime

from app.contracts import ExecutionTrace, ImageInput, Modality, QueryRequest, TraceStep
from app.router import (
    TaskType,
    VetoReasonCode,
    create_router_trace_step,
    route,
    router_trace_params,
)

PS_QUERY_1 = "Describe the land-cover and major objects visible in this image."
PS_QUERY_2 = "Highlight the water body referred to in the query."
PS_QUERY_3 = "What changed between these two dates, and where did the change occur?"
PS_QUERY_4 = (
    "Use the optical and SAR images together to identify built-up and water-covered regions."
)
PS_QUERY_5 = "Has the built-up area increased, decreased, or remained unchanged?"


def _opt(img_id: str = "opt-01") -> ImageInput:
    return ImageInput(id=img_id, modality=Modality.OPTICAL, format="GeoTIFF", path=f"{img_id}.tif")


def _sar(img_id: str = "sar-01") -> ImageInput:
    return ImageInput(id=img_id, modality=Modality.SAR, format="GeoTIFF", path=f"{img_id}.tif")


# ---------------------------------------------------------------------------
# 1. Five Representative Problem Statement Queries (Dispatched)
# ---------------------------------------------------------------------------
def test_ps_query_1_vqa_dispatched():
    """Query 1: Single-image VQA routes to TaskType.VQA and tool 'vqa_grounding'."""
    req = QueryRequest(query=PS_QUERY_1, images=[_opt("opt-1")])
    decision = route(req)

    assert decision.is_dispatched
    assert not decision.is_vetoed
    assert decision.intent.task_type is TaskType.VQA
    assert decision.dispatch_plan is not None
    assert decision.dispatch_plan.tool_name == "vqa_grounding"
    assert decision.dispatch_plan.image_bindings == {"image": "opt-1"}
    assert decision.dispatch_plan.task_parameters == {"prompt": PS_QUERY_1}
    assert decision.veto is None


def test_ps_query_2_grounding_dispatched():
    """Query 2: Grounding routes to TaskType.GROUNDING and tool 'vqa_grounding'."""
    req = QueryRequest(query=PS_QUERY_2, images=[_opt("opt-1")])
    decision = route(req)

    assert decision.is_dispatched
    assert decision.intent.task_type is TaskType.GROUNDING
    assert decision.dispatch_plan is not None
    assert decision.dispatch_plan.tool_name == "vqa_grounding"
    assert decision.dispatch_plan.image_bindings == {"image": "opt-1"}
    assert decision.dispatch_plan.task_parameters == {"prompt": PS_QUERY_2, "grounding": True}


def test_ps_query_3_change_vqa_dispatched():
    """Query 3: Bi-temporal change routes to TaskType.CHANGE_VQA and 'change_detection'."""
    req = QueryRequest(query=PS_QUERY_3, images=[_opt("opt-pre"), _opt("opt-post")])
    decision = route(req)

    assert decision.is_dispatched
    assert decision.intent.task_type is TaskType.CHANGE_VQA
    assert decision.dispatch_plan is not None
    assert decision.dispatch_plan.tool_name == "change_detection"
    assert decision.dispatch_plan.image_bindings == {
        "pre_image": "opt-pre",
        "post_image": "opt-post",
    }
    assert decision.dispatch_plan.task_parameters == {"prompt": PS_QUERY_3}


def test_ps_query_4_fusion_dispatched():
    """Query 4: Joint Optical+SAR routes to TaskType.FUSION and tool 'fusion'."""
    req = QueryRequest(query=PS_QUERY_4, images=[_opt("opt-1"), _sar("sar-1")])
    decision = route(req)

    assert decision.is_dispatched
    assert decision.intent.task_type is TaskType.FUSION
    assert decision.dispatch_plan is not None
    assert decision.dispatch_plan.tool_name == "fusion"
    assert decision.dispatch_plan.image_bindings == {
        "optical_image": "opt-1",
        "sar_image": "sar-1",
    }
    assert decision.dispatch_plan.task_parameters == {"prompt": PS_QUERY_4}


def test_ps_query_5_change_vqa_sar_dispatched():
    """Query 5: Categorical change on SAR pair routes to TaskType.CHANGE_VQA."""
    req = QueryRequest(query=PS_QUERY_5, images=[_sar("sar-t1"), _sar("sar-t2")])
    decision = route(req)

    assert decision.is_dispatched
    assert decision.intent.task_type is TaskType.CHANGE_VQA
    assert decision.dispatch_plan is not None
    assert decision.dispatch_plan.tool_name == "change_detection"
    assert decision.dispatch_plan.image_bindings == {
        "pre_image": "sar-t1",
        "post_image": "sar-t2",
    }
    assert decision.dispatch_plan.task_parameters == {"prompt": PS_QUERY_5}


# ---------------------------------------------------------------------------
# 2. Deterministic Structural Veto Logic
# ---------------------------------------------------------------------------
def test_veto_change_vqa_malformed_single_image():
    """VETO-03: CHANGE_VQA with only 1 image is vetoed (required malformed case)."""
    req = QueryRequest(query=PS_QUERY_3, images=[_opt("single-scene")])
    decision = route(req)

    assert decision.is_vetoed
    assert not decision.is_dispatched
    assert decision.intent.task_type is TaskType.CHANGE_VQA
    assert decision.dispatch_plan is None
    assert decision.veto is not None
    assert decision.veto.reason_code is VetoReasonCode.INSUFFICIENT_IMAGES
    assert "requires 2 temporal images" in decision.veto.message


def test_veto_empty_whitespace_query():
    """VETO-01: Whitespace-only query accepted by QueryRequest is vetoed by router."""
    req = QueryRequest(query="   ", images=[_opt()])
    decision = route(req)

    assert decision.is_vetoed
    assert decision.dispatch_plan is None
    assert decision.veto is not None
    assert decision.veto.reason_code is VetoReasonCode.EMPTY_QUERY


def test_veto_single_image_insufficient_images():
    """VETO-05: Single-image VQA with 0 images is vetoed."""
    req = QueryRequest(query=PS_QUERY_1, images=[])
    decision = route(req)

    assert decision.is_vetoed
    assert decision.veto is not None
    assert decision.veto.reason_code is VetoReasonCode.INSUFFICIENT_IMAGES


def test_veto_single_image_excess_images():
    """VETO-05: Single-image VQA with >1 image is vetoed."""
    req = QueryRequest(query=PS_QUERY_1, images=[_opt("img-1"), _opt("img-2")])
    decision = route(req)

    assert decision.is_vetoed
    assert decision.veto is not None
    assert decision.veto.reason_code is VetoReasonCode.EXCESS_IMAGES


def test_veto_change_vqa_excess_images():
    """VETO-03: CHANGE_VQA with >2 images is vetoed."""
    req = QueryRequest(query=PS_QUERY_3, images=[_opt("i1"), _opt("i2"), _opt("i3")])
    decision = route(req)

    assert decision.is_vetoed
    assert decision.veto is not None
    assert decision.veto.reason_code is VetoReasonCode.EXCESS_IMAGES


def test_veto_fusion_missing_modalities():
    """VETO-04: FUSION missing optical or SAR is vetoed."""
    # Optical only
    dec_opt = route(QueryRequest(query=PS_QUERY_4, images=[_opt("o1"), _opt("o2")]))
    assert dec_opt.is_vetoed
    assert dec_opt.veto is not None
    assert dec_opt.veto.reason_code is VetoReasonCode.CROSS_MODAL_PAIR_MISSING

    # SAR only
    dec_sar = route(QueryRequest(query=PS_QUERY_4, images=[_sar("s1"), _sar("s2")]))
    assert dec_sar.is_vetoed
    assert dec_sar.veto is not None
    assert dec_sar.veto.reason_code is VetoReasonCode.CROSS_MODAL_PAIR_MISSING


def test_veto_capability_unavailable_bonus_archive():
    """VETO-02: Bonus archive search is disabled by default in registry capabilities."""
    req = QueryRequest(query="Search archive for Cartosat imagery of Hyderabad", images=[])
    decision = route(req)

    assert decision.is_vetoed
    assert decision.intent.task_type is TaskType.ARCHIVE_SEARCH_BONUS
    assert decision.veto is not None
    assert decision.veto.reason_code is VetoReasonCode.CAPABILITY_UNAVAILABLE


# ---------------------------------------------------------------------------
# 3. Dispatch Bindings & Capability Options
# ---------------------------------------------------------------------------
def test_bonus_archive_search_when_enabled():
    """VETO-02: Archive search dispatches when explicitly enabled in registry."""
    req = QueryRequest(query="Search catalog for Cartosat imagery", images=[_opt("ref-1")])
    decision = route(req, registry_capabilities={TaskType.ARCHIVE_SEARCH_BONUS: True})

    assert decision.is_dispatched
    assert decision.dispatch_plan is not None
    assert decision.dispatch_plan.tool_name == "archive_search"
    assert decision.dispatch_plan.image_bindings == {"reference_image_0": "ref-1"}


def test_sar_vqa_dispatches_without_structural_veto():
    """Feasibility Boundary: SAR VQA is structurally valid and dispatches to vqa_grounding."""
    req = QueryRequest(query="Describe the objects in this radar scene.", images=[_sar("sar-1")])
    decision = route(req)

    assert decision.is_dispatched
    assert decision.dispatch_plan is not None
    assert decision.dispatch_plan.tool_name == "vqa_grounding"
    assert decision.dispatch_plan.image_bindings == {"image": "sar-1"}


def test_change_vqa_preserves_request_image_order():
    """Change detection binds pre_image to images[0] and post_image to images[1]."""
    req = QueryRequest(query=PS_QUERY_3, images=[_opt("scene-alpha"), _opt("scene-beta")])
    decision = route(req)

    assert decision.dispatch_plan is not None
    assert decision.dispatch_plan.image_bindings["pre_image"] == "scene-alpha"
    assert decision.dispatch_plan.image_bindings["post_image"] == "scene-beta"


# ---------------------------------------------------------------------------
# 4. TraceStep & ExecutionTrace Assembly (F12)
# ---------------------------------------------------------------------------
def test_router_decision_and_trace_step_assemble_into_execution_trace():
    """RouterDecision and TraceStep assemble correctly into ExecutionTrace."""
    started = datetime.now(UTC)
    req = QueryRequest(query=PS_QUERY_1, images=[_opt("opt-1")])
    decision = route(req)
    completed = datetime.now(UTC)

    step = create_router_trace_step(decision, started_at=started, completed_at=completed)

    assert isinstance(step, TraceStep)
    assert step.module == "router"
    assert step.action == "route"
    assert step.started_at == started
    assert step.completed_at == completed
    assert step.params["status"] == "dispatched"
    assert step.params["task_type"] == "vqa"
    assert step.params["tool_name"] == "vqa_grounding"
    assert step.params["image_bindings"] == {"image": "opt-1"}

    # Assemble into full ExecutionTrace
    trace = ExecutionTrace(trace_id="tr-101", steps=[step], created_at=started)
    assert trace.trace_id == "tr-101"
    assert len(trace.steps) == 1
    assert trace.steps[0].params["tool_name"] == "vqa_grounding"


def test_veto_trace_params_format():
    """Vetoed decisions emit structured trace params with veto reason code and message."""
    req = QueryRequest(query=PS_QUERY_3, images=[_opt("only-one")])
    decision = route(req)
    params = router_trace_params(decision)

    assert params["status"] == "vetoed"
    assert params["task_type"] == "change_vqa"
    assert params["veto_reason"] == "INSUFFICIENT_IMAGES"
    assert "requires 2 temporal images" in params["veto_message"]
