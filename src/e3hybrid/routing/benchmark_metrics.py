"""BenchmarkMetrics and AlgorithmMetadata — metrics and metadata for benchmarks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class AlgorithmMetadata:
    """Metadata about a routing algorithm under test.

    Attributes
    ----------
    name:
        Algorithm name (must match algorithm.name property).
    version:
        Algorithm version or implementation identifier.
    description:
        Human-readable description of the algorithm.
    parameters:
        Algorithm-specific parameters used in this benchmark.
    """

    name: str
    version: str = "1.0.0"
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BenchmarkMetrics:
    """Metrics collected for a single routing request execution.

    These metrics are algorithm-independent and collected for every run
    to enable fair comparison.

    Attributes
    ----------
    algorithm_name:
        Name of the algorithm that produced this result.
    runtime_s:
        Wall-clock runtime in seconds.
    expanded_nodes:
        Number of nodes expanded during search.
    visited_nodes:
        Number of nodes visited (may differ from expanded in some algorithms).
    route_distance_m:
        Total distance of the primary route in meters (0 if failed).
    travel_time_s:
        Estimated travel time of the primary route in seconds (0 if failed).
    total_cost:
        Total cost of the primary route (0 if failed).
    route_valid:
        Whether the route passed validation.
    success:
        Whether routing succeeded.
    failure_reason:
        Human-readable failure reason (None if success).
    request_description:
        Description of the routing request.
    memory_bytes:
        Estimated memory usage in bytes (0 if not collected).
    candidates_generated:
        Number of route candidates generated.
    """

    algorithm_name: str
    runtime_s: float
    expanded_nodes: int
    visited_nodes: int
    route_distance_m: float
    travel_time_s: float
    total_cost: float
    route_valid: bool
    success: bool
    failure_reason: str | None = None
    request_description: str = ""
    memory_bytes: int = 0
    candidates_generated: int = 0
