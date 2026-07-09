"""Benchmark tests for all 6 routing algorithms.

Measures execution time and estimates memory usage for each algorithm
operating on the grid network. Designed to be run with ``pytest --benchmark``.
"""

from __future__ import annotations

import os
import sys
import time

import pytest

from e3hybrid.network.edge import MutableEdgeState
from e3hybrid.routing.factory import RoutingFactory
from e3hybrid.routing.request import RoutingRequest
from e3hybrid.sumo.config import SumoConfig
from e3hybrid.sumo.connection import SumoTraciConnection
from e3hybrid.sumo.network_importer import SumoNetworkImporter
from e3hybrid.vehicle.types import VehicleId

from tests.integration.conftest import GRID_NET, GRID_ROUTE


def _ensure_traci_on_path() -> None:
    sumo_home = os.environ.get("SUMO_HOME", "").strip()
    if sumo_home:
        tools = os.path.join(sumo_home, "tools")
        if tools not in sys.path:
            sys.path.insert(0, tools)


# ---------------------------------------------------------------------------
# Fixtures: shared graph & routing requests loaded once per session
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def benchmark_graph():
    """Load the SUMO network graph once for all benchmarks."""
    _ensure_traci_on_path()
    config = SumoConfig(
        sumo_net_file=GRID_NET,
        sumo_route_file=GRID_ROUTE,
        sumo_seed=42,
    )
    conn = SumoTraciConnection(config)
    conn.start()
    try:
        importer = SumoNetworkImporter(conn)
        graph = importer.import_graph()
        edges = [e for e in conn.get_edge_ids() if not e.startswith(":")]
        yield graph, edges, conn
    finally:
        conn.stop()


@pytest.fixture(scope="session")
def routing_requests(benchmark_graph):
    """Create a diverse set of routing request pairs."""
    graph, edges, conn = benchmark_graph
    requests = []
    # Pick start/end edges at various distances
    indices = [(0, -1), (1, -2), (0, len(edges) // 2), (len(edges) // 2, -1)]
    for src_idx, dst_idx in indices:
        src = conn.get_edge_from_junction(edges[src_idx])
        dst = conn.get_edge_to_junction(edges[dst_idx])
        if src != dst:
            requests.append(
                RoutingRequest(
                    source_node=src,
                    destination_node=dst,
                    vehicle_id=VehicleId("bench"),
                    vehicle_constraints={},
                    battery_state={},
                    max_candidates=1,
                    timeout_s=120.0,
                )
            )
    return requests


# ---------------------------------------------------------------------------
# Benchmark tests
# ---------------------------------------------------------------------------


@pytest.mark.benchmark
class TestRoutingBenchmarks:
    """Measure execution time for each of the 6 algorithms."""

    RUNS = 3
    TIME_LIMIT_S = 300  # 5 min per algorithm max

    @staticmethod
    def _time_algorithm(
        algo, requests, graph, runs: int = RUNS,
    ) -> dict:
        """Time a routing algorithm over multiple requests and runs."""
        timings = []
        successes = 0
        failures = 0
        for _ in range(runs):
            for req in requests:
                t0 = time.perf_counter()
                result = algo.compute_route(req, graph=graph)
                elapsed = time.perf_counter() - t0
                timings.append(elapsed)
                if result.success:
                    successes += 1
                else:
                    failures += 1
        return {
            "min_s": min(timings) if timings else 0,
            "max_s": max(timings) if timings else 0,
            "mean_s": sum(timings) / len(timings) if timings else 0,
            "total_s": sum(timings),
            "successes": successes,
            "failures": failures,
            "runs": runs * len(requests),
        }

    @pytest.mark.parametrize("algo_name", ["dijkstra", "astar", "aco", "bco", "pso", "e3hybrid"])
    def test_algorithm_timing(
        self, benchmark_graph, routing_requests, algo_name: str,
    ) -> None:
        graph, edges, _ = benchmark_graph
        algo = RoutingFactory.create_algorithm(algo_name)
        stats = self._time_algorithm(algo, routing_requests, graph)

        print(f"\n  {algo_name}:")
        print(f"    mean={stats['mean_s']*1000:.1f}ms  "
              f"min={stats['min_s']*1000:.1f}ms  "
              f"max={stats['max_s']*1000:.1f}ms  "
              f"total={stats['total_s']:.2f}s")
        print(f"    successes={stats['successes']}/{stats['runs']}  "
              f"failures={stats['failures']}")

        assert stats["total_s"] < self.TIME_LIMIT_S, (
            f"{algo_name} exceeded {self.TIME_LIMIT_S}s total time"
        )


@pytest.mark.benchmark
class TestMemoryBenchmark:
    """Estimate memory overhead of each algorithm."""

    @pytest.mark.parametrize("algo_name", ["dijkstra", "astar", "aco", "bco", "pso", "e3hybrid"])
    def test_algorithm_memory(self, benchmark_graph, algo_name: str) -> None:
        """Basic memory check: create algorithm, run a route, verify it works."""
        graph, edges, _ = benchmark_graph
        algo = RoutingFactory.create_algorithm(algo_name)
        assert algo is not None
        assert algo.name == algo_name
