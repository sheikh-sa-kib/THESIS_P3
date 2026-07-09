"""Unit tests for Phase 7C Benchmark and Verification Framework."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path

import pytest
import yaml

from e3hybrid.network.edge import Edge, MutableEdgeState
from e3hybrid.network.graph import DirectedGraph
from e3hybrid.network.node import Node
from e3hybrid.network.types import EdgeId, NodeId
from e3hybrid.routing.benchmark_config import BenchmarkConfig
from e3hybrid.routing.benchmark_metrics import AlgorithmMetadata, BenchmarkMetrics
from e3hybrid.routing.benchmark_reporter import BenchmarkReporter
from e3hybrid.routing.benchmark_result import BenchmarkResult, BenchmarkSummary
from e3hybrid.routing.benchmark_runner import BenchmarkRunner
from e3hybrid.routing.benchmark_scenario import BenchmarkRequest, BenchmarkScenario
from e3hybrid.routing.benchmark_validator import BenchmarkValidator
from e3hybrid.routing.cost_calculator import CostWeights
from e3hybrid.routing.request import RoutingRequest
from e3hybrid.routing.verifier import (
    DeterministicReplayReport,
    VerificationError,
    VerificationReport,
    RoutingVerifier,
)
from e3hybrid.vehicle.types import VehicleId


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def simple_graph() -> DirectedGraph:
    """Create a simple linear graph: A -> B -> C -> D."""
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
    return graph


@pytest.fixture
def graph_with_blocked() -> DirectedGraph:
    """Graph with one blocked edge: A -> B -(blocked)> C -> D."""
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
        edge_id=EdgeId("BC"), source=NodeId("B"), target=NodeId("C"),
        length_m=100.0, speed_limit_mps=10.0, lane_count=1,
        state=MutableEdgeState(is_blocked=True),
    ))
    graph.add_edge(Edge(
        edge_id=EdgeId("CD"), source=NodeId("C"), target=NodeId("D"),
        length_m=100.0, speed_limit_mps=10.0, lane_count=1,
    ))
    return graph


@pytest.fixture
def empty_request() -> RoutingRequest:
    return RoutingRequest(
        source_node=NodeId("A"),
        destination_node=NodeId("D"),
        vehicle_id=VehicleId("test_vehicle"),
        vehicle_constraints=None,
        battery_state=None,
        max_candidates=3,
        timeout_s=10.0,
    )


# =============================================================================
# RoutingVerifier Tests
# =============================================================================

class TestRoutingVerifier:
    """Tests for RoutingVerifier — algorithm-independent verification."""

    def test_verify_valid_route(self, simple_graph: DirectedGraph) -> None:
        from e3hybrid.routing.route import Route
        from e3hybrid.routing.types import RouteId

        route = Route(
            route_id=RouteId("test_route"),
            node_sequence=(NodeId("A"), NodeId("B"), NodeId("C"), NodeId("D")),
            edge_sequence=(EdgeId("AB"), EdgeId("BC"), EdgeId("CD")),
            total_distance_m=300.0,
            estimated_travel_time_s=30.0,
            estimated_energy_kwh=0.0,
        )
        report = RoutingVerifier.verify_route(route, simple_graph)
        assert report.is_valid
        assert report.checks_performed > 0
        assert report.checks_passed == report.checks_performed

    def test_verify_route_with_nonexistent_node(self, simple_graph: DirectedGraph) -> None:
        from e3hybrid.routing.route import Route
        from e3hybrid.routing.types import RouteId

        route = Route(
            route_id=RouteId("bad_route"),
            node_sequence=(NodeId("A"), NodeId("X"), NodeId("D")),
            edge_sequence=(EdgeId("AB"), EdgeId("BC")),
            total_distance_m=200.0,
            estimated_travel_time_s=20.0,
            estimated_energy_kwh=0.0,
        )
        report = RoutingVerifier.verify_route(route, simple_graph)
        assert not report.is_valid
        assert any("X" in e.message for e in report.errors)

    def test_verify_route_with_nonexistent_edge(self, simple_graph: DirectedGraph) -> None:
        from e3hybrid.routing.route import Route
        from e3hybrid.routing.types import RouteId

        route = Route(
            route_id=RouteId("bad_edge_route"),
            node_sequence=(NodeId("A"), NodeId("B"), NodeId("D")),
            edge_sequence=(EdgeId("AB"), EdgeId("XX")),
            total_distance_m=200.0,
            estimated_travel_time_s=20.0,
            estimated_energy_kwh=0.0,
        )
        report = RoutingVerifier.verify_route(route, simple_graph)
        assert not report.is_valid
        assert any("XX" in e.message for e in report.errors)

    def test_verify_blocked_edge_rejected(self, graph_with_blocked: DirectedGraph) -> None:
        from e3hybrid.routing.route import Route
        from e3hybrid.routing.types import RouteId

        route = Route(
            route_id=RouteId("blocked_route"),
            node_sequence=(NodeId("A"), NodeId("B"), NodeId("C"), NodeId("D")),
            edge_sequence=(EdgeId("AB"), EdgeId("BC"), EdgeId("CD")),
            total_distance_m=300.0,
            estimated_travel_time_s=30.0,
            estimated_energy_kwh=0.0,
        )
        report = RoutingVerifier.verify_route(route, graph_with_blocked)
        assert not report.is_valid
        assert any("BC" in e.message for e in report.errors)

    def test_verify_blocked_edge_allowed(self, graph_with_blocked: DirectedGraph) -> None:
        from e3hybrid.routing.route import Route
        from e3hybrid.routing.types import RouteId

        route = Route(
            route_id=RouteId("blocked_route"),
            node_sequence=(NodeId("A"), NodeId("B"), NodeId("C"), NodeId("D")),
            edge_sequence=(EdgeId("AB"), EdgeId("BC"), EdgeId("CD")),
            total_distance_m=300.0,
            estimated_travel_time_s=30.0,
            estimated_energy_kwh=0.0,
        )
        report = RoutingVerifier.verify_route(
            route, graph_with_blocked, allow_blocked=True
        )
        assert report.is_valid

    def test_verify_route_with_request(self, simple_graph: DirectedGraph,
                                        empty_request: RoutingRequest) -> None:
        from e3hybrid.routing.route import Route
        from e3hybrid.routing.types import RouteId

        route = Route(
            route_id=RouteId("test_route"),
            node_sequence=(NodeId("A"), NodeId("B"), NodeId("C"), NodeId("D")),
            edge_sequence=(EdgeId("AB"), EdgeId("BC"), EdgeId("CD")),
            total_distance_m=300.0,
            estimated_travel_time_s=30.0,
            estimated_energy_kwh=0.0,
        )
        report = RoutingVerifier.verify_route(route, simple_graph, empty_request)
        assert report.is_valid

    def test_verify_route_wrong_destination(self, simple_graph: DirectedGraph) -> None:
        from e3hybrid.routing.route import Route
        from e3hybrid.routing.types import RouteId

        request = RoutingRequest(
            source_node=NodeId("A"),
            destination_node=NodeId("D"),
            vehicle_id=VehicleId("test"),
            vehicle_constraints=None, battery_state=None,
            max_candidates=3, timeout_s=10.0,
        )
        route = Route(
            route_id=RouteId("wrong_dest"),
            node_sequence=(NodeId("A"), NodeId("B"), NodeId("C")),
            edge_sequence=(EdgeId("AB"), EdgeId("BC")),
            total_distance_m=200.0,
            estimated_travel_time_s=20.0,
            estimated_energy_kwh=0.0,
        )
        report = RoutingVerifier.verify_route(route, simple_graph, request)
        assert not report.is_valid

    def test_verify_result_success(self, simple_graph: DirectedGraph,
                                   empty_request: RoutingRequest) -> None:
        from e3hybrid.routing.candidate import RouteCandidate, SearchStatistics
        from e3hybrid.routing.cost import RouteCost
        from e3hybrid.routing.result import RoutingResult
        from e3hybrid.routing.route import Route
        from e3hybrid.routing.statistics import RoutingStatistics
        from e3hybrid.routing.types import RouteId

        route = Route(
            route_id=RouteId("test"),
            node_sequence=(NodeId("A"), NodeId("B"), NodeId("C"), NodeId("D")),
            edge_sequence=(EdgeId("AB"), EdgeId("BC"), EdgeId("CD")),
            total_distance_m=300.0, estimated_travel_time_s=30.0, estimated_energy_kwh=0.0,
        )
        candidate = RouteCandidate(
            route_id=RouteId("c1"), node_sequence=route.node_sequence,
            edge_sequence=route.edge_sequence, total_cost=30.0,
            cost_breakdown=RouteCost(total=30.0, distance_cost=10.0, time_cost=10.0,
                                     energy_cost=5.0, congestion_penalty=2.0,
                                     hazard_penalty=1.0, emergency_penalty=1.0,
                                     communication_penalty=1.0),
            algorithm="dijkstra",
        )
        result = RoutingResult(
            candidates=(candidate,), primary_route=route, success=True,
            failure_reason=None,
            statistics=RoutingStatistics(nodes_explored=3, edges_explored=2, candidates_generated=1),
            runtime_s=0.01,
        )
        report = RoutingVerifier.verify_result(result, simple_graph, empty_request)
        assert report.is_valid

    def test_verify_result_failure(self, simple_graph: DirectedGraph) -> None:
        from e3hybrid.routing.result import RoutingResult
        from e3hybrid.routing.statistics import RoutingStatistics

        result = RoutingResult(
            candidates=(), primary_route=None, success=False,
            failure_reason="No path exists",
            statistics=RoutingStatistics(nodes_explored=0, edges_explored=0, candidates_generated=0),
            runtime_s=0.0,
        )
        report = RoutingVerifier.verify_result(result, simple_graph)
        assert report.is_valid

    def test_verify_result_invalid_success_no_route(self, simple_graph: DirectedGraph) -> None:
        from e3hybrid.routing.result import RoutingResult
        from e3hybrid.routing.statistics import RoutingStatistics

        result = object.__new__(RoutingResult)
        object.__setattr__(result, "candidates", ())
        object.__setattr__(result, "primary_route", None)
        object.__setattr__(result, "success", True)
        object.__setattr__(result, "failure_reason", None)
        object.__setattr__(result, "statistics", RoutingStatistics(
            nodes_explored=0, edges_explored=0, candidates_generated=0,
        ))
        object.__setattr__(result, "runtime_s", 0.0)
        report = RoutingVerifier.verify_result(result, simple_graph)
        assert not report.is_valid

    def test_verify_graph_integrity(self, simple_graph: DirectedGraph) -> None:
        report = RoutingVerifier.verify_graph_integrity(simple_graph)
        assert report.is_valid

    def test_verify_graph_integrity_empty(self) -> None:
        graph = DirectedGraph()
        report = RoutingVerifier.verify_graph_integrity(graph)
        assert report.is_valid

    def test_compute_expected_distance(self, simple_graph: DirectedGraph) -> None:
        from e3hybrid.routing.route import Route
        from e3hybrid.routing.types import RouteId

        route = Route(
            route_id=RouteId("r1"), node_sequence=(NodeId("A"), NodeId("B"), NodeId("D")),
            edge_sequence=(EdgeId("AB"), EdgeId("BC")),
            total_distance_m=200.0, estimated_travel_time_s=20.0, estimated_energy_kwh=0.0,
        )
        expected = RoutingVerifier.compute_expected_distance(route, simple_graph)
        assert abs(expected - 200.0) < 1e-6

    def test_compute_expected_travel_time(self, simple_graph: DirectedGraph) -> None:
        from e3hybrid.routing.route import Route
        from e3hybrid.routing.types import RouteId

        route = Route(
            route_id=RouteId("r1"), node_sequence=(NodeId("A"), NodeId("B"), NodeId("D")),
            edge_sequence=(EdgeId("AB"), EdgeId("BC")),
            total_distance_m=200.0, estimated_travel_time_s=20.0, estimated_energy_kwh=0.0,
        )
        expected = RoutingVerifier.compute_expected_travel_time(route, simple_graph)
        assert abs(expected - 20.0) < 1e-6

    def test_verify_cost_breakdown(self) -> None:
        from e3hybrid.routing.candidate import RouteCandidate, SearchStatistics
        from e3hybrid.routing.cost import RouteCost
        from e3hybrid.routing.types import RouteId

        candidate = RouteCandidate(
            route_id=RouteId("c1"),
            node_sequence=(NodeId("A"), NodeId("B")),
            edge_sequence=(EdgeId("AB"),),
            total_cost=50.0,
            cost_breakdown=RouteCost(
                total=50.0, distance_cost=10.0, time_cost=20.0, energy_cost=5.0,
                congestion_penalty=5.0, hazard_penalty=5.0, emergency_penalty=3.0,
                communication_penalty=2.0,
            ),
            algorithm="dijkstra",
        )
        report = RoutingVerifier.verify_cost_breakdown(candidate)
        assert report.is_valid

    def test_verify_cost_breakdown_mismatch(self) -> None:
        from e3hybrid.routing.candidate import RouteCandidate
        from e3hybrid.routing.cost import RouteCost
        from e3hybrid.routing.types import RouteId

        cost = object.__new__(RouteCost)
        object.__setattr__(cost, "total", 99.0)
        object.__setattr__(cost, "distance_cost", 10.0)
        object.__setattr__(cost, "time_cost", 20.0)
        object.__setattr__(cost, "energy_cost", 5.0)
        object.__setattr__(cost, "congestion_penalty", 5.0)
        object.__setattr__(cost, "hazard_penalty", 5.0)
        object.__setattr__(cost, "emergency_penalty", 3.0)
        object.__setattr__(cost, "communication_penalty", 2.0)
        object.__setattr__(cost, "components", {})

        candidate = object.__new__(RouteCandidate)
        object.__setattr__(candidate, "route_id", RouteId("c1"))
        object.__setattr__(candidate, "node_sequence", (NodeId("A"), NodeId("B")))
        object.__setattr__(candidate, "edge_sequence", (EdgeId("AB"),))
        object.__setattr__(candidate, "total_cost", 50.0)
        object.__setattr__(candidate, "cost_breakdown", cost)
        object.__setattr__(candidate, "algorithm", "dijkstra")
        object.__setattr__(candidate, "metadata", {})
        object.__setattr__(candidate, "runtime_s", 0.0)
        object.__setattr__(candidate, "search_statistics", None)

        report = RoutingVerifier.verify_cost_breakdown(candidate)
        assert not report.is_valid

    def test_verify_candidate(self, simple_graph: DirectedGraph) -> None:
        from e3hybrid.routing.candidate import RouteCandidate, SearchStatistics
        from e3hybrid.routing.cost import RouteCost
        from e3hybrid.routing.types import RouteId

        candidate = RouteCandidate(
            route_id=RouteId("c1"),
            node_sequence=(NodeId("A"), NodeId("B"), NodeId("C")),
            edge_sequence=(EdgeId("AB"), EdgeId("BC")),
            total_cost=20.0,
            cost_breakdown=RouteCost(total=20.0, distance_cost=10.0, time_cost=10.0,
                                     energy_cost=0.0, congestion_penalty=0.0,
                                     hazard_penalty=0.0, emergency_penalty=0.0,
                                     communication_penalty=0.0),
            algorithm="dijkstra",
        )
        report = RoutingVerifier.verify_candidate(candidate, simple_graph)
        assert report.is_valid

    def test_verify_deterministic_replay(self, simple_graph: DirectedGraph) -> None:
        from e3hybrid.routing.dijkstra import DijkstraRouting

        algorithm = DijkstraRouting()
        request = RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("D"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=10.0,
        )
        report = RoutingVerifier.verify_deterministic_replay(
            algorithm, request, simple_graph, num_runs=3
        )
        assert report.is_deterministic
        assert report.num_runs == 3
        assert report.has_route
        assert report.cost_consistency
        assert report.route_consistency


# =============================================================================
# BenchmarkValidator Tests
# =============================================================================

class TestBenchmarkValidator:
    """Tests for BenchmarkValidator."""

    def test_validate_valid_config(self) -> None:
        config = BenchmarkConfig(algorithm_names=("dijkstra",), num_requests=5)
        report = BenchmarkValidator.validate_config(config)
        assert report.is_valid

    def test_validate_config_empty_algorithms(self) -> None:
        config = BenchmarkConfig(algorithm_names=())
        report = BenchmarkValidator.validate_config(config)
        assert not report.is_valid
        assert any("algorithm_names" in e.field_name for e in report.errors)

    def test_validate_config_zero_requests(self) -> None:
        config = BenchmarkConfig(num_requests=0)
        report = BenchmarkValidator.validate_config(config)
        assert not report.is_valid

    def test_validate_config_negative_timeout(self) -> None:
        config = BenchmarkConfig(timeout_s=-1.0)
        report = BenchmarkValidator.validate_config(config)
        assert not report.is_valid

    def test_validate_scenario(self, simple_graph: DirectedGraph) -> None:
        request = RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("D"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=10.0,
        )
        scenario = BenchmarkScenario(
            graph=simple_graph,
            requests=(BenchmarkRequest(request=request),),
            name="test_scenario",
        )
        report = BenchmarkValidator.validate_scenario(scenario)
        assert report.is_valid

    def test_validate_scenario_empty_requests(self, simple_graph: DirectedGraph) -> None:
        scenario = BenchmarkScenario(
            graph=simple_graph, requests=(), name="empty",
        )
        report = BenchmarkValidator.validate_scenario(scenario)
        assert not report.is_valid

    def test_validate_scenario_nonexistent_node(self, simple_graph: DirectedGraph) -> None:
        request = RoutingRequest(
            source_node=NodeId("X"), destination_node=NodeId("D"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=10.0,
        )
        scenario = BenchmarkScenario(
            graph=simple_graph,
            requests=(BenchmarkRequest(request=request),),
            name="bad_node",
        )
        report = BenchmarkValidator.validate_scenario(scenario)
        assert not report.is_valid

    def test_validate_metrics_valid(self) -> None:
        metrics = BenchmarkMetrics(
            algorithm_name="dijkstra",
            runtime_s=0.05,
            expanded_nodes=10,
            visited_nodes=10,
            route_distance_m=300.0,
            travel_time_s=30.0,
            total_cost=30.0,
            route_valid=True,
            success=True,
        )
        report = BenchmarkValidator.validate_metrics(metrics)
        assert report.is_valid

    def test_validate_metrics_empty_name(self) -> None:
        metrics = BenchmarkMetrics(
            algorithm_name="",
            runtime_s=0.0, expanded_nodes=0, visited_nodes=0,
            route_distance_m=0.0, travel_time_s=0.0, total_cost=0.0,
            route_valid=False, success=False, failure_reason="failed",
        )
        report = BenchmarkValidator.validate_metrics(metrics)
        assert not report.is_valid

    def test_validate_metrics_success_with_reason(self) -> None:
        metrics = BenchmarkMetrics(
            algorithm_name="test", runtime_s=0.0, expanded_nodes=0, visited_nodes=0,
            route_distance_m=0.0, travel_time_s=0.0, total_cost=0.0,
            route_valid=False, success=True, failure_reason="should be None",
        )
        report = BenchmarkValidator.validate_metrics(metrics)
        assert not report.is_valid

    def test_validate_metrics_failure_no_reason(self) -> None:
        metrics = BenchmarkMetrics(
            algorithm_name="test", runtime_s=0.0, expanded_nodes=0, visited_nodes=0,
            route_distance_m=0.0, travel_time_s=0.0, total_cost=0.0,
            route_valid=False, success=False,
        )
        report = BenchmarkValidator.validate_metrics(metrics)
        assert not report.is_valid

    def test_validate_result(self) -> None:
        config = BenchmarkConfig()
        metrics = BenchmarkMetrics(
            algorithm_name="dijkstra", runtime_s=0.05, expanded_nodes=10, visited_nodes=10,
            route_distance_m=300.0, travel_time_s=30.0, total_cost=30.0,
            route_valid=True, success=True,
        )
        from e3hybrid.routing.verifier import VerificationReport
        summary = BenchmarkSummary(
            total_requests=1, successful_requests=1, failed_requests=0,
            avg_runtime_s=0.05, max_runtime_s=0.05, min_runtime_s=0.05,
            avg_route_distance_m=300.0, avg_travel_time_s=30.0, avg_total_cost=30.0,
            total_expanded_nodes=10, avg_expanded_nodes=10.0,
            total_verified=1, verification_failures=0,
        )
        scenario = BenchmarkScenario(
            graph=DirectedGraph(), requests=(), name="test",
        )
        result = BenchmarkResult(
            algorithm=AlgorithmMetadata(name="dijkstra"),
            scenario=scenario,
            metrics=(metrics,),
            verification_reports=(VerificationReport(is_valid=True, errors=(), checks_performed=1, checks_passed=1),),
            summary=summary,
            config=config,
            timestamp="2026-01-01T00:00:00",
            duration_s=0.1,
        )
        report = BenchmarkValidator.validate_result(result)
        assert report.is_valid


# =============================================================================
# BenchmarkReporter Tests
# =============================================================================

class TestBenchmarkReporter:
    """Tests for BenchmarkReporter — CSV, JSON, YAML generation."""

    @pytest.fixture
    def result(self) -> BenchmarkResult:
        config = BenchmarkConfig(algorithm_names=("dijkstra",))
        metrics = BenchmarkMetrics(
            algorithm_name="dijkstra", runtime_s=0.05, expanded_nodes=10, visited_nodes=10,
            route_distance_m=300.0, travel_time_s=30.0, total_cost=30.0,
            route_valid=True, success=True,
        )
        from e3hybrid.routing.verifier import VerificationReport
        summary = BenchmarkSummary(
            total_requests=1, successful_requests=1, failed_requests=0,
            avg_runtime_s=0.05, max_runtime_s=0.05, min_runtime_s=0.05,
            avg_route_distance_m=300.0, avg_travel_time_s=30.0, avg_total_cost=30.0,
            total_expanded_nodes=10, avg_expanded_nodes=10.0,
            total_verified=1, verification_failures=0,
        )
        scenario = BenchmarkScenario(
            graph=DirectedGraph(), requests=(), name="test_scenario",
        )
        return BenchmarkResult(
            algorithm=AlgorithmMetadata(name="dijkstra"),
            scenario=scenario,
            metrics=(metrics,),
            verification_reports=(
                VerificationReport(is_valid=True, errors=(), checks_performed=5, checks_passed=5),
            ),
            summary=summary,
            config=config,
            timestamp="2026-01-01T00:00:00",
            duration_s=0.1,
        )

    def test_write_summary_csv(self, result: BenchmarkResult) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "summary.csv"
            BenchmarkReporter.write_summary([result], path)
            assert path.exists()
            with open(path, newline="") as f:
                reader = csv.reader(f)
                rows = list(reader)
            assert len(rows) == 2  # Header + 1 data row
            assert rows[1][0] == "dijkstra"

    def test_write_routing_results_csv(self, result: BenchmarkResult) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.csv"
            BenchmarkReporter.write_routing_results([result], path)
            assert path.exists()
            with open(path, newline="") as f:
                reader = csv.reader(f)
                rows = list(reader)
            assert len(rows) == 2
            assert rows[1][0] == "dijkstra"

    def test_write_verification_report_csv(self, result: BenchmarkResult) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "verification.csv"
            BenchmarkReporter.write_verification_report([result], path)
            assert path.exists()
            with open(path, newline="") as f:
                reader = csv.reader(f)
                rows = list(reader)
            assert len(rows) == 2
            assert rows[1][3] == "True"

    def test_write_metadata_json(self, result: BenchmarkResult) -> None:
        config = BenchmarkConfig(algorithm_names=("dijkstra",))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metadata.json"
            BenchmarkReporter.write_metadata([result], config, path)
            assert path.exists()
            with open(path) as f:
                data = json.load(f)
            assert data["total_algorithms"] == 1
            assert data["algorithms"][0]["name"] == "dijkstra"

    def test_write_config_snapshot_yaml(self) -> None:
        config = BenchmarkConfig(algorithm_names=("dijkstra",), num_requests=5)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            BenchmarkReporter.write_config_snapshot(config, path)
            assert path.exists()
            with open(path) as f:
                data = yaml.safe_load(f)
            assert data["algorithm_names"] == ["dijkstra"]
            assert data["num_requests"] == 5

    def test_write_all(self, result: BenchmarkResult) -> None:
        config = BenchmarkConfig(algorithm_names=("dijkstra",))
        with tempfile.TemporaryDirectory() as tmp:
            reporter = BenchmarkReporter(base_dir=tmp)
            run_dir = reporter.write_all([result], config)
            assert run_dir.exists()
            assert (run_dir / "benchmark_summary.csv").exists()
            assert (run_dir / "routing_results.csv").exists()
            assert (run_dir / "verification_report.csv").exists()
            assert (run_dir / "metadata.json").exists()
            assert (run_dir / "configuration_snapshot.yaml").exists()


# =============================================================================
# BenchmarkRunner Tests
# =============================================================================

class TestBenchmarkRunner:
    """Tests for BenchmarkRunner — benchmark execution lifecycle."""

    def test_run_scenario(self, simple_graph: DirectedGraph) -> None:
        config = BenchmarkConfig(
            algorithm_names=("dijkstra",),
            num_requests=2,
            timeout_s=10.0,
            max_candidates=3,
        )
        request = RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("D"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=10.0,
        )
        scenario = BenchmarkScenario(
            graph=simple_graph,
            requests=(
                BenchmarkRequest(request=request, description="A to D"),
            ),
            name="test_scenario",
        )
        runner = BenchmarkRunner(config)
        results = runner.run_scenario(scenario)
        assert len(results) == 1
        result = results[0]
        assert result.algorithm.name == "dijkstra"
        assert len(result.metrics) == 1
        assert result.metrics[0].success
        assert result.metrics[0].route_valid
        assert result.metrics[0].runtime_s >= 0
        assert result.metrics[0].route_distance_m > 0

    def test_run_scenario_failure(self, simple_graph: DirectedGraph) -> None:
        # Create a disconnected graph: A->B exists, but C->D is separate
        config = BenchmarkConfig(
            algorithm_names=("dijkstra",),
            num_requests=1,
            timeout_s=10.0,
        )
        disconnected = DirectedGraph()
        disconnected.add_node(Node(node_id=NodeId("A")))
        disconnected.add_node(Node(node_id=NodeId("B")))
        disconnected.add_node(Node(node_id=NodeId("C")))
        disconnected.add_node(Node(node_id=NodeId("D")))
        disconnected.add_edge(Edge(
            edge_id=EdgeId("AB"), source=NodeId("A"), target=NodeId("B"),
            length_m=100.0, speed_limit_mps=10.0, lane_count=1,
        ))
        disconnected.add_edge(Edge(
            edge_id=EdgeId("CD"), source=NodeId("C"), target=NodeId("D"),
            length_m=100.0, speed_limit_mps=10.0, lane_count=1,
        ))
        request = RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("D"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=10.0,
        )
        scenario = BenchmarkScenario(
            graph=disconnected,
            requests=(
                BenchmarkRequest(request=request, description="A to D"),
            ),
            name="failing_scenario",
        )
        runner = BenchmarkRunner(config)
        results = runner.run_scenario(scenario)
        assert len(results) == 1
        assert not results[0].metrics[0].success

    def test_run_scenario_with_verification_disabled(self, simple_graph: DirectedGraph) -> None:
        config = BenchmarkConfig(
            algorithm_names=("dijkstra",),
            verify_routes=False,
        )
        request = RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("D"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=10.0,
        )
        scenario = BenchmarkScenario(
            graph=simple_graph,
            requests=(BenchmarkRequest(request=request),),
            name="no_verify",
        )
        runner = BenchmarkRunner(config)
        results = runner.run_scenario(scenario)
        assert len(results) == 1
        assert results[0].metrics[0].success

    def test_multiple_requests(self, simple_graph: DirectedGraph) -> None:
        config = BenchmarkConfig(
            algorithm_names=("dijkstra",),
            timeout_s=10.0,
        )
        requests = (
            BenchmarkRequest(
                request=RoutingRequest(
                    source_node=NodeId("A"), destination_node=NodeId("D"),
                    vehicle_id=VehicleId("v1"), vehicle_constraints=None,
                    battery_state=None, max_candidates=3, timeout_s=10.0,
                ),
                description="A to D",
            ),
            BenchmarkRequest(
                request=RoutingRequest(
                    source_node=NodeId("A"), destination_node=NodeId("C"),
                    vehicle_id=VehicleId("v2"), vehicle_constraints=None,
                    battery_state=None, max_candidates=3, timeout_s=10.0,
                ),
                description="A to C",
            ),
        )
        scenario = BenchmarkScenario(
            graph=simple_graph, requests=requests, name="multi_request",
        )
        runner = BenchmarkRunner(config)
        results = runner.run_scenario(scenario)
        assert len(results[0].metrics) == 2
        assert results[0].metrics[0].success
        assert results[0].metrics[1].success

    def test_summary_statistics(self, simple_graph: DirectedGraph) -> None:
        config = BenchmarkConfig(
            algorithm_names=("dijkstra",),
            timeout_s=10.0,
        )
        requests = (
            BenchmarkRequest(
                request=RoutingRequest(
                    source_node=NodeId("A"), destination_node=NodeId("D"),
                    vehicle_id=VehicleId("v1"), vehicle_constraints=None,
                    battery_state=None, max_candidates=3, timeout_s=10.0,
                ),
            ),
        )
        scenario = BenchmarkScenario(
            graph=simple_graph, requests=requests, name="summary_test",
        )
        runner = BenchmarkRunner(config)
        results = runner.run_scenario(scenario)
        summary = results[0].summary
        assert summary.total_requests == 1
        assert summary.successful_requests == 1
        assert summary.failed_requests == 0
        assert summary.avg_runtime_s >= 0
        assert summary.avg_route_distance_m > 0

    def test_unknown_algorithm(self) -> None:
        config = BenchmarkConfig(algorithm_names=("nonexistent_algo",))
        request = RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("B"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=10.0,
        )
        from e3hybrid.network.graph import DirectedGraph
        graph = DirectedGraph()
        graph.add_node(Node(node_id=NodeId("A")))
        graph.add_node(Node(node_id=NodeId("B")))
        scenario = BenchmarkScenario(
            graph=graph,
            requests=(BenchmarkRequest(request=request),),
            name="unknown_algo",
        )
        runner = BenchmarkRunner(config)
        with pytest.raises(ValueError):
            runner.run_scenario(scenario)

    def test_invalid_scenario_raises(self) -> None:
        config = BenchmarkConfig(algorithm_names=("dijkstra",))
        scenario = BenchmarkScenario(
            graph=DirectedGraph(), requests=(), name="empty",
        )
        runner = BenchmarkRunner(config)
        with pytest.raises(ValueError, match="Invalid benchmark scenario"):
            runner.run_scenario(scenario)


# =============================================================================
# Deterministic Replay Tests
# =============================================================================

class TestDeterministicReplay:
    """Tests for deterministic replay verification."""

    def test_deterministic_dijkstra(self, simple_graph: DirectedGraph) -> None:
        from e3hybrid.routing.dijkstra import DijkstraRouting

        algorithm = DijkstraRouting()
        request = RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("D"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=10.0,
        )
        report = RoutingVerifier.verify_deterministic_replay(
            algorithm, request, simple_graph, num_runs=5
        )
        assert report.is_deterministic
        assert report.num_runs == 5
        assert report.has_route


# =============================================================================
# Verification Failure Tests
# =============================================================================

class TestVerificationFailures:
    """Tests for verification of invalid routes."""

    def test_disconnected_route(self, simple_graph: DirectedGraph) -> None:
        from e3hybrid.routing.route import Route
        from e3hybrid.routing.types import RouteId

        route = Route(
            route_id=RouteId("r1"),
            node_sequence=(NodeId("A"), NodeId("B"), NodeId("D")),
            edge_sequence=(EdgeId("AB"), EdgeId("CD")),  # CD does not connect B->D
            total_distance_m=200.0,
            estimated_travel_time_s=20.0,
            estimated_energy_kwh=0.0,
        )
        report = RoutingVerifier.verify_route(route, simple_graph)
        assert not report.is_valid
        # Should have edge connectivity failure
        edge_connectivity_errors = [e for e in report.errors if "connectivity" in e.check_name]
        assert len(edge_connectivity_errors) > 0

    def test_empty_node_sequence(self, simple_graph: DirectedGraph) -> None:
        from e3hybrid.routing.route import Route
        from e3hybrid.routing.types import RouteId

        route = object.__new__(Route)
        object.__setattr__(route, "route_id", RouteId("r1"))
        object.__setattr__(route, "node_sequence", (NodeId("A"),))
        object.__setattr__(route, "edge_sequence", ())
        object.__setattr__(route, "total_distance_m", 0.0)
        object.__setattr__(route, "estimated_travel_time_s", 0.0)
        object.__setattr__(route, "estimated_energy_kwh", 0.0)
        report = RoutingVerifier.verify_route(route, simple_graph)
        assert not report.is_valid

    def test_distance_mismatch(self, simple_graph: DirectedGraph) -> None:
        from e3hybrid.routing.route import Route
        from e3hybrid.routing.types import RouteId

        route = Route(
            route_id=RouteId("r1"),
            node_sequence=(NodeId("A"), NodeId("B")),
            edge_sequence=(EdgeId("AB"),),
            total_distance_m=999.0,  # Wrong! Should be 100.0
            estimated_travel_time_s=10.0,
            estimated_energy_kwh=0.0,
        )
        report = RoutingVerifier.verify_route(route, simple_graph)
        assert not report.is_valid
        assert any("distance" in e.check_name for e in report.errors)


# =============================================================================
# BenchmarkRequest Tests
# =============================================================================

class TestBenchmarkRequest:
    def test_create_with_metadata(self) -> None:
        request = RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("B"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=10.0,
        )
        br = BenchmarkRequest(
            request=request,
            description="test request",
            expected_success=True,
            metadata={"priority": "high"},
        )
        assert br.description == "test request"
        assert br.expected_success
        assert br.metadata["priority"] == "high"

    def test_defaults(self) -> None:
        request = RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("B"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=3, timeout_s=10.0,
        )
        br = BenchmarkRequest(request=request)
        assert br.description == ""
        assert br.expected_success
        assert br.metadata == {}


# =============================================================================
# AlgorithmMetadata Tests
# =============================================================================

class TestAlgorithmMetadata:
    def test_defaults(self) -> None:
        meta = AlgorithmMetadata(name="dijkstra")
        assert meta.name == "dijkstra"
        assert meta.version == "1.0.0"
        assert meta.description == ""
        assert meta.parameters == {}

    def test_custom_values(self) -> None:
        meta = AlgorithmMetadata(
            name="aco", version="2.0.0",
            description="Ant Colony Optimization",
            parameters={"alpha": 1.0, "beta": 2.0},
        )
        assert meta.name == "aco"
        assert meta.parameters["alpha"] == 1.0


# =============================================================================
# BenchmarkConfig Tests
# =============================================================================

class TestBenchmarkConfig:
    def test_defaults(self) -> None:
        config = BenchmarkConfig()
        assert config.algorithm_names == ("dijkstra",)
        assert config.num_requests == 10
        assert config.timeout_s == 10.0
        assert config.max_candidates == 5
        assert config.seed == 42
        assert config.verify_routes
        assert not config.collect_memory

    def test_custom_values(self) -> None:
        weights = CostWeights(distance=2.0, time=1.0)
        config = BenchmarkConfig(
            algorithm_names=("dijkstra", "astar"),
            num_requests=20,
            timeout_s=30.0,
            max_candidates=10,
            seed=123,
            cost_weights=weights,
            description="test benchmark",
        )
        assert len(config.algorithm_names) == 2
        assert config.cost_weights.distance == 2.0
        assert config.description == "test benchmark"
