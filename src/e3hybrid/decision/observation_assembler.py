"""ObservationAssembler — builds VehicleObservation once per simulation tick.

Design (Decision 1 — approved)
-------------------------------
The Decision Engine evaluates exactly ONCE per simulation tick.
The ObservationAssembler is called by the simulation core to build a
VehicleObservation snapshot.  The DE never queries subsystems directly.

Design (Decision 2 — approved)
-------------------------------
The DE never receives the full DirectedGraph.  This assembler builds a
GraphSnapshot limited to the vehicle's current edge and configurable
neighbourhood depth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from e3hybrid.decision.config import DecisionConfig
from e3hybrid.decision.observation import (
    BatterySnapshot,
    EdgeSnapshot,
    GraphSnapshot,
    RouteSnapshot,
    VehicleObservation,
)
from e3hybrid.network.types import EdgeId, NodeId
from e3hybrid.vehicle.types import VehicleId

if TYPE_CHECKING:
    from e3hybrid.network.graph import DirectedGraph
    from e3hybrid.vehicle.battery import Battery
    from e3hybrid.vehicle.entity import ElectricVehicle


@dataclass(frozen=True, slots=True)
class ObservationAssembler:
    """Assembles VehicleObservation snapshots from subsystem state.

    The assembler is the ONLY bridge between the Decision Engine and the
    simulation subsystems.  Policies never import graph, vehicle, or emergency
    modules directly.
    """

    config: DecisionConfig

    def assemble(
        self,
        vehicle: ElectricVehicle,
        graph: DirectedGraph,
        route_candidate_source: object,  # RouteCandidateSource protocol
        sim_time_s: float,
        active_events: tuple[object, ...],  # tuple[EmergencyEvent, ...]
        inbox_messages: tuple[object, ...],  # tuple[Message, ...]
    ) -> VehicleObservation:
        """Build a complete VehicleObservation for one evaluation cycle.

        Parameters
        ----------
        vehicle:
            The EV being evaluated.
        graph:
            The full road-network graph (used only to build GraphSnapshot).
        route_candidate_source:
            Source for routing candidates (e.g., NullRouteCandidateSource in Phase 6).
        sim_time_s:
            Current simulation clock.
        active_events:
            All emergency events currently active in the simulation.
        inbox_messages:
            Messages drained from the vehicle's Receiver inbox this tick.

        Returns
        -------
        VehicleObservation
            Immutable snapshot containing all information the DE may use.
        """
        # Build battery snapshot.
        battery = self._build_battery_snapshot(vehicle.battery)

        # Build graph snapshot (neighbourhood-scoped).
        graph_snapshot = self._build_graph_snapshot(
            graph, vehicle.state.current_edge_id, self.config.neighbourhood_depth
        )

        # Build route snapshot.
        current_route = self._build_route_snapshot(vehicle, graph_snapshot)

        # Request routing candidates.
        routing_candidates = self._get_routing_candidates(
            route_candidate_source,
            vehicle.vehicle_id,
            vehicle.state.current_node_id,
            vehicle.destination_node_id,
            self.config.max_candidates,
        )

        return VehicleObservation(
            vehicle_id=vehicle.vehicle_id,
            sim_time_s=sim_time_s,
            vehicle_state=vehicle.state,
            battery=battery,
            constraints=vehicle.constraints,
            graph_snapshot=graph_snapshot,
            routing_candidates=routing_candidates,
            current_route=current_route,
            inbox_messages=inbox_messages,
            active_events=active_events,
        )

    def _build_battery_snapshot(self, battery: object) -> BatterySnapshot:  # Battery protocol
        """Extract battery state for observation."""
        return BatterySnapshot(
            soc_kwh=battery.soc_kwh,
            capacity_kwh=battery.capacity_kwh,
            soc_fraction=battery.soc_fraction,
        )

    def _build_graph_snapshot(
        self,
        graph: DirectedGraph,
        current_edge_id: EdgeId | None,
        neighbourhood_depth: int,
    ) -> GraphSnapshot:
        """Build a neighbourhood-scoped graph view.

        Only the current edge and edges within N hops are included.
        The full DirectedGraph is never passed to the Decision Engine.
        """
        if current_edge_id is None:
            # Vehicle is stationary — no current edge.
            return GraphSnapshot(
                current_edge=None,
                neighbour_edges=(),
                blocked_edge_ids=frozenset(),
            )

        # Get current edge.
        current_edge = graph.get_edge(current_edge_id)
        if current_edge is None:
            return GraphSnapshot(
                current_edge=None,
                neighbour_edges=(),
                blocked_edge_ids=frozenset(),
            )

        # Build neighbour edges within depth.
        neighbour_edges = self._collect_neighbour_edges(
            graph, current_edge.target, neighbourhood_depth - 1
        )

        # Build current edge snapshot.
        current_snapshot = self._build_edge_snapshot(current_edge)

        # Build neighbour edge snapshots.
        neighbour_snapshots = tuple(
            self._build_edge_snapshot(graph.get_edge(eid))
            for eid in neighbour_edges
            if graph.get_edge(eid) is not None
        )

        # Collect blocked edge IDs.
        blocked_edge_ids = frozenset(
            eid
            for eid in [current_edge_id] + list(neighbour_edges)
            if graph.get_edge(eid) is not None and graph.get_edge(eid).is_blocked
        )

        return GraphSnapshot(
            current_edge=current_snapshot,
            neighbour_edges=neighbour_snapshots,
            blocked_edge_ids=blocked_edge_ids,
        )

    def _collect_neighbour_edges(
        self, graph: DirectedGraph, start_node: NodeId, depth: int
    ) -> tuple[EdgeId, ...]:
        """Collect edge IDs within N hops from a start node (BFS)."""
        if depth <= 0:
            return ()

        visited_nodes = {start_node}
        edge_ids: list[EdgeId] = []
        frontier = [start_node]

        for _ in range(depth):
            if not frontier:
                break
            next_frontier: list[NodeId] = []
            for node in frontier:
                for edge in graph.get_outgoing_edges(node):
                    if edge.target not in visited_nodes:
                        visited_nodes.add(edge.target)
                        edge_ids.append(edge.edge_id)
                        next_frontier.append(edge.target)
            frontier = next_frontier

        return tuple(edge_ids)

    def _build_edge_snapshot(self, edge: object) -> EdgeSnapshot:  # Edge protocol
        """Build EdgeSnapshot from an Edge object."""
        return EdgeSnapshot(
            edge_id=edge.edge_id,
            source=edge.source,
            target=edge.target,
            length_m=edge.length_m,
            speed_limit_mps=edge.speed_limit_mps,
            is_blocked=edge.is_blocked,
            congestion_factor=edge.congestion_factor,
            hazard_penalty_s=edge.hazard_penalty_s,
            emergency_penalty_s=edge.emergency_penalty_s,
            communication_penalty_s=edge.communication_penalty_s,
            estimated_cost=edge.estimated_cost,
        )

    def _build_route_snapshot(
        self, vehicle: ElectricVehicle, graph_snapshot: GraphSnapshot
    ) -> RouteSnapshot | None:
        """Build route snapshot from vehicle's current route."""
        if not vehicle.route:
            return None

        remaining_edge_ids = vehicle.route.remaining_edge_ids
        destination_node = vehicle.route.destination_node

        # Check if any remaining edge is blocked.
        has_blocked_edge = any(
            graph_snapshot.is_blocked(eid) for eid in remaining_edge_ids
        )

        # Estimate remaining cost (sum of edge costs in snapshot).
        estimated_cost = 0.0
        for eid in remaining_edge_ids:
            edge = graph_snapshot.get_edge(eid)
            if edge is not None:
                estimated_cost += edge.estimated_cost

        return RouteSnapshot(
            route_id=vehicle.route.route_id,
            remaining_edge_ids=remaining_edge_ids,
            destination_node=destination_node,
            estimated_remaining_cost=estimated_cost,
            has_blocked_edge=has_blocked_edge,
        )

    def _get_routing_candidates(
        self,
        source: object,  # RouteCandidateSource protocol
        vehicle_id: VehicleId,
        origin: NodeId,
        destination: NodeId,
        max_candidates: int,
    ) -> tuple[object, ...]:  # tuple[RouteCandidate, ...]
        """Request routing candidates from the source."""
        try:
            return source.get_candidates(vehicle_id, origin, destination, max_candidates)
        except Exception:
            # Phase 6: NullRouteCandidateSource returns empty tuple.
            # Future phases: handle routing errors gracefully.
            return ()
