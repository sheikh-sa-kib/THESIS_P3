"""DijkstraRouting — classical shortest-path algorithm.

This is the reference implementation for all routing algorithms.
It becomes the gold standard for RoutingResult structure.
"""

from __future__ import annotations

import heapq
import time
import uuid
from typing import TYPE_CHECKING

from e3hybrid.network.types import EdgeId, NodeId
from e3hybrid.routing.cost import RouteCost
from e3hybrid.routing.cost_calculator import CompositeCostCalculator, CostWeights
from e3hybrid.routing.candidate import RouteCandidate, SearchStatistics
from e3hybrid.routing.exceptions import NoPathError, TimeoutError
from e3hybrid.routing.protocol import RoutingAlgorithm
from e3hybrid.routing.request import RoutingRequest
from e3hybrid.routing.result import RoutingResult
from e3hybrid.routing.route import Route
from e3hybrid.routing.statistics import RoutingStatistics
from e3hybrid.routing.types import RouteId

if TYPE_CHECKING:
    from e3hybrid.network.graph import DirectedGraph


class DijkstraRouting:
    """Classical Dijkstra shortest-path algorithm.
    
    This is the reference implementation for all routing algorithms.
    It demonstrates the correct structure for RoutingResult and
    serves as the baseline for algorithm comparison.
    
    Mathematical Formulation
    ------------------------
    Dijkstra's algorithm finds the shortest path from source to destination
    in a graph with non-negative edge weights. It maintains a priority queue
    of nodes to explore, always expanding the node with the minimum known
    distance from the source.
    
    Complexity
    ---------
    Time: O((V + E) log V) with a binary heap priority queue
    Space: O(V) for distance and predecessor arrays
    
    Assumptions
    -----------
    - Edge weights are non-negative (guaranteed by CostProvider)
    - Graph is directed (as per DirectedGraph design)
    - Graph may contain cycles (handled correctly by visited set)
    
    Limitations
    -----------
    - Does not handle negative edge weights (not required for this use case)
    - Returns only the single best route (no candidates)
    - No heuristic guidance (unlike A*)
    """

    def __init__(self, cost_weights: CostWeights | None = None) -> None:
        """Initialize Dijkstra routing algorithm.
        
        Parameters
        ----------
        cost_weights:
            Optional cost weights. If None, uses default weights.
        """
        self._cost_calculator = CompositeCostCalculator(
            cost_weights if cost_weights is not None else CostWeights()
        )

    @property
    def name(self) -> str:
        """Return the algorithm name."""
        return "dijkstra"

    def compute_route(
        self,
        request: RoutingRequest,
        graph: "DirectedGraph" | None = None,
    ) -> RoutingResult:
        """Compute the shortest path from source to destination.
        
        This is the ONLY method that implements the algorithm.
        
        Parameters
        ----------
        request:
            The routing request.
        graph:
            The directed graph (passed separately to avoid circular imports).
        
        Returns
        -------
        RoutingResult
            The routing result with primary route and statistics.
        
        Raises
        ------
        NoPathError
            If no path exists from source to destination.
        TimeoutError
            If routing exceeds the timeout.
        """
        if graph is None:
            raise ValueError("graph must be provided")

        start_time = time.perf_counter()
        nodes_explored = 0
        edges_explored = 0

        # Validate source and destination exist
        if not graph.has_node(request.source_node):
            return RoutingResult(
                candidates=(),
                primary_route=None,
                success=False,
                failure_reason=f"Source node {request.source_node} does not exist in graph",
                statistics=RoutingStatistics(
                    nodes_explored=0,
                    edges_explored=0,
                    candidates_generated=0,
                ),
                runtime_s=time.perf_counter() - start_time,
            )

        if not graph.has_node(request.destination_node):
            return RoutingResult(
                candidates=(),
                primary_route=None,
                success=False,
                failure_reason=f"Destination node {request.destination_node} does not exist in graph",
                statistics=RoutingStatistics(
                    nodes_explored=0,
                    edges_explored=0,
                    candidates_generated=0,
                ),
                runtime_s=time.perf_counter() - start_time,
            )

        # Dijkstra's algorithm
        distances: dict[NodeId, float] = {request.source_node: 0.0}
        predecessors: dict[NodeId, NodeId] = {}
        predecessor_edges: dict[NodeId, EdgeId] = {}
        visited: set[NodeId] = set()

        # Priority queue: (distance, node_id)
        pq: list[tuple[float, NodeId]] = [(0.0, request.source_node)]

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

            current_distance, current_node = heapq.heappop(pq)

            # Skip if we've already found a better path
            if current_node in visited:
                continue

            visited.add(current_node)
            nodes_explored += 1

            # Check if we reached destination
            if current_node == request.destination_node:
                break

            # Use lane-level successors when arriving via a known edge.
            # For the source node, check if the request specifies a source edge
            # (used during rerouting where the vehicle is already on an edge).
            incoming_edge_id = predecessor_edges.get(current_node)
            if incoming_edge_id is not None and graph.has_successors(incoming_edge_id):
                outgoing_iter = graph.get_successors(incoming_edge_id)
            elif (incoming_edge_id is None
                  and current_node == request.source_node
                  and "source_edge_id" in request.metadata):
                src_eid = EdgeId(str(request.metadata["source_edge_id"]))
                if graph.has_successors(src_eid):
                    outgoing_iter = graph.get_successors(src_eid)
                else:
                    outgoing_iter = graph.outgoing_edges(current_node)
            else:
                outgoing_iter = graph.outgoing_edges(current_node)

            # Explore neighbors
            for edge in outgoing_iter:
                edges_explored += 1

                # Skip blocked edges
                if edge.state.is_blocked:
                    continue

                # Compute edge cost
                edge_cost, _ = self._cost_calculator.compute_edge_cost(edge)

                # If edge is impassable (infinite cost), skip
                if edge_cost == float("inf"):
                    continue

                neighbor = edge.target
                new_distance = current_distance + edge_cost

                if neighbor not in distances or new_distance < distances[neighbor]:
                    distances[neighbor] = new_distance
                    predecessors[neighbor] = current_node
                    predecessor_edges[neighbor] = edge.edge_id
                    heapq.heappush(pq, (new_distance, neighbor))

        # Check if destination was reached
        if request.destination_node not in visited:
            return RoutingResult(
                candidates=(),
                primary_route=None,
                success=False,
                failure_reason=f"No path exists from {request.source_node} to {request.destination_node}",
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
        current = request.destination_node

        while current != request.source_node:
            path_nodes.append(current)
            if current in predecessor_edges:
                path_edges.append(predecessor_edges[current])
            if current in predecessors:
                current = predecessors[current]
            else:
                # Should not happen if destination was reached
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

        path_nodes.append(request.source_node)
        path_nodes.reverse()
        path_edges.reverse()

        # Build route
        route = self._build_route(
            path_nodes=path_nodes,
            path_edges=path_edges,
            graph=graph,
        )

        # Build route candidate
        candidate = self._build_candidate(
            route=route,
            graph=graph,
        )

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
            
            # Compute travel time
            if edge.state.current_speed_mps is not None:
                effective_speed = edge.state.current_speed_mps
            else:
                effective_speed = edge.speed_limit_mps
            
            if effective_speed > 0:
                total_time_s += edge.length_m / effective_speed
            
            # Energy will be computed by energy model in future phases
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
            search_statistics=SearchStatistics(iterations=0),  # Dijkstra has no iterations
        )
