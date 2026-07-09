"""AStarRouting — heuristic search algorithm.

A* is a best-first search algorithm that uses a heuristic function
to guide exploration toward the destination, typically exploring fewer
nodes than Dijkstra while guaranteeing optimality for admissible heuristics.
"""

from __future__ import annotations

import heapq
import time
import uuid
from typing import TYPE_CHECKING

from e3hybrid.network.types import EdgeId, NodeId
from e3hybrid.routing.candidate import RouteCandidate, SearchStatistics
from e3hybrid.routing.cost import RouteCost
from e3hybrid.routing.cost_calculator import CompositeCostCalculator, CostWeights
from e3hybrid.routing.heuristic import Heuristic, ZeroHeuristic
from e3hybrid.routing.request import RoutingRequest
from e3hybrid.routing.result import RoutingResult
from e3hybrid.routing.route import Route
from e3hybrid.routing.statistics import RoutingStatistics
from e3hybrid.routing.types import RouteId

if TYPE_CHECKING:
    from e3hybrid.network.graph import DirectedGraph


class AStarRouting:
    """A* heuristic search algorithm.

    A* extends Dijkstra's algorithm by incorporating a heuristic function
    h(n) that estimates the remaining cost from node n to the destination.
    The algorithm expands nodes in order of f(n) = g(n) + h(n), where g(n)
    is the known path cost from the source.

    Optimality Guarantee
    --------------------
    A* returns an optimal path whenever the heuristic is **admissible**
    (never overestimates the true cost to the destination). This holds
    because:

    Let f(n) = g(n) + h(n) where:
      - g(n) is the shortest known cost from source to node n
      - h(n) is the heuristic estimate from node n to destination

    If h is admissible (h(n) <= h*(n) for all n), then when A* selects
    a goal node for expansion, f(goal) = g(goal) + 0 = true optimal cost.
    All other paths have f(n) >= f(goal), so no better path exists.

    If h is also **consistent** (h(n) <= cost(n,n') + h(n')), A* never
    needs to re-expand nodes, matching Dijkstra's efficiency on the
    opened set.

    Complexity
    ----------
    Time:  O(E + V log V) with a good heuristic (fewer nodes expanded)
    Space: O(V) for the open and closed sets

    The effective branching factor depends on heuristic quality.
    A perfect heuristic (h = h*) reduces explored nodes to O(V) on the
    optimal path. A zero heuristic (h = 0) degenerates to Dijkstra.

    Assumptions
    -----------
    - Edge weights are non-negative (guaranteed by CostProvider)
    - Graph is directed (as per DirectedGraph design)
    - Heuristic is admissible for optimality guarantee
    """

    def __init__(
        self,
        heuristic: Heuristic | None = None,
        cost_weights: CostWeights | None = None,
    ) -> None:
        """Initialize A* routing algorithm.

        Parameters
        ----------
        heuristic:
            Heuristic function for goal-directed search.
            If None, uses ZeroHeuristic (behaves like Dijkstra).
        cost_weights:
            Optional cost weights. If None, uses default weights.
        """
        self._heuristic = heuristic if heuristic is not None else ZeroHeuristic()
        self._cost_calculator = CompositeCostCalculator(
            cost_weights if cost_weights is not None else CostWeights()
        )

    @property
    def name(self) -> str:
        """Return the algorithm name."""
        return "astar"

    @property
    def heuristic(self) -> Heuristic:
        """Return the heuristic used by this A* instance."""
        return self._heuristic

    def compute_route(
        self,
        request: RoutingRequest,
        graph: "DirectedGraph" | None = None,
    ) -> RoutingResult:
        """Compute the shortest path from source to destination using A*.

        Parameters
        ----------
        request:
            The routing request.
        graph:
            The directed graph.

        Returns
        -------
        RoutingResult
            The routing result with primary route and statistics.
        """
        if graph is None:
            raise ValueError("graph must be provided")

        start_time = time.perf_counter()
        nodes_explored = 0
        edges_explored = 0
        source = request.source_node
        destination = request.destination_node

        # Validate source and destination exist
        if not graph.has_node(source):
            return RoutingResult(
                candidates=(),
                primary_route=None,
                success=False,
                failure_reason=f"Source node {source} does not exist in graph",
                statistics=RoutingStatistics(
                    nodes_explored=0, edges_explored=0, candidates_generated=0,
                ),
                runtime_s=time.perf_counter() - start_time,
            )

        if not graph.has_node(destination):
            return RoutingResult(
                candidates=(),
                primary_route=None,
                success=False,
                failure_reason=f"Destination node {destination} does not exist in graph",
                statistics=RoutingStatistics(
                    nodes_explored=0, edges_explored=0, candidates_generated=0,
                ),
                runtime_s=time.perf_counter() - start_time,
            )

        # A* main loop
        # g_score: known shortest cost from source to node
        g_score: dict[NodeId, float] = {source: 0.0}
        # f_score: g(n) + h(n) — estimated total cost through node
        h_source = self._heuristic.estimate(source, destination, graph)
        f_score: dict[NodeId, float] = {source: g_score[source] + h_source}

        predecessors: dict[NodeId, NodeId] = {}
        predecessor_edges: dict[NodeId, EdgeId] = {}

        # Priority queue: (f_score, node_id)
        # Using f_score as the sort key ensures we expand the most
        # promising node first.
        pq: list[tuple[float, NodeId]] = [(f_score[source], source)]
        closed: set[NodeId] = set()

        while pq:
            # Check timeout
            if time.perf_counter() - start_time > request.timeout_s:
                return RoutingResult(
                    candidates=(),
                    primary_route=None,
                    success=False,
                    failure_reason=f"Routing exceeded timeout of {request.timeout_s}s",
                    statistics=RoutingStatistics(
                        nodes_explored=nodes_explored,
                        edges_explored=edges_explored,
                        candidates_generated=0,
                    ),
                    runtime_s=time.perf_counter() - start_time,
                )

            _, current = heapq.heappop(pq)

            # Skip if already processed (stale entry in pq)
            if current in closed:
                continue

            # Mark as expanded
            closed.add(current)
            nodes_explored += 1

            # Goal test
            if current == destination:
                break

            # Explore neighbors
            for edge in graph.outgoing_edges(current):
                edges_explored += 1

                # Skip blocked edges
                if edge.state.is_blocked:
                    continue

                # Compute edge cost
                edge_cost, _ = self._cost_calculator.compute_edge_cost(edge)
                if edge_cost == float("inf"):
                    continue

                neighbor = edge.target

                # Skip if already processed
                if neighbor in closed:
                    continue

                tentative_g = g_score[current] + edge_cost

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    # Better path found
                    g_score[neighbor] = tentative_g
                    predecessors[neighbor] = current
                    predecessor_edges[neighbor] = edge.edge_id

                    h = self._heuristic.estimate(
                        neighbor, destination, graph
                    )
                    f = tentative_g + h
                    f_score[neighbor] = f
                    heapq.heappush(pq, (f, neighbor))

        # Check if destination was reached
        if destination not in closed:
            return RoutingResult(
                candidates=(),
                primary_route=None,
                success=False,
                failure_reason=f"No path exists from {source} to {destination}",
                statistics=RoutingStatistics(
                    nodes_explored=nodes_explored,
                    edges_explored=edges_explored,
                    candidates_generated=0,
                ),
                runtime_s=time.perf_counter() - start_time,
            )

        # Reconstruct path
        path_nodes: list[NodeId] = []
        path_edges: list[EdgeId] = []
        current = destination

        while current != source:
            path_nodes.append(current)
            if current in predecessor_edges:
                path_edges.append(predecessor_edges[current])
            if current in predecessors:
                current = predecessors[current]
            else:
                return RoutingResult(
                    candidates=(),
                    primary_route=None,
                    success=False,
                    failure_reason="Path reconstruction failed",
                    statistics=RoutingStatistics(
                        nodes_explored=nodes_explored,
                        edges_explored=edges_explored,
                        candidates_generated=0,
                    ),
                    runtime_s=time.perf_counter() - start_time,
                )

        path_nodes.append(source)
        path_nodes.reverse()
        path_edges.reverse()

        # Build route and candidate
        route = self._build_route(path_nodes, path_edges, graph)
        candidate = self._build_candidate(route, graph, nodes_explored)

        runtime = time.perf_counter() - start_time

        return RoutingResult(
            candidates=(candidate,),
            primary_route=route,
            success=True,
            failure_reason=None,
            statistics=RoutingStatistics(
                nodes_explored=nodes_explored,
                edges_explored=edges_explored,
                candidates_generated=1,
            ),
            runtime_s=runtime,
        )

    def _build_route(
        self,
        path_nodes: list[NodeId],
        path_edges: list[EdgeId],
        graph: "DirectedGraph",
    ) -> Route:
        """Build a Route from node and edge sequences."""
        total_distance_m = 0.0
        total_time_s = 0.0
        total_energy_kwh = 0.0

        for edge_id in path_edges:
            edge = graph.get_edge(edge_id)
            total_distance_m += edge.length_m

            if edge.state.current_speed_mps is not None:
                effective_speed = edge.state.current_speed_mps
            else:
                effective_speed = edge.speed_limit_mps

            if effective_speed > 0:
                total_time_s += edge.length_m / effective_speed

            total_energy_kwh += 0.0

        return Route(
            route_id=RouteId(str(uuid.uuid4())),
            node_sequence=tuple(path_nodes),
            edge_sequence=tuple(path_edges),
            total_distance_m=total_distance_m,
            estimated_travel_time_s=total_time_s,
            estimated_energy_kwh=total_energy_kwh,
        )

    def _build_candidate(
        self,
        route: Route,
        graph: "DirectedGraph",
        nodes_explored: int = 0,
    ) -> RouteCandidate:
        """Build a RouteCandidate from a Route."""
        edges = [graph.get_edge(eid) for eid in route.edge_sequence]
        total_cost, breakdown = self._cost_calculator.compute_route_cost(edges)

        return RouteCandidate(
            route_id=route.route_id,
            node_sequence=route.node_sequence,
            edge_sequence=route.edge_sequence,
            total_cost=total_cost,
            cost_breakdown=RouteCost(
                total=total_cost,
                distance_cost=breakdown.distance_cost,
                time_cost=breakdown.time_cost,
                energy_cost=breakdown.energy_cost,
                congestion_penalty=breakdown.congestion_penalty,
                hazard_penalty=breakdown.hazard_penalty,
                emergency_penalty=breakdown.emergency_penalty,
                communication_penalty=breakdown.communication_penalty,
                components={
                    "distance": breakdown.distance_cost,
                    "time": breakdown.time_cost,
                    "energy": breakdown.energy_cost,
                    "congestion": breakdown.congestion_penalty,
                    "hazard": breakdown.hazard_penalty,
                    "emergency": breakdown.emergency_penalty,
                    "communication": breakdown.communication_penalty,
                },
            ),
            algorithm=self.name,
            search_statistics=SearchStatistics(
                iterations=nodes_explored,
            ),
        )
