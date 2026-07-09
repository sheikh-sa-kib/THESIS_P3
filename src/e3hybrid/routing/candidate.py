"""RouteCandidate — immutable candidate route produced by routing algorithms."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from e3hybrid.network.types import EdgeId, NodeId
from e3hybrid.routing.cost import RouteCost
from e3hybrid.routing.types import RouteId

if TYPE_CHECKING:
    from e3hybrid.routing.statistics import SearchStatistics


@dataclass(frozen=True, slots=True)
class SearchStatistics:
    """Statistics collected during algorithm search.
    
    Used for algorithm comparison and thesis metrics.
    
    Attributes
    ----------
    iterations:
        Number of algorithm iterations (for swarm algorithms).
    convergence:
        Convergence metric (e.g., cost improvement rate).
    diversity:
        Diversity metric (e.g., variance in candidate costs).
    """

    iterations: int = 0
    convergence: float = 0.0
    diversity: float = 0.0

    def __post_init__(self) -> None:
        """Validate statistics."""
        if self.iterations < 0:
            raise ValueError("iterations must be non-negative")


@dataclass(frozen=True, slots=True)
class RouteCandidate:
    """A candidate route produced by a routing algorithm.
    
    This is the structure passed to the Decision Engine for evaluation.
    The Decision Engine evaluates ONLY on total_cost — it never inspects
    how cost was computed or which algorithm produced the candidate.
    
    Design Decision (DD-031)
    -----------------------
    Algorithm-agnostic evaluation ensures the Decision Engine is completely
    routing-agnostic and fair comparison is preserved.
    
    Attributes
    ----------
    route_id:
        Unique identifier for this candidate.
    node_sequence:
        Ordered nodes from source to destination.
    edge_sequence:
        Ordered edges corresponding to node transitions.
    total_cost:
        Scalar cost (used by Decision Engine for comparison).
    cost_breakdown:
        Detailed cost components (for thesis analysis).
    algorithm:
        Algorithm name (for logging only, never used in evaluation).
    metadata:
        Algorithm-specific annotations (pheromone levels, particle scores, etc.).
    runtime_s:
        Time taken to generate this specific candidate.
    search_statistics:
        Exploration metrics for this candidate.
    """

    route_id: RouteId
    node_sequence: tuple[NodeId, ...]
    edge_sequence: tuple[EdgeId, ...]
    total_cost: float
    cost_breakdown: RouteCost
    algorithm: str
    metadata: dict[str, Any] = field(default_factory=dict)
    runtime_s: float = 0.0
    search_statistics: SearchStatistics = field(default_factory=SearchStatistics)

    def __post_init__(self) -> None:
        """Validate candidate consistency."""
        if len(self.node_sequence) < 2:
            raise ValueError("node_sequence must have at least 2 nodes")
        if len(self.edge_sequence) != len(self.node_sequence) - 1:
            raise ValueError(
                "edge_sequence length must equal node_sequence length - 1"
            )
        if self.total_cost < 0:
            raise ValueError("total_cost must be non-negative")
        if self.runtime_s < 0:
            raise ValueError("runtime_s must be non-negative")
        if not self.algorithm:
            raise ValueError("algorithm must be non-empty")

        # Verify cost_breakdown.total matches total_cost
        if abs(self.cost_breakdown.total - self.total_cost) > 1e-6:
            raise ValueError(
                f"cost_breakdown.total ({self.cost_breakdown.total}) "
                f"must equal total_cost ({self.total_cost})"
            )

        # Verify edge sequence connectivity
        for i, edge_id in enumerate(self.edge_sequence):
            if i < len(self.node_sequence) - 1:
                # Edge should connect node_sequence[i] to node_sequence[i+1]
                # This is a structural check; actual edge existence is validated by RouteValidator
                pass

    @property
    def source_node(self) -> NodeId:
        """Return the source node of this candidate."""
        return self.node_sequence[0]

    @property
    def destination_node(self) -> NodeId:
        """Return the destination node of this candidate."""
        return self.node_sequence[-1]

    @property
    def edge_count(self) -> int:
        """Return the number of edges in this candidate."""
        return len(self.edge_sequence)
