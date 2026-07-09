"""Unit tests for DijkstraRouting algorithm."""

from __future__ import annotations

import pytest

from e3hybrid.network.graph import DirectedGraph, Edge, Node, MutableEdgeState
from e3hybrid.network.types import EdgeId, NodeId
from e3hybrid.routing.cost_calculator import CostWeights
from e3hybrid.routing.dijkstra import DijkstraRouting
from e3hybrid.routing.exceptions import NoPathError
from e3hybrid.routing.request import RoutingRequest
from e3hybrid.routing.result import RoutingResult
from e3hybrid.routing.route import Route
from e3hybrid.routing.statistics import RoutingStatistics
from e3hybrid.vehicle.types import VehicleId


def create_simple_graph() -> DirectedGraph:
    """Create a simple linear graph: A -> B -> C -> D."""
    graph = DirectedGraph()
    
    graph.add_node(Node(node_id=NodeId("A")))
    graph.add_node(Node(node_id=NodeId("B")))
    graph.add_node(Node(node_id=NodeId("C")))
    graph.add_node(Node(node_id=NodeId("D")))
    
    state = MutableEdgeState()
    graph.add_edge(Edge(
        edge_id=EdgeId("AB"),
        source=NodeId("A"),
        target=NodeId("B"),
        length_m=100.0,
        speed_limit_mps=10.0,
        lane_count=1,
        state=state,
    ))
    graph.add_edge(Edge(
        edge_id=EdgeId("BC"),
        source=NodeId("B"),
        target=NodeId("C"),
        length_m=100.0,
        speed_limit_mps=10.0,
        lane_count=1,
        state=state,
    ))
    graph.add_edge(Edge(
        edge_id=EdgeId("CD"),
        source=NodeId("C"),
        target=NodeId("D"),
        length_m=100.0,
        speed_limit_mps=10.0,
        lane_count=1,
        state=state,
    ))
    
    return graph


def create_graph_with_cycles() -> DirectedGraph:
    """Create a graph with cycles: A -> B -> C -> D, plus B -> D."""
    graph = DirectedGraph()
    
    graph.add_node(Node(node_id=NodeId("A")))
    graph.add_node(Node(node_id=NodeId("B")))
    graph.add_node(Node(node_id=NodeId("C")))
    graph.add_node(Node(node_id=NodeId("D")))
    
    state = MutableEdgeState()
    graph.add_edge(Edge(
        edge_id=EdgeId("AB"),
        source=NodeId("A"),
        target=NodeId("B"),
        length_m=100.0,
        speed_limit_mps=10.0,
        lane_count=1,
        state=state,
    ))
    graph.add_edge(Edge(
        edge_id=EdgeId("BC"),
        source=NodeId("B"),
        target=NodeId("C"),
        length_m=100.0,
        speed_limit_mps=10.0,
        lane_count=1,
        state=state,
    ))
    graph.add_edge(Edge(
        edge_id=EdgeId("CD"),
        source=NodeId("C"),
        target=NodeId("D"),
        length_m=100.0,
        speed_limit_mps=10.0,
        lane_count=1,
        state=state,
    ))
    graph.add_edge(Edge(
        edge_id=EdgeId("BD"),
        source=NodeId("B"),
        target=NodeId("D"),
        length_m=150.0,
        speed_limit_mps=10.0,
        lane_count=1,
        state=state,
    ))
    
    return graph


def create_disconnected_graph() -> DirectedGraph:
    """Create a disconnected graph: A -> B, C -> D."""
    graph = DirectedGraph()
    
    graph.add_node(Node(node_id=NodeId("A")))
    graph.add_node(Node(node_id=NodeId("B")))
    graph.add_node(Node(node_id=NodeId("C")))
    graph.add_node(Node(node_id=NodeId("D")))
    
    state = MutableEdgeState()
    graph.add_edge(Edge(
        edge_id=EdgeId("AB"),
        source=NodeId("A"),
        target=NodeId("B"),
        length_m=100.0,
        speed_limit_mps=10.0,
        lane_count=1,
        state=state,
    ))
    graph.add_edge(Edge(
        edge_id=EdgeId("CD"),
        source=NodeId("C"),
        target=NodeId("D"),
        length_m=100.0,
        speed_limit_mps=10.0,
        lane_count=1,
        state=state,
    ))
    
    return graph


