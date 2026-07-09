"""SumoRoutingAdapter — wraps any RoutingAlgorithm for SUMO-based routing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from e3hybrid.routing.protocol import RoutingAlgorithm

if TYPE_CHECKING:
    from e3hybrid.network.graph import DirectedGraph
    from e3hybrid.routing.request import RoutingRequest
    from e3hybrid.routing.result import RoutingResult


class SumoRoutingAdapter(RoutingAlgorithm):
    """Wraps any RoutingAlgorithm for SUMO-based route computation.

    The adapter satisfies the RoutingAlgorithm protocol and can be used
    anywhere a routing algorithm is expected (BenchmarkRunner, experiment scripts).

    Unlike SwarmToRoutingAdapter, this adapter does NOT call optimize()
    directly. Instead, it:

    1. Accepts a RoutingAlgorithm (Dijkstra, A*, ACO, BCO, PSO, E3-Hybrid)
    2. On compute_route(), builds the request and delegates to the wrapped
       algorithm
    3. The wrapped algorithm receives a DirectedGraph (imported from SUMO) and
       works exactly as it does in the static benchmark case.

    Parameters
    ----------
    algorithm:
        The routing algorithm to wrap.
    """

    def __init__(self, algorithm: RoutingAlgorithm) -> None:
        self._algorithm = algorithm

    @property
    def name(self) -> str:
        """Return the wrapped algorithm's name."""
        return self._algorithm.name

    def compute_route(
        self,
        request: "RoutingRequest",
        graph: "DirectedGraph | None" = None,
    ) -> "RoutingResult":
        """Compute a route by delegating to the wrapped algorithm.

        The graph is passed through — the wrapped algorithm consumes it
        exactly as it would in the static benchmark case.
        """
        return self._algorithm.compute_route(request, graph=graph)