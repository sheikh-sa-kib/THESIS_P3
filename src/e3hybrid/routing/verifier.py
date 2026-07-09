"""RoutingVerifier — algorithm-independent route verification utilities.

Every routing algorithm's output can be verified using these utilities.
The verifier never depends on algorithm internals.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from e3hybrid.network.graph import DirectedGraph
    from e3hybrid.network.types import EdgeId, NodeId
    from e3hybrid.routing.candidate import RouteCandidate
    from e3hybrid.routing.cost_calculator import CompositeCostCalculator
    from e3hybrid.routing.protocol import RoutingAlgorithm
    from e3hybrid.routing.request import RoutingRequest
    from e3hybrid.routing.result import RoutingResult
    from e3hybrid.routing.route import Route


@dataclass(frozen=True, slots=True)
class VerificationError:
    """A single verification error."""

    check_name: str
    message: str


@dataclass(frozen=True, slots=True)
class VerificationReport:
    """Report of verification results for a route.

    Attributes
    ----------
    is_valid:
        Whether all checks passed.
    errors:
        Tuple of verification errors found.
    checks_performed:
        Number of checks that were performed.
    checks_passed:
        Number of checks that passed.
    """

    is_valid: bool
    errors: tuple[VerificationError, ...]
    checks_performed: int
    checks_passed: int

    def __str__(self) -> str:
        if self.is_valid:
            return f"All {self.checks_performed} checks passed"
        error_lines = [f"  - {e.check_name}: {e.message}" for e in self.errors]
        return (
            f"{len(self.errors)}/{self.checks_performed} checks failed:\n"
            + "\n".join(error_lines)
        )


@dataclass(frozen=True, slots=True)
class DeterministicReplayReport:
    """Report of deterministic replay verification.

    Attributes
    ----------
    is_deterministic:
        Whether all runs produced identical results.
    num_runs:
        Number of runs performed.
    has_route:
        Whether a route was found in all runs.
    primary_route_ids:
        Route IDs from each run.
    cost_consistency:
        Whether total cost was identical across runs.
    route_consistency:
        Whether route sequences were identical across runs.
    errors:
        Any errors found during replay verification.
    """

    is_deterministic: bool
    num_runs: int
    has_route: bool
    primary_route_ids: tuple[str, ...]
    cost_consistency: bool
    route_consistency: bool
    errors: tuple[VerificationError, ...]


class RoutingVerifier:
    """Algorithm-independent route verification utilities.

    Every verification method works on RoutingResult, Route, RouteCandidate,
    or graph primitives — never on algorithm-specific internals.
    """

    @staticmethod
    def verify_route(
        route: "Route",
        graph: "DirectedGraph",
        request: "RoutingRequest | None" = None,
        allow_blocked: bool = False,
    ) -> VerificationReport:
        """Verify a route against the current graph state.

        Parameters
        ----------
        route:
            The route to verify.
        graph:
            The current graph state.
        request:
            Optional routing request for additional checks.
        allow_blocked:
            If True, blocked edges are allowed in the route.

        Returns
        -------
        VerificationReport
            Report of all verification checks.
        """
        errors: list[VerificationError] = []
        checks_performed = 0
        checks_passed = 0

        def _check(name: str, passed: bool, msg: str = "") -> None:
            nonlocal checks_performed, checks_passed
            checks_performed += 1
            if passed:
                checks_passed += 1
            else:
                errors.append(VerificationError(check_name=name, message=msg))

        # 1. Node sequence is non-empty
        _check(
            "node_sequence_non_empty",
            len(route.node_sequence) >= 2,
            "node_sequence must have at least 2 nodes",
        )

        # 2. Edge sequence matches node sequence length
        _check(
            "edge_sequence_length",
            len(route.edge_sequence) == len(route.node_sequence) - 1,
            f"edge_sequence length ({len(route.edge_sequence)}) "
            f"!= node_sequence length - 1 ({len(route.node_sequence) - 1})",
        )

        # 3. All nodes exist in graph
        for node_id in route.node_sequence:
            _check(
                "node_exists",
                graph.has_node(node_id),
                f"Node {node_id} does not exist in graph",
            )

        # 4. All edges exist in graph
        for edge_id in route.edge_sequence:
            _check(
                "edge_exists",
                graph.has_edge(edge_id),
                f"Edge {edge_id} does not exist in graph",
            )

        # 5. Edge connectivity (each edge connects consecutive nodes)
        for i, edge_id in enumerate(route.edge_sequence):
            if not graph.has_edge(edge_id):
                continue
            edge = graph.get_edge(edge_id)
            expected_source = route.node_sequence[i]
            expected_target = route.node_sequence[i + 1]
            _check(
                "edge_connectivity",
                edge.source == expected_source and edge.target == expected_target,
                f"Edge {edge_id} connects {edge.source}->{edge.target}, "
                f"expected {expected_source}->{expected_target}",
            )

        # 6. No blocked edges (unless allowed)
        if not allow_blocked:
            for edge_id in route.edge_sequence:
                if not graph.has_edge(edge_id):
                    continue
                edge = graph.get_edge(edge_id)
                _check(
                    "blocked_edge",
                    not edge.state.is_blocked,
                    f"Edge {edge_id} is blocked",
                )

        # 7. Request-specific checks
        if request is not None:
            _check(
                "source_node_matches",
                route.source_node == request.source_node,
                f"Route source {route.source_node} != request source {request.source_node}",
            )
            _check(
                "destination_node_matches",
                route.destination_node == request.destination_node,
                f"Route destination {route.destination_node} "
                f"!= request destination {request.destination_node}",
            )

        # 8. Distance consistency
        expected_distance = 0.0
        for edge_id in route.edge_sequence:
            if graph.has_edge(edge_id):
                expected_distance += graph.get_edge(edge_id).length_m
        _check(
            "distance_consistency",
            abs(route.total_distance_m - expected_distance) < 1e-6,
            f"Route distance {route.total_distance_m} != "
            f"sum of edge lengths {expected_distance}",
        )

        return VerificationReport(
            is_valid=len(errors) == 0,
            errors=tuple(errors),
            checks_performed=checks_performed,
            checks_passed=checks_passed,
        )

    @staticmethod
    def verify_result(
        result: "RoutingResult",
        graph: "DirectedGraph",
        request: "RoutingRequest | None" = None,
    ) -> VerificationReport:
        """Verify a routing result.

        Parameters
        ----------
        result:
            The routing result to verify.
        graph:
            The current graph state.
        request:
            Optional routing request for additional checks.

        Returns
        -------
        VerificationReport
            Report of all verification checks.
        """
        errors: list[VerificationError] = []
        checks_performed = 0
        checks_passed = 0

        def _check(name: str, passed: bool, msg: str = "") -> None:
            nonlocal checks_performed, checks_passed
            checks_performed += 1
            if passed:
                checks_passed += 1
            else:
                errors.append(VerificationError(check_name=name, message=msg))

        # 1. Result consistency (success vs failure invariants)
        if result.success:
            _check(
                "success_requires_route",
                result.primary_route is not None,
                "success=True requires primary_route",
            )
            _check(
                "success_no_failure_reason",
                result.failure_reason is None,
                "success=True requires failure_reason=None",
            )
        else:
            _check(
                "failure_no_route",
                result.primary_route is None,
                "success=False requires primary_route=None",
            )
            _check(
                "failure_requires_reason",
                result.failure_reason is not None,
                "success=False requires failure_reason",
            )

        # 2. Runtime is non-negative
        _check(
            "runtime_non_negative",
            result.runtime_s >= 0,
            f"runtime_s ({result.runtime_s}) must be non-negative",
        )

        # 3. Statistics are valid
        _check(
            "nodes_explored_non_negative",
            result.statistics.nodes_explored >= 0,
            "nodes_explored must be non-negative",
        )
        _check(
            "edges_explored_non_negative",
            result.statistics.edges_explored >= 0,
            "edges_explored must be non-negative",
        )
        _check(
            "candidates_generated_non_negative",
            result.statistics.candidates_generated >= 0,
            "candidates_generated must be non-negative",
        )

        # 4. Candidates are valid
        for candidate in result.candidates:
            candidate_errors = RoutingVerifier.verify_candidate(
                candidate, graph, request
            )
            if not candidate_errors.is_valid:
                for err in candidate_errors.errors:
                    errors.append(err)

        # 5. Verify primary route if present
        if result.primary_route is not None:
            route_report = RoutingVerifier.verify_route(
                result.primary_route, graph, request
            )
            if not route_report.is_valid:
                for err in route_report.errors:
                    errors.append(err)

        return VerificationReport(
            is_valid=len(errors) == 0,
            errors=tuple(errors),
            checks_performed=checks_performed,
            checks_passed=checks_passed,
        )

    @staticmethod
    def verify_candidate(
        candidate: "RouteCandidate",
        graph: "DirectedGraph",
        request: "RoutingRequest | None" = None,
    ) -> VerificationReport:
        """Verify a route candidate.

        Parameters
        ----------
        candidate:
            The candidate to verify.
        graph:
            The current graph state.
        request:
            Optional routing request for additional checks.

        Returns
        -------
        VerificationReport
            Report of all verification checks.
        """
        errors: list[VerificationError] = []
        checks_performed = 0
        checks_passed = 0

        def _check(name: str, passed: bool, msg: str = "") -> None:
            nonlocal checks_performed, checks_passed
            checks_performed += 1
            if passed:
                checks_passed += 1
            else:
                errors.append(VerificationError(check_name=name, message=msg))

        # 1. Node sequence is valid
        _check(
            "candidate_node_sequence",
            len(candidate.node_sequence) >= 2,
            "node_sequence must have at least 2 nodes",
        )

        # 2. Edge sequence matches
        _check(
            "candidate_edge_sequence_length",
            len(candidate.edge_sequence) == len(candidate.node_sequence) - 1,
            f"edge_sequence length ({len(candidate.edge_sequence)}) "
            f"!= node_sequence length - 1 ({len(candidate.node_sequence) - 1})",
        )

        # 3. All nodes exist in graph
        for node_id in candidate.node_sequence:
            _check(
                "candidate_node_exists",
                graph.has_node(node_id),
                f"Node {node_id} does not exist in graph",
            )

        # 4. All edges exist
        for edge_id in candidate.edge_sequence:
            _check(
                "candidate_edge_exists",
                graph.has_edge(edge_id),
                f"Edge {edge_id} does not exist in graph",
            )

        # 5. Edge connectivity
        for i, edge_id in enumerate(candidate.edge_sequence):
            if not graph.has_edge(edge_id):
                continue
            edge = graph.get_edge(edge_id)
            expected_source = candidate.node_sequence[i]
            expected_target = candidate.node_sequence[i + 1]
            _check(
                "candidate_edge_connectivity",
                edge.source == expected_source and edge.target == expected_target,
                f"Edge {edge_id} connects {edge.source}->{edge.target}, "
                f"expected {expected_source}->{expected_target}",
            )

        # 6. Cost consistency
        _check(
            "candidate_cost_non_negative",
            candidate.total_cost >= 0,
            f"total_cost ({candidate.total_cost}) must be non-negative",
        )

        # 7. Algorithm name is non-empty
        _check(
            "candidate_algorithm_name",
            bool(candidate.algorithm),
            "algorithm name must be non-empty",
        )

        # 8. Request-specific checks
        if request is not None:
            _check(
                "candidate_source_matches",
                candidate.source_node == request.source_node,
                f"Candidate source {candidate.source_node} "
                f"!= request source {request.source_node}",
            )
            _check(
                "candidate_destination_matches",
                candidate.destination_node == request.destination_node,
                f"Candidate destination {candidate.destination_node} "
                f"!= request destination {request.destination_node}",
            )

        return VerificationReport(
            is_valid=len(errors) == 0,
            errors=tuple(errors),
            checks_performed=checks_performed,
            checks_passed=checks_passed,
        )

    @staticmethod
    def verify_graph_integrity(
        graph: "DirectedGraph",
    ) -> VerificationReport:
        """Verify graph structural integrity.

        Parameters
        ----------
        graph:
            The graph to verify.

        Returns
        -------
        VerificationReport
            Report of all integrity checks.
        """
        errors: list[VerificationError] = []
        checks_performed = 0
        checks_passed = 0

        def _check(name: str, passed: bool, msg: str = "") -> None:
            nonlocal checks_performed, checks_passed
            checks_performed += 1
            if passed:
                checks_passed += 1
            else:
                errors.append(VerificationError(check_name=name, message=msg))

        # 1. Outgoing adjacency consistency
        for node in graph.nodes():
            node_id = node.node_id
            outgoing = graph.outgoing_edges(node_id)
            for edge in outgoing:
                _check(
                    "outgoing_edge_source",
                    edge.source == node_id,
                    f"Edge {edge.edge_id} in outgoing of {node_id} "
                    f"has source {edge.source}",
                )

        # 2. Incoming adjacency consistency
        for node in graph.nodes():
            node_id = node.node_id
            incoming = graph.incoming_edges(node_id)
            for edge in incoming:
                _check(
                    "incoming_edge_target",
                    edge.target == node_id,
                    f"Edge {edge.edge_id} in incoming of {node_id} "
                    f"has target {edge.target}",
                )

        # 3. Edge references are valid
        for node in graph.nodes():
            node_id = node.node_id
            outgoing = graph.outgoing_edges(node_id)
            for edge in outgoing:
                _check(
                    "outgoing_edge_exists",
                    graph.has_edge(edge.edge_id),
                    f"Outgoing edge {edge.edge_id} from {node_id} not in graph",
                )
                _check(
                    "outgoing_target_exists",
                    graph.has_node(edge.target),
                    f"Outgoing edge {edge.edge_id} target {edge.target} not in graph",
                )

        # 4. All edges have valid sources and targets
        for edge in graph.edges():
            _check(
                "edge_source_exists",
                graph.has_node(edge.source),
                f"Edge {edge.edge_id} source {edge.source} not in graph",
            )
            _check(
                "edge_target_exists",
                graph.has_node(edge.target),
                f"Edge {edge.edge_id} target {edge.target} not in graph",
            )

        return VerificationReport(
            is_valid=len(errors) == 0,
            errors=tuple(errors),
            checks_performed=checks_performed,
            checks_passed=checks_passed,
        )

    @staticmethod
    def verify_deterministic_replay(
        algorithm: "RoutingAlgorithm",
        request: "RoutingRequest",
        graph: "DirectedGraph",
        num_runs: int = 3,
    ) -> DeterministicReplayReport:
        """Verify that an algorithm produces identical results across runs.

        Parameters
        ----------
        algorithm:
            The routing algorithm to test.
        request:
            The routing request.
        graph:
            The graph to route on.
        num_runs:
            Number of runs to perform.

        Returns
        -------
        DeterministicReplayReport
            Report of deterministic replay verification.
        """
        errors: list[VerificationError] = []
        results: list[RoutingResult] = []

        for _ in range(num_runs):
            result = algorithm.compute_route(request, graph)
            results.append(result)

        has_route = all(r.success for r in results)
        primary_route_ids = tuple(
            str(r.primary_route.route_id) if r.primary_route else ""
            for r in results
        )

        # Check cost consistency across runs
        cost_consistency = True
        if has_route:
            costs = [
                r.primary_route.estimated_travel_time_s if r.primary_route else 0.0
                for r in results
            ]
            cost_consistency = all(abs(c - costs[0]) < 1e-6 for c in costs)

        # Check route sequence consistency
        route_consistency = True
        if has_route:
            sequences = [
                tuple(r.primary_route.edge_sequence) if r.primary_route else ()
                for r in results
            ]
            route_consistency = all(s == sequences[0] for s in sequences)

        if not cost_consistency:
            errors.append(
                VerificationError(
                    check_name="cost_consistency",
                    message="Total cost differs across runs",
                )
            )

        if not route_consistency:
            errors.append(
                VerificationError(
                    check_name="route_consistency",
                    message="Route sequence differs across runs",
                )
            )

        success_consistency = len(set(r.success for r in results)) == 1
        if not success_consistency:
            errors.append(
                VerificationError(
                    check_name="success_consistency",
                    message="Success/failure status differs across runs",
                )
            )

        return DeterministicReplayReport(
            is_deterministic=len(errors) == 0,
            num_runs=num_runs,
            has_route=has_route,
            primary_route_ids=primary_route_ids,
            cost_consistency=cost_consistency,
            route_consistency=route_consistency,
            errors=tuple(errors),
        )

    @staticmethod
    def compute_expected_distance(
        route: "Route",
        graph: "DirectedGraph",
    ) -> float:
        """Compute the expected total distance for a route from edge lengths.

        Parameters
        ----------
        route:
            The route to compute distance for.
        graph:
            The graph containing the edges.

        Returns
        -------
        float
            The expected total distance in meters.
        """
        total = 0.0
        for edge_id in route.edge_sequence:
            if graph.has_edge(edge_id):
                total += graph.get_edge(edge_id).length_m
        return total

    @staticmethod
    def compute_expected_travel_time(
        route: "Route",
        graph: "DirectedGraph",
    ) -> float:
        """Compute the expected travel time for a route.

        Parameters
        ----------
        route:
            The route to compute travel time for.
        graph:
            The graph containing the edges.

        Returns
        -------
        float
            The expected travel time in seconds.
        """
        total = 0.0
        for edge_id in route.edge_sequence:
            if not graph.has_edge(edge_id):
                continue
            edge = graph.get_edge(edge_id)
            effective_speed = (
                edge.state.current_speed_mps
                if edge.state.current_speed_mps is not None
                else edge.speed_limit_mps
            )
            if effective_speed > 0:
                total += edge.length_m / effective_speed
        return total

    @staticmethod
    def compute_expected_cost(
        route: "Route",
        cost_calculator: "CompositeCostCalculator",
        graph: "DirectedGraph",
    ) -> float:
        """Compute the expected total cost for a route using a cost calculator.

        Parameters
        ----------
        route:
            The route to compute cost for.
        cost_calculator:
            The cost calculator to use.
        graph:
            The graph containing the edges.

        Returns
        -------
        float
            The expected total cost.
        """
        edges = [graph.get_edge(eid) for eid in route.edge_sequence if graph.has_edge(eid)]
        if not edges:
            return 0.0
        total_cost, _ = cost_calculator.compute_route_cost(edges)
        return total_cost

    @staticmethod
    def verify_cost_breakdown(
        candidate: "RouteCandidate",
        tolerance: float = 1e-6,
    ) -> VerificationReport:
        """Verify that cost_breakdown.total matches the candidate total_cost.

        Parameters
        ----------
        candidate:
            The candidate to verify.
        tolerance:
            Floating-point comparison tolerance.

        Returns
        -------
        VerificationReport
            Report of cost consistency verification.
        """
        errors: list[VerificationError] = []
        checks_performed = 0
        checks_passed = 0

        def _check(name: str, passed: bool, msg: str = "") -> None:
            nonlocal checks_performed, checks_passed
            checks_performed += 1
            if passed:
                checks_passed += 1
            else:
                errors.append(VerificationError(check_name=name, message=msg))

        _check(
            "cost_breakdown_matches_total",
            abs(candidate.cost_breakdown.total - candidate.total_cost) < tolerance,
            f"cost_breakdown.total ({candidate.cost_breakdown.total}) "
            f"!= total_cost ({candidate.total_cost})",
        )

        computed = (
            candidate.cost_breakdown.distance_cost
            + candidate.cost_breakdown.time_cost
            + candidate.cost_breakdown.energy_cost
            + candidate.cost_breakdown.congestion_penalty
            + candidate.cost_breakdown.hazard_penalty
            + candidate.cost_breakdown.emergency_penalty
            + candidate.cost_breakdown.communication_penalty
        )
        _check(
            "cost_breakdown_sum_consistency",
            abs(candidate.cost_breakdown.total - computed) < tolerance,
            f"cost_breakdown.total ({candidate.cost_breakdown.total}) "
            f"!= sum of components ({computed})",
        )

        return VerificationReport(
            is_valid=len(errors) == 0,
            errors=tuple(errors),
            checks_performed=checks_performed,
            checks_passed=checks_passed,
        )
