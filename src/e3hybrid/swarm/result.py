"""SwarmResult — immutable result of a swarm optimization run."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from e3hybrid.routing.candidate import RouteCandidate
    from e3hybrid.swarm.statistics import IterationStatistics, SwarmStatistics


@dataclass(frozen=True, slots=True)
class SwarmResult:
    """Result of a swarm optimization run.

    Compatible with the existing RoutingResult through SwarmToRoutingAdapter.
    The best_solution is always a valid RouteCandidate.

    Parameters
    ----------
    best_solution:
        The best route candidate found during optimization.
    candidates:
        All route candidates generated (may include alternatives).
    statistics:
        Aggregate optimization statistics.
    iterations:
        Per-iteration statistics for analysis and convergence plotting.
    success:
        Whether optimization completed successfully.
    failure_reason:
        Human-readable failure explanation (or None if success).
    """

    best_solution: "RouteCandidate"
    candidates: tuple["RouteCandidate", ...] = field(default_factory=tuple)
    statistics: "SwarmStatistics" = field(default_factory=lambda: _empty_statistics())  # type: ignore
    iterations: tuple["IterationStatistics", ...] = field(default_factory=tuple)
    success: bool = True
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if self.success and self.failure_reason is not None:
            raise ValueError("success=True requires failure_reason=None")
        if not self.success and self.failure_reason is None:
            raise ValueError("success=False requires failure_reason")


def _empty_statistics():
    """Create default empty SwarmStatistics."""
    from e3hybrid.swarm.statistics import SwarmStatistics

    return SwarmStatistics(
        total_iterations=0,
        total_runtime_s=0.0,
        best_score=0.0,
        average_score=0.0,
        worst_score=0.0,
        convergence_iteration=None,
        candidate_count=0,
        solutions_evaluated=0,
    )
