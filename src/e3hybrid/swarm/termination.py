"""Termination conditions for swarm optimization.

Supports configurable stopping conditions evaluated by the framework,
not by individual algorithms.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from e3hybrid.swarm.config import SwarmConfig
from e3hybrid.swarm.models import SearchState


@dataclass(frozen=True, slots=True)
class TerminationCondition:
    """Signals whether optimization should continue or stop.

    Evaluated after each iteration by the TerminationChecker.

    Parameters
    ----------
    should_stop:
        Whether optimization should stop.
    reason:
        Human-readable explanation of why optimization stopped.
    iteration:
        The iteration at which termination was triggered.
    elapsed_time_s:
        Wall-clock time elapsed when termination was triggered.
    """

    should_stop: bool = False
    reason: str = ""
    iteration: int = 0
    elapsed_time_s: float = 0.0

    def __post_init__(self) -> None:
        if self.iteration < 0:
            raise ValueError("iteration must be non-negative")
        if self.elapsed_time_s < 0:
            raise ValueError("elapsed_time_s must be non-negative")


class TerminationChecker:
    """Evaluates all configured stopping conditions after each iteration.

    Checks are evaluated in order. The first condition that triggers
    determines the termination reason.

    Parameters
    ----------
    config:
        SwarmConfig containing termination settings.
    """

    def __init__(self, config: SwarmConfig) -> None:
        self._config = config
        self._start_time: float | None = None

    def start(self) -> None:
        """Record the start time."""
        self._start_time = time.perf_counter()

    def check(self, state: SearchState) -> TerminationCondition:
        """Evaluate all configured termination conditions.

        Parameters
        ----------
        state:
            Current search state from the optimization lifecycle.

        Returns
        -------
        TerminationCondition
            Signals whether to stop and why.
        """
        config = self._config
        elapsed = time.perf_counter() - (self._start_time or 0.0)

        # 1. Maximum iterations
        if config.max_iterations > 0 and state.iteration >= config.max_iterations:
            return TerminationCondition(
                should_stop=True,
                reason=f"Maximum iterations reached ({config.max_iterations})",
                iteration=state.iteration,
                elapsed_time_s=elapsed,
            )

        # 2. Time limit
        if config.time_limit_s > 0.0 and elapsed >= config.time_limit_s:
            return TerminationCondition(
                should_stop=True,
                reason=f"Time limit reached ({config.time_limit_s}s)",
                iteration=state.iteration,
                elapsed_time_s=elapsed,
            )

        # 3. Target score
        if config.target_score > 0.0 and state.best_score <= config.target_score:
            return TerminationCondition(
                should_stop=True,
                reason=f"Target score achieved ({config.target_score})",
                iteration=state.iteration,
                elapsed_time_s=elapsed,
            )

        # 4. Convergence (no improvement below threshold)
        if config.convergence_threshold > 0.0:
            improvement = abs(state.best_score - state.previous_best_score)
            if improvement < config.convergence_threshold:
                return TerminationCondition(
                    should_stop=True,
                    reason=(
                        f"Converged: improvement {improvement} < "
                        f"threshold {config.convergence_threshold}"
                    ),
                    iteration=state.iteration,
                    elapsed_time_s=elapsed,
                )

        # 5. No improvement for stall_limit iterations
        if (
            config.stall_limit > 0
            and state.no_improvement_count >= config.stall_limit
        ):
            return TerminationCondition(
                should_stop=True,
                reason=(
                    f"No improvement for {config.stall_limit} "
                    f"consecutive iterations"
                ),
                iteration=state.iteration,
                elapsed_time_s=elapsed,
            )

        # 6. Continue
        return TerminationCondition(
            should_stop=False,
            reason="Continuing",
            iteration=state.iteration,
            elapsed_time_s=elapsed,
        )

    def reset(self) -> None:
        """Reset the checker for a new optimization run."""
        self._start_time = None
