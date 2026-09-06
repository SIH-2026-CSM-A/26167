"""Public runtime routing boundary for pipeline composition."""

from app.router.runtime import RouterDecision, RouterIntent, route_request

__all__ = ["RouterDecision", "RouterIntent", "route_request"]