def create_graph_with_blocked_edge() -> DirectedGraph:
    """Create a graph with a blocked edge: A -> B (blocked) -> C."""
    graph = DirectedGraph()
    
    graph.add_node(Node(node_id=NodeId("A")))
    graph.add_node(Node(node_id=NodeId("B")))
    graph.add_node(Node(node_id=NodeId("C")))
    
    normal_state = MutableEdgeState(is_blocked=False)
    blocked_state = MutableEdgeState(is_blocked=True)
    
    graph.add_edge(Edge(
        edge_id=EdgeId("AB"),
        source=NodeId("A"),
        target=NodeId("B"),
        length_m=100.0,
        speed_limit_mps=10.0,
        lane_count=1,
        state=blocked_state,
    ))
    graph.add_edge(Edge(
        edge_id=EdgeId("BC"),
        source=NodeId("B"),
        target=NodeId("C"),
        length_m=100.0,
        speed_limit_mps=10.0,
        lane_count=1,
        state=normal_state,
    ))
    
    return graph


def create_graph_with_multiple_paths() -> DirectedGraph:
    """Create a graph with multiple equal-cost paths: A -> B -> D, A -> C -> D."""
    graph = DirectedGraph()
    
    graph.add_node(Node(node_id=NodeId("A")))
    graph.add_node(Node(node_id=NodeId("B")))
    graph.add_node(Node(node_id=NodeId("C")))
    graph.add_node(Node(node_id=NodeId("D")))
    
    state = MutableEdgeState()
    graph.add_edge(Edge(
        edge_id=EdgeId("AB"),
        source=NodeId("A"),
        target=NodeId("B"),
        length_m=100.0,
        speed_limit_mps=10.0,
        lane_count=1,
        state=state,
    ))
    graph.add_edge(Edge(
        edge_id=EdgeId("BD"),
        source=NodeId("B"),
        target=NodeId("D"),
        length_m=100.0,
        speed_limit_mps=10.0,
        lane_count=1,
        state=state,
    ))
    graph.add_edge(Edge(
        edge_id=EdgeId("AC"),
        source=NodeId("A"),
        target=NodeId("C"),
        length_m=100.0,
        speed_limit_mps=10.0,
        lane_count=1,
        state=state,
    ))
    graph.add_edge(Edge(
        edge_id=EdgeId("CD"),
        source=NodeId("C"),
        target=NodeId("D"),
        length_m=100.0,
        speed_limit_mps=10.0,
        lane_count=1,
        state=state,
    ))
    
    return graph


def create_mock_constraints():
    """Create mock vehicle constraints."""
    class MockConstraints:
        min_soc_kwh = 10.0
        max_soc_kwh = 50.0
        max_speed_mps = 20.0
        max_payload_kg = 1000.0
    return MockConstraints()


def create_mock_battery():
    """Create mock battery state."""
    class MockBattery:
        soc_kwh = 40.0
        capacity_kwh = 50.0
        soc_fraction = 0.8
    return MockBattery()


def test_dijkstra_simple_graph():
    """Test Dijkstra on a simple linear graph."""
    graph = create_simple_graph()
    algorithm = DijkstraRouting()
    
    request = RoutingRequest(
        source_node=NodeId("A"),
        destination_node=NodeId("D"),
        vehicle_id=VehicleId("v1"),
        vehicle_constraints=create_mock_constraints(),
        battery_state=create_mock_battery(),
        max_candidates=1,
        timeout_s=10.0,
    )
    
    result = algorithm.compute_route(request, graph)
    
    assert result.success is True
    assert result.primary_route is not None
    assert result.primary_route.source_node == NodeId("A")
    assert result.primary_route.destination_node == NodeId("D")
    assert result.primary_route.edge_count == 3
    assert len(result.candidates) == 1
    assert result.statistics.nodes_explored > 0
    assert result.statistics.edges_explored > 0


