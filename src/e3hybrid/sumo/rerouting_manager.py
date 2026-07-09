"""SumoReroutingManager — schedules and executes rerouting decisions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from e3hybrid.network.types import EdgeId, NodeId

if TYPE_CHECKING:
    from e3hybrid.network.graph import DirectedGraph
    from e3hybrid.routing.protocol import RoutingAlgorithm
    from e3hybrid.routing.request import RoutingRequest
    from e3hybrid.sumo.config import SumoConfig
    from e3hybrid.sumo.connection import SumoTraciConnection


class SumoReroutingManager:
    """Manages rerouting decisions and route updates.

    Decoupled from the simulation loop so it can be tested independently
    with mock graph states.

    Parameters
    ----------
    connection:
        The TraCI connection for applying routes.
    config:
        SUMO configuration (reroute interval, etc.).
    algorithm:
        The routing algorithm used for all reroute computations.
    vehicle_ids:
        The list of vehicle IDs managed by this manager.
    """

    def __init__(
        self,
        connection: SumoTraciConnection,
        config: SumoConfig,
        algorithm: RoutingAlgorithm,
        vehicle_ids: list[str],
    ) -> None:
        self._connection = connection
        self._config = config
        self._algorithm = algorithm
        self._vehicle_ids = list(vehicle_ids)
        self._reroute_count = 0

    @property
    def algorithm(self) -> RoutingAlgorithm:
        return self._algorithm

    @property
    def reroute_count(self) -> int:
        return self._reroute_count

    @property
    def vehicle_ids(self) -> list[str]:
        return list(self._vehicle_ids)

    def should_reroute(self, step_count: int) -> bool:
        """Check if rerouting should occur based on the configured interval.

        Returns True when *step_count* is a multiple of the reroute interval,
        or when there are active emergency vehicles.
        """
        if self._config.reroute_interval_steps <= 0:
            return False
        return step_count > 0 and step_count % self._config.reroute_interval_steps == 0

    def compute_reroute(
        self,
        vehicle_id: str,
        current_edge_id: str,
        destination_node_id: NodeId,
        graph_snapshot: DirectedGraph,
    ) -> list[str] | None:
        """Compute a new route for a single vehicle.

        Parameters
        ----------
        vehicle_id:
            The SUMO vehicle ID.
        current_edge_id:
            The SUMO edge ID the vehicle is currently on.
        destination_node_id:
            The target node ID for the vehicle.
        graph_snapshot:
            A snapshot of the current graph with up-to-date states.

        Returns
        -------
        list[str] | None
            Edge ID sequence for the new route, or None if no route found.
        """
        current_edge = graph_snapshot.get_edge(EdgeId(current_edge_id))
        source_nid = current_edge.target

        if source_nid == destination_node_id:
            return None

        from e3hybrid.routing.request import RoutingRequest
        from e3hybrid.vehicle.types import VehicleId

        request = RoutingRequest(
            source_node=source_nid,
            destination_node=destination_node_id,
            vehicle_id=VehicleId(vehicle_id),
            vehicle_constraints={},
            battery_state={},
            max_candidates=1,
            timeout_s=30.0,
            metadata={"reroute": True},
        )

        result = self._algorithm.compute_route(request, graph=graph_snapshot)

        if not result.success or result.primary_route is None:
            return None

        return [current_edge_id] + [str(eid) for eid in result.primary_route.edge_sequence]

    def compute_reroutes(
        self,
        graph_snapshot: DirectedGraph,
        vehicles_with_destinations: dict[str, NodeId] | None = None,
    ) -> list[tuple[str, list[str]]]:
        """Compute routes for all vehicles that need rerouting.

        Parameters
        ----------
        graph_snapshot:
            A snapshot of the current graph with up-to-date states.
        vehicles_with_destinations:
            Optional mapping of vehicle_id -> destination_node_id.
            If None, queries destinations from SUMO via TraCI.

        Returns
        -------
        list[tuple[str, list[str]]]
            List of (vehicle_id, new_edge_sequence) pairs.
        """
        conn = self._connection
        results: list[tuple[str, list[str]]] = []

        for veh_id in self._vehicle_ids:
            try:
                current_edge = conn.get_vehicle_position(veh_id)[2]
                if vehicles_with_destinations is not None and veh_id in vehicles_with_destinations:
                    dest = vehicles_with_destinations[veh_id]
                else:
                    route = conn.get_vehicle_route(veh_id)
                    if not route:
                        continue
                    last_edge = graph_snapshot.get_edge(EdgeId(route[-1]))
                    dest = last_edge.target
            except Exception:
                continue

            new_route = self.compute_reroute(veh_id, current_edge, dest, graph_snapshot)
            if new_route and len(new_route) > 1:
                results.append((veh_id, new_route))

        return results

    def apply_reroute(self, vehicle_id: str, edge_ids: list[str]) -> None:
        """Set the vehicle's route in SUMO."""
        self._connection.set_vehicle_route(vehicle_id, edge_ids)
        self._reroute_count += 1

    def apply_reroutes(self, reroutes: list[tuple[str, list[str]]]) -> None:
        """Apply multiple reroutes in batch."""
        for veh_id, edge_seq in reroutes:
            self.apply_reroute(veh_id, edge_seq)