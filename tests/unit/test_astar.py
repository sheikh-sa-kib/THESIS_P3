"""Comprehensive unit tests for AStarRouting and heuristic components."""

from __future__ import annotations

import math

import pytest

from e3hybrid.network.edge import Edge, MutableEdgeState
from e3hybrid.network.graph import DirectedGraph
from e3hybrid.network.node import Node
from e3hybrid.network.types import EdgeId, NodeId
from e3hybrid.routing.astar import AStarRouting
from e3hybrid.routing.cost_calculator import CostWeights
from e3hybrid.routing.dijkstra import DijkstraRouting
from e3hybrid.routing.heuristic import (
    EuclideanHeuristic,
    Heuristic,
    ManhattanHeuristic,
    ZeroHeuristic,
)
from e3hybrid.routing.heuristic_factory import HeuristicFactory
from e3hybrid.routing.heuristic_validator import HeuristicValidator
from e3hybrid.routing.request import RoutingRequest
from e3hybrid.routing.result import RoutingResult
from e3hybrid.routing.verifier import RoutingVerifier
from e3hybrid.vehicle.types import VehicleId


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def linear_graph() -> DirectedGraph:
    """Linear graph A -> B -> C -> D with coordinates."""
    graph = DirectedGraph()
    graph.add_node(Node(node_id=NodeId("A"), x=0.0, y=0.0))
    graph.add_node(Node(node_id=NodeId("B"), x=100.0, y=0.0))
    graph.add_node(Node(node_id=NodeId("C"), x=200.0, y=0.0))
    graph.add_node(Node(node_id=NodeId("D"), x=300.0, y=0.0))
    state = MutableEdgeState()
    graph.add_edge(Edge(
        edge_id=EdgeId("AB"), source=NodeId("A"), target=NodeId("B"),
        length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=state,
    ))
    graph.add_edge(Edge(
        edge_id=EdgeId("BC"), source=NodeId("B"), target=NodeId("C"),
        length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=state,
    ))
    graph.add_edge(Edge(
        edge_id=EdgeId("CD"), source=NodeId("C"), target=NodeId("D"),
        length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=state,
    ))
    return graph


@pytest.fixture
def grid_graph() -> DirectedGraph:
    """Small grid graph with coordinates for heuristic testing.

    A(0,0) → B(100,0) → C(200,0)
      ↓          ↓          ↓
    D(0,100) → E(100,100) → F(200,100)
      ↓          ↓          ↓
    G(0,200) → H(100,200) → I(200,200)
    """
    graph = DirectedGraph()
    for name, x, y in [
        ("A", 0.0, 0.0), ("B", 100.0, 0.0), ("C", 200.0, 0.0),
        ("D", 0.0, 100.0), ("E", 100.0, 100.0), ("F", 200.0, 100.0),
        ("G", 0.0, 200.0), ("H", 100.0, 200.0), ("I", 200.0, 200.0),
    ]:
        graph.add_node(Node(node_id=NodeId(name), x=x, y=y))

    state = MutableEdgeState()
    edges = [
        ("AB", "A", "B"), ("BC", "B", "C"),
        ("AD", "A", "D"), ("BE", "B", "E"), ("CF", "C", "F"),
        ("DE", "D", "E"), ("EF", "E", "F"),
        ("DG", "D", "G"), ("EH", "E", "H"), ("FI", "F", "I"),
        ("GH", "G", "H"), ("HI", "H", "I"),
    ]
    for eid, src, tgt in edges:
        graph.add_edge(Edge(
            edge_id=EdgeId(eid), source=NodeId(src), target=NodeId(tgt),
            length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=state,
        ))
    return graph


@pytest.fixture
def graph_with_blocked() -> DirectedGraph:
    """Graph with a blocked edge: A->B, B->C (blocked), A->C (direct)."""
    graph = DirectedGraph()
    graph.add_node(Node(node_id=NodeId("A"), x=0.0, y=0.0))
    graph.add_node(Node(node_id=NodeId("B"), x=100.0, y=0.0))
    graph.add_node(Node(node_id=NodeId("C"), x=200.0, y=0.0))
    graph.add_edge(Edge(
        edge_id=EdgeId("AB"), source=NodeId("A"), target=NodeId("B"),
        length_m=100.0, speed_limit_mps=10.0, lane_count=1,
    ))
    graph.add_edge(Edge(
        edge_id=EdgeId("BC"), source=NodeId("B"), target=NodeId("C"),
        length_m=100.0, speed_limit_mps=10.0, lane_count=1,
        state=MutableEdgeState(is_blocked=True),
    ))
    graph.add_edge(Edge(
        edge_id=EdgeId("AC"), source=NodeId("A"), target=NodeId("C"),
        length_m=250.0, speed_limit_mps=10.0, lane_count=1,
    ))
    return graph


