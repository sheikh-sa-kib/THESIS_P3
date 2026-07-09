"""HeuristicFactory — creates heuristic instances from configuration."""

from __future__ import annotations

from e3hybrid.routing.heuristic import (
    EuclideanHeuristic,
    Heuristic,
    ManhattanHeuristic,
    ZeroHeuristic,
)


class HeuristicFactory:
    """Factory for creating heuristic instances.

    Heuristic selection is configurable through configuration strings
    (e.g., from YAML), enabling experiment-level heuristic selection
    without code changes.
    """

    @staticmethod
    def create(heuristic_name: str, **kwargs: float) -> "Heuristic":
        """Create a heuristic instance by name.

        Parameters
        ----------
        heuristic_name:
            Name of the heuristic ("zero", "euclidean", "manhattan").
        **kwargs:
            Additional parameters passed to the heuristic constructor
            (e.g., scale=1.0 for Euclidean/Manhattan).

        Returns
        -------
        Heuristic
            Heuristic instance.

        Raises
        ------
        ValueError
            If heuristic_name is not recognized.
        """
        name_lower = heuristic_name.lower().strip()

        if name_lower == "zero":
            return ZeroHeuristic()

        if name_lower == "euclidean":
            scale = kwargs.get("scale", 1.0)
            return EuclideanHeuristic(scale=scale)

        if name_lower == "manhattan":
            scale = kwargs.get("scale", 1.0)
            return ManhattanHeuristic(scale=scale)

        raise ValueError(
            f"Unknown heuristic: '{heuristic_name}'. "
            f"Available: zero, euclidean, manhattan"
        )

    @staticmethod
    def available_heuristics() -> tuple[str, ...]:
        """Return the names of all available heuristics."""
        return ("zero", "euclidean", "manhattan")
