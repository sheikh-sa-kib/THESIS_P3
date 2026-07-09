"""BenchmarkConfig — configuration for routing benchmarks."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from e3hybrid.routing.cost_calculator import CostWeights


@dataclass(frozen=True, slots=True)
class BenchmarkConfig:
    """Configuration for a routing benchmark.

    This configuration is used by every algorithm in the benchmark to ensure
    identical conditions for fair comparison.

    Attributes
    ----------
    algorithm_names:
        Names of algorithms to benchmark.
    num_requests:
        Number of routing requests to generate per scenario.
    timeout_s:
        Maximum allowed runtime per routing request in seconds.
    max_candidates:
        Maximum number of route candidates per request.
    output_dir:
        Directory for benchmark output artifacts.
    seed:
        Random seed for deterministic request generation.
    cost_weights:
        Cost weights for all algorithms.
    verify_routes:
        If True, verify every route after computation.
    collect_memory:
        If True, collect memory usage statistics (may slow benchmarks).
    description:
        Human-readable description of this benchmark run.
    metadata:
        Additional metadata for the benchmark.
    """

    algorithm_names: tuple[str, ...] = ("dijkstra",)
    num_requests: int = 10
    timeout_s: float = 10.0
    max_candidates: int = 5
    output_dir: str = "results"
    seed: int = 42
    cost_weights: CostWeights = field(default_factory=CostWeights)
    verify_routes: bool = True
    collect_memory: bool = False
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
