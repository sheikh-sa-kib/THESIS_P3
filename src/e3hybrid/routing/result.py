"""RoutingResult — immutable result returned by every routing algorithm."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from e3hybrid.routing.candidate import RouteCandidate
    from e3hybrid.routing.route import Route
    from e3hybrid.routing.statistics import RoutingStatistics


@dataclass(frozen=True, slots=True)
class RoutingResult:
    """Immutable result returned by every routing algorithm.
    
    All algorithms return exactly this structure. No algorithm-specific fields.
    
    Attributes
    ----------
    candidates:
        All generated candidates (may be empty if routing failed).
    primary_route:
        Best route (or None if failure).
    success:
        Whether routing succeeded.
    failure_reason:
        Human-readable failure explanation (or None if success).
    statistics:
        Exploration and performance metrics.
    runtime_s:
        Actual computation time in seconds.
    """

    candidates: tuple["RouteCandidate", ...]
    primary_route: "Route | None"
    success: bool
    failure_reason: str | None
    statistics: "RoutingStatistics"
    runtime_s: float

    def __post_init__(self) -> None:
        """Validate result consistency."""
        if self.success and self.primary_route is None:
            raise ValueError("success=True requires primary_route")
        if not self.success and self.primary_route is not None:
            raise ValueError("success=False requires primary_route=None")
        if self.success and self.failure_reason is not None:
            raise ValueError("success=True requires failure_reason=None")
        if not self.success and self.failure_reason is None:
            raise ValueError("success=False requires failure_reason")
        if self.runtime_s < 0:
            raise ValueError("runtime_s must be non-negative")
