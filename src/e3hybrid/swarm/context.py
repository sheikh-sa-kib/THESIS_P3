"""SwarmContext — immutable context for swarm optimization."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from e3hybrid.network.graph import DirectedGraph
    from e3hybrid.routing.cost_calculator import CostWeights, CompositeCostCalculator
    from e3hybrid.routing.request import RoutingRequest


@dataclass(frozen=True, slots=True)
class SwarmContext:
    """Immutable context provided to every swarm optimization.

    Contains all information needed for optimization without allowing
    modification. Analogous to RoutingContext for routing algorithms.

    Parameters
    ----------
    cost_weights:
        Weights for cost components used in fitness evaluation.
    config:
        Algorithm-agnostic swarm configuration.
    random_seed:
        Base seed for deterministic random number generation.
    routing_request:
        The routing request being solved.
    sim_time_s:
        Current simulation time in seconds.
    graph:
        Read-only access to the full directed graph (never modified).
    cost_calculator:
        Cost calculator for edge cost evaluation (never modified).
    """

    cost_weights: "CostWeights"
    config: "SwarmConfig"  # type: ignore[name-defined]
    random_seed: int
    routing_request: "RoutingRequest"
    sim_time_s: float
    graph: "DirectedGraph | None" = None
    cost_calculator: "CompositeCostCalculator | None" = None

    def __post_init__(self) -> None:
        if self.random_seed < 0:
            raise ValueError("random_seed must be non-negative")
        if self.sim_time_s < 0:
            raise ValueError("sim_time_s must be non-negative")


# Import at bottom to resolve forward reference
from e3hybrid.swarm.config import SwarmConfig  # noqa: E402, F401
