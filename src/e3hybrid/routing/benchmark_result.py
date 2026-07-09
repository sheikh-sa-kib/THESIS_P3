"""BenchmarkResult — result of running a benchmark."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from e3hybrid.routing.benchmark_metrics import AlgorithmMetadata, BenchmarkMetrics
from e3hybrid.routing.verifier import VerificationReport

if TYPE_CHECKING:
    from e3hybrid.routing.benchmark_config import BenchmarkConfig
    from e3hybrid.routing.benchmark_scenario import BenchmarkScenario


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """Result of running one algorithm on one benchmark scenario.

    Attributes
    ----------
    algorithm:
        Metadata about the algorithm used.
    scenario:
        The benchmark scenario that was executed.
    metrics:
        Per-request metrics collected during the run.
    verification_reports:
        Per-request verification reports (if verification was enabled).
    summary:
        Summary statistics across all requests.
    config:
        The benchmark configuration used.
    timestamp:
        ISO-8601 timestamp of when the benchmark was run.
    duration_s:
        Total wall-clock duration of the benchmark in seconds.
    """

    algorithm: AlgorithmMetadata
    scenario: "BenchmarkScenario"
    metrics: tuple[BenchmarkMetrics, ...]
    verification_reports: tuple[VerificationReport, ...]
    summary: "BenchmarkSummary"
    config: "BenchmarkConfig"
    timestamp: str
    duration_s: float


@dataclass(frozen=True, slots=True)
class BenchmarkSummary:
    """Summary statistics across all requests in a benchmark.

    Attributes
    ----------
    total_requests:
        Total number of routing requests.
    successful_requests:
        Number of successful routing requests.
    failed_requests:
        Number of failed routing requests.
    avg_runtime_s:
        Average runtime per request in seconds.
    max_runtime_s:
        Maximum runtime across all requests.
    min_runtime_s:
        Minimum runtime across all requests.
    avg_route_distance_m:
        Average route distance in meters (successful only).
    avg_travel_time_s:
        Average estimated travel time in seconds (successful only).
    avg_total_cost:
        Average total cost (successful only).
    total_expanded_nodes:
        Total number of nodes expanded across all requests.
    avg_expanded_nodes:
        Average nodes expanded per request.
    total_verified:
        Number of routes that passed verification.
    verification_failures:
        Number of routes that failed verification.
    """

    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_runtime_s: float
    max_runtime_s: float
    min_runtime_s: float
    avg_route_distance_m: float
    avg_travel_time_s: float
    avg_total_cost: float
    total_expanded_nodes: int
    avg_expanded_nodes: float
    total_verified: int
    verification_failures: int
