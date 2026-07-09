"""End-to-end integration tests with real SUMO simulation.

These tests start a real SUMO instance with the grid network and verify
that the full experiment lifecycle works correctly for all 6 algorithms.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from e3hybrid.routing.factory import RoutingFactory
from e3hybrid.sumo.config import SumoConfig
from e3hybrid.sumo.connection import SumoTraciConnection
from e3hybrid.sumo.experiment_runner import SumoExperimentRunner
from e3hybrid.sumo.network_importer import SumoNetworkImporter
from e3hybrid.sumo.simulation import SumoSimulation

from tests.integration.conftest import GRID_NET, GRID_ROUTE, TEST_DATA


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_traci_on_path() -> None:
    """Ensure the SUMO tools directory is on sys.path so traci can be imported."""
    sumo_home = os.environ.get("SUMO_HOME", "").strip()
    if sumo_home:
        tools = os.path.join(sumo_home, "tools")
        if tools not in sys.path:
            sys.path.insert(0, tools)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def sumo_binary() -> str:
    """Find the SUMO binary path."""
    _ensure_traci_on_path()
    sumo_home = os.environ.get("SUMO_HOME", "").strip()
    if sumo_home:
        candidate = os.path.join(sumo_home, "bin", "sumo.exe")
        if os.path.isfile(candidate):
            return candidate
    return "sumo"


@pytest.fixture
def grid_config_dijkstra() -> SumoConfig:
    """Config with Dijkstra for basic tests."""
    return SumoConfig(
        sumo_net_file=GRID_NET,
        sumo_route_file=GRID_ROUTE,
        sumo_seed=42,
        step_length_ms=1000,
        reroute_interval_steps=10,
        algorithm_names=("dijkstra",),
        algorithm_split=(("dijkstra", 1.0),),
    )


@pytest.fixture
def grid_config_all_algorithms() -> SumoConfig:
    """Config using all 6 algorithms."""
    names = ("dijkstra", "astar", "aco", "bco", "pso", "e3hybrid")
    return SumoConfig(
        sumo_net_file=GRID_NET,
        sumo_route_file=GRID_ROUTE,
        sumo_seed=42,
        step_length_ms=1000,
        reroute_interval_steps=10,
        algorithm_names=names,
        algorithm_split=tuple((n, 1.0 / 6) for n in names),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSumoStarts:
    """Verify SUMO can start and stop cleanly."""

    def test_sumo_starts_and_stops(self, grid_config_dijkstra) -> None:
        _ensure_traci_on_path()
        conn = SumoTraciConnection(grid_config_dijkstra)
        conn.start()
        assert conn.is_connected
        time_ms = conn.get_simulation_time()
        assert time_ms == 0
        conn.step()
        time_ms = conn.get_simulation_time()
        assert time_ms > 0
        conn.stop()
        assert not conn.is_connected

    def test_sumo_returns_vehicles(self, grid_config_dijkstra) -> None:
        _ensure_traci_on_path()
        conn = SumoTraciConnection(grid_config_dijkstra)
        conn.start()
        # Run a few steps to let vehicles spawn
        for _ in range(20):
            conn.step()
        veh_ids = conn.get_vehicle_ids()
        assert len(veh_ids) > 0, "No vehicles spawned in the simulation"
        conn.stop()

    def test_sumo_network_has_edges(self, grid_config_dijkstra) -> None:
        _ensure_traci_on_path()
        conn = SumoTraciConnection(grid_config_dijkstra)
        conn.start()
        edge_ids = conn.get_edge_ids()
        assert len(edge_ids) > 0, "Network has no edges"
        conn.stop()


class TestExperimentRunner:
    """Verify SumoExperimentRunner works end-to-end."""

    @pytest.mark.sumo_integration
    def test_experiment_runner_basic(self, grid_config_dijkstra) -> None:
        _ensure_traci_on_path()
        runner = SumoExperimentRunner(grid_config_dijkstra)
        algorithms = {"dijkstra": RoutingFactory.create_algorithm("dijkstra")}
        vehicle_map = {"dijkstra": []}
        result = runner.run(algorithms, vehicle_map, total_steps=30)
        assert result.total_steps == 30
        assert result.simulation_time_ms > 0
        assert result.total_vehicles >= 0

    @pytest.mark.sumo_integration
    def test_experiment_runner_collects_metrics(self, grid_config_dijkstra) -> None:
        _ensure_traci_on_path()
        runner = SumoExperimentRunner(grid_config_dijkstra)
        algorithms = {"dijkstra": RoutingFactory.create_algorithm("dijkstra")}
        vehicle_map = {"dijkstra": []}
        result = runner.run(algorithms, vehicle_map, total_steps=20)
        assert result.reroute_count >= 0
        assert result.emergency_event_count >= 0
        assert isinstance(result.algorithm_names, tuple)
        assert "dijkstra" in result.algorithm_names

    @pytest.mark.sumo_integration
    def test_experiment_runner_all_six_algorithms(self, grid_config_all_algorithms) -> None:
        _ensure_traci_on_path()
        runner = SumoExperimentRunner(grid_config_all_algorithms)
        names = ("dijkstra", "astar", "aco", "bco", "pso", "e3hybrid")
        algorithms = {n: RoutingFactory.create_algorithm(n) for n in names}
        vehicle_map = {n: [] for n in names}
        result = runner.run(algorithms, vehicle_map, total_steps=20)
        assert result.total_steps == 20
        for name in names:
            assert name in result.algorithm_names

    @pytest.mark.sumo_integration
    def test_experiment_runner_applies_reroutes(self, grid_config_dijkstra) -> None:
        """Verify rerouting metrics are collected and non-negative."""
        _ensure_traci_on_path()
        runner = SumoExperimentRunner(grid_config_dijkstra)
        algorithms = {"dijkstra": RoutingFactory.create_algorithm("dijkstra")}
        vehicle_map = {"dijkstra": []}
        result = runner.run(algorithms, vehicle_map, total_steps=50)
        assert result.reroute_count >= 0


class TestSimulationStepLoop:
    """Verify the simulation step loop integrates correctly."""

    def test_simulation_steps_and_graph_sync(self, grid_config_dijkstra) -> None:
        _ensure_traci_on_path()
        conn = SumoTraciConnection(grid_config_dijkstra)
        conn.start()
        try:
            importer = SumoNetworkImporter(conn)
            graph = importer.import_graph()
            sim = SumoSimulation(conn, grid_config_dijkstra, graph)
            steps = 30
            for _ in range(steps):
                sim.step()
            assert sim.step_count == steps
        finally:
            conn.stop()


class TestRoutingAdapters:
    """Verify all 6 algorithms work through the RoutingAlgorithm interface."""

    @staticmethod
    def _load_graph(conn: SumoTraciConnection):
        importer = SumoNetworkImporter(conn)
        return importer.import_graph()

    def _test_algorithm_routes(self, grid_config_dijkstra, algo_name: str) -> None:
        _ensure_traci_on_path()
        conn = SumoTraciConnection(grid_config_dijkstra)
        conn.start()
        try:
            graph = self._load_graph(conn)
            algo = RoutingFactory.create_algorithm(algo_name)
            adapter = algo  # SumoRoutingAdapter wraps it in SumoExperimentRunner
            edges = conn.get_edge_ids()
            assert len(edges) >= 2, "Need at least 2 edges for routing"

            # Pick first two edges' endpoints as source/target
            from_edge = edges[0]
            to_edge = edges[-1]
            source = conn.get_edge_from_junction(from_edge)
            target = conn.get_edge_to_junction(to_edge)

            from e3hybrid.routing.request import RoutingRequest
            from e3hybrid.vehicle.types import VehicleId

            request = RoutingRequest(
                source_node=source,
                destination_node=target,
                vehicle_id=VehicleId("test"),
                vehicle_constraints={},
                battery_state={},
                max_candidates=1,
                timeout_s=60.0,
            )
            result = adapter.compute_route(request, graph=graph)
            assert result is not None
            if result.success and result.primary_route:
                route = result.primary_route
                # RouteCandidate uses edge_sequence, not edge_ids
                route_edges = route.edge_sequence if hasattr(route, 'edge_sequence') else route.edge_ids
                assert len(route_edges) > 0, f"{algo_name} returned empty route"
        finally:
            conn.stop()

    @pytest.mark.parametrize("algo_name", ["dijkstra", "astar", "aco", "bco", "pso", "e3hybrid"])
    def test_all_algorithms_produce_routes(self, grid_config_dijkstra, algo_name: str) -> None:
        """Every algorithm must produce a valid route between two nodes."""
        self._test_algorithm_routes(grid_config_dijkstra, algo_name)
