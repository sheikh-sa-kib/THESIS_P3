"""Route and RouteSegment — immutable route representations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from e3hybrid.network.types import EdgeId, NodeId
from e3hybrid.routing.types import RouteId

if TYPE_CHECKING:
    from e3hybrid.routing.cost import RouteCost


@dataclass(frozen=True, slots=True)
class RouteSegment:
    """Immutable segment of a route (one edge with traversal metadata).
    
    Used for incremental rerouting and partial route updates.
    
    Attributes
    ----------
    edge_id:
        Edge identifier.
    source:
        Source node ID.
    target:
        Target node ID.
    distance_m:
        Physical length in meters.
    travel_time_s:
        Estimated travel time in seconds.
    energy_kwh:
        Estimated energy consumption in kWh.
    cost:
        Traversal cost (from CostProvider).
    """

    edge_id: EdgeId
    source: NodeId
    target: NodeId
    distance_m: float
    travel_time_s: float
    energy_kwh: float
    cost: float

    def __post_init__(self) -> None:
        """Validate segment parameters."""
        if self.distance_m < 0:
            raise ValueError("distance_m must be non-negative")
        if self.travel_time_s < 0:
            raise ValueError("travel_time_s must be non-negative")
        if self.energy_kwh < 0:
            raise ValueError("energy_kwh must be non-negative")
        if self.cost < 0:
            raise ValueError("cost must be non-negative")


@dataclass(frozen=True, slots=True)
class Route:
    """Immutable ordered sequence of edges from source to destination.
    
    The Route is the actual path. RouteCandidate wraps Route with metadata.
    
    Attributes
    ----------
    route_id:
        Unique route identifier.
    node_sequence:
        Ordered nodes from source to destination.
    edge_sequence:
        Ordered edges corresponding to node transitions.
    total_distance_m:
        Total physical distance in meters.
    estimated_travel_time_s:
        Total estimated travel time in seconds.
    estimated_energy_kwh:
        Total estimated energy consumption in kWh.
    """

    route_id: RouteId
    node_sequence: tuple[NodeId, ...]
    edge_sequence: tuple[EdgeId, ...]
    total_distance_m: float
    estimated_travel_time_s: float
    estimated_energy_kwh: float

    def __post_init__(self) -> None:
        """Validate route consistency."""
        if len(self.node_sequence) < 2:
            raise ValueError("node_sequence must have at least 2 nodes")
        if len(self.edge_sequence) != len(self.node_sequence) - 1:
            raise ValueError(
                "edge_sequence length must equal node_sequence length - 1"
            )
        if self.total_distance_m < 0:
            raise ValueError("total_distance_m must be non-negative")
        if self.estimated_travel_time_s < 0:
            raise ValueError("estimated_travel_time_s must be non-negative")
        if self.estimated_energy_kwh < 0:
            raise ValueError("estimated_energy_kwh must be non-negative")

    @property
    def source_node(self) -> NodeId:
        """Return the source node of this route."""
        return self.node_sequence[0]

    @property
    def destination_node(self) -> NodeId:
        """Return the destination node of this route."""
        return self.node_sequence[-1]

    @property
    def edge_count(self) -> int:
        """Return the number of edges in this route."""
        return len(self.edge_sequence)
