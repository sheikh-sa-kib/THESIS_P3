"""SwarmLifecycle — common optimization lifecycle for all swarm algorithms.

Encapsulates the shared iteration loop, termination checking, and
statistics collection that every swarm algorithm uses.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Callable

from e3hybrid.swarm.config import SwarmConfig
from e3hybrid.swarm.context import SwarmContext
from e3hybrid.swarm.models import CandidateSolution, Population, SearchState
from e3hybrid.swarm.result import SwarmResult
from e3hybrid.swarm.statistics import IterationStatistics, SwarmStatistics
from e3hybrid.swarm.termination import TerminationChecker


@dataclass
class SwarmLifecycle:
    """Common optimization lifecycle for swarm algorithms.

    Manages the shared iteration loop: Initialize -> Observe -> Evaluate ->
    Update -> Generate -> Check Termination -> Repeat -> Return.

    Each swarm algorithm provides callbacks for the algorithm-specific
    steps (Initialize, Update, Generate). The lifecycle handles the rest.

    Parameters
    ----------
    config:
        Swarm configuration with termination settings.
    """

    config: SwarmConfig

    def run(
        self,
        context: SwarmContext,
        initialize_fn: Callable[[SwarmContext, SwarmConfig], Population],
        update_fn: Callable[
            [SwarmContext, SwarmConfig, Population, CandidateSolution | None],
            Population,
        ],
        extract_best_fn: Callable[
            [Population, CandidateSolution | None],
            CandidateSolution | None,
        ] = lambda pop, prev: pop.best,
    ) -> SwarmResult:
        """Run the full optimization lifecycle.

        Parameters
        ----------
        context:
            Immutable swarm context.
        initialize_fn:
            Callback that creates the initial population.
            Signature: (context, config) -> Population
        update_fn:
            Callback that produces the next population from current state.
            Signature: (context, config, population, best) -> Population
        extract_best_fn:
            Callback to extract the best solution from a population.
            Default: uses Population.best property.

        Returns
        -------
        SwarmResult
            The complete optimization result.
        """
        checker = TerminationChecker(self.config)
        checker.start()

        # Initialize
        population = initialize_fn(context, self.config)
        best_solution = extract_best_fn(population, None)

        iteration_stats: list[IterationStatistics] = []
        start_time = time.perf_counter()

        # Build initial search state
        search_state = SearchState(
            iteration=0,
            best_score=best_solution.score if best_solution else float("inf"),
            previous_best_score=float("inf"),
            no_improvement_count=0,
            diversity=population.diversity,
            elapsed_time_s=0.0,
        )

        # Record iteration 0 statistics
        iter_stats = self._compute_iteration_stats(
            iteration=0,
            population=population,
            best_solution=best_solution,
            start_time=start_time,
            previous_best_score=float("inf"),
        )
        iteration_stats.append(iter_stats)

        # Check termination after initialization
        term = checker.check(search_state)
        if term.should_stop:
            return self._build_result(
                population=population,
                best_solution=best_solution,
                iteration_stats=iteration_stats,
                start_time=start_time,
                term=term,
            )

        # Iteration loop
        for iteration in range(1, self.config.max_iterations + 1):
            iter_start = time.perf_counter()

            # Update: generate next population from algorithm-specific logic
            population = update_fn(context, self.config, population, best_solution)

            # Extract best solution
            candidate_best = extract_best_fn(population, best_solution)
            if candidate_best is not None:
                if best_solution is None or candidate_best.score < best_solution.score:
                    best_solution = candidate_best

            # Update search state
            prev_best = search_state.best_score
            current_best = best_solution.score if best_solution else float("inf")
            no_improvement = (
                search_state.no_improvement_count + 1
                if current_best >= prev_best
                else 0
            )

            search_state = SearchState(
                iteration=iteration,
                best_score=current_best,
                previous_best_score=prev_best,
                no_improvement_count=no_improvement,
                diversity=population.diversity,
                elapsed_time_s=time.perf_counter() - start_time,
            )

            # Record iteration statistics
            iter_stats = self._compute_iteration_stats(
                iteration=iteration,
                population=population,
                best_solution=best_solution,
                start_time=start_time,
                previous_best_score=prev_best,
            )
            iteration_stats.append(iter_stats)

            # Check termination
            term = checker.check(search_state)
            if term.should_stop:
                return self._build_result(
                    population=population,
                    best_solution=best_solution,
                    iteration_stats=iteration_stats,
                    start_time=start_time,
                    term=term,
                )

        # Max iterations reached without explicit termination
        total_time = time.perf_counter() - start_time
        term = TerminationCondition(
            should_stop=True,
            reason=f"Maximum iterations reached ({self.config.max_iterations})",
            iteration=self.config.max_iterations,
            elapsed_time_s=total_time,
        )
        return self._build_result(
            population=population,
            best_solution=best_solution,
            iteration_stats=iteration_stats,
            start_time=start_time,
            term=term,
        )

    def _compute_iteration_stats(
        self,
        iteration: int,
        population: Population,
        best_solution: CandidateSolution | None,
        start_time: float,
        previous_best_score: float,
    ) -> IterationStatistics:
        """Compute per-iteration statistics from the current population."""
        scores = [c.score for c in population.individuals]
        if scores:
            avg = sum(scores) / len(scores)
            variance = sum((s - avg) ** 2 for s in scores) / len(scores)
            std_dev = math.sqrt(variance)
        else:
            avg = 0.0
            std_dev = 0.0

        current_best = best_solution.score if best_solution else float("inf")
        best_changed = current_best < previous_best_score

        return IterationStatistics(
            iteration=iteration,
            best_score=min(scores) if scores else 0.0,
            average_score=avg,
            midrange_score=(min(scores) + max(scores)) / 2.0 if scores else 0.0,
            worst_score=max(scores) if scores else 0.0,
            std_dev=std_dev,
            diversity=population.diversity,
            best_solution_changed=best_changed,
            runtime_s=time.perf_counter() - start_time,
        )

    def _build_result(
        self,
        population: Population,
        best_solution: CandidateSolution | None,
        iteration_stats: list[IterationStatistics],
        start_time: float,
        term: TerminationCondition,
    ) -> SwarmResult:
        """Build a SwarmResult from lifecycle state."""
        from e3hybrid.routing.candidate import RouteCandidate
        from e3hybrid.routing.cost import RouteCost
        from e3hybrid.routing.types import RouteId

        total_time = time.perf_counter() - start_time

        # Build RouteCandidate from best solution
        candidates: list[RouteCandidate] = []
        if best_solution is not None:
            score = best_solution.score
            route_cost = best_solution.cost_breakdown or RouteCost(
                total=score,
                distance_cost=score,
                time_cost=0.0,
                energy_cost=0.0,
                congestion_penalty=0.0,
                hazard_penalty=0.0,
                emergency_penalty=0.0,
                communication_penalty=0.0,
                components={"distance": score},
            )
            route_candidate = RouteCandidate(
                route_id=RouteId(f"swarm_{id(best_solution)}"),
                node_sequence=best_solution.solution.node_sequence,
                edge_sequence=best_solution.solution.edge_sequence,
                total_cost=best_solution.score,
                cost_breakdown=route_cost,
                algorithm=self.config.algorithm_name,
                metadata=dict(best_solution.solution.metadata),
                runtime_s=total_time,
                search_statistics=None,  # type: ignore[arg-type]
            )
            candidates.append(route_candidate)

        # Compute aggregate statistics
        scores = [c.score for c in population.individuals]
        all_iter_scores = [s.best_score for s in iteration_stats if s.best_score < float("inf")]
        convergence_iter = None
        for i in range(len(iteration_stats) - 1, -1, -1):
            if iteration_stats[i].best_solution_changed:
                convergence_iter = iteration_stats[i].iteration
                break

        statistics = SwarmStatistics(
            total_iterations=term.iteration,
            total_runtime_s=total_time,
            best_score=best_solution.score if best_solution else 0.0,
            average_score=sum(scores) / len(scores) if scores else 0.0,
            worst_score=max(scores) if scores else 0.0,
            convergence_iteration=convergence_iter,
            candidate_count=len(candidates),
            solutions_evaluated=sum(population.size for _ in iteration_stats),
            diversity_history=tuple(s.diversity for s in iteration_stats),
            score_history=tuple(all_iter_scores),
            termination_reason=term.reason,
        )

        return SwarmResult(
            best_solution=route_candidate if best_solution is not None else None,  # type: ignore[arg-type]
            candidates=tuple(candidates),
            statistics=statistics,
            iterations=tuple(iteration_stats),
            success=best_solution is not None,
            failure_reason=None if best_solution is not None else "No solution found",
        )
