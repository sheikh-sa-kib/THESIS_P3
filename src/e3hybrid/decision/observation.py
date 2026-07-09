"""Observation model — immutable snapshot assembled once per simulation tick.

Design (Decision 1 — approved)
-------------------------------
The Decision Engine evaluates exactly ONCE per simulation tick.
The ObservationAssembler builds a VehicleObservation snapshot from the
current state of every subsystem.  The DE never queries subsystems directly.

Design (Decision 2 — approved)
-------------------------------
The DE never receives the full DirectedGraph.  It receives a GraphSnapshot
limited to the vehicle's current edge and configurable neighbourhood depth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from e3hybrid.emergency.event import EmergencyEvent
from e3hybrid.network.edge import MutableEdgeState
from e3hybrid.network.types import EdgeId, NodeId
from e3hybrid.vehicle.state import VehicleConstraints, VehicleState
from e3hybrid.vehicle.types import VehicleId


@dataclass(frozen=True, slots=True)
class BatterySnapshot:
    """Current battery state at observation time."""

    soc_kwh: float
    capacity_kwh: float
    soc_fraction: float


@dataclass(frozen=True, slots=True)
class EdgeSnapshot:
    """Minimal read-only view of one edge for decision making.

    The full Edge object is not included — only the fields relevant to
    deciding whether to reroute, slow down, or broadcast.
    """

    edge_id: EdgeId
    source: NodeId
    target: NodeId
    length_m: float
    speed_limit_mps: float
    is_blocked: bool
    congestion_factor: float
    hazard_penalty_s: float
    emergency_penalty_s: float
    communication_penalty_s: float
    estimated_cost: float            # from active CostProvider


@dataclass(frozen=True, slots=True)
class GraphSnapshot:
    """Neighbourhood-scoped graph view for one vehicle's decision cycle.

    Contains only the edges relevant to this vehicle's immediate decisions:
    the current edge and its N-hop neighbours (N configurable via DecisionConfig).

    The full DirectedGraph is never passed to the Decision Engine.

    Attributes
    ----------
    current_edge:
        The edge the vehicle is currently traversing.  None when stationary.
    neighbour_edges:
        Edges reachable within the configured neighbourhood depth.
    blocked_edge_ids:
        Set of edge IDs that are currently blocked within the snapshot.
        Pre-computed for O(1) lookup by policies.
    """

    current_edge: EdgeSnapshot | None
    neighbour_edges: tuple[EdgeSnapshot, ...]
    blocked_edge_ids: frozenset[EdgeId]

    def is_blocked(self, edge_id: EdgeId) -> bool:
        """Return True if the edge is blocked in this snapshot."""
        return edge_id in self.blocked_edge_ids

    def get_edge(self, edge_id: EdgeId) -> EdgeSnapshot | None:
        """Return the snapshot for an edge, or None if not in neighbourhood."""
        if self.current_edge and self.current_edge.edge_id == edge_id:
            return self.current_edge
        for edge in self.neighbour_edges:
            if edge.edge_id == edge_id:
                return edge
        return None


@dataclass(frozen=True, slots=True)
class RouteSnapshot:
    """Current planned route state at observation time."""

    route_id: str
    remaining_edge_ids: tuple[EdgeId, ...]
    destination_node: NodeId
    estimated_remaining_cost: float
    has_blocked_edge: bool           # pre-computed: True if any remaining edge is blocked


@dataclass(frozen=True, slots=True)
class VehicleObservation:
    """Immutable snapshot of all information the Decision Engine may use.

    Assembled once per simulation tick by the ObservationAssembler.
    The same observation always produces the same decision (determinism).

    Attributes
    ----------
    vehicle_id:
        Vehicle being evaluated.
    sim_time_s:
        Simulation clock at observation time.
    vehicle_state:
        Position, speed, acceleration, distance, elapsed time.
    battery:
        Compact battery snapshot (soc_kwh, capacity_kwh, soc_fraction).
    constraints:
        Operational limits (min/max SoC, max speed, max payload).
    graph_snapshot:
        Neighbourhood graph view — not the full DirectedGraph.
    current_route:
        Current planned route, or None if no route is set.
    routing_candidates:
        Candidate routes from the RouteCandidateSource.  May be empty in
        Phase 6.  Never pre-filtered (Decision 3).
    inbox_messages:
        All messages drained from the vehicle's Receiver inbox this tick.
    active_events:
        All emergency events currently active in the simulation.
    """

    vehicle_id: VehicleId
    sim_time_s: float
    vehicle_state: VehicleState
    battery: BatterySnapshot
    constraints: VehicleConstraints
    graph_snapshot: GraphSnapshot
    routing_candidates: tuple[Any, ...]  # tuple[RouteCandidate, ...] — avoids circular
    current_route: RouteSnapshot | None = None
    inbox_messages: tuple[Any, ...] = field(default_factory=tuple)
    active_events: tuple[Any, ...] = field(default_factory=tuple)
