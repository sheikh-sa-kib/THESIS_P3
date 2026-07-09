"""RoutingAlgorithm Protocol — interface for all routing algorithms.

Every routing algorithm must satisfy this Protocol. The Protocol ensures
that all algorithms receive identical inputs and produce identical outputs
for fair comparison.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from e3hybrid.routing.request import RoutingRequest
    from e3hybrid.routing.result import RoutingResult


class RoutingAlgorithm(Protocol):
    """Interface that every routing algorithm must satisfy.
    
    Every algorithm is a pure function: given identical inputs, it produces
    identical outputs. No global state, no side effects, no graph modification.
    
    Design Decision (DD-028)
    -----------------------
    Pure function requirement ensures fair comparison between algorithms
    and deterministic replay for reproducibility.
    """

    @property
    def name(self) -> str:
        """Return the stable algorithm name used in logs and metrics.
        
        Returns
        -------
        str
            Algorithm name (e.g., "dijkstra", "astar", "aco").
        """
        ...

    def compute_route(
        self,
        request: "RoutingRequest",
    ) -> "RoutingResult":
        """Compute a route from source to destination.
        
        This is the ONLY method an algorithm must implement.
        
        Parameters
        ----------
        request:
            The routing request (source, destination, constraints).
        
        Returns
        -------
        RoutingResult
            The routing result with candidates, primary route, and statistics.
        
        Raises
        ------
        RoutingError
            If routing fails (no path exists, timeout, etc.).
        
        Notes
        -----
        - The algorithm must be a pure function (no side effects).
        - The algorithm must use the CostProvider interface for edge costs.
        - The algorithm must work entirely on the internal graph.
        - The algorithm must be deterministic (given same inputs → same outputs).
        """
        ...