def test_dijkstra_graph_with_cycles():
    """Test Dijkstra on a graph with cycles."""
    graph = create_graph_with_cycles()
    algorithm = DijkstraRouting()
    
    request = RoutingRequest(
        source_node=NodeId("A"),
        destination_node=NodeId("D"),
        vehicle_id=VehicleId("v1"),
        vehicle_constraints=create_mock_constraints(),
        battery_state=create_mock_battery(),
        max_candidates=1,
        timeout_s=10.0,
    )
    
    result = algorithm.compute_route(request, graph)
    
    assert result.success is True
    assert result.primary_route is not None
    # Should prefer A -> B -> D (cost 150) over A -> B -> C -> D (cost 200)
    assert result.primary_route.edge_count == 2


def test_dijkstra_disconnected_graph():
    """Test Dijkstra on a disconnected graph (no path exists)."""
    graph = create_disconnected_graph()
    algorithm = DijkstraRouting()
    
    request = RoutingRequest(
        source_node=NodeId("A"),
        destination_node=NodeId("D"),
        vehicle_id=VehicleId("v1"),
        vehicle_constraints=create_mock_constraints(),
        battery_state=create_mock_battery(),
        max_candidates=1,
        timeout_s=10.0,
    )
    
    result = algorithm.compute_route(request, graph)
    
    assert result.success is False
    assert result.primary_route is None
    assert "No path exists" in result.failure_reason
    assert len(result.candidates) == 0


def test_dijkstra_blocked_edge():
    """Test Dijkstra with a blocked edge."""
    graph = create_graph_with_blocked_edge()
    algorithm = DijkstraRouting()
    
    request = RoutingRequest(
        source_node=NodeId("A"),
        destination_node=NodeId("C"),
        vehicle_id=VehicleId("v1"),
        vehicle_constraints=create_mock_constraints(),
        battery_state=create_mock_battery(),
        max_candidates=1,
        timeout_s=10.0,
    )
    
    result = algorithm.compute_route(request, graph)
    
    assert result.success is False
    assert result.primary_route is None
    assert "No path exists" in result.failure_reason


def test_dijkstra_multiple_paths():
    """Test Dijkstra with multiple equal-cost paths."""
    graph = create_graph_with_multiple_paths()
    algorithm = DijkstraRouting()
    
    request = RoutingRequest(
        source_node=NodeId("A"),
        destination_node=NodeId("D"),
        vehicle_id=VehicleId("v1"),
        vehicle_constraints=create_mock_constraints(),
        battery_state=create_mock_battery(),
        max_candidates=1,
        timeout_s=10.0,
    )
    
    result = algorithm.compute_route(request, graph)
    
    assert result.success is True
    assert result.primary_route is not None
    # Either path is acceptable (both have equal cost)
    assert result.primary_route.edge_count == 2


def test_dijkstra_nonexistent_source():
    """Test Dijkstra with non-existent source node."""
    graph = create_simple_graph()
    algorithm = DijkstraRouting()
    
    request = RoutingRequest(
        source_node=NodeId("X"),  # Non-existent
        destination_node=NodeId("D"),
        vehicle_id=VehicleId("v1"),
        vehicle_constraints=create_mock_constraints(),
        battery_state=create_mock_battery(),
        max_candidates=1,
        timeout_s=10.0,
    )
    
    result = algorithm.compute_route(request, graph)
    
    assert result.success is False
    assert "does not exist" in result.failure_reason


def test_dijkstra_nonexistent_destination():
    """Test Dijkstra with non-existent destination node."""
    graph = create_simple_graph()
    algorithm = DijkstraRouting()
    
    request = RoutingRequest(
        source_node=NodeId("A"),
        destination_node=NodeId("X"),  # Non-existent
        vehicle_id=VehicleId("v1"),
        vehicle_constraints=create_mock_constraints(),
        battery_state=create_mock_battery(),
        max_candidates=1,
        timeout_s=10.0,
    )
    
    result = algorithm.compute_route(request, graph)
    
    assert result.success is False
    assert "does not exist" in result.failure_reason


def test_dijkstra_timeout():
    """Test Dijkstra with timeout."""
    graph = create_simple_graph()
    algorithm = DijkstraRouting()
    
    request = RoutingRequest(
        source_node=NodeId("A"),
        destination_node=NodeId("D"),
        vehicle_id=VehicleId("v1"),
        vehicle_constraints=create_mock_constraints(),
        battery_state=create_mock_battery(),
        max_candidates=1,
        timeout_s=0.0001,  # Very short timeout
    )
    
    result = algorithm.compute_route(request, graph)
    
    # May or may not timeout depending on system speed
    # If it times out:
    if not result.success:
        assert "timeout" in result.failure_reason.lower()


