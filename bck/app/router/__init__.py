"""SatQuery AI Router module: intent classification, feasibility veto, and dispatch planning."""

from app.router.classifier import classify_intent
from app.router.inventory import extract_inventory
from app.router.planner import build_dispatch_plan
from app.router.router import create_router_trace_step, route, router_trace_params
from app.router.runtime import RouterIntent, route_request
from app.router.schemas import (
    DispatchPlan,
    InputInventory,
    IntentClassification,
    RouterDecision,
    TaskType,
    VetoDecision,
    VetoReasonCode,
)
from app.router.veto import DEFAULT_REGISTRY_CAPABILITIES, evaluate_veto

__all__ = [
    "DEFAULT_REGISTRY_CAPABILITIES",
    "DispatchPlan",
    "InputInventory",
    "IntentClassification",
    "RouterDecision",
    "RouterIntent",
    "TaskType",
    "VetoDecision",
    "VetoReasonCode",
    "build_dispatch_plan",
    "classify_intent",
    "create_router_trace_step",
    "evaluate_veto",
    "extract_inventory",
    "route",
    "route_request",
    "router_trace_params",
]
