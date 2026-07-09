"""BenchmarkValidator — validates benchmark results and configurations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from e3hybrid.routing.benchmark_config import BenchmarkConfig
    from e3hybrid.routing.benchmark_metrics import BenchmarkMetrics
    from e3hybrid.routing.benchmark_result import BenchmarkResult
    from e3hybrid.routing.benchmark_scenario import BenchmarkScenario


@dataclass(frozen=True, slots=True)
class BenchmarkValidationError:
    """A single validation error for benchmark components."""

    field_name: str
    error_message: str


@dataclass(frozen=True, slots=True)
class BenchmarkValidationReport:
    """Report of validation results.

    Attributes
    ----------
    is_valid:
        Whether all checks passed.
    errors:
        Tuple of validation errors found.
    """

    is_valid: bool
    errors: tuple[BenchmarkValidationError, ...]

    def __str__(self) -> str:
        if self.is_valid:
            return "Benchmark validation passed"
        lines = [f"  - {e.field_name}: {e.error_message}" for e in self.errors]
        return "Benchmark validation failed:\n" + "\n".join(lines)


class BenchmarkValidator:
    """Validator for benchmark configurations, scenarios, results, and metrics.

    Ensures that benchmarks are correctly configured before execution and
    that results are internally consistent after execution.
    """

    @staticmethod
    def validate_config(
        config: "BenchmarkConfig",
    ) -> BenchmarkValidationReport:
        """Validate a benchmark configuration.

        Parameters
        ----------
        config:
            The configuration to validate.

        Returns
        -------
        BenchmarkValidationReport
            Report of validation errors.
        """
        errors: list[BenchmarkValidationError] = []

        if not config.algorithm_names:
            errors.append(
                BenchmarkValidationError(
                    field_name="algorithm_names",
                    error_message="Must specify at least one algorithm",
                )
            )

        if config.num_requests <= 0:
            errors.append(
                BenchmarkValidationError(
                    field_name="num_requests",
                    error_message="num_requests must be positive",
                )
            )

        if config.timeout_s <= 0:
            errors.append(
                BenchmarkValidationError(
                    field_name="timeout_s",
                    error_message="timeout_s must be positive",
                )
            )

        if config.max_candidates <= 0:
            errors.append(
                BenchmarkValidationError(
                    field_name="max_candidates",
                    error_message="max_candidates must be positive",
                )
            )

        if not config.output_dir:
            errors.append(
                BenchmarkValidationError(
                    field_name="output_dir",
                    error_message="output_dir must not be empty",
                )
            )

        return BenchmarkValidationReport(
            is_valid=len(errors) == 0,
            errors=tuple(errors),
        )

    @staticmethod
    def validate_scenario(
        scenario: "BenchmarkScenario",
    ) -> BenchmarkValidationReport:
        """Validate a benchmark scenario.

        Parameters
        ----------
        scenario:
            The scenario to validate.

        Returns
        -------
        BenchmarkValidationReport
            Report of validation errors.
        """
        errors: list[BenchmarkValidationError] = []

        if not scenario.requests:
            errors.append(
                BenchmarkValidationError(
                    field_name="requests",
                    error_message="Scenario must have at least one request",
                )
            )

        if not scenario.name:
            errors.append(
                BenchmarkValidationError(
                    field_name="name",
                    error_message="Scenario name must not be empty",
                )
            )

        # Validate every request has a valid source and destination
        for i, br in enumerate(scenario.requests):
            if br.request.source_node == br.request.destination_node:
                errors.append(
                    BenchmarkValidationError(
                        field_name=f"requests[{i}]",
                        error_message=(
                            f"Source and destination must differ "
                            f"(both are {br.request.source_node})"
                        ),
                    )
                )

            if not scenario.graph.has_node(br.request.source_node):
                errors.append(
                    BenchmarkValidationError(
                        field_name=f"requests[{i}]",
                        error_message=(
                            f"Source node {br.request.source_node} "
                            f"does not exist in graph"
                        ),
                    )
                )

            if not scenario.graph.has_node(br.request.destination_node):
                errors.append(
                    BenchmarkValidationError(
                        field_name=f"requests[{i}]",
                        error_message=(
                            f"Destination node {br.request.destination_node} "
                            f"does not exist in graph"
                        ),
                    )
                )

        return BenchmarkValidationReport(
            is_valid=len(errors) == 0,
            errors=tuple(errors),
        )

    @staticmethod
    def validate_metrics(
        metrics: "BenchmarkMetrics",
    ) -> BenchmarkValidationReport:
        """Validate individual benchmark metrics.

        Parameters
        ----------
        metrics:
            The metrics to validate.

        Returns
        -------
        BenchmarkValidationReport
            Report of validation errors.
        """
        errors: list[BenchmarkValidationError] = []

        if not metrics.algorithm_name:
            errors.append(
                BenchmarkValidationError(
                    field_name="algorithm_name",
                    error_message="Algorithm name must not be empty",
                )
            )

        if metrics.runtime_s < 0:
            errors.append(
                BenchmarkValidationError(
                    field_name="runtime_s",
                    error_message=f"runtime_s ({metrics.runtime_s}) must be non-negative",
                )
            )

        if metrics.expanded_nodes < 0:
            errors.append(
                BenchmarkValidationError(
                    field_name="expanded_nodes",
                    error_message="expanded_nodes must be non-negative",
                )
            )

        if metrics.visited_nodes < 0:
            errors.append(
                BenchmarkValidationError(
                    field_name="visited_nodes",
                    error_message="visited_nodes must be non-negative",
                )
            )

        if metrics.total_cost < 0:
            errors.append(
                BenchmarkValidationError(
                    field_name="total_cost",
                    error_message=f"total_cost ({metrics.total_cost}) must be non-negative",
                )
            )

        if metrics.success and metrics.failure_reason is not None:
            errors.append(
                BenchmarkValidationError(
                    field_name="failure_reason",
                    error_message="success=True requires failure_reason=None",
                )
            )

        if not metrics.success and metrics.failure_reason is None:
            errors.append(
                BenchmarkValidationError(
                    field_name="failure_reason",
                    error_message="success=False requires failure_reason",
                )
            )

        return BenchmarkValidationReport(
            is_valid=len(errors) == 0,
            errors=tuple(errors),
        )

    @staticmethod
    def validate_result(
        result: "BenchmarkResult",
    ) -> BenchmarkValidationReport:
        """Validate a complete benchmark result.

        Parameters
        ----------
        result:
            The benchmark result to validate.

        Returns
        -------
        BenchmarkValidationReport
            Report of validation errors.
        """
        errors: list[BenchmarkValidationError] = []

        if not result.metrics:
            errors.append(
                BenchmarkValidationError(
                    field_name="metrics",
                    error_message="Result must have at least one metric entry",
                )
            )

        if result.duration_s < 0:
            errors.append(
                BenchmarkValidationError(
                    field_name="duration_s",
                    error_message=f"duration_s ({result.duration_s}) must be non-negative",
                )
            )

        # Verify summary consistency
        if result.summary.total_requests != len(result.metrics):
            errors.append(
                BenchmarkValidationError(
                    field_name="summary.total_requests",
                    error_message=(
                        f"summary.total_requests ({result.summary.total_requests}) "
                        f"!= len(metrics) ({len(result.metrics)})"
                    ),
                )
            )

        # Count successful and failed requests
        actual_successful = sum(1 for m in result.metrics if m.success)
        actual_failed = sum(1 for m in result.metrics if not m.success)

        if result.summary.successful_requests != actual_successful:
            errors.append(
                BenchmarkValidationError(
                    field_name="summary.successful_requests",
                    error_message=(
                        f"Expected {actual_successful}, "
                        f"got {result.summary.successful_requests}"
                    ),
                )
            )

        if result.summary.failed_requests != actual_failed:
            errors.append(
                BenchmarkValidationError(
                    field_name="summary.failed_requests",
                    error_message=(
                        f"Expected {actual_failed}, "
                        f"got {result.summary.failed_requests}"
                    ),
                )
            )

        return BenchmarkValidationReport(
            is_valid=len(errors) == 0,
            errors=tuple(errors),
        )
