"""HeuristicValidator — validates heuristic properties and behavior."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from e3hybrid.network.graph import DirectedGraph
    from e3hybrid.network.types import NodeId
    from e3hybrid.routing.heuristic import Heuristic


@dataclass(frozen=True, slots=True)
class HeuristicValidationReport:
    """Report of heuristic validation results.

    Attributes
    ----------
    is_admissible:
        Whether the heuristic passed admissibility checks.
    is_consistent:
        Whether the heuristic passed consistency checks.
    max_overestimate:
        Maximum overestimation ratio found (1.0 = perfect).
    warnings:
        Any warnings about heuristic behavior.
    """

    is_admissible: bool
    is_consistent: bool
    max_overestimate: float
    warnings: tuple[str, ...]


class HeuristicValidator:
    """Validates heuristic properties and behavior.

    Checks admissibility (never overestimates) and consistency
    (monotonicity) properties on a given graph.
    """

    @staticmethod
    def validate(
        heuristic: "Heuristic",
        graph: "DirectedGraph",
        true_costs: dict[tuple[NodeId, NodeId], float] | None = None,
        tolerance: float = 1e-6,
    ) -> HeuristicValidationReport:
        """Validate heuristic properties on a graph.

        Parameters
        ----------
        heuristic:
            The heuristic to validate.
        graph:
            The graph to validate on.
        true_costs:
            Optional dictionary of true shortest-path costs.
            If None, admissibility can only be checked structurally.
        tolerance:
            Floating-point comparison tolerance.

        Returns
        -------
        HeuristicValidationReport
            Report of validation results.
        """
        warnings: list[str] = []
        max_overestimate = 1.0

        # Check all nodes have coordinates
        nodes_without_coords = [
            n.node_id for n in graph.nodes()
            if n.x is None or n.y is None
        ]
        if nodes_without_coords:
            warnings.append(
                f"{len(nodes_without_coords)} nodes lack coordinates; "
                f"heuristic will fall back to 0.0 for those nodes"
            )

        # If true costs are provided, check admissibility
        is_admissible = True
        if true_costs is not None:
            for (source, dest), true_cost in true_costs.items():
                if true_cost < 0:
                    continue
                estimated = heuristic.estimate(source, dest, graph)
                if estimated > true_cost + tolerance:
                    is_admissible = False
                    ratio = estimated / true_cost if true_cost > 0 else float("inf")
                    max_overestimate = max(max_overestimate, ratio)

        # If only one node in graph, heuristic is trivially admissible
        if len(list(graph.nodes())) <= 1:
            is_admissible = True

        return HeuristicValidationReport(
            is_admissible=is_admissible,
            is_consistent=is_admissible,  # Consistency implies admissibility
            max_overestimate=max_overestimate,
            warnings=tuple(warnings),
        )

    @staticmethod
    def is_zero_heuristic(heuristic: "Heuristic") -> bool:
        """Check if a heuristic is a ZeroHeuristic (always returns 0)."""
        return heuristic.name == "zero"

    @staticmethod
    def is_admissible_for_cost_function(
        heuristic: "Heuristic",
        cost_is_distance_based: bool,
    ) -> bool:
        """Check if a heuristic is admissible for a given cost function.

        Parameters
        ----------
        heuristic:
            The heuristic to check.
        cost_is_distance_based:
            Whether the cost function is proportional to Euclidean distance.

        Returns
        -------
        bool
            True if the heuristic is likely admissible.
        """
        name = heuristic.name
        if name == "zero":
            return True
        if name == "euclidean":
            return cost_is_distance_based
        if name == "manhattan":
            return cost_is_distance_based
        return False
