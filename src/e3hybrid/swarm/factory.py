"""SwarmFactory — creates swarm algorithms by name from configuration.

Algorithm-agnostic. Supports 'aco', 'bco', 'pso', and future algorithms.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Type

if TYPE_CHECKING:
    from e3hybrid.swarm.config import SwarmConfig
    from e3hybrid.swarm.protocol import SwarmAlgorithm


class SwarmFactory:
    """Creates swarm algorithms by name from configuration.

    Supports registration of new algorithm classes at runtime.
    """

    _registry: dict[str, type] = {}

    @classmethod
    def register(cls, name: str, algorithm_class: type) -> None:
        """Register a swarm algorithm class.

        Parameters
        ----------
        name:
            Algorithm name (e.g., "aco", "bco", "pso").
        algorithm_class:
            The class implementing SwarmAlgorithm Protocol.

        Raises
        ------
        ValueError
            If name is empty or algorithm_class has already been registered.
        """
        if not name:
            raise ValueError("name must be non-empty")
        if name in cls._registry:
            raise ValueError(f"Algorithm '{name}' is already registered")
        cls._registry[name] = algorithm_class

    @classmethod
    def create_algorithm(
        cls,
        name: str,
        config: "SwarmConfig | None" = None,
    ) -> "SwarmAlgorithm":
        """Create a swarm algorithm instance by name.

        Parameters
        ----------
        name:
            Algorithm name (e.g., "aco", "bco", "pso").
        config:
            Optional configuration for the algorithm instance.

        Returns
        -------
        SwarmAlgorithm
            An instance of the requested algorithm.

        Raises
        ------
        ValueError
            If the algorithm name is not registered.
        """
        if name not in cls._registry:
            available = ", ".join(sorted(cls._registry.keys())) or "none"
            raise ValueError(
                f"Unknown algorithm '{name}'. "
                f"Available algorithms: {available}"
            )
        algorithm_class = cls._registry[name]
        return algorithm_class() if config is None else algorithm_class(config)

    @classmethod
    def available_algorithms(cls) -> dict[str, str]:
        """Return mapping of algorithm names to descriptions.

        Returns
        -------
        dict[str, str]
            Mapping of algorithm name -> class qualified name.
        """
        return {
            name: f"{cls.__module__}.{cls.__qualname__}"
            for name, cls in cls._registry.items()
        }

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if an algorithm name is registered.

        Parameters
        ----------
        name:
            Algorithm name to check.

        Returns
        -------
        bool
            True if the algorithm is registered.
        """
        return name in cls._registry

    @classmethod
    def clear_registry(cls) -> None:
        """Clear all registered algorithms (useful for testing)."""
        cls._registry.clear()
