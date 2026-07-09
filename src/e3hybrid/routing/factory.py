"""RoutingFactory — factory for creating routing algorithm instances."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from e3hybrid.routing.protocol import RoutingAlgorithm
    from e3hybrid.swarm.config import SwarmConfig


class RoutingFactory:
    """Factory for creating routing algorithm instances.
    
    This factory provides a centralized way to instantiate routing algorithms
    with configuration. Future phases will support algorithm selection via
    configuration strings.
    """

    @staticmethod
    def create_dijkstra() -> "RoutingAlgorithm":
        """Create a Dijkstra routing algorithm instance.
        
        Returns
        -------
        RoutingAlgorithm
            DijkstraRouting instance.
        """
        from e3hybrid.routing.dijkstra import DijkstraRouting
        return DijkstraRouting()

    @staticmethod
    def create_astar(
        heuristic_name: str = "zero",
    ) -> "RoutingAlgorithm":
        """Create an A* routing algorithm instance.

        Parameters
        ----------
        heuristic_name:
            Name of the heuristic ("zero", "euclidean", "manhattan").

        Returns
        -------
        RoutingAlgorithm
            AStarRouting instance.
        """
        from e3hybrid.routing.heuristic_factory import HeuristicFactory
        from e3hybrid.routing.astar import AStarRouting

        heuristic = HeuristicFactory.create(heuristic_name)
        return AStarRouting(heuristic=heuristic)

    @staticmethod
    def create_algorithm(algorithm_name: str) -> "RoutingAlgorithm":
        """Create a routing algorithm instance by name.
        
        Parameters
        ----------
        algorithm_name:
            Name of the algorithm (e.g., "dijkstra", "astar").
        
        Returns
        -------
        RoutingAlgorithm
            Algorithm instance.
        
        Raises
        ------
        ValueError
            If algorithm_name is not recognized.
        """
        algorithm_name_lower = algorithm_name.lower()
        
        if algorithm_name_lower == "dijkstra":
            return RoutingFactory.create_dijkstra()

        if algorithm_name_lower == "astar":
            return RoutingFactory.create_astar()

        if algorithm_name_lower.startswith("astar/"):
            heuristic_name = algorithm_name_lower.split("/", 1)[1]
            return RoutingFactory.create_astar(heuristic_name=heuristic_name)

        if algorithm_name_lower == "aco":
            return RoutingFactory.create_aco()

        if algorithm_name_lower == "bco":
            return RoutingFactory.create_bco()

        if algorithm_name_lower == "pso":
            return RoutingFactory.create_pso()

        if algorithm_name_lower in ("e3hybrid", "e3-hybrid", "hybrid"):
            return RoutingFactory.create_e3hybrid()

        raise ValueError(f"Unknown algorithm: {algorithm_name}")

    @staticmethod
    def create_aco(config: SwarmConfig | None = None) -> "RoutingAlgorithm":
        """Create an ACO routing algorithm instance.

        Parameters
        ----------
        config:
            Optional swarm configuration.

        Returns
        -------
        RoutingAlgorithm
            SwarmToRoutingAdapter wrapping ACORouting.
        """
        from e3hybrid.swarm.aco import ACORouting
        from e3hybrid.swarm.adapter import SwarmToRoutingAdapter

        aco = ACORouting()
        return SwarmToRoutingAdapter(swarm_algorithm=aco, swarm_config=config)

    @staticmethod
    def create_bco(config: SwarmConfig | None = None) -> "RoutingAlgorithm":
        """Create a BCO routing algorithm instance.

        Parameters
        ----------
        config:
            Optional swarm configuration.

        Returns
        -------
        RoutingAlgorithm
            SwarmToRoutingAdapter wrapping BCORouting.
        """
        from e3hybrid.swarm.bco import BCORouting
        from e3hybrid.swarm.adapter import SwarmToRoutingAdapter

        bco = BCORouting()
        return SwarmToRoutingAdapter(swarm_algorithm=bco, swarm_config=config)

    @staticmethod
    def create_pso(config: SwarmConfig | None = None) -> "RoutingAlgorithm":
        """Create a PSO routing algorithm instance.

        Parameters
        ----------
        config:
            Optional swarm configuration.

        Returns
        -------
        RoutingAlgorithm
            SwarmToRoutingAdapter wrapping PSORouting.
        """
        from e3hybrid.swarm.pso import PSORouting
        from e3hybrid.swarm.adapter import SwarmToRoutingAdapter

        pso = PSORouting()
        return SwarmToRoutingAdapter(swarm_algorithm=pso, swarm_config=config)

    @staticmethod
    def create_e3hybrid(config: SwarmConfig | None = None) -> "RoutingAlgorithm":
        """Create an E3-Hybrid routing algorithm instance.

        Parameters
        ----------
        config:
            Optional swarm configuration.

        Returns
        -------
        RoutingAlgorithm
            SwarmToRoutingAdapter wrapping E3HybridRouting.
        """
        from e3hybrid.swarm.hybrid import E3HybridRouting
        from e3hybrid.swarm.adapter import SwarmToRoutingAdapter

        hybrid = E3HybridRouting()
        return SwarmToRoutingAdapter(swarm_algorithm=hybrid, swarm_config=config)
