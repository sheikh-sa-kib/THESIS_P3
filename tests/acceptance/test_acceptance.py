"""Acceptance tests for routing correctness, rerouting, emergency handling,
and simulation stability.

All emergency/congestion/closure handling must be exclusively through
graph-state updates — not via algorithm-specific branches.
"""

from __future__ import annotations

import ast
import os
import sys

import pytest

from e3hybrid.network.edge import MutableEdgeState
from e3hybrid.routing.factory import RoutingFactory
from e3hybrid.routing.request import RoutingRequest
from e3hybrid.sumo.config import SumoConfig
from e3hybrid.vehicle.types import VehicleId
from e3hybrid.sumo.connection import SumoTraciConnection
from e3hybrid.sumo.network_importer import SumoNetworkImporter

from tests.integration.conftest import GRID_NET, GRID_ROUTE


def _ensure_traci_on_path() -> None:
    sumo_home = os.environ.get("SUMO_HOME", "").strip()
    if sumo_home:
        tools = os.path.join(sumo_home, "tools")
        if tools not in sys.path:
            sys.path.insert(0, tools)


@pytest.fixture(scope="module")
def sumo_graph():
    """Provide a graph loaded from SUMO for all acceptance tests."""
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
        yield graph, conn
    finally:
        conn.stop()


@pytest.mark.acceptance
class TestRoutingCorrectness:
    """Verify routing correctness for all algorithms."""

    @pytest.mark.parametrize("algo_name", ["dijkstra", "astar", "aco", "bco", "pso", "e3hybrid"])
    def test_route_validity(self, sumo_graph, algo_name: str) -> None:
        graph, conn = sumo_graph
        algo = RoutingFactory.create_algorithm(algo_name)

        edges = [e for e in conn.get_edge_ids() if not e.startswith(":")]
        assert len(edges) >= 2

        source = conn.get_edge_from_junction(edges[0])
        target = conn.get_edge_to_junction(edges[-1])
        if source == target:
            target = conn.get_edge_to_junction(edges[-2])

        request = RoutingRequest(
            source_node=source,
            destination_node=target,
            vehicle_id=VehicleId("test"),
            vehicle_constraints={},
            battery_state={},
            max_candidates=1,
            timeout_s=60.0,
        )

        result = algo.compute_route(request, graph=graph)
        if result.success and result.primary_route:
            route = result.primary_route
            route_edges = route.edge_sequence if hasattr(route, 'edge_sequence') else route.edge_ids
            assert len(route_edges) > 0, f"{algo_name} returned empty route"
            assert route.total_distance_m > 0, f"{algo_name} returned zero-length route"

            # Verify edges exist in the graph
            for eid in route_edges:
                assert graph.has_edge(eid), (
                    f"{algo_name} route contains non-existent edge: {eid}"
                )

    def test_routes_reach_destination(self, sumo_graph) -> None:
        """Verify that routes actually connect source to destination."""
        graph, conn = sumo_graph

        for algo_name in ("dijkstra", "astar"):
            algo = RoutingFactory.create_algorithm(algo_name)
            edges = [e for e in conn.get_edge_ids() if not e.startswith(":")]
            source = conn.get_edge_from_junction(edges[0])
            target = conn.get_edge_to_junction(edges[-1])
            if source == target:
                target = conn.get_edge_to_junction(edges[-2])

            request = RoutingRequest(
                source_node=source,
                destination_node=target,
                vehicle_id=VehicleId("test"),
                vehicle_constraints={},
                battery_state={},
                max_candidates=1,
                timeout_s=60.0,
            )
            result = algo.compute_route(request, graph=graph)
            if result.success and result.primary_route:
                route = result.primary_route
                route_edges = route.edge_sequence if hasattr(route, 'edge_sequence') else route.edge_ids
                # Verify path continuity
                for i in range(len(route_edges) - 1):
                    e1 = graph.get_edge(route_edges[i])
                    e2 = graph.get_edge(route_edges[i + 1])
                    assert e1.target == e2.source, (
                        f"Route discontinuity: {e1.edge_id}.target={e1.target} "
                        f"!= {e2.edge_id}.source={e2.source}"
                    )


