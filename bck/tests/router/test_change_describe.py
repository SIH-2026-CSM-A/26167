"""CHANGE_DESCRIBE routing: the change -> VQA sequence, its trigger rule, cap and vetoes."""

import pytest
from pydantic import ValidationError

from app.contracts import ImageInput, Modality, QueryRequest
from app.router import (
    MAX_TOOL_CALLS,
    PLANNED_TOOL_SEQUENCE,
    DispatchPlan,
    TaskType,
    ToolStep,
    VetoReasonCode,
    classify_intent,
    route,
)

# A change cue AND a cue asking what the changed area contains.
COMPOSITE_PARAPHRASES = [
    "What changed between these dates, and what are the new structures in the changed area?",
    "What new buildings were constructed between these two images?",
    "Between these two dates, what was built in the changed region?",
    "Compare the pre-event and post-event scenes and identify the new construction.",
    "What kind of development appeared between these acquisitions?",
    "Run change detection and tell me what type of structures now stand in the changed area.",
    "What has been demolished between these two years?",
    "Describe the new roads that changed between these images.",
]

# Near misses: one cue without the other, or a higher-priority intent.
NEAR_MISSES = [
    ("What changed between these two dates, and where did the change occur?", TaskType.CHANGE_VQA),
    ("Has the built-up area increased, decreased, or remained unchanged?", TaskType.CHANGE_VQA),
    ("Describe what changed between these two images.", TaskType.CHANGE_VQA),
    ("What kind of buildings are visible in this image?", TaskType.VQA),
    ("Identify the new buildings in this scene.", TaskType.VQA),
    ("Use the optical and SAR images together to identify new structures.", TaskType.FUSION),
]


def _optical(image_id: str, capture_order: int | None) -> ImageInput:
    metadata = {} if capture_order is None else {"capture_order": capture_order}
    return ImageInput(
        id=image_id, modality=Modality.OPTICAL, format="PNG", path="/tmp/x.png", metadata=metadata
    )


@pytest.mark.parametrize("query", COMPOSITE_PARAPHRASES)
def test_composite_paraphrases_classify_as_change_describe(query):
    assert classify_intent(query).task_type == TaskType.CHANGE_DESCRIBE


@pytest.mark.parametrize(("query", "expected"), NEAR_MISSES)
def test_near_misses_keep_their_single_tool_intent(query, expected):
    assert classify_intent(query).task_type == expected


def test_change_describe_plans_change_detection_then_vqa_on_the_post_image():
    request = QueryRequest(
        query=COMPOSITE_PARAPHRASES[0],
        images=[_optical("pre", 0), _optical("post", 1)],
    )
    decision = route(request)
    assert decision.is_dispatched
    plan = decision.dispatch_plan
    assert plan.tool_sequence == ["change_detection", "vqa_grounding"]
    assert plan.image_bindings == {"pre_image": "pre", "post_image": "post"}
    (step,) = plan.followups
    assert step.image_bindings == {"image": "post"}
    assert step.input_from_previous == "largest_change_component"
    assert COMPOSITE_PARAPHRASES[0] in step.task_parameters["prompt"]


def test_single_tool_plans_have_no_followups():
    request = QueryRequest(
        query="What changed between these two dates, and where did the change occur?",
        images=[_optical("pre", 0), _optical("post", 1)],
    )
    plan = route(request).dispatch_plan
    assert plan.followups == ()
    assert plan.tool_sequence == ["change_detection"]


def test_plan_longer_than_max_tool_calls_is_rejected():
    step = ToolStep(
        tool_name="vqa_grounding",
        image_bindings={"image": "post"},
        input_from_previous="largest_change_component",
    )
    assert MAX_TOOL_CALLS == 2
    DispatchPlan(tool_name="change_detection", image_bindings={}, followups=(step,))
    with pytest.raises(ValidationError, match="MAX_TOOL_CALLS"):
        DispatchPlan(tool_name="change_detection", image_bindings={}, followups=(step, step))


def test_single_image_is_vetoed_as_insufficient():
    decision = route(QueryRequest(query=COMPOSITE_PARAPHRASES[0], images=[_optical("post", 1)]))
    assert decision.is_vetoed
    assert decision.intent.task_type == TaskType.CHANGE_DESCRIBE
    assert decision.veto.reason_code == VetoReasonCode.INSUFFICIENT_IMAGES


def test_missing_capture_order_is_vetoed():
    request = QueryRequest(
        query=COMPOSITE_PARAPHRASES[0],
        images=[_optical("a", None), _optical("b", None)],
    )
    decision = route(request)
    assert decision.is_vetoed
    assert decision.veto.reason_code == VetoReasonCode.TEMPORAL_ORDER_MISSING


def test_planned_sequence_table_matches_what_the_planner_builds():
    images = [_optical("pre", 0), _optical("post", 1)]
    cases = {
        TaskType.VQA: ("What is in this image?", images[:1]),
        TaskType.GROUNDING: ("Highlight the river.", images[:1]),
        TaskType.CHANGE_VQA: ("What changed between these two images?", images),
        TaskType.CHANGE_DESCRIBE: (COMPOSITE_PARAPHRASES[0], images),
    }
    for task_type, (query, request_images) in cases.items():
        decision = route(QueryRequest(query=query, images=request_images))
        assert decision.intent.task_type == task_type
        assert decision.dispatch_plan.tool_sequence == PLANNED_TOOL_SEQUENCE[task_type]


def test_region_prompt_prefix_does_not_trigger_the_spatial_bbox_pass():
    from app.router.planner import CHANGE_REGION_PROMPT_PREFIX
    from app.tools.vqa_grounding.tool import SPATIAL_TRIGGER_PATTERN

    assert SPATIAL_TRIGGER_PATTERN.search(CHANGE_REGION_PROMPT_PREFIX) is None
    non_spatial = route(
        QueryRequest(
            query=COMPOSITE_PARAPHRASES[0], images=[_optical("pre", 0), _optical("post", 1)]
        )
    )
    prompt = non_spatial.dispatch_plan.followups[0].task_parameters["prompt"]
    assert SPATIAL_TRIGGER_PATTERN.search(prompt) is None
