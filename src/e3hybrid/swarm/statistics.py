"""SwarmStatistics and IterationStatistics — aggregate and per-iteration metrics."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class IterationStatistics:
    """Per-iteration metrics for logging and analysis.

    Collected by the swarm lifecycle after each iteration.
    """

    iteration: int
    best_score: float
    average_score: float
    midrange_score: float
    worst_score: float
    std_dev: float
    diversity: float
    best_solution_changed: bool
    runtime_s: float

    def __post_init__(self) -> None:
        if self.iteration < 0:
            raise ValueError("iteration must be non-negative")
        if self.runtime_s < 0:
            raise ValueError("runtime_s must be non-negative")


@dataclass(frozen=True, slots=True)
class SwarmStatistics:
    """Aggregate statistics for a complete swarm optimization run.

    Computed from iteration-level data after optimization completes.
    """

    total_iterations: int
    total_runtime_s: float
    best_score: float
    average_score: float
    worst_score: float
    convergence_iteration: int | None
    candidate_count: int
    solutions_evaluated: int
    diversity_history: tuple[float, ...] = field(default_factory=tuple)
    score_history: tuple[float, ...] = field(default_factory=tuple)
    termination_reason: str = ""

    def __post_init__(self) -> None:
        if self.total_iterations < 0:
            raise ValueError("total_iterations must be non-negative")
        if self.total_runtime_s < 0:
            raise ValueError("total_runtime_s must be non-negative")
        if self.solutions_evaluated < 0:
            raise ValueError("solutions_evaluated must be non-negative")
        if self.convergence_iteration is not None and self.convergence_iteration < 0:
            raise ValueError("convergence_iteration must be non-negative")
