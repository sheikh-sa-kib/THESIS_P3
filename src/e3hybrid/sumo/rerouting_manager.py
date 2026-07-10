"""SumoReroutingManager — schedules and executes rerouting decisions.

Every reroute is **validated** against SUMO lane-level connectivity
before being installed.  Invalid routes are either **repaired** via
SUMO's own router (``simulation.findRoute``) or silently rejected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from e3hybrid.network.types import EdgeId, NodeId

if TYPE_CHECKING:
    from e3hybrid.network.graph import DirectedGraph
    from e3hybrid.routing.protocol import RoutingAlgorithm
    from e3hybrid.sumo.config import SumoConfig
    from e3hybrid.sumo.connection import SumoTraciConnection


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

@dataclass
class RerouteLogEntry:
    """A single reroute attempt, whether successful, repaired, or rejected."""

    vehicle_id: str
    current_edge: str
    destination_node: NodeId
    algo_route: list[str]                         # edges the algorithm produced
    attempted_route: list[str]                    # edges actually sent to TraCI
    sumo_success: bool                            # setRoute succeeded
    sumo_error: str = ""
    was_repaired: bool = False
    repair_attempted: bool = False
    repair_succeeded: bool = False
    repair_route: list[str] = field(default_factory=list)
    invalid_pair_index: int = -1                  # first invalid (i, i+1)
    invalid_from: str = ""
    invalid_to: str = ""


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class SumoReroutingManager:
    """Manages rerouting decisions and route updates.

    Every route is validated against SUMO lane-level connectivity before
    installation.  If validation fails the route is repaired via SUMO's
    internal router; if repair also fails the reroute is skipped.

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
        self._repair_count = 0
        self._repair_fail_count = 0
        self._reject_count = 0
        self._log: list[RerouteLogEntry] = []

    # -- public properties ------------------------------------------------

    @property
    def algorithm(self) -> RoutingAlgorithm:
        return self._algorithm

    @property
    def reroute_count(self) -> int:
        return self._reroute_count

    @property
    def repair_count(self) -> int:
        """Number of routes that were repaired before installation."""
        return self._repair_count

    @property
    def repair_fail_count(self) -> int:
        """Number of repair attempts that themselves failed."""
        return self._repair_fail_count

    @property
    def reject_count(self) -> int:
        """Number of reroute attempts rejected (no valid route found)."""
        return self._reject_count

    @property
    def vehicle_ids(self) -> list[str]:
        return list(self._vehicle_ids)

    @property
    def log(self) -> list[RerouteLogEntry]:
        return list(self._log)

    # -- scheduling --------------------------------------------------------

    def should_reroute(self, step_count: int) -> bool:
        """Check if rerouting should occur based on the configured interval.

        Returns True when *step_count* is a multiple of the reroute interval,
        or when there are active emergency vehicles.
        """
        if self._config.reroute_interval_steps <= 0:
            return False
        return step_count > 0 and step_count % self._config.reroute_interval_steps == 0

    # -- core: compute + validate + repair ---------------------------------

    def compute_reroute(
        self,
        vehicle_id: str,
        current_edge_id: str,
        destination_node_id: NodeId,
        graph_snapshot: DirectedGraph,
        *,
        known_dest_edge: str | None = None,
    ) -> list[str] | None:
        """Compute a new route for a single vehicle.

        Parameters
        ----------
        vehicle_id:
            SUMO vehicle ID.
        current_edge_id:
            Edge the vehicle occupies.
        destination_node_id:
            Target junction node.
        graph_snapshot:
            Current graph state.
        known_dest_edge:
            Optional edge ID known to terminate at the destination node.
            Used as the target for ``simulation.findRoute`` during repair.

        Returns
        -------
        list[str] | None
            Validated edge sequence (first element = current_edge_id),
            or None if no usable route found.
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
            metadata={"reroute": True, "source_edge_id": current_edge_id},
        )

        result = self._algorithm.compute_route(request, graph=graph_snapshot)

        if not result.success or result.primary_route is None:
            return None

        algo_edges = [str(eid) for eid in result.primary_route.edge_sequence]
        full_route = [current_edge_id] + algo_edges

        # ---------------------------------------------------------------
        # Validation: every consecutive pair must have a SUMO lane-level
        # connection.
        # ---------------------------------------------------------------
        valid, idx, fr, to = self._validate_edges(full_route)

        if valid:
            entry = RerouteLogEntry(
                vehicle_id=vehicle_id,
                current_edge=current_edge_id,
                destination_node=destination_node_id,
                algo_route=algo_edges,
                attempted_route=full_route,
                sumo_success=True,
            )
            self._log.append(entry)
            self._reroute_count += 1
            return full_route

        # ---------------------------------------------------------------
        # Repair: first invalid pair at index idx
        # ---------------------------------------------------------------
        entry = RerouteLogEntry(
            vehicle_id=vehicle_id,
            current_edge=current_edge_id,
            destination_node=destination_node_id,
            algo_route=algo_edges,
            attempted_route=full_route,
            sumo_success=False,
            sumo_error=f"No lane connection: {fr} -> {to}",
            invalid_pair_index=idx,
            invalid_from=fr,
            invalid_to=to,
        )

        # Repair strategy: use SUMO's own router for the full route.
        repaired = self._repair_via_sumo(
            vehicle_id, current_edge_id, destination_node_id,
            graph_snapshot, known_dest_edge=known_dest_edge,
        )
        entry.repair_attempted = True

        if repaired is not None:
            entry.was_repaired = True
            entry.repair_succeeded = True
            entry.repair_route = repaired
            entry.attempted_route = repaired
            entry.sumo_success = True
            self._log.append(entry)
            self._reroute_count += 1
            self._repair_count += 1
            return repaired

        entry.was_repaired = True
        entry.repair_succeeded = False
        self._log.append(entry)
        self._repair_fail_count += 1
        self._reject_count += 1
        return None

    # -- validation --------------------------------------------------------

    def _validate_edges(
        self, edge_ids: list[str],
    ) -> tuple[bool, int, str, str]:
        """Check every consecutive pair ``(i, i+1)``.

        Returns ``(True, -1, "", "")`` if all pairs are valid.
        Returns ``(False, i, edge_ids[i], edge_ids[i+1])`` on the first
        invalid pair.
        """
        conn = self._connection
        for i in range(len(edge_ids) - 1):
            e1, e2 = edge_ids[i], edge_ids[i + 1]

            # Skip checks for internal edges (SUMO handles these).
            if e1.startswith(":") or e2.startswith(":"):
                continue

            if not conn.has_lane_connection(e1, e2):
                return False, i, e1, e2
        return True, -1, "", ""

    # -- repair -----------------------------------------------------------

    def _repair_via_sumo(
        self,
        vehicle_id: str,
        current_edge: str,
        destination_node: NodeId,
        graph_snapshot: DirectedGraph,
        *,
        known_dest_edge: str | None = None,
    ) -> list[str] | None:
        """Compute a legal route via SUMO's internal router.

        Returns the full edge sequence including *current_edge*, or
        None if no route exists.
        """
        conn = self._connection

        # Determine the destination edge to pass to findRoute.
        if known_dest_edge is not None:
            dest_edge = known_dest_edge
        else:
            # Fall back to the last edge of the vehicle's current SUMO route.
            try:
                route = conn.get_vehicle_route(vehicle_id)
            except Exception:
                route = []
            if not route:
                # Search the graph for any edge terminating at destination_node.
                dest_edge = self._find_dest_edge(destination_node, graph_snapshot)
                if dest_edge is None:
                    return None
            else:
                dest_edge = route[-1]

        if current_edge == dest_edge:
            return None

        sumo_route = conn.find_route(current_edge, dest_edge)
        if len(sumo_route) < 2:
            return None

        return sumo_route

    @staticmethod
    def _find_dest_edge(
        destination_node: NodeId, graph: DirectedGraph,
    ) -> str | None:
        """Return any edge whose target equals *destination_node*."""
        for e in graph.edges():
            if e.target == destination_node:
                return str(e.edge_id)
        return None

    # -- batch operations -------------------------------------------------

    def compute_reroutes(
        self,
        graph_snapshot: DirectedGraph,
        vehicles_with_destinations: dict[str, NodeId] | None = None,
    ) -> list[tuple[str, list[str]]]:
        """Compute routes for all vehicles that need rerouting.

        Returns
        -------
        list[tuple[str, list[str]]]
            List of (vehicle_id, new_edge_sequence) pairs, all validated.
        """
        conn = self._connection
        results: list[tuple[str, list[str]]] = []

        for veh_id in self._vehicle_ids:
            try:
                current_edge = conn.get_vehicle_position(veh_id)[2]
                if vehicles_with_destinations is not None and veh_id in vehicles_with_destinations:
                    dest = vehicles_with_destinations[veh_id]
                    known_dest = None
                else:
                    route = conn.get_vehicle_route(veh_id)
                    if not route:
                        continue
                    last_edge = graph_snapshot.get_edge(EdgeId(route[-1]))
                    dest = last_edge.target
                    known_dest = route[-1]
            except Exception:
                continue

            if not current_edge:
                continue

            new_route = self.compute_reroute(
                veh_id, current_edge, dest, graph_snapshot,
                known_dest_edge=known_dest,
            )
            if new_route and len(new_route) > 1:
                results.append((veh_id, new_route))

        return results

    def apply_reroute(self, vehicle_id: str, edge_ids: list[str]) -> None:
        """Set the vehicle's route in SUMO.

        If ``edge_ids`` were already validated by ``compute_reroute`` this
        call should never fail; the try/except is a final safety net.
        """
        try:
            self._connection.set_vehicle_route(vehicle_id, edge_ids)
        except Exception as exc:
            msg = str(exc)
            # This should not happen after pre-validation, but we log it
            # to detect any remaining gaps.
            entry = RerouteLogEntry(
                vehicle_id=vehicle_id,
                current_edge=edge_ids[0] if edge_ids else "",
                destination_node=NodeId("?"),
                algo_route=list(edge_ids),
                attempted_route=list(edge_ids),
                sumo_success=False,
                sumo_error=msg,
            )
            self._log.append(entry)
            self._reject_count += 1

    def apply_reroutes(self, reroutes: list[tuple[str, list[str]]]) -> None:
        """Apply multiple reroutes in batch."""
        for veh_id, edge_seq in reroutes:
            self.apply_reroute(veh_id, edge_seq)