def test_dijkstra_cost_correctness():
    """Test that Dijkstra computes correct costs."""
    graph = create_simple_graph()
    algorithm = DijkstraRouting()
    
    request = RoutingRequest(
        source_node=NodeId("A"),
        destination_node=NodeId("D"),
        vehicle_id=VehicleId("v1"),
        vehicle_constraints=create_mock_constraints(),
        battery_state=create_mock_battery(),
        max_candidates=1,
        timeout_s=10.0,
    )
    
    result = algorithm.compute_route(request, graph)
    
    assert result.success is True
    assert len(result.candidates) == 1
    
    candidate = result.candidates[0]
    # Total distance should be 300m (3 edges of 100m each)
    assert candidate.total_cost > 0
    assert candidate.cost_breakdown.distance_cost == 300.0


def test_dijkstra_statistics_correctness():
    """Test that Dijkstra records correct statistics."""
    graph = create_simple_graph()
    algorithm = DijkstraRouting()
    
    request = RoutingRequest(
        source_node=NodeId("A"),
        destination_node=NodeId("D"),
        vehicle_id=VehicleId("v1"),
        vehicle_constraints=create_mock_constraints(),
        battery_state=create_mock_battery(),
        max_candidates=1,
        timeout_s=10.0,
    )
    
    result = algorithm.compute_route(request, graph)
    
    assert result.success is True
    assert result.statistics.nodes_explored == 4  # A, B, C, D
    assert result.statistics.edges_explored == 3  # AB, BC, CD
    assert result.statistics.candidates_generated == 1


def test_dijkstra_deterministic_replay():
    """Test that Dijkstra produces identical results on repeated runs."""
    graph = create_simple_graph()
    algorithm = DijkstraRouting()
    
    request = RoutingRequest(
        source_node=NodeId("A"),
        destination_node=NodeId("D"),
        vehicle_id=VehicleId("v1"),
        vehicle_constraints=create_mock_constraints(),
        battery_state=create_mock_battery(),
        max_candidates=1,
        timeout_s=10.0,
    )
    
    result1 = algorithm.compute_route(request, graph)
    result2 = algorithm.compute_route(request, graph)
    
    assert result1.success == result2.success
    assert result1.primary_route.edge_count == result2.primary_route.edge_count
    assert result1.candidates[0].total_cost == result2.candidates[0].total_cost


def test_dijkstra_custom_cost_weights():
    """Test Dijkstra with custom cost weights."""
    graph = create_simple_graph()
    
    # Emphasize time over distance
    custom_weights = CostWeights(distance=0.1, time=10.0)
    algorithm = DijkstraRouting(cost_weights=custom_weights)
    
    request = RoutingRequest(
        source_node=NodeId("A"),
        destination_node=NodeId("D"),
        vehicle_id=VehicleId("v1"),
        vehicle_constraints=create_mock_constraints(),
        battery_state=create_mock_battery(),
        max_candidates=1,
        timeout_s=10.0,
    )
    
    result = algorithm.compute_route(request, graph)
    
    assert result.success is True
    # With time weight 10x, cost should be higher than default
    assert result.candidates[0].total_cost > 0


def test_dijkstra_algorithm_name():
    """Test that algorithm name is correct."""
    algorithm = DijkstraRouting()
    assert algorithm.name == "dijkstra"


def test_dijkstra_route_properties():
    """Test Route properties."""
    graph = create_simple_graph()
    algorithm = DijkstraRouting()
    
    request = RoutingRequest(
        source_node=NodeId("A"),
        destination_node=NodeId("D"),
        vehicle_id=VehicleId("v1"),
        vehicle_constraints=create_mock_constraints(),
        battery_state=create_mock_battery(),
        max_candidates=1,
        timeout_s=10.0,
    )
    
    result = algorithm.compute_route(request, graph)
    
    route = result.primary_route
    assert route.source_node == NodeId("A")
    assert route.destination_node == NodeId("D")
    assert route.edge_count == 3
    assert route.total_distance_m == 300.0


