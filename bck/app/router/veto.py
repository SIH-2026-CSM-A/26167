"""Deterministic structural veto layer for SatQuery AI router."""

from __future__ import annotations

from app.router.schemas import (
    InputInventory,
    IntentClassification,
    TaskType,
    VetoDecision,
    VetoReasonCode,
)

DEFAULT_REGISTRY_CAPABILITIES: dict[TaskType, bool] = {
    TaskType.VQA: True,
    TaskType.GROUNDING: True,
    TaskType.CHANGE_VQA: True,
    TaskType.FUSION: True,
    TaskType.ARCHIVE_SEARCH_BONUS: False,
}


def evaluate_veto(
    raw_query: str,
    intent: IntentClassification,
    inventory: InputInventory,
    registry_capabilities: dict[TaskType, bool] | None = None,
) -> VetoDecision | None:
    """Evaluate deterministic structural feasibility rules.

    Returns VetoDecision on failure, None on success.
    Strictly evaluates structural/inventory feasibility; domain-level sensor
    incompatibilities are handled downstream by app.verification (F15/F16).
    """
    # 1. Direct raw query structural validity gate (VETO-01)
    if not raw_query or not raw_query.strip():
        return VetoDecision(
            reason_code=VetoReasonCode.EMPTY_QUERY,
            message="Query text is empty or whitespace-only.",
            suggested_action="Provide a specific geospatial question or command.",
        )

    # 2. Tool registry capability availability gate (VETO-02)
    capabilities = DEFAULT_REGISTRY_CAPABILITIES.copy()
    if registry_capabilities is not None:
        capabilities.update(registry_capabilities)

    if not capabilities.get(intent.task_type, False):
        return VetoDecision(
            reason_code=VetoReasonCode.CAPABILITY_UNAVAILABLE,
            message=(
                f"Capability '{intent.task_type.value}' is currently "
                f"unavailable or disabled in the tool registry."
            ),
            suggested_action=(
                "Use single-image VQA, change detection, or cross-modal fusion workflows."
            ),
        )

    # 3. TaskType-derived structural inventory feasibility rules
    task = intent.task_type

    if task == TaskType.CHANGE_VQA:
        if inventory.total_images < 2:
            count_str = (
                f"{inventory.total_images} was"
                if inventory.total_images == 1
                else f"{inventory.total_images} were"
            )
            return VetoDecision(
                reason_code=VetoReasonCode.INSUFFICIENT_IMAGES,
                message=(
                    f"Change detection requires 2 temporal images (pre- and post-event), "
                    f"but {count_str} provided."
                ),
                suggested_action="Upload both pre-event and post-event satellite scenes.",
            )
        if inventory.total_images > 2:
            return VetoDecision(
                reason_code=VetoReasonCode.EXCESS_IMAGES,
                message=(
                    f"Change detection currently supports bi-temporal pairs (2 images), "
                    f"but {inventory.total_images} were provided."
                ),
                suggested_action="Select exactly two scenes (pre- and post-event) to compare.",
            )

    elif task == TaskType.FUSION:
        if not (inventory.has_optical and inventory.has_sar):
            return VetoDecision(
                reason_code=VetoReasonCode.CROSS_MODAL_PAIR_MISSING,
                message="Cross-modal fusion requires both Optical and SAR imagery.",
                suggested_action=(
                    "Upload a co-registered pair containing at least one Optical and one SAR scene."
                ),
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
                suggested_action=(
                    "Provide a single image, or select bi-temporal / cross-modal workflows."
                ),
            )

    elif task == TaskType.ARCHIVE_SEARCH_BONUS:
        # If enabled in registry, archive search accepts 0 or more reference rasters
        pass

    return None
