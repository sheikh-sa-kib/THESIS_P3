"""BenchmarkRunner — orchestrates benchmark lifecycle for routing algorithms.

Lifecycle
---------
1. Load benchmark configuration
2. Generate (or load) routing requests
3. For each algorithm:
   a. Validate configuration
   b. Validate scenario
   c. For each request:
      i.   Execute algorithm
      ii.  Verify result (if enabled)
      iii. Collect metrics
   d. Compute summary statistics
4. Write benchmark artifacts

The BenchmarkRunner does NOT know algorithm internals.
It interacts with algorithms only through the RoutingAlgorithm Protocol.
"""

from __future__ import annotations

import time
import tracemalloc
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from e3hybrid.routing.benchmark_metrics import AlgorithmMetadata, BenchmarkMetrics
from e3hybrid.routing.benchmark_result import BenchmarkResult, BenchmarkSummary
from e3hybrid.routing.benchmark_validator import BenchmarkValidator
from e3hybrid.routing.exceptions import RoutingError
from e3hybrid.routing.factory import RoutingFactory
from e3hybrid.routing.verifier import RoutingVerifier

if TYPE_CHECKING:
    from e3hybrid.routing.benchmark_config import BenchmarkConfig
    from e3hybrid.routing.benchmark_scenario import BenchmarkScenario


@dataclass(frozen=True, slots=True)
class BenchmarkContext:
    """Execution context for a single benchmark run.

    This is assembled by the runner and passed to internal methods;
    algorithms never see this object. They only see RoutingRequest.
    """

    algorithm_name: str
    verify_routes: bool
    collect_memory: bool


