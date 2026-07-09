"""SwarmToRoutingAdapter — adapts SwarmAlgorithm to RoutingAlgorithm Protocol.

Allows any SwarmAlgorithm to be used wherever a RoutingAlgorithm is
expected (e.g., BenchmarkRunner, DecisionEngine).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from e3hybrid.routing.candidate import RouteCandidate
from e3hybrid.routing.protocol import RoutingAlgorithm
from e3hybrid.routing.route import Route

if TYPE_CHECKING:
    from e3hybrid.network.graph import DirectedGraph
    from e3hybrid.routing.request import RoutingRequest
    from e3hybrid.routing.result import RoutingResult
    from e3hybrid.swarm.config import SwarmConfig
    from e3hybrid.swarm.context import SwarmContext
    from e3hybrid.swarm.protocol import SwarmAlgorithm


class SwarmToRoutingAdapter(RoutingAlgorithm):
    """Adapts SwarmAlgorithm to the RoutingAlgorithm Protocol.

    Converts SwarmResult to RoutingResult without knowing which swarm
    algorithm produced the result.

    Parameters
    ----------
    swarm_algorithm:
        The swarm algorithm to adapt.
    swarm_config:
        Configuration for the swarm optimization.
    """

    def __init__(
        self,
        swarm_algorithm: "SwarmAlgorithm",
        swarm_config: "SwarmConfig | None" = None,
    ) -> None:
        self._swarm = swarm_algorithm
        self._swarm_config = swarm_config

    @property
    def name(self) -> str:
        """Return the underlying swarm algorithm name."""
        return self._swarm.name

    @property
    def swarm_algorithm(self) -> "SwarmAlgorithm":
        """Return the underlying swarm algorithm instance."""
        return self._swarm

    def compute_route(
        self,
        request: "RoutingRequest",
        graph: "DirectedGraph | None" = None,
    ) -> "RoutingResult":
        """Compute a route using swarm optimization.

        Builds SwarmContext from the routing context, runs the swarm
        algorithm, and converts the result.

        Parameters
        ----------
        request:
            The routing request.
        graph:
            The directed graph (passed from BenchmarkRunner).

        Returns
        -------
        RoutingResult
            The routing result compatible with BenchmarkRunner and
            DecisionEngine.
        """
        from e3hybrid.routing.cost_calculator import (
            CompositeCostCalculator,
            CostWeights,
        )
        from e3hybrid.routing.result import RoutingResult
        from e3hybrid.routing.statistics import RoutingStatistics
        from e3hybrid.swarm.config import SwarmConfig
        from e3hybrid.swarm.context import SwarmContext

        # Build swarm config from request metadata if available
        config = self._swarm_config or SwarmConfig(
            algorithm_name=self._swarm.name,
            seed=42,
        )

        # Extract seed from request metadata or use config seed
        seed = config.seed
        if request.metadata and "seed" in request.metadata:
            seed = int(request.metadata["seed"])  # type: ignore[arg-type]

        # Build cost calculator from config weights
        cost_weights = config.cost_weights
        cost_calculator = CompositeCostCalculator(cost_weights) if graph is not None else None

        # Build the swarm context
        swarm_context = SwarmContext(
            cost_weights=cost_weights,
            config=config,
            random_seed=seed,
            routing_request=request,
            sim_time_s=0.0,
            graph=graph,
            cost_calculator=cost_calculator,
        )

        # Run swarm optimization
        swarm_result = self._swarm.optimize(swarm_context)

        # Build routing statistics
        routing_stats = RoutingStatistics(
            nodes_explored=swarm_result.statistics.solutions_evaluated,
            edges_explored=0,
            candidates_generated=swarm_result.statistics.candidate_count,
        )

        # Convert RouteCandidate list to tuple, build Route for primary_route
        candidate_tuple: tuple[RouteCandidate, ...] = tuple(swarm_result.candidates)

        primary: Route | None = None
        if candidate_tuple and swarm_result.success:
            best = candidate_tuple[0]
            total_dist = 0.0
            total_time = 0.0
            total_energy = 0.0
            if graph is not None:
                for eid in best.edge_sequence:
                    try:
                        edge = graph.get_edge(eid)
                    except Exception:
                        continue
                    speed = edge.state.current_speed_mps or edge.speed_limit_mps
                    total_dist += edge.length_m
                    total_time += edge.length_m / max(speed, 0.1)
                    total_energy += edge.length_m * 0.2  # rough kWh/m
            primary = Route(
                route_id=best.route_id,
                node_sequence=best.node_sequence,
                edge_sequence=best.edge_sequence,
                total_distance_m=total_dist,
                estimated_travel_time_s=total_time,
                estimated_energy_kwh=total_energy,
            )

        return RoutingResult(
            candidates=candidate_tuple,
            primary_route=primary,
            success=swarm_result.success,
            failure_reason=swarm_result.failure_reason,
            statistics=routing_stats,
            runtime_s=swarm_result.statistics.total_runtime_s,
        )
