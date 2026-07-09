"""Shared data structures for swarm optimization.

Algorithm-agnostic models used by all swarm algorithms.
No references to ACO, BCO, PSO, or E³-Hybrid.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Mapping

from e3hybrid.network.types import EdgeId, NodeId

if TYPE_CHECKING:
    from e3hybrid.routing.cost import RouteCost


@dataclass(frozen=True, slots=True)
class Solution:
    """Base representation of a candidate route in swarm optimization.

    Algorithm-agnostic. ACO, BCO, and PSO all produce Solutions that
    are evaluated and compared using the same fitness function.
    """

    node_sequence: tuple[NodeId, ...]
    edge_sequence: tuple[EdgeId, ...]
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.node_sequence) < 2:
            raise ValueError("node_sequence must have at least 2 nodes")
        if len(self.edge_sequence) != len(self.node_sequence) - 1:
            raise ValueError(
                "edge_sequence length must equal node_sequence length - 1"
            )

    @property
    def source_node(self) -> NodeId:
        return self.node_sequence[0]

    @property
    def destination_node(self) -> NodeId:
        return self.node_sequence[-1]

    @property
    def edge_count(self) -> int:
        return len(self.edge_sequence)


@dataclass(frozen=True, slots=True)
class CandidateSolution:
    """A candidate solution with its evaluated fitness score.

    Core evaluation unit across all swarm algorithms.
    """

    solution: Solution
    score: float
    cost_breakdown: "RouteCost | None" = None
    iteration_created: int = 0
    algorithm_specific: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.score < 0:
            raise ValueError("score must be non-negative")
        if self.iteration_created < 0:
            raise ValueError("iteration_created must be non-negative")


@dataclass(frozen=True, slots=True)
class OptimizationScore:
    """Fitness value with detailed breakdown for analysis."""

    total: float
    components: Mapping[str, float] = field(default_factory=dict)
    normalized: float = 0.0
    rank: int = 0

    def __post_init__(self) -> None:
        if self.rank < 0:
            raise ValueError("rank must be non-negative")


@dataclass(frozen=True, slots=True)
class SearchState:
    """Tracks optimization progress across iterations.

    Updated every iteration. Used for convergence detection
    and termination decisions.
    """

    iteration: int
    best_score: float
    previous_best_score: float
    no_improvement_count: int
    diversity: float
    elapsed_time_s: float

    def __post_init__(self) -> None:
        if self.iteration < 0:
            raise ValueError("iteration must be non-negative")
        if self.no_improvement_count < 0:
            raise ValueError("no_improvement_count must be non-negative")
        if self.elapsed_time_s < 0:
            raise ValueError("elapsed_time_s must be non-negative")


@dataclass(frozen=True, slots=True)
class Population:
    """Generic population container used by all swarm algorithms.

    ACO: population = ants
    BCO: population = bees (scouts + employed + onlookers)
    PSO: population = particles
    """

    individuals: tuple[CandidateSolution, ...]
    diversity: float = 0.0
    iteration: int = 0

    def __post_init__(self) -> None:
        if self.iteration < 0:
            raise ValueError("iteration must be non-negative")

    @property
    def size(self) -> int:
        return len(self.individuals)

    @property
    def best(self) -> CandidateSolution | None:
        if not self.individuals:
            return None
        return min(self.individuals, key=lambda c: c.score)

    @property
    def average_score(self) -> float:
        if not self.individuals:
            return 0.0
        return sum(c.score for c in self.individuals) / len(self.individuals)

    @property
    def worst_score(self) -> float:
        if not self.individuals:
            return 0.0
        return max(c.score for c in self.individuals)