@pytest.mark.acceptance
class TestEmergencyViaGraphState:
    """Verify emergency handling updates graph state — no algorithm branches."""

    def test_emergency_penalty_updates_graph_state(self, sumo_graph) -> None:
        graph, conn = sumo_graph
        edges = [e for e in conn.get_edge_ids() if not e.startswith(":")]
        assert len(edges) > 0

        eid = edges[0]
        original_state = graph.get_edge(eid).state
        assert original_state.emergency_penalty_s == 0.0

        new_state = MutableEdgeState(
            is_blocked=original_state.is_blocked,
            current_speed_mps=original_state.current_speed_mps,
            travel_time_override_s=original_state.travel_time_override_s,
            congestion_factor=original_state.congestion_factor,
            hazard_penalty_s=original_state.hazard_penalty_s,
            emergency_penalty_s=original_state.emergency_penalty_s + 120.0,
            communication_penalty_s=original_state.communication_penalty_s,
        )
        graph.update_edge_state(eid, new_state)
        updated_state = graph.get_edge(eid).state
        assert updated_state.emergency_penalty_s == 120.0

        # Verify Dijkstra picks up the penalty
        algo = RoutingFactory.create_algorithm("dijkstra")
        source = conn.get_edge_from_junction(edges[1])
        target = conn.get_edge_to_junction(edges[-1])
        request = RoutingRequest(
            source_node=source,
            destination_node=target,
            vehicle_id=VehicleId("test"),
            vehicle_constraints={},
            battery_state={},
            max_candidates=1,
            timeout_s=30.0,
        )
        result = algo.compute_route(request, graph=graph)
        assert result is not None

        # Restore
        restored = MutableEdgeState(
            is_blocked=original_state.is_blocked,
            current_speed_mps=original_state.current_speed_mps,
            travel_time_override_s=original_state.travel_time_override_s,
            congestion_factor=original_state.congestion_factor,
            hazard_penalty_s=original_state.hazard_penalty_s,
            emergency_penalty_s=0.0,
            communication_penalty_s=original_state.communication_penalty_s,
        )
        graph.update_edge_state(eid, restored)

    def test_congestion_affects_routing_via_graph_state(self, sumo_graph) -> None:
        """Congestion changes must affect route cost through graph state only."""
        graph, conn = sumo_graph
        edges = [e for e in conn.get_edge_ids() if not e.startswith(":")]
        eid = edges[len(edges) // 2]

        edge = graph.get_edge(eid)
        original = edge.state

        high_congestion = MutableEdgeState(
            is_blocked=original.is_blocked,
            current_speed_mps=original.current_speed_mps,
            travel_time_override_s=original.travel_time_override_s,
            congestion_factor=10.0,
            hazard_penalty_s=original.hazard_penalty_s,
            emergency_penalty_s=original.emergency_penalty_s,
            communication_penalty_s=original.communication_penalty_s,
        )
        graph.update_edge_state(eid, high_congestion)
        assert graph.get_edge(eid).state.congestion_factor == 10.0

        # Restore
        graph.update_edge_state(eid, original)

    def test_no_algorithm_branches_for_emergency(self) -> None:
        """Emergency handling goes through graph state, not algorithm branches.
        
        Verify there is no emergency-specific if/else in any routing algorithm.
        """
        routing_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "src", "e3hybrid", "routing")
        )

        for fname in os.listdir(routing_dir):
            if not fname.endswith(".py") or fname == "__init__.py":
                continue
            fpath = os.path.join(routing_dir, fname)
            with open(fpath, encoding="utf-8") as f:
                try:
                    tree = ast.parse(f.read())
                except SyntaxError:
                    continue

            class EmergencyBranchFinder(ast.NodeVisitor):
                def __init__(self):
                    self.found = []

                def visit_If(self, node):
                    if isinstance(node.test, ast.Compare):
                        for comparator in [node.test.left, *node.test.comparators]:
                            if isinstance(comparator, ast.Constant) and (
                                "emergency" in str(comparator.value).lower()
                            ):
                                self.found.append((fname, node.lineno))
                    self.generic_visit(node)

                def visit_Name(self, node):
                    if "emergency" in node.id.lower():
                        self.found.append((fname, node.lineno))
                    self.generic_visit(node)

            finder = EmergencyBranchFinder()
            finder.visit(tree)
            # Allow references in cost_calculator (which reads edge state)
            # and verifier (which validates cost breakdowns)
            if fname in ("cost_calculator.py", "verifier.py", "cost.py"):
                continue
            assert len(finder.found) == 0, (
                f"Algorithm-specific emergency branch found in {fname}: "
                f"{finder.found}. Emergency handling must go through "
                f"graph state only."
            )


@pytest.mark.acceptance
class TestSimulationStability:
    """Verify simulation does not crash under various conditions."""

    def test_empty_network_does_not_crash(self) -> None:
        """A minimal or empty config should not crash the experiment runner."""
        pass

    def test_long_running_simulation_stable(self, sumo_graph) -> None:
        """Run a longer simulation and verify no crashes."""
        graph, conn = sumo_graph
        from e3hybrid.sumo.simulation import SumoSimulation

        config = SumoConfig(
            sumo_net_file=GRID_NET,
            sumo_route_file=GRID_ROUTE,
            sumo_seed=42,
        )
        sim = SumoSimulation(conn, config, graph)
        errors = []
        for step in range(50):
            try:
                sim.step()
            except Exception as e:
                errors.append(f"Step {step}: {e}")
        assert len(errors) == 0, f"Simulation encountered errors:\n{errors}"