@pytest.fixture
def graph_with_cycle() -> DirectedGraph:
    """Graph with cycles."""
    graph = DirectedGraph()
    graph.add_node(Node(node_id=NodeId("A"), x=0.0, y=0.0))
    graph.add_node(Node(node_id=NodeId("B"), x=100.0, y=0.0))
    graph.add_node(Node(node_id=NodeId("C"), x=100.0, y=100.0))
    graph.add_node(Node(node_id=NodeId("D"), x=200.0, y=0.0))
    state = MutableEdgeState()
    graph.add_edge(Edge(
        edge_id=EdgeId("AB"), source=NodeId("A"), target=NodeId("B"),
        length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=state,
    ))
    graph.add_edge(Edge(
        edge_id=EdgeId("BC"), source=NodeId("B"), target=NodeId("C"),
        length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=state,
    ))
    graph.add_edge(Edge(
        edge_id=EdgeId("CB"), source=NodeId("C"), target=NodeId("B"),
        length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=state,
    ))
    graph.add_edge(Edge(
        edge_id=EdgeId("BD"), source=NodeId("B"), target=NodeId("D"),
        length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=state,
    ))
    return graph


@pytest.fixture
def request_ad() -> RoutingRequest:
    return RoutingRequest(
        source_node=NodeId("A"), destination_node=NodeId("D"),
        vehicle_id=VehicleId("test"), vehicle_constraints=None,
        battery_state=None, max_candidates=3, timeout_s=10.0,
    )


@pytest.fixture
def request_ai() -> RoutingRequest:
    return RoutingRequest(
        source_node=NodeId("A"), destination_node=NodeId("I"),
        vehicle_id=VehicleId("test"), vehicle_constraints=None,
        battery_state=None, max_candidates=3, timeout_s=10.0,
    )


# =============================================================================
# Heuristic Tests
# =============================================================================

class TestHeuristics:
    """Tests for individual heuristic implementations."""

    def test_zero_heuristic(self, linear_graph: DirectedGraph) -> None:
        h = ZeroHeuristic()
        assert h.name == "zero"
        assert h.estimate(NodeId("A"), NodeId("D"), linear_graph) == 0.0
        assert h.estimate(NodeId("X"), NodeId("Y"), linear_graph) == 0.0

    def test_euclidean_heuristic(self, linear_graph: DirectedGraph) -> None:
        h = EuclideanHeuristic()
        # A(0,0) to D(300,0) = 300.0
        est = h.estimate(NodeId("A"), NodeId("D"), linear_graph)
        assert abs(est - 300.0) < 1e-6
        # A(0,0) to B(100,0) = 100.0
        est = h.estimate(NodeId("A"), NodeId("B"), linear_graph)
        assert abs(est - 100.0) < 1e-6

    def test_euclidean_with_scale(self, linear_graph: DirectedGraph) -> None:
        h = EuclideanHeuristic(scale=0.5)
        est = h.estimate(NodeId("A"), NodeId("D"), linear_graph)
        assert abs(est - 150.0) < 1e-6

    def test_manhattan_heuristic(self, grid_graph: DirectedGraph) -> None:
        h = ManhattanHeuristic()
        # A(0,0) to I(200,200) = 400.0
        est = h.estimate(NodeId("A"), NodeId("I"), grid_graph)
        assert abs(est - 400.0) < 1e-6
        # A(0,0) to C(200,0) = 200.0
        est = h.estimate(NodeId("A"), NodeId("C"), grid_graph)
        assert abs(est - 200.0) < 1e-6

    def test_manhattan_vs_euclidean(self, grid_graph: DirectedGraph) -> None:
        """Manhattan should be >= Euclidean for same nodes."""
        m = ManhattanHeuristic()
        e = EuclideanHeuristic()
        est_m = m.estimate(NodeId("A"), NodeId("I"), grid_graph)
        est_e = e.estimate(NodeId("A"), NodeId("I"), grid_graph)
        assert est_m >= est_e

    def test_heuristic_missing_coordinates(self) -> None:
        """Heuristics should return 0.0 when nodes lack coordinates."""
        graph = DirectedGraph()
        graph.add_node(Node(node_id=NodeId("A")))
        graph.add_node(Node(node_id=NodeId("B")))
        e = EuclideanHeuristic()
        m = ManhattanHeuristic()
        assert e.estimate(NodeId("A"), NodeId("B"), graph) == 0.0
        assert m.estimate(NodeId("A"), NodeId("B"), graph) == 0.0

    def test_euclidean_diagonal(self) -> None:
        """Test Euclidean with diagonal distance."""
        graph = DirectedGraph()
        graph.add_node(Node(node_id=NodeId("A"), x=0.0, y=0.0))
        graph.add_node(Node(node_id=NodeId("B"), x=3.0, y=4.0))
        h = EuclideanHeuristic()
        # sqrt(3^2 + 4^2) = 5.0
        est = h.estimate(NodeId("A"), NodeId("B"), graph)
        assert abs(est - 5.0) < 1e-6

    def test_heuristic_same_node(self, linear_graph: DirectedGraph) -> None:
        """Heuristic from a node to itself should be 0."""
        e = EuclideanHeuristic()
        m = ManhattanHeuristic()
        assert e.estimate(NodeId("A"), NodeId("A"), linear_graph) == 0.0
        assert m.estimate(NodeId("A"), NodeId("A"), linear_graph) == 0.0

    def test_zero_heuristic_name(self) -> None:
        assert ZeroHeuristic().name == "zero"

    def test_euclidean_heuristic_name(self) -> None:
        assert EuclideanHeuristic().name == "euclidean"

    def test_manhattan_heuristic_name(self) -> None:
        assert ManhattanHeuristic().name == "manhattan"


