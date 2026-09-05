"""Dispatch planner mapping validated intents and inventory to tool parameter bindings."""

from __future__ import annotations

from app.contracts import ImageInput
from app.router.schemas import DispatchPlan, InputInventory, IntentClassification, TaskType


def build_dispatch_plan(
    intent: IntentClassification,
    raw_query: str,
    images: list[ImageInput],
    inventory: InputInventory,
) -> DispatchPlan:
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

    if task == TaskType.CHANGE_VQA:
        # Request order is strictly preserved: first image is pre-event, second is post-event
        return DispatchPlan(
            tool_name="change_detection",
            image_bindings={"pre_image": images[0].id, "post_image": images[1].id},
            task_parameters={"prompt": raw_query},
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
