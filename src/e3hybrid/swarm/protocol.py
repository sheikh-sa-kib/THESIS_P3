"""SwarmAlgorithm Protocol — interface for all swarm optimization algorithms.

Every swarm algorithm must satisfy this Protocol. The Protocol ensures
that all algorithms share a common interface for fair comparison.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from e3hybrid.swarm.context import SwarmContext
    from e3hybrid.swarm.result import SwarmResult


class SwarmAlgorithm(Protocol):
    """Interface that every swarm optimization algorithm must satisfy.

    Each algorithm implements ONLY its optimization strategy.
    The framework handles lifecycle, termination, statistics, and routing.

    Every algorithm is a pure function: given identical inputs, it produces
    identical outputs. No global state, no side effects, no graph modification.
    """

    @property
    def name(self) -> str:
        """Return the stable algorithm name used in logs and metrics.

        Returns
        -------
        str
            Algorithm name (e.g., "aco", "bco", "pso").
        """
        ...

    def optimize(
        self,
        context: "SwarmContext",
    ) -> "SwarmResult":
        """Run the swarm optimization and return the best solution found.

        This is the ONLY method a swarm algorithm must implement.

        Parameters
        ----------
        context:
            Immutable context with graph, cost provider, config, and random stream.

        Returns
        -------
        SwarmResult
            The optimization result with best solution, candidates, and statistics.

        Notes
        -----
        - The algorithm must be a pure function (no side effects).
        - The algorithm must use SwarmRandom for all stochastic decisions.
        - The algorithm must be deterministic (given same inputs -> same outputs).
        """
        ...
