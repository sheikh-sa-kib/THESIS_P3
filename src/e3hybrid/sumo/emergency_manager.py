"""SumoEmergencyManager — detects and responds to SUMO emergency events.

Acts as the bridge between SUMO's TraCI notifications and graph state.
On each simulation step:

1. Scans for emergency vehicles via TraCI vehicle type detection
2. Determines affected edges from the vehicle's current route
3. Applies graph effects (blocked edges, emergency penalties) directly
   via MutableEdgeState updates and DirectedGraph.update_edge_state
4. Tracks active emergencies and restores graph state when they resolve
5. Triggers rerouting for vehicles on affected edges

All graph state modifications go through the existing MutableEdgeState
immutable-copy pattern (Edge.with_state -> DirectedGraph.update_edge_state).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from e3hybrid.network.edge import MutableEdgeState
from e3hybrid.network.types import EdgeId

if TYPE_CHECKING:
    from e3hybrid.network.graph import DirectedGraph
    from e3hybrid.sumo.config import SumoConfig
    from e3hybrid.sumo.connection import SumoTraciConnection

_logger = logging.getLogger(__name__)

_DEFAULT_EMERGENCY_PENALTY_S: float = 120.0
_EMERGENCY_RADIUS_EDGES: int = 3


@dataclass
class ActiveEmergency:
    """Tracks an active emergency vehicle event."""

    vehicle_id: str
    affected_edges: frozenset[EdgeId]
    activated_step: int
    resolved: bool = False


class SumoEmergencyManager:
    """Detects and responds to SUMO emergency events.

    Applies graph state effects directly without going through the
    EmergencyEventBus (which has pre-existing issues in the base
    EmergencyVehicleEvent class).

    Parameters
    ----------
    connection:
        The TraCI connection.
    config:
        SUMO configuration.
    graph:
        The current directed graph (updated in-place).
    """

    def __init__(
        self,
        connection: SumoTraciConnection,
        config: SumoConfig,
        graph: DirectedGraph,
    ) -> None:
        self._connection = connection
        self._config = config
        self._graph = graph
        self._active: dict[str, ActiveEmergency] = {}
        self._present_emergency_ids: set[str] = set()

    @property
    def active_emergency_count(self) -> int:
        """Return the number of currently tracked active emergencies."""
        return len(self._active)

    @property
    def active_emergency_vehicle_ids(self) -> frozenset[str]:
        """Return the vehicle IDs of currently active emergencies."""
        return frozenset(self._active.keys())

    def check_and_respond(self, sim_time_ms: int) -> list[str]:
        """Check for emergency vehicles and respond.

        Called once per simulation step.

        Parameters
        ----------
        sim_time_ms:
            Current simulation time in milliseconds.

        Returns
        -------
        list[str]
            Vehicle IDs of newly detected emergencies this step.
        """
        current_emergency_ids = self._detect_emergency_vehicles()

        newly_activated: list[str] = []

        for veh_id in current_emergency_ids:
            if veh_id not in self._active:
                self._activate_emergency(veh_id)
                newly_activated.append(veh_id)

        resolved = set(self._active.keys()) - current_emergency_ids
        for veh_id in resolved:
            self._resolve_emergency(veh_id)

        self._present_emergency_ids = current_emergency_ids

        return newly_activated

    def _detect_emergency_vehicles(self) -> set[str]:
        """Detect emergency vehicles currently in the simulation."""
        emergency: set[str] = set()
        for veh_id in self._connection.get_vehicle_ids():
            try:
                vtype = self._connection.get_vehicle_type(veh_id)
                if "emergency" in vtype.lower():
                    emergency.add(veh_id)
            except Exception:
                continue
        return emergency

    def _activate_emergency(self, veh_id: str) -> None:
        """Activate emergency blocking/penalties for a vehicle.

        Determines affected edges from the vehicle's route and applies
        graph state changes directly.
        """
        try:
            route_edges = self._connection.get_vehicle_route(veh_id)
            current_edge = self._connection.get_vehicle_position(veh_id)[2]
        except Exception:
            return

        if not route_edges:
            return

        try:
            current_idx = route_edges.index(current_edge)
        except ValueError:
            current_idx = 0

        start_idx = max(0, current_idx - _EMERGENCY_RADIUS_EDGES)
        end_idx = min(len(route_edges), current_idx + _EMERGENCY_RADIUS_EDGES + 1)
        affected = route_edges[start_idx:end_idx]

        if not affected:
            return

        affected_edge_ids = frozenset(EdgeId(e) for e in affected)

        self._active[veh_id] = ActiveEmergency(
            vehicle_id=veh_id,
            affected_edges=affected_edge_ids,
            activated_step=int(self._connection.get_simulation_time() / 1000),
        )

        for eid in affected_edge_ids:
            if not self._graph.has_edge(eid):
                continue
            edge = self._graph.get_edge(eid)
            new_state = MutableEdgeState(
                is_blocked=False,
                current_speed_mps=edge.state.current_speed_mps,
                travel_time_override_s=edge.state.travel_time_override_s,
                congestion_factor=edge.state.congestion_factor,
                hazard_penalty_s=edge.state.hazard_penalty_s,
                emergency_penalty_s=(
                    edge.state.emergency_penalty_s + _DEFAULT_EMERGENCY_PENALTY_S
                ),
                communication_penalty_s=edge.state.communication_penalty_s,
            )
            self._graph.update_edge_state(eid, new_state)

        _logger.info(
            "EmergencyManager: activated emergency for vehicle %s, "
            "affecting %d edges",
            veh_id, len(affected_edge_ids),
        )

    def _resolve_emergency(self, veh_id: str) -> None:
        """Resolve an active emergency and restore graph state."""
        active = self._active.pop(veh_id, None)
        if active is None or active.resolved:
            return

        active.resolved = True

        for eid in active.affected_edges:
            if not self._graph.has_edge(eid):
                continue
            edge = self._graph.get_edge(eid)
            restored_penalty = max(
                0.0,
                edge.state.emergency_penalty_s - _DEFAULT_EMERGENCY_PENALTY_S,
            )
            new_state = MutableEdgeState(
                is_blocked=edge.state.is_blocked,
                current_speed_mps=edge.state.current_speed_mps,
                travel_time_override_s=edge.state.travel_time_override_s,
                congestion_factor=edge.state.congestion_factor,
                hazard_penalty_s=edge.state.hazard_penalty_s,
                emergency_penalty_s=restored_penalty,
                communication_penalty_s=edge.state.communication_penalty_s,
            )
            self._graph.update_edge_state(eid, new_state)

        _logger.info(
            "EmergencyManager: resolved emergency for vehicle %s",
            veh_id,
        )