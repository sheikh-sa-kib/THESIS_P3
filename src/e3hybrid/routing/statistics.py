"""RoutingStatistics — statistics collected during routing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RoutingStatistics:
    """Statistics collected during routing.
    
    Used for algorithm comparison and thesis metrics.
    
    Attributes
    ----------
    nodes_explored:
        Number of nodes visited during search.
    edges_explored:
        Number of edges examined during search.
    candidates_generated:
        Number of route candidates generated.
    cache_hits:
        Number of cache hits (for future caching implementation).
    cache_misses:
        Number of cache misses (for future caching implementation).
    memory_bytes:
        Estimated memory usage in bytes.
    """

    nodes_explored: int
    edges_explored: int
    candidates_generated: int
    cache_hits: int = 0
    cache_misses: int = 0
    memory_bytes: int = 0

    def __post_init__(self) -> None:
        """Validate statistics."""
        if self.nodes_explored < 0:
            raise ValueError("nodes_explored must be non-negative")
        if self.edges_explored < 0:
            raise ValueError("edges_explored must be non-negative")
        if self.candidates_generated < 0:
            raise ValueError("candidates_generated must be non-negative")
        if self.cache_hits < 0:
            raise ValueError("cache_hits must be non-negative")
        if self.cache_misses < 0:
            raise ValueError("cache_misses must be non-negative")
        if self.memory_bytes < 0:
            raise ValueError("memory_bytes must be non-negative")