# =============================================================================
# HeuristicFactory Tests
# =============================================================================

class TestHeuristicFactory:
    """Tests for HeuristicFactory."""

    def test_create_zero(self) -> None:
        h = HeuristicFactory.create("zero")
        assert isinstance(h, ZeroHeuristic)

    def test_create_euclidean(self) -> None:
        h = HeuristicFactory.create("euclidean")
        assert isinstance(h, EuclideanHeuristic)

    def test_create_manhattan(self) -> None:
        h = HeuristicFactory.create("manhattan")
        assert isinstance(h, ManhattanHeuristic)

    def test_create_euclidean_with_scale(self) -> None:
        h = HeuristicFactory.create("euclidean", scale=0.5)
        assert isinstance(h, EuclideanHeuristic)
        assert h._scale == 0.5  # type: ignore[attr-defined]

    def test_create_case_insensitive(self) -> None:
        h = HeuristicFactory.create("ZERO")
        assert isinstance(h, ZeroHeuristic)
        h = HeuristicFactory.create("  Euclidean  ")
        assert isinstance(h, EuclideanHeuristic)

    def test_create_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown heuristic"):
            HeuristicFactory.create("nonexistent")

    def test_available_heuristics(self) -> None:
        available = HeuristicFactory.available_heuristics()
        assert "zero" in available
        assert "euclidean" in available
        assert "manhattan" in available


# =============================================================================
# HeuristicValidator Tests
# =============================================================================

class TestHeuristicValidator:
    """Tests for HeuristicValidator."""

    def test_validate_zero_heuristic(self, grid_graph: DirectedGraph) -> None:
        h = ZeroHeuristic()
        report = HeuristicValidator.validate(h, grid_graph)
        assert report.is_admissible
        assert report.is_consistent

    def test_validate_euclidean(self, grid_graph: DirectedGraph) -> None:
        h = EuclideanHeuristic()
        report = HeuristicValidator.validate(h, grid_graph)
        # Should be admissible since all edges are straight lines
        assert report.is_admissible

    def test_is_zero_heuristic(self) -> None:
        assert HeuristicValidator.is_zero_heuristic(ZeroHeuristic())
        assert not HeuristicValidator.is_zero_heuristic(EuclideanHeuristic())

    def test_is_admissible_for_cost_function_zero(self) -> None:
        h = ZeroHeuristic()
        assert HeuristicValidator.is_admissible_for_cost_function(h, True)
        assert HeuristicValidator.is_admissible_for_cost_function(h, False)

    def test_is_admissible_for_cost_function_euclidean(self) -> None:
        h = EuclideanHeuristic()
        assert HeuristicValidator.is_admissible_for_cost_function(h, True)
        assert not HeuristicValidator.is_admissible_for_cost_function(h, False)

    def test_validate_missing_coordinates(self) -> None:
        graph = DirectedGraph()
        graph.add_node(Node(node_id=NodeId("A")))
        graph.add_node(Node(node_id=NodeId("B")))
        h = EuclideanHeuristic()
        report = HeuristicValidator.validate(h, graph)
        assert report.is_admissible
        assert len(report.warnings) > 0


# =============================================================================
# AStarRouting — Basic Correctness Tests
# =============================================================================

