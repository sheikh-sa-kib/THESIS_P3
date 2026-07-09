"""SumoSimulation — main simulation step loop with graph state sync."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from e3hybrid.network.edge import MutableEdgeState
from e3hybrid.network.types import EdgeId

if TYPE_CHECKING:
    from e3hybrid.network.graph import DirectedGraph
    from e3hybrid.sumo.config import SumoConfig
    from e3hybrid.sumo.connection import SumoTraciConnection


class SumoSimulation:
    """Main SUMO simulation step loop.

    Owns the connection, the graph, and the per-step state sync.
    External consumers observe via the graph state after each step.

    Usage::

        sim = SumoSimulation(connection, config, graph)
        sim.run(total_steps)
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
        self._step_count = 0
        self._running = False
        self._on_step_callbacks: list[Callable[[int], None]] = []

    @property
    def graph(self) -> DirectedGraph:
        """Return the current graph with up-to-date edge states."""
        return self._graph

    @property
    def step_count(self) -> int:
        """Return the number of steps executed so far."""
        return self._step_count

    @property
    def is_running(self) -> bool:
        """Return True if the simulation loop is active."""
        return self._running

    def register_on_step(self, callback: Callable[[int], None]) -> None:
        """Register a callback invoked after each step.

        The callback receives the current simulation time (ms).
        """
        self._on_step_callbacks.append(callback)

    def step(self) -> int:
        """Advance one timestep.

        Returns
        -------
        int
            Current simulation time in milliseconds.
        """
        sim_time = self._connection.step()
        self._step_count += 1
        self._update_graph_state()
        for cb in self._on_step_callbacks:
            cb(sim_time)
        return sim_time

    def run(self, total_steps: int) -> None:
        """Run the step loop for *total_steps* iterations."""
        self._running = True
        try:
            for _ in range(total_steps):
                self.step()
        finally:
            self._running = False

    def update_graph_state(self) -> None:
        """Pull dynamic state from SUMO into each edge's MutableEdgeState."""
        self._update_graph_state()

    def _update_graph_state(self) -> None:
        conn = self._connection
        for edge in self._graph.edges():
            eid_str = str(edge.edge_id)
            try:
                travel_time = conn.get_edge_travel_time(eid_str)
                mean_speed = conn.get_edge_mean_speed(eid_str)
                occupancy = conn.get_edge_occupancy(eid_str)
                lane_count = conn.get_edge_lane_count(eid_str)
            except Exception:
                continue

            is_blocked = False
            try:
                travel_time_raw = travel_time
                if travel_time_raw is None or travel_time_raw > 1e9:
                    is_blocked = True
            except Exception:
                pass

            congestion = 1.0
            if lane_count > 0 and occupancy > 0:
                congestion = 1.0 + (occupancy / lane_count)

            new_state = MutableEdgeState(
                is_blocked=is_blocked,
                current_speed_mps=mean_speed if mean_speed > 0 else None,
                travel_time_override_s=travel_time if travel_time > 0 else None,
                congestion_factor=congestion,
                hazard_penalty_s=edge.state.hazard_penalty_s,
                emergency_penalty_s=edge.state.emergency_penalty_s,
                communication_penalty_s=edge.state.communication_penalty_s,
            )
            self._graph.update_edge_state(edge.edge_id, new_state)

    def check_emergency(self) -> list[str]:
        """Return list of emergency vehicle IDs currently active.

        Detects vehicles whose type ID contains "emergency" (case-insensitive).
        """
        conn = self._connection
        emergency: list[str] = []
        for veh_id in conn.get_vehicle_ids():
            try:
                vtype = conn.get_vehicle_type(veh_id)
                if "emergency" in vtype.lower():
                    emergency.append(veh_id)
            except Exception:
                continue
        return emergency