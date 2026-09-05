"""Cognitive dispatch router orchestrating classification, inventory, veto, and planning."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.contracts import QueryRequest, TraceStep
from app.router.classifier import classify_intent
from app.router.inventory import extract_inventory
from app.router.planner import build_dispatch_plan
from app.router.schemas import RouterDecision, TaskType
from app.router.veto import evaluate_veto


def route(
    request: QueryRequest,
    registry_capabilities: dict[TaskType, bool] | None = None,
) -> RouterDecision:
    """Evaluate QueryRequest through deterministic router lifecycle.

    Lifecycle:
    1. Classify intent into closed TaskType.
    2. Extract structural input inventory.
    3. Evaluate deterministic veto gates (empty query, capability, inventory feasibility).
    4. If vetoed, return RouterDecision with typed VetoDecision.
    5. If feasible, return RouterDecision with immutable DispatchPlan for app.pipeline.
    """
    raw_query = request.query
    intent = classify_intent(raw_query)
    inventory = extract_inventory(request.images)

    veto = evaluate_veto(
        raw_query=raw_query,
        intent=intent,
        inventory=inventory,
        registry_capabilities=registry_capabilities,
    )

    if veto is not None:
        return RouterDecision(
            status="vetoed",
            intent=intent,
            veto=veto,
        )

    dispatch_plan = build_dispatch_plan(
        intent=intent,
        raw_query=raw_query,
        images=request.images,
        inventory=inventory,
    )

    return RouterDecision(
        status="dispatched",
        intent=intent,
        dispatch_plan=dispatch_plan,
    )


def router_trace_params(decision: RouterDecision) -> dict[str, Any]:
    """Generate auditable parameter dictionary for contracts.TraceStep.params."""
    if decision.is_dispatched and decision.dispatch_plan:
        return {
            "status": decision.status,
            "task_type": decision.intent.task_type.value,
            "tool_name": decision.dispatch_plan.tool_name,
            "image_bindings": decision.dispatch_plan.image_bindings,
        }

    return {
        "status": decision.status,
        "task_type": decision.intent.task_type.value,
        "veto_reason": decision.veto.reason_code.value if decision.veto else None,
        "veto_message": decision.veto.message if decision.veto else None,
        "suggested_action": decision.veto.suggested_action if decision.veto else None,
    }


def create_router_trace_step(
    decision: RouterDecision,
    started_at: datetime,
    completed_at: datetime | None = None,
) -> TraceStep:
    """Build a valid TraceStep contract representing the router execution hop."""
    return TraceStep(
        module="router",
        action="route",
        params=router_trace_params(decision),
        started_at=started_at,
        completed_at=completed_at,
    )