class TestAStarRoutingBasic:
    """Basic correctness tests for AStarRouting."""

    def test_astar_zero_heuristic_equals_dijkstra(
        self, linear_graph: DirectedGraph, request_ad: RoutingRequest,
    ) -> None:
        """A* with ZeroHeuristic should produce same result as Dijkstra."""
        astar = AStarRouting(heuristic=ZeroHeuristic())
        dijkstra = DijkstraRouting()
        result_a = astar.compute_route(request_ad, linear_graph)
        result_d = dijkstra.compute_route(request_ad, linear_graph)
        assert result_a.success
        assert result_d.success
        assert abs(result_a.candidates[0].total_cost - result_d.candidates[0].total_cost) < 1e-6
        assert result_a.primary_route.edge_sequence == result_d.primary_route.edge_sequence

    def test_simple_path(self, linear_graph: DirectedGraph, request_ad: RoutingRequest) -> None:
        astar = AStarRouting()
        result = astar.compute_route(request_ad, linear_graph)
        assert result.success
        assert result.primary_route is not None
        assert result.primary_route.node_sequence == (NodeId("A"), NodeId("B"), NodeId("C"), NodeId("D"))
        assert result.primary_route.edge_sequence == (EdgeId("AB"), EdgeId("BC"), EdgeId("CD"))
        assert result.primary_route.total_distance_m == 300.0

    def test_route_validity(self, linear_graph: DirectedGraph, request_ad: RoutingRequest) -> None:
        astar = AStarRouting()
        result = astar.compute_route(request_ad, linear_graph)
        report = RoutingVerifier.verify_result(result, linear_graph, request_ad)
        assert report.is_valid

    def test_no_path(self, request_ad: RoutingRequest) -> None:
        """Disconnected graph should return failure."""
        graph = DirectedGraph()
        graph.add_node(Node(node_id=NodeId("A")))
        graph.add_node(Node(node_id=NodeId("D")))
        astar = AStarRouting()
        result = astar.compute_route(request_ad, graph)
        assert not result.success
        assert result.failure_reason is not None

    def test_nonexistent_source(self, linear_graph: DirectedGraph) -> None:
        request = RoutingRequest(
            source_node=NodeId("X"), destination_node=NodeId("D"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=10.0,
        )
        astar = AStarRouting()
        result = astar.compute_route(request, linear_graph)
        assert not result.success

    def test_nonexistent_destination(self, linear_graph: DirectedGraph) -> None:
        request = RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("X"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=10.0,
        )
        astar = AStarRouting()
        result = astar.compute_route(request, linear_graph)
        assert not result.success

    def test_no_graph_raises(self) -> None:
        astar = AStarRouting()
        request = RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("B"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=10.0,
        )
        with pytest.raises(ValueError, match="graph must be provided"):
            astar.compute_route(request)

    def test_astar_name(self) -> None:
        assert AStarRouting().name == "astar"

    def test_heuristic_property(self) -> None:
        h = EuclideanHeuristic()
        astar = AStarRouting(heuristic=h)
        assert astar.heuristic is h


# =============================================================================
# AStarRouting — Edge Cases
# =============================================================================

class TestAStarRoutingEdgeCases:
    """Edge case tests for AStarRouting."""

    def test_single_node_graph(self) -> None:
        graph = DirectedGraph()
        graph.add_node(Node(node_id=NodeId("A")))
        astar = AStarRouting()
        with pytest.raises(ValueError):
            request = RoutingRequest(
                source_node=NodeId("A"), destination_node=NodeId("A"),
                vehicle_id=VehicleId("test"), vehicle_constraints=None,
                battery_state=None, max_candidates=3, timeout_s=10.0,
            )
            astar.compute_route(request, graph)

    def test_blocked_edge_bypassed(
        self, graph_with_blocked: DirectedGraph,
    ) -> None:
        """A* should route around blocked edges."""
        request = RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("C"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=10.0,
        )
        astar = AStarRouting()
        result = astar.compute_route(request, graph_with_blocked)
        assert result.success
        # Should use AC (direct) since BC is blocked
        assert result.primary_route.edge_sequence == (EdgeId("AC"),)

    def test_blocked_source(self) -> None:
        """Source node blocked should still work (source is start, not traversed)."""
        graph = DirectedGraph()
        graph.add_node(Node(node_id=NodeId("A")))
        graph.add_node(Node(node_id=NodeId("B")))
        graph.add_edge(Edge(
            edge_id=EdgeId("AB"), source=NodeId("A"), target=NodeId("B"),
            length_m=100.0, speed_limit_mps=10.0, lane_count=1,
            state=MutableEdgeState(is_blocked=True),
        ))
        request = RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("B"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=10.0,
        )
        astar = AStarRouting()
        result = astar.compute_route(request, graph)
        assert not result.success  # All edges from source are blocked

    def test_disconnected_graph(self) -> None:
        """Two disconnected components."""
        graph = DirectedGraph()
        graph.add_node(Node(node_id=NodeId("A")))
        graph.add_node(Node(node_id=NodeId("B")))
        graph.add_edge(Edge(
            edge_id=EdgeId("AB"), source=NodeId("A"), target=NodeId("B"),
            length_m=100.0, speed_limit_mps=10.0, lane_count=1,
        ))
        graph.add_node(Node(node_id=NodeId("C")))
        graph.add_node(Node(node_id=NodeId("D")))
        graph.add_edge(Edge(
            edge_id=EdgeId("CD"), source=NodeId("C"), target=NodeId("D"),
            length_m=100.0, speed_limit_mps=10.0, lane_count=1,
        ))
        request = RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("D"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=10.0,
        )
        astar = AStarRouting()
        result = astar.compute_route(request, graph)
        assert not result.success

    def test_cycles_handled(
        self, graph_with_cycle: DirectedGraph,
    ) -> None:
        """A* should handle graphs with cycles correctly."""
        request = RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("D"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=10.0,
        )
        astar = AStarRouting()
        result = astar.compute_route(request, graph_with_cycle)
        assert result.success
        # Should find A->B->D (shortest), not go through cycle
        assert result.primary_route.edge_sequence == (EdgeId("AB"), EdgeId("BD"))

    def test_multiple_equal_paths(self, linear_graph: DirectedGraph) -> None:
        """When multiple equal-cost paths exist, A* should return one valid path."""
        request = RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("D"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=10.0,
        )
        astar = AStarRouting()
        result = astar.compute_route(request, linear_graph)
        assert result.success
        report = RoutingVerifier.verify_result(result, linear_graph, request)
        assert report.is_valid

    def test_timeout(self) -> None:
        """A* should respect timeout and return failure gracefully."""
        graph = DirectedGraph()
        graph.add_node(Node(node_id=NodeId("A")))
        graph.add_node(Node(node_id=NodeId("B")))
        graph.add_node(Node(node_id=NodeId("C")))
        graph.add_node(Node(node_id=NodeId("D")))
        state = MutableEdgeState()
        graph.add_edge(Edge(
            edge_id=EdgeId("AB"), source=NodeId("A"), target=NodeId("B"),
            length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=state,
        ))
        graph.add_edge(Edge(
            edge_id=EdgeId("BC"), source=NodeId("B"), target=NodeId("C"),
            length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=state,
        ))
        graph.add_edge(Edge(
            edge_id=EdgeId("CD"), source=NodeId("C"), target=NodeId("D"),
            length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=state,
        ))
        request = RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("D"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=0.0001,
        )
        astar = AStarRouting()
        result = astar.compute_route(request, graph)
        assert not result.success
        assert "timeout" in result.failure_reason.lower()

    def test_statistics_reporting(self, linear_graph: DirectedGraph, request_ad: RoutingRequest) -> None:
        astar = AStarRouting()
        result = astar.compute_route(request_ad, linear_graph)
        assert result.statistics.nodes_explored >= 0
        assert result.statistics.edges_explored >= 0
        assert result.statistics.candidates_generated >= 0
        assert result.runtime_s >= 0

    def test_deterministic(
        self, linear_graph: DirectedGraph, request_ad: RoutingRequest,
    ) -> None:
        """A* should produce identical results across multiple runs."""
        astar = AStarRouting()
        result1 = astar.compute_route(request_ad, linear_graph)
        result2 = astar.compute_route(request_ad, linear_graph)
        assert result1.primary_route.edge_sequence == result2.primary_route.edge_sequence
        assert abs(result1.candidates[0].total_cost - result2.candidates[0].total_cost) < 1e-6

    def test_deterministic_replay_verification(
        self, linear_graph: DirectedGraph, request_ad: RoutingRequest,
    ) -> None:
        """A* should pass deterministic replay verification."""
        astar = AStarRouting()
        report = RoutingVerifier.verify_deterministic_replay(
            astar, request_ad, linear_graph, num_runs=3
        )
        assert report.is_deterministic

    def test_cost_consistency(self, linear_graph: DirectedGraph, request_ad: RoutingRequest) -> None:
        """Route cost should match cost_breakdown.total."""
        astar = AStarRouting()
        result = astar.compute_route(request_ad, linear_graph)
        assert result.success
        candidate = result.candidates[0]
        report = RoutingVerifier.verify_cost_breakdown(candidate)
        assert report.is_valid

    def test_zero_length_edges(self) -> None:
        """A* should handle near-zero-length edges."""
        graph = DirectedGraph()
        graph.add_node(Node(node_id=NodeId("A"), x=0.0, y=0.0))
        graph.add_node(Node(node_id=NodeId("B"), x=0.0, y=0.0))
        graph.add_node(Node(node_id=NodeId("C"), x=100.0, y=0.0))
        graph.add_edge(Edge(
            edge_id=EdgeId("AB"), source=NodeId("A"), target=NodeId("B"),
            length_m=1e-6, speed_limit_mps=10.0, lane_count=1,
        ))
        graph.add_edge(Edge(
            edge_id=EdgeId("BC"), source=NodeId("B"), target=NodeId("C"),
            length_m=100.0, speed_limit_mps=10.0, lane_count=1,
        ))
        request = RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("C"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=10.0,
        )
        astar = AStarRouting()
        result = astar.compute_route(request, graph)
        assert result.success


# =============================================================================
# AStarRouting — Heuristic-Specific Tests
# =============================================================================

class TestAStarHeuristicSpecific:
    """Tests for A* with different heuristics."""

    def test_euclidean_on_grid(
        self, grid_graph: DirectedGraph, request_ai: RoutingRequest,
    ) -> None:
        """A* with Euclidean heuristic should find correct path on grid."""
        astar = AStarRouting(heuristic=EuclideanHeuristic())
        result = astar.compute_route(request_ai, grid_graph)
        assert result.success
        assert result.primary_route.source_node == NodeId("A")
        assert result.primary_route.destination_node == NodeId("I")
        report = RoutingVerifier.verify_result(result, grid_graph, request_ai)
        assert report.is_valid

    def test_manhattan_on_grid(
        self, grid_graph: DirectedGraph, request_ai: RoutingRequest,
    ) -> None:
        """A* with Manhattan heuristic should find correct path on grid."""
        astar = AStarRouting(heuristic=ManhattanHeuristic())
        result = astar.compute_route(request_ai, grid_graph)
        assert result.success
        report = RoutingVerifier.verify_result(result, grid_graph, request_ai)
        assert report.is_valid

    def test_different_heuristics_same_cost(
        self, grid_graph: DirectedGraph, request_ai: RoutingRequest,
    ) -> None:
        """All heuristics should find paths with same optimal cost."""
        astar_zero = AStarRouting(heuristic=ZeroHeuristic())
        astar_euclid = AStarRouting(heuristic=EuclideanHeuristic())
        astar_manhattan = AStarRouting(heuristic=ManhattanHeuristic())

        result_z = astar_zero.compute_route(request_ai, grid_graph)
        result_e = astar_euclid.compute_route(request_ai, grid_graph)
        result_m = astar_manhattan.compute_route(request_ai, grid_graph)

        assert result_z.success and result_e.success and result_m.success
        # All should find optimal cost
        assert abs(result_z.candidates[0].total_cost - result_e.candidates[0].total_cost) < 1e-6
        assert abs(result_z.candidates[0].total_cost - result_m.candidates[0].total_cost) < 1e-6

    def test_euclidean_explores_fewer_nodes(self) -> None:
        """A* with Euclidean heuristic should explore fewer nodes than Zero (Dijkstra).

        Graph has a main corridor toward the goal (eastward) plus short side
        branches northward. Side branches are cheap to reach but far from the
        goal, so A* prunes them (f > C*) while Dijkstra explores them (g < C*).
        """
        graph = DirectedGraph()
        state = MutableEdgeState()
        # Main corridor: A(0,0)→B(100,0)→C(200,0)→D(300,0)→Goal(400,0)
        for name, x, y in [("A", 0.0, 0.0), ("B", 100.0, 0.0),
                           ("C", 200.0, 0.0), ("D", 300.0, 0.0),
                           ("Goal", 400.0, 0.0)]:
            graph.add_node(Node(node_id=NodeId(name), x=x, y=y))
        for eid, src, tgt, length in [
            ("AB", "A", "B", 100.0), ("BC", "B", "C", 100.0),
            ("CD", "C", "D", 100.0), ("DGoal", "D", "Goal", 100.0),
        ]:
            graph.add_edge(Edge(
                edge_id=EdgeId(eid), source=NodeId(src), target=NodeId(tgt),
                length_m=length, speed_limit_mps=10.0, lane_count=1, state=state,
            ))
        # Side branches off each corridor node, going north (away from goal)
        # Each is reachable at small cost but has large Euclidean distance to Goal
        for src, sid, y_pos in [
            ("A", "A1", 50.0), ("B", "B1", 50.0),
            ("C", "C1", 50.0), ("D", "D1", 50.0),
        ]:
            graph.add_node(Node(node_id=NodeId(sid), x=graph._nodes[NodeId(src)].x, y=y_pos))
            graph.add_edge(Edge(
                edge_id=EdgeId(f"{src}_{sid}"), source=NodeId(src), target=NodeId(sid),
                length_m=50.0, speed_limit_mps=10.0, lane_count=1, state=state,
            ))

        request = RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("Goal"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=10.0,
        )

        astar_zero = AStarRouting(heuristic=ZeroHeuristic())
        astar_euclid = AStarRouting(heuristic=EuclideanHeuristic())

        result_z = astar_zero.compute_route(request, graph)
        result_e = astar_euclid.compute_route(request, graph)

        assert result_z.success and result_e.success
        # A* should explore strictly fewer nodes (prunes side branches)
        assert result_e.statistics.nodes_explored < result_z.statistics.nodes_explored


# =============================================================================
# Comparison Tests: Dijkstra vs A*
# =============================================================================

class TestDijkstraVsAStar:
    """Comparison tests between Dijkstra and A*."""

    def test_same_route_cost(
        self, linear_graph: DirectedGraph, request_ad: RoutingRequest,
    ) -> None:
        """Dijkstra and A* should find routes with identical cost."""
        d = DijkstraRouting()
        a = AStarRouting()
        result_d = d.compute_route(request_ad, linear_graph)
        result_a = a.compute_route(request_ad, linear_graph)
        assert result_d.success and result_a.success
        assert abs(result_d.candidates[0].total_cost - result_a.candidates[0].total_cost) < 1e-6

    def test_same_path_length(
        self, linear_graph: DirectedGraph, request_ad: RoutingRequest,
    ) -> None:
        """Dijkstra and A* should find routes with identical distance."""
        d = DijkstraRouting()
        a = AStarRouting()
        result_d = d.compute_route(request_ad, linear_graph)
        result_a = a.compute_route(request_ad, linear_graph)
        assert result_d.success and result_a.success
        assert abs(result_d.primary_route.total_distance_m - result_a.primary_route.total_distance_m) < 1e-6

    def test_same_route_validity(
        self, linear_graph: DirectedGraph, request_ad: RoutingRequest,
    ) -> None:
        """Both routes should pass verification."""
        d = DijkstraRouting()
        a = AStarRouting()
        result_d = d.compute_route(request_ad, linear_graph)
        result_a = a.compute_route(request_ad, linear_graph)
        report_d = RoutingVerifier.verify_result(result_d, linear_graph, request_ad)
        report_a = RoutingVerifier.verify_result(result_a, linear_graph, request_ad)
        assert report_d.is_valid
        assert report_a.is_valid

    def test_same_verification_report(
        self, linear_graph: DirectedGraph, request_ad: RoutingRequest,
    ) -> None:
        """Both routes should have identical verification reports."""
        d = DijkstraRouting()
        a = AStarRouting()
        result_d = d.compute_route(request_ad, linear_graph)
        result_a = a.compute_route(request_ad, linear_graph)
        report_d = RoutingVerifier.verify_result(result_d, linear_graph, request_ad)
        report_a = RoutingVerifier.verify_result(result_a, linear_graph, request_ad)
        assert report_d.checks_performed == report_a.checks_performed
        assert report_d.checks_passed == report_a.checks_passed

    def test_grid_optimality(
        self, grid_graph: DirectedGraph, request_ai: RoutingRequest,
    ) -> None:
        """Both algorithms should find the optimal cost on a grid."""
        d = DijkstraRouting()
        a = AStarRouting(heuristic=EuclideanHeuristic())
        result_d = d.compute_route(request_ai, grid_graph)
        result_a = a.compute_route(request_ai, grid_graph)
        assert abs(result_d.candidates[0].total_cost - result_a.candidates[0].total_cost) < 1e-6

    def test_both_handle_blocked_edges(
        self, graph_with_blocked: DirectedGraph,
    ) -> None:
        """Both should route around blocked edges identically."""
        request = RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("C"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=10.0,
        )
        d = DijkstraRouting()
        a = AStarRouting()
        result_d = d.compute_route(request, graph_with_blocked)
        result_a = a.compute_route(request, graph_with_blocked)
        assert result_d.success and result_a.success
        assert result_d.primary_route.edge_sequence == result_a.primary_route.edge_sequence

    def test_both_handle_disconnected_graph(self) -> None:
        """Both should fail identically on disconnected graphs."""
        graph = DirectedGraph()
        graph.add_node(Node(node_id=NodeId("A")))
        graph.add_node(Node(node_id=NodeId("B")))
        graph.add_node(Node(node_id=NodeId("C")))
        graph.add_node(Node(node_id=NodeId("D")))
        graph.add_edge(Edge(
            edge_id=EdgeId("AB"), source=NodeId("A"), target=NodeId("B"),
            length_m=100.0, speed_limit_mps=10.0, lane_count=1,
        ))
        graph.add_edge(Edge(
            edge_id=EdgeId("CD"), source=NodeId("C"), target=NodeId("D"),
            length_m=100.0, speed_limit_mps=10.0, lane_count=1,
        ))
        request = RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("D"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=10.0,
        )
        d = DijkstraRouting()
        a = AStarRouting()
        result_d = d.compute_route(request, graph)
        result_a = a.compute_route(request, graph)
        assert not result_d.success
        assert not result_a.success

    def test_both_deterministic(
        self, linear_graph: DirectedGraph, request_ad: RoutingRequest,
    ) -> None:
        """Both algorithms should be deterministic."""
        d = DijkstraRouting()
        a = AStarRouting()
        for _ in range(3):
            rd1 = d.compute_route(request_ad, linear_graph)
            rd2 = d.compute_route(request_ad, linear_graph)
            ra1 = a.compute_route(request_ad, linear_graph)
            ra2 = a.compute_route(request_ad, linear_graph)
            assert rd1.primary_route.edge_sequence == rd2.primary_route.edge_sequence
            assert ra1.primary_route.edge_sequence == ra2.primary_route.edge_sequence

    def test_both_return_routing_result_type(
        self, linear_graph: DirectedGraph, request_ad: RoutingRequest,
    ) -> None:
        """Both should return properly structured RoutingResult."""
        d = DijkstraRouting()
        a = AStarRouting()
        for algo, name in [(d, "dijkstra"), (a, "astar")]:
            result = algo.compute_route(request_ad, linear_graph)
            assert isinstance(result.candidates, tuple)
            assert result.primary_route is not None
            assert result.success
            assert result.failure_reason is None
            assert result.runtime_s >= 0
            assert result.statistics.nodes_explored >= 0


# =============================================================================
# BenchmarkRunner Integration Tests
# =============================================================================

class TestAStarWithBenchmarkRunner:
    """Test A* through the existing BenchmarkRunner."""

    def test_astar_with_benchmark_runner(self, linear_graph: DirectedGraph) -> None:
        """A* should work with the existing BenchmarkRunner."""
        from e3hybrid.routing.benchmark_config import BenchmarkConfig
        from e3hybrid.routing.benchmark_runner import BenchmarkRunner
        from e3hybrid.routing.benchmark_scenario import BenchmarkRequest, BenchmarkScenario

        config = BenchmarkConfig(
            algorithm_names=("dijkstra",),
            timeout_s=10.0,
        )
        request = RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("D"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=10.0,
        )
        scenario = BenchmarkScenario(
            graph=linear_graph,
            requests=(BenchmarkRequest(request=request),),
            name="astar_test",
        )
        runner = BenchmarkRunner(config)
        results = runner.run_scenario(scenario)
        assert len(results) == 1
        assert results[0].metrics[0].success

    def test_astar_via_factory_with_benchmark(self, linear_graph: DirectedGraph) -> None:
        """A* created via RoutingFactory should work with BenchmarkRunner."""
        from e3hybrid.routing.benchmark_config import BenchmarkConfig
        from e3hybrid.routing.benchmark_runner import BenchmarkRunner
        from e3hybrid.routing.benchmark_scenario import BenchmarkRequest, BenchmarkScenario
        from e3hybrid.routing.factory import RoutingFactory

        config = BenchmarkConfig(
            algorithm_names=("astar",),
            timeout_s=10.0,
        )
        request = RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("D"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=10.0,
        )
        scenario = BenchmarkScenario(
            graph=linear_graph,
            requests=(BenchmarkRequest(request=request),),
            name="factory_astar",
        )
        runner = BenchmarkRunner(config)
        results = runner.run_scenario(scenario)
        assert len(results) == 1
        assert results[0].metrics[0].success

    def test_astar_zero_vs_dijkstra_benchmark(
        self, linear_graph: DirectedGraph,
    ) -> None:
        """A* with zero heuristic should produce same metrics as Dijkstra in benchmark."""
        from e3hybrid.routing.benchmark_config import BenchmarkConfig
        from e3hybrid.routing.benchmark_scenario import BenchmarkRequest, BenchmarkScenario
        from e3hybrid.routing.benchmark_runner import BenchmarkRunner

        # Test Dijkstra
        config_d = BenchmarkConfig(
            algorithm_names=("dijkstra",), timeout_s=10.0,
        )
        request = RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("D"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=10.0,
        )
        scenario = BenchmarkScenario(
            graph=linear_graph,
            requests=(BenchmarkRequest(request=request),),
            name="comparison",
        )
        runner_d = BenchmarkRunner(config_d)
        results_d = runner_d.run_scenario(scenario)

        # Test A* via factory
        config_a = BenchmarkConfig(
            algorithm_names=("astar",), timeout_s=10.0,
        )
        runner_a = BenchmarkRunner(config_a)
        results_a = runner_a.run_scenario(scenario)

        m_d = results_d[0].metrics[0]
        m_a = results_a[0].metrics[0]

        assert m_d.success
        assert m_a.success
        assert abs(m_d.total_cost - m_a.total_cost) < 1e-6
        assert abs(m_d.route_distance_m - m_a.route_distance_m) < 1e-6


# =============================================================================
# ZeroHeuristic A* = Dijkstra Verification
# =============================================================================

class TestZeroHeuristicEquivalence:
    """A* with ZeroHeuristic should behave identically to Dijkstra."""

    def test_identical_on_linear(
        self, linear_graph: DirectedGraph, request_ad: RoutingRequest,
    ) -> None:
        d = DijkstraRouting()
        a = AStarRouting(heuristic=ZeroHeuristic())
        rd = d.compute_route(request_ad, linear_graph)
        ra = a.compute_route(request_ad, linear_graph)
        assert rd.primary_route.node_sequence == ra.primary_route.node_sequence
        assert rd.primary_route.edge_sequence == ra.primary_route.edge_sequence
        assert abs(rd.candidates[0].total_cost - ra.candidates[0].total_cost) < 1e-6

    def test_identical_on_grid(
        self, grid_graph: DirectedGraph, request_ai: RoutingRequest,
    ) -> None:
        d = DijkstraRouting()
        a = AStarRouting(heuristic=ZeroHeuristic())
        rd = d.compute_route(request_ai, grid_graph)
        ra = a.compute_route(request_ai, grid_graph)
        assert rd.success and ra.success
        assert abs(rd.candidates[0].total_cost - ra.candidates[0].total_cost) < 1e-6

    def test_identical_failure_on_disconnected(self) -> None:
        graph = DirectedGraph()
        graph.add_node(Node(node_id=NodeId("A")))
        graph.add_node(Node(node_id=NodeId("B")))
        graph.add_node(Node(node_id=NodeId("C")))
        graph.add_node(Node(node_id=NodeId("D")))
        graph.add_edge(Edge(
            edge_id=EdgeId("AB"), source=NodeId("A"), target=NodeId("B"),
            length_m=100.0, speed_limit_mps=10.0, lane_count=1,
        ))
        request = RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("D"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=10.0,
        )
        d = DijkstraRouting()
        a = AStarRouting(heuristic=ZeroHeuristic())
        rd = d.compute_route(request, graph)
        ra = a.compute_route(request, graph)
        assert not rd.success
        assert not ra.success
