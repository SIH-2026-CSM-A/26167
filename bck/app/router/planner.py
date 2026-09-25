"""Dispatch planner mapping validated intents and inventory to tool parameter bindings."""

from __future__ import annotations

from app.contracts import ImageInput
from app.router.schemas import (
    DispatchPlan,
    InputInventory,
    IntentClassification,
    TaskType,
    ToolStep,
    VetoDecision,
    VetoReasonCode,
)

CHANGE_REGION_PROMPT_PREFIX = (
    "This image region is the part of the scene in which a change was detected between two "
    "acquisition dates."
)

# The tool sequence each intent plans, known before any feasibility check. The pipeline records
# it on vetoed requests too, so a refused composite query still shows what would have run.
# tests/router/test_change_describe.py keeps this equal to what build_dispatch_plan builds.
PLANNED_TOOL_SEQUENCE: dict[TaskType, list[str]] = {
    TaskType.VQA: ["vqa_grounding"],
    TaskType.GROUNDING: ["vqa_grounding"],
    TaskType.CHANGE_VQA: ["change_detection"],
    TaskType.CHANGE_DESCRIBE: ["change_detection", "vqa_grounding"],
    TaskType.FUSION: ["fusion"],
    TaskType.ARCHIVE_SEARCH_BONUS: ["archive_search"],
}


def build_dispatch_plan(
    intent: IntentClassification,
    raw_query: str,
    images: list[ImageInput],
    inventory: InputInventory,
) -> DispatchPlan | VetoDecision:
    """Construct immutable DispatchPlan with tool name, image bindings, and parameters.

    The router never invokes tools directly. It produces explicit slot bindings
    for consumption and execution by app.pipeline.
    """
    task = intent.task_type

    if task == TaskType.VQA:
        bound_id = (
            inventory.optical_ids[0]
            if inventory.has_optical
            else inventory.sar_ids[0]
            if inventory.has_sar
            else images[0].id
        )
        return DispatchPlan(
            tool_name="vqa_grounding",
            image_bindings={"image": bound_id},
            task_parameters={"prompt": raw_query},
        )

    if task == TaskType.GROUNDING:
        bound_id = (
            inventory.optical_ids[0]
            if inventory.has_optical
            else inventory.sar_ids[0]
            if inventory.has_sar
            else images[0].id
        )
        return DispatchPlan(
            tool_name="vqa_grounding",
            image_bindings={"image": bound_id},
            task_parameters={"prompt": raw_query, "grounding": True},
        )

    if task in (TaskType.CHANGE_VQA, TaskType.CHANGE_DESCRIBE):
        capture_orders = {image.metadata.get("capture_order") for image in images}
        if capture_orders != {0, 1}:
            return VetoDecision(
                reason_code=VetoReasonCode.TEMPORAL_ORDER_MISSING,
                message=(
                    "Temporal order not specified — use the bi-temporal Upload "
                    "slots to indicate before/after."
                ),
                suggested_action=(
                    "Re-submit via the Upload page's bi-temporal slots "
                    "(Slot 1 = before, Slot 2 = after) instead of Chat."
                ),
            )
        pre_id = next(image.id for image in images if image.metadata.get("capture_order") == 0)
        post_id = next(image.id for image in images if image.metadata.get("capture_order") == 1)
        followups: tuple[ToolStep, ...] = ()
        if task == TaskType.CHANGE_DESCRIBE:
            # VQA sees only a crop of the post image, so the prompt says what the crop is. The
            # prefix must not contain a spatial trigger word ("where", "locate", ...): those
            # would add the VQA bbox pass (~45-60 s on the Space) to every composite query.
            followups = (
                ToolStep(
                    tool_name="vqa_grounding",
                    image_bindings={"image": post_id},
                    task_parameters={
                        "prompt": f"{CHANGE_REGION_PROMPT_PREFIX} {raw_query.strip()}"
                    },
                    input_from_previous="largest_change_component",
                ),
            )
        return DispatchPlan(
            tool_name="change_detection",
            image_bindings={"pre_image": pre_id, "post_image": post_id},
            task_parameters={"prompt": raw_query},
            followups=followups,
        )

    if task == TaskType.FUSION:
        return DispatchPlan(
            tool_name="fusion",
            image_bindings={
                "optical_image": inventory.optical_ids[0],
                "sar_image": inventory.sar_ids[0],
            },
            task_parameters={"prompt": raw_query},
        )

    if task == TaskType.ARCHIVE_SEARCH_BONUS:
        ref_bindings = {f"reference_image_{i}": img.id for i, img in enumerate(images)}
        return DispatchPlan(
            tool_name="archive_search",
            image_bindings=ref_bindings,
            task_parameters={"query": raw_query},
        )

    raise ValueError(f"Unsupported task type for dispatch planning: {task}")
