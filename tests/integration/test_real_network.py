"""Integration test using the user's real midtown_manhattan network.

This test is optional — it skips if the network file is not present.
The user must place the file at data/maps/midtown_manhattan.net.xml
and generate routes with randomTrips.py.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from e3hybrid.network.types import NodeId
from e3hybrid.routing.factory import RoutingFactory
from e3hybrid.routing.request import RoutingRequest
from e3hybrid.sumo.config import SumoConfig
from e3hybrid.sumo.connection import SumoTraciConnection
from e3hybrid.sumo.experiment_runner import SumoExperimentRunner
from e3hybrid.sumo.network_importer import SumoNetworkImporter
from e3hybrid.vehicle.types import VehicleId


DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
MIDTOWN_NET = DATA_DIR / "maps" / "midtown_manhattan.net.xml"
MIDTOWN_ROUTE = DATA_DIR / "routes" / "midtown_manhattan.rou.xml"

ALL_SIX = ("dijkstra", "astar", "aco", "bco", "pso", "e3hybrid")


def _ensure_traci_on_path() -> None:
    sumo_home = os.environ.get("SUMO_HOME", "").strip()
    if sumo_home:
        tools = os.path.join(sumo_home, "tools")
        if tools not in sys.path:
            sys.path.insert(0, tools)


@pytest.fixture(scope="module")
def midtown_config():
    _ensure_traci_on_path()
    return SumoConfig(
        sumo_net_file=MIDTOWN_NET,
        sumo_route_file=MIDTOWN_ROUTE,
        sumo_seed=42,
        step_length_ms=1000,
        reroute_interval_steps=10,
        algorithm_names=ALL_SIX,
        algorithm_split=tuple((n, 1.0 / 6.0) for n in ALL_SIX),
    )


@pytest.mark.skipif(
    not MIDTOWN_NET.exists(),
    reason=f"midtown_manhattan.net.xml not found at {MIDTOWN_NET}",
)
class TestMidtownManhattanNetwork:
    """End-to-end tests using the real midtown Manhattan network."""

    @pytest.mark.sumo_integration
    def test_network_loads(self, midtown_config) -> None:
        _ensure_traci_on_path()
        conn = SumoTraciConnection(midtown_config)
        conn.start()
        try:
            edge_ids = conn.get_edge_ids()
            assert len(edge_ids) > 100, (
                f"midtown_manhattan should have >100 edges, got {len(edge_ids)}"
            )
            junction_ids = conn.get_junction_ids()
            assert len(junction_ids) > 50, (
                f"midtown_manhattan should have >50 junctions, got {len(junction_ids)}"
            )
        finally:
            conn.stop()

    @pytest.mark.sumo_integration
    def test_experiment_runner_all_six_algorithms(self, midtown_config) -> None:
        _ensure_traci_on_path()
        runner = SumoExperimentRunner(midtown_config)
        algorithms = {n: RoutingFactory.create_algorithm(n) for n in ALL_SIX}
        vehicle_map = {n: [] for n in ALL_SIX}
        result = runner.run(algorithms, vehicle_map, total_steps=30)
        assert result.total_steps == 30
        assert result.simulation_time_ms > 0

    @pytest.mark.determinism
    def test_deterministic_routing_on_real_network(self, midtown_config) -> None:
        _ensure_traci_on_path()
        conn = SumoTraciConnection(midtown_config)
        conn.start()
        try:
            importer = SumoNetworkImporter(conn)
            graph = importer.import_graph()
            edges = [e for e in conn.get_edge_ids() if not e.startswith(":")]
            source = conn.get_edge_from_junction(edges[0])
            target = conn.get_edge_to_junction(edges[-1])
            if source == target:
                target = conn.get_edge_to_junction(edges[-2])
            request = RoutingRequest(
                source_node=NodeId(source),
                destination_node=NodeId(target),
                vehicle_id=VehicleId("det-test"),
                vehicle_constraints={},
                battery_state={},
                max_candidates=1,
                timeout_s=30.0,
            )
            for algo_name in ("dijkstra", "astar"):
                algo = RoutingFactory.create_algorithm(algo_name)
                r1 = algo.compute_route(request, graph=graph)
                r2 = algo.compute_route(request, graph=graph)
                if r1.success and r2.success:
                    e1 = list(r1.primary_route.edge_sequence)
                    e2 = list(r2.primary_route.edge_sequence)
                    assert e1 == e2, (
                        f"{algo_name} non-deterministic on real network: "
                        f"{e1} != {e2}"
                    )
        finally:
            conn.stop()
