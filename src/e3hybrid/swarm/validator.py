"""SwarmValidator — algorithm-independent validation for swarm components.

Validates configurations, states, and results without knowing which
swarm algorithm produced them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from e3hybrid.swarm.config import SwarmConfig
    from e3hybrid.swarm.models import Population
    from e3hybrid.swarm.result import SwarmResult
    from e3hybrid.swarm.state import SwarmState


@dataclass(frozen=True, slots=True)
class SwarmValidationReport:
    """Structured validation report for swarm components.

    Parameters
    ----------
    is_valid:
        Whether all validation checks passed.
    errors:
        List of error messages for failed checks.
    warnings:
        List of non-blocking warning messages.
    checks_performed:
        Total number of validation checks performed.
    checks_passed:
        Number of checks that passed.
    """

    is_valid: bool
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    checks_performed: int = 0
    checks_passed: int = 0


class SwarmValidator:
    """Validates swarm configurations, states, and results.

    Algorithm-independent checks that apply to ACO, BCO, PSO, and any
    future swarm algorithm.
    """

    @staticmethod
    def validate_config(config: "SwarmConfig") -> SwarmValidationReport:
        """Validate a swarm configuration.

        Checks:
        - algorithm_name is non-empty
        - population_size is positive
        - max_iterations is positive
        - time_limit_s is non-negative
        - convergence_threshold is non-negative
        - stall_limit is non-negative
        - target_score is non-negative

        Parameters
        ----------
        config:
            The swarm configuration to validate.

        Returns
        -------
        SwarmValidationReport
            Report with validation results.
        """
        errors: list[str] = []
        warnings: list[str] = []
        checks = 0
        passed = 0

        checks += 1
        if not config.algorithm_name:
            errors.append("algorithm_name must be non-empty")
        else:
            passed += 1

        checks += 1
        if config.population_size < 1:
            errors.append("population_size must be positive")
        else:
            passed += 1

        checks += 1
        if config.max_iterations < 1:
            errors.append("max_iterations must be positive")
        else:
            passed += 1

        checks += 1
        if config.time_limit_s < 0:
            errors.append("time_limit_s must be non-negative")
        else:
            passed += 1

        checks += 1
        if config.convergence_threshold < 0:
            errors.append("convergence_threshold must be non-negative")
        else:
            passed += 1

        checks += 1
        if config.stall_limit < 0:
            errors.append("stall_limit must be non-negative")
        else:
            passed += 1

        checks += 1
        if config.target_score < 0:
            errors.append("target_score must be non-negative")
        else:
            passed += 1

        # Warning: time_limit_s and max_iterations both set (either could trigger)
        checks += 1
        if config.time_limit_s > 0 and config.max_iterations > 0:
            warnings.append(
                "Both time_limit_s and max_iterations are set; "
                "the first condition to trigger will terminate optimization"
            )
        passed += 1  # This is informational, not an error

        return SwarmValidationReport(
            is_valid=len(errors) == 0,
            errors=tuple(errors),
            warnings=tuple(warnings),
            checks_performed=checks,
            checks_passed=passed,
        )

    @staticmethod
    def validate_state(state: "SwarmState") -> SwarmValidationReport:
        """Validate a swarm state snapshot.

        Checks:
        - iteration is non-negative
        - population is not empty
        - best_solution exists
        - best_solution score is consistent with population

        Parameters
        ----------
        state:
            The swarm state to validate.

        Returns
        -------
        SwarmValidationReport
            Report with validation results.
        """
        errors: list[str] = []
        checks = 0
        passed = 0

        checks += 1
        if state.iteration < 0:
            errors.append("iteration must be non-negative")
        else:
            passed += 1

        checks += 1
        if state.population.size == 0:
            errors.append("population must not be empty")
        else:
            passed += 1

        checks += 1
        if state.best_solution is None:
            errors.append("best_solution must not be None")
        else:
            passed += 1

        if state.best_solution is not None and state.population.size > 0:
            checks += 1
            pop_best = state.population.best
            if pop_best is not None and state.best_solution.score > pop_best.score:
                errors.append(
                    "best_solution score must be <= population best score"
                )
            else:
                passed += 1

        return SwarmValidationReport(
            is_valid=len(errors) == 0,
            errors=tuple(errors),
            checks_performed=checks,
            checks_passed=passed,
        )

    @staticmethod
    def validate_result(result: "SwarmResult") -> SwarmValidationReport:
        """Validate a swarm result.

        Checks:
        - success and failure_reason consistency
        - best_solution is valid when success is True
        - statistics are consistent

        Parameters
        ----------
        result:
            The swarm result to validate.

        Returns
        -------
        SwarmValidationReport
            Report with validation results.
        """
        errors: list[str] = []
        checks = 0
        passed = 0

        checks += 1
        if result.success and result.failure_reason is not None:
            errors.append("success=True requires failure_reason=None")
        else:
            passed += 1

        checks += 1
        if not result.success and result.failure_reason is None:
            errors.append("success=False requires failure_reason")
        else:
            passed += 1

        if result.success:
            checks += 1
            if result.best_solution is None:
                errors.append("success=True requires best_solution")
            else:
                passed += 1

        checks += 1
        if result.statistics.total_iterations < 0:
            errors.append("total_iterations must be non-negative")
        else:
            passed += 1

        checks += 1
        if result.statistics.total_runtime_s < 0:
            errors.append("total_runtime_s must be non-negative")
        else:
            passed += 1

        return SwarmValidationReport(
            is_valid=len(errors) == 0,
            errors=tuple(errors),
            checks_performed=checks,
            checks_passed=passed,
        )

    @staticmethod
    def validate_population(population: "Population") -> SwarmValidationReport:
        """Validate a population of candidates.

        Checks:
        - population is not empty
        - all individuals have valid scores
        - iteration is non-negative

        Parameters
        ----------
        population:
            The population to validate.

        Returns
        -------
        SwarmValidationReport
            Report with validation results.
        """
        errors: list[str] = []
        checks = 0
        passed = 0

        checks += 1
        if population.size == 0:
            errors.append("population must not be empty")
        else:
            passed += 1

        checks += 1
        if population.iteration < 0:
            errors.append("iteration must be non-negative")
        else:
            passed += 1

        for i, individual in enumerate(population.individuals):
            checks += 1
            if individual.score < 0:
                errors.append(f"individual {i}: score must be non-negative")
            else:
                passed += 1

        return SwarmValidationReport(
            is_valid=len(errors) == 0,
            errors=tuple(errors),
            checks_performed=checks,
            checks_passed=passed,
        )