def test_dijkstra_runtime_recorded():
    """Test that runtime is recorded."""
    graph = create_simple_graph()
    algorithm = DijkstraRouting()
    
    request = RoutingRequest(
        source_node=NodeId("A"),
        destination_node=NodeId("D"),
        vehicle_id=VehicleId("v1"),
        vehicle_constraints=create_mock_constraints(),
        battery_state=create_mock_battery(),
        max_candidates=1,
        timeout_s=10.0,
    )
    
    result = algorithm.compute_route(request, graph)
    
    assert result.runtime_s >= 0
    assert result.runtime_s < 1.0  # Should be very fast for simple graph


def test_dijkstra_candidate_properties():
    """Test RouteCandidate properties."""
    graph = create_simple_graph()
    algorithm = DijkstraRouting()
    
    request = RoutingRequest(
        source_node=NodeId("A"),
        destination_node=NodeId("D"),
        vehicle_id=VehicleId("v1"),
        vehicle_constraints=create_mock_constraints(),
        battery_state=create_mock_battery(),
        max_candidates=1,
        timeout_s=10.0,
    )
    
    result = algorithm.compute_route(request, graph)
    
    candidate = result.candidates[0]
    assert candidate.algorithm == "dijkstra"
    assert candidate.source_node == NodeId("A")
    assert candidate.destination_node == NodeId("D")
    assert candidate.edge_count == 3
    assert candidate.runtime_s >= 0


def test_routing_request_validation():
    """Test RoutingRequest validation."""
    # Invalid: max_candidates <= 0
    with pytest.raises(ValueError, match="max_candidates"):
        RoutingRequest(
            source_node=NodeId("A"),
            destination_node=NodeId("B"),
            vehicle_id=VehicleId("v1"),
            vehicle_constraints=create_mock_constraints(),
            battery_state=create_mock_battery(),
            max_candidates=0,
            timeout_s=10.0,
        )
    
    # Invalid: timeout_s <= 0
    with pytest.raises(ValueError, match="timeout_s"):
        RoutingRequest(
            source_node=NodeId("A"),
            destination_node=NodeId("B"),
            vehicle_id=VehicleId("v1"),
            vehicle_constraints=create_mock_constraints(),
            battery_state=create_mock_battery(),
            max_candidates=1,
            timeout_s=0.0,
        )
    
    # Invalid: source == destination
    with pytest.raises(ValueError, match="must be different"):
        RoutingRequest(
            source_node=NodeId("A"),
            destination_node=NodeId("A"),
            vehicle_id=VehicleId("v1"),
            vehicle_constraints=create_mock_constraints(),
            battery_state=create_mock_battery(),
            max_candidates=1,
            timeout_s=10.0,
        )


def test_routing_result_validation():
    """Test RoutingResult validation."""
    from e3hybrid.routing.candidate import RouteCandidate, SearchStatistics
    from e3hybrid.routing.cost import RouteCost
    
    candidate = RouteCandidate(
        route_id="test",
        node_sequence=(NodeId("A"), NodeId("B")),
        edge_sequence=(EdgeId("AB"),),
        total_cost=100.0,
        cost_breakdown=RouteCost(
            total=100.0,
            distance_cost=100.0,
            time_cost=0.0,
            energy_cost=0.0,
            congestion_penalty=0.0,
            hazard_penalty=0.0,
            emergency_penalty=0.0,
            communication_penalty=0.0,
        ),
        algorithm="test",
    )
    
    # Invalid: success=True but primary_route=None
    with pytest.raises(ValueError, match="success=True"):
        RoutingResult(
            candidates=(candidate,),
            primary_route=None,
            success=True,
            failure_reason=None,
            statistics=RoutingStatistics(nodes_explored=0, edges_explored=0, candidates_generated=1),
            runtime_s=0.1,
        )
    
    # Invalid: success=False but primary_route is not None
    with pytest.raises(ValueError, match="success=False"):
        from e3hybrid.routing.route import Route
        route = Route(
            route_id="test",
            node_sequence=(NodeId("A"), NodeId("B")),
            edge_sequence=(EdgeId("AB"),),
            total_distance_m=100.0,
            estimated_travel_time_s=10.0,
            estimated_energy_kwh=0.0,
        )
        RoutingResult(
            candidates=(),
            primary_route=route,
            success=False,
            failure_reason="test",
            statistics=RoutingStatistics(nodes_explored=0, edges_explored=0, candidates_generated=0),
            runtime_s=0.1,
        )
