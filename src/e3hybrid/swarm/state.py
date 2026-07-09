"""SwarmState — immutable snapshot of optimization state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from e3hybrid.swarm.models import CandidateSolution, Population


@dataclass(frozen=True, slots=True)
class SwarmState:
    """Snapshot of swarm optimization state at a given iteration.

    Immutable for deterministic replay and auditability.

    Parameters
    ----------
    iteration:
        Current iteration number (0-indexed).
    population:
        Current population of candidate solutions.
    best_solution:
        Best solution found so far (or None if no solutions evaluated).
    internal_state:
        Algorithm-specific state data (pheromones, velocities, etc.).
        Generic mapping to keep the framework algorithm-agnostic.
    """

    iteration: int
    population: Population
    best_solution: CandidateSolution | None = None
    internal_state: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.iteration < 0:
            raise ValueError("iteration must be non-negative")