class BenchmarkRunner:
    """Orchestrates benchmark execution for routing algorithms.

    The runner is algorithm-agnostic. It creates algorithm instances via
    RoutingFactory and interacts with them only through the RoutingAlgorithm
    Protocol.
    """

    def __init__(self, config: "BenchmarkConfig") -> None:
        """Initialize the benchmark runner.

        Parameters
        ----------
        config:
            Benchmark configuration.
        """
        self._config = config
        self._validator = BenchmarkValidator()

    @property
    def config(self) -> "BenchmarkConfig":
        """Return the benchmark configuration."""
        return self._config

    def run_scenario(
        self,
        scenario: "BenchmarkScenario",
    ) -> list[BenchmarkResult]:
        """Run all algorithms on a single scenario.

        Parameters
        ----------
        scenario:
            The benchmark scenario to execute.

        Returns
        -------
        list[BenchmarkResult]
            Results for each algorithm in the configuration.
        """
        # Validate scenario
        scenario_report = self._validator.validate_scenario(scenario)
        if not scenario_report.is_valid:
            raise ValueError(
                f"Invalid benchmark scenario '{scenario.name}': {scenario_report}"
            )

        results: list[BenchmarkResult] = []

        for algo_name in self._config.algorithm_names:
            algorithm = RoutingFactory.create_algorithm(algo_name)

            metadata = AlgorithmMetadata(
                name=algo_name,
                description=f"{algo_name} routing algorithm",
                parameters={
                    "timeout_s": self._config.timeout_s,
                    "max_candidates": self._config.max_candidates,
                    "cost_weights": {
                        "distance": self._config.cost_weights.distance,
                        "time": self._config.cost_weights.time,
                        "energy": self._config.cost_weights.energy,
                        "congestion": self._config.cost_weights.congestion,
                        "hazard": self._config.cost_weights.hazard,
                        "emergency": self._config.cost_weights.emergency,
                        "communication": self._config.cost_weights.communication,
                    },
                },
            )

            ctx = BenchmarkContext(
                algorithm_name=algo_name,
                verify_routes=self._config.verify_routes,
                collect_memory=self._config.collect_memory,
            )

            result = self._run_single_algorithm(
                algorithm=algorithm,
                metadata=metadata,
                scenario=scenario,
                ctx=ctx,
            )

            results.append(result)

        return results

    def _run_single_algorithm(
        self,
        algorithm: "RoutingAlgorithm",  # type: ignore[name-defined]
        metadata: AlgorithmMetadata,
        scenario: "BenchmarkScenario",
        ctx: BenchmarkContext,
    ) -> BenchmarkResult:
        """Run a single algorithm on a benchmark scenario.

        Parameters
        ----------
        algorithm:
            The routing algorithm instance.
        metadata:
            Algorithm metadata.
        scenario:
            The benchmark scenario.
        ctx:
            Execution context.

        Returns
        -------
        BenchmarkResult
            Complete benchmark result for this algorithm.
        """
        metrics_list: list[BenchmarkMetrics] = []
        verification_reports_list = []
        start_time = time.perf_counter()

        for benchmark_request in scenario.requests:
            request = benchmark_request.request

            # Execute the algorithm
            if ctx.collect_memory:
                tracemalloc.start()

            algo_start = time.perf_counter()
            try:
                result = algorithm.compute_route(request, scenario.graph)
                algo_runtime = time.perf_counter() - algo_start
                algorithm_success = result.success
            except RoutingError as e:
                algo_runtime = time.perf_counter() - algo_start
                algorithm_success = False
                result = None  # type: ignore[assignment]
                failure_reason = str(e)
            except Exception as e:
                algo_runtime = time.perf_counter() - algo_start
                algorithm_success = False
                result = None
                failure_reason = f"Unexpected error: {e}"

            # Collect memory
            memory_bytes = 0
            if ctx.collect_memory:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                memory_bytes = peak

            # Extract metrics
            if algorithm_success and result is not None:
                expanded_nodes = result.statistics.nodes_explored
                visited_nodes = result.statistics.nodes_explored
                candidates_generated = result.statistics.candidates_generated
                route_distance = (
                    result.primary_route.total_distance_m
                    if result.primary_route
                    else 0.0
                )
                travel_time = (
                    result.primary_route.estimated_travel_time_s
                    if result.primary_route
                    else 0.0
                )
                total_cost = (
                    result.candidates[0].total_cost if result.candidates else 0.0
                )
                failure_reason = None
            else:
                expanded_nodes = result.statistics.nodes_explored if result is not None else 0
                visited_nodes = result.statistics.nodes_explored if result is not None else 0
                candidates_generated = result.statistics.candidates_generated if result is not None else 0
                route_distance = 0.0
                travel_time = 0.0
                total_cost = 0.0
                failure_reason = result.failure_reason if result is not None else "No result"

            # Verify the result if enabled
            route_valid = False
            if ctx.verify_routes and algorithm_success and result is not None:
                ver_report = RoutingVerifier.verify_result(
                    result, scenario.graph, request
                )
                route_valid = ver_report.is_valid
            elif ctx.verify_routes:
                ver_report = RoutingVerifier.verify_result(
                    _create_empty_result(request),
                    scenario.graph,
                    request,
                )
                route_valid = False

            if ctx.verify_routes:
                verification_reports_list.append(ver_report)
            else:
                verification_reports_list.append(
                    RoutingVerifier.verify_result(
                        _create_empty_result(request) if not algorithm_success
                        else result,
                        scenario.graph,
                        request,
                    )
                )

            metrics = BenchmarkMetrics(
                algorithm_name=ctx.algorithm_name,
                runtime_s=algo_runtime,
                expanded_nodes=expanded_nodes,
                visited_nodes=visited_nodes,
                route_distance_m=route_distance,
                travel_time_s=travel_time,
                total_cost=total_cost,
                route_valid=route_valid,
                success=algorithm_success,
                failure_reason=failure_reason,
                request_description=benchmark_request.description,
                memory_bytes=memory_bytes,
                candidates_generated=candidates_generated,
            )

            metrics_list.append(metrics)

        total_duration = time.perf_counter() - start_time

        # Compute summary statistics
        successful = [m for m in metrics_list if m.success]
        failed = [m for m in metrics_list if not m.success]
        verified = [m for m in metrics_list if m.route_valid]

        if successful:
            avg_runtime = sum(m.runtime_s for m in successful) / len(successful)
            max_runtime = max(m.runtime_s for m in successful)
            min_runtime = min(m.runtime_s for m in successful)
            avg_distance = sum(m.route_distance_m for m in successful) / len(successful)
            avg_travel = sum(m.travel_time_s for m in successful) / len(successful)
            avg_cost = sum(m.total_cost for m in successful) / len(successful)
            avg_expanded = sum(m.expanded_nodes for m in successful) / len(successful)
            total_expanded = sum(m.expanded_nodes for m in successful)
        else:
            avg_runtime = 0.0
            max_runtime = 0.0
            min_runtime = 0.0
            avg_distance = 0.0
            avg_travel = 0.0
            avg_cost = 0.0
            avg_expanded = 0.0
            total_expanded = 0

        summary = BenchmarkSummary(
            total_requests=len(metrics_list),
            successful_requests=len(successful),
            failed_requests=len(failed),
            avg_runtime_s=avg_runtime,
            max_runtime_s=max_runtime,
            min_runtime_s=min_runtime,
            avg_route_distance_m=avg_distance,
            avg_travel_time_s=avg_travel,
            avg_total_cost=avg_cost,
            total_expanded_nodes=total_expanded,
            avg_expanded_nodes=avg_expanded,
            total_verified=len(verified),
            verification_failures=len(metrics_list) - len(verified),
        )

        return BenchmarkResult(
            algorithm=metadata,
            scenario=scenario,
            metrics=tuple(metrics_list),
            verification_reports=tuple(verification_reports_list),
            summary=summary,
            config=self._config,
            timestamp=datetime.now(timezone.utc).isoformat(),
            duration_s=total_duration,
        )


def _create_empty_result(request: "RoutingRequest") -> "RoutingResult":  # type: ignore[name-defined]
    """Create an empty (failure) RoutingResult for verification without a real result."""
    from e3hybrid.routing.result import RoutingResult
    from e3hybrid.routing.statistics import RoutingStatistics

    return RoutingResult(
        candidates=(),
        primary_route=None,
        success=False,
        failure_reason="No result (empty placeholder)",
        statistics=RoutingStatistics(
            nodes_explored=0,
            edges_explored=0,
            candidates_generated=0,
        ),
        runtime_s=0.0,
    )
