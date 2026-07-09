"""Heuristic Protocol and implementations for A* routing.

The heuristic must be completely independent of the routing algorithm.
AStarRouting depends only on the Heuristic Protocol, allowing new
heuristics to be added without modifying A*.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from e3hybrid.network.types import NodeId
    from e3hybrid.network.graph import DirectedGraph


class Heuristic(Protocol):
    """Interface for heuristic functions used in A* search.

    A heuristic estimates the cost from a given node to the destination.
    For A* to guarantee optimality, the heuristic must be:

    1. **Admissible**: never overestimates the actual cost to the destination.
       Formally: h(n) <= h*(n) for all nodes n, where h*(n) is the true
       shortest distance from n to the destination.

    2. **Consistent (monotone)**: h(n) <= cost(n, n') + h(n') for all
       edges n → n'. Consistency implies admissibility for goal nodes
       where h(goal) = 0.

    Attributes
    ----------
    name:
        Stable heuristic name used in logs and metrics.
    """

    @property
    def name(self) -> str:
        """Return the stable heuristic name."""
        ...

    def estimate(
        self,
        node_id: "NodeId",
        destination_id: "NodeId",
        graph: "DirectedGraph",
    ) -> float:
        """Estimate the cost from node_id to destination_id.

        Parameters
        ----------
        node_id:
            The current node.
        destination_id:
            The destination node.
        graph:
            The graph for node coordinate lookups.

        Returns
        -------
        float
            Estimated cost (non-negative). Returns 0.0 if no estimate
            can be made (e.g., node has no coordinates).
        """
        ...


class ZeroHeuristic:
    """Heuristic that always returns 0.0.

    With h(n) = 0 for all n, A* degenerates to Dijkstra's algorithm.
    The search order is determined entirely by the known path cost g(n).

    This heuristic is trivially admissible and consistent.
    Useful for testing and as a baseline.
    """

    @property
    def name(self) -> str:
        return "zero"

    def estimate(
        self,
        node_id: "NodeId",
        destination_id: "NodeId",
        graph: "DirectedGraph",
    ) -> float:
        """Return 0.0 regardless of inputs."""
        return 0.0


class EuclideanHeuristic:
    """Euclidean (straight-line) distance heuristic.

    Estimates cost as the straight-line distance between two nodes.
    Admissible when edge costs are proportional to Euclidean distance,
    which holds for distance-based cost functions.

    Mathematical definition:
        h(n) = sqrt((x_n - x_dest)^2 + (y_n - y_dest)^2)

    If either node lacks coordinates, returns 0.0 (safe fallback).

    Admissibility proof:
    The shortest path between two points in Euclidean space is the
    straight line. Any path constrained to the road network is at least
    as long as the straight line. Therefore h(n) <= h*(n) for all n.
    """

    def __init__(self, scale: float = 1.0) -> None:
        """Initialize the heuristic.

        Parameters
        ----------
        scale:
            Scaling factor to match cost units. For distance-based costs,
            use 1.0. For time-based costs, scale by 1/speed_limit.
        """
        self._scale = scale

    @property
    def name(self) -> str:
        return "euclidean"

    def estimate(
        self,
        node_id: "NodeId",
        destination_id: "NodeId",
        graph: "DirectedGraph",
    ) -> float:
        """Compute straight-line distance between two nodes."""
        try:
            node = graph.get_node(node_id)
            dest = graph.get_node(destination_id)
        except LookupError:
            return 0.0

        if node.x is None or node.y is None or dest.x is None or dest.y is None:
            return 0.0

        dx = node.x - dest.x
        dy = node.y - dest.y
        return math.sqrt(dx * dx + dy * dy) * self._scale


class ManhattanHeuristic:
    """Manhattan (city-block) distance heuristic.

    Estimates cost as the sum of absolute coordinate differences.
    Admissible for grid-like road networks where movement is restricted
    to orthogonal directions.

    Mathematical definition:
        h(n) = |x_n - x_dest| + |y_n - y_dest|

    If either node lacks coordinates, returns 0.0 (safe fallback).

    Admissibility proof:
    In a grid with axis-aligned movement, the shortest path between
    two points is the Manhattan distance. Any path that deviates from
    the direct Manhattan path is at least as long, so h(n) <= h*(n).
    For non-grid networks, Manhattan may overestimate if diagonal
    shortcuts exist, making it inadmissible in those cases.
    """

    def __init__(self, scale: float = 1.0) -> None:
        """Initialize the heuristic.

        Parameters
        ----------
        scale:
            Scaling factor to match cost units.
        """
        self._scale = scale

    @property
    def name(self) -> str:
        return "manhattan"

    def estimate(
        self,
        node_id: "NodeId",
        destination_id: "NodeId",
        graph: "DirectedGraph",
    ) -> float:
        """Compute Manhattan distance between two nodes."""
        try:
            node = graph.get_node(node_id)
            dest = graph.get_node(destination_id)
        except LookupError:
            return 0.0

        if node.x is None or node.y is None or dest.x is None or dest.y is None:
            return 0.0

        return (abs(node.x - dest.x) + abs(node.y - dest.y)) * self._scale
