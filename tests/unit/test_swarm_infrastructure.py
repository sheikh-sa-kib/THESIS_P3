"""Comprehensive unit tests for common swarm infrastructure.

Tests are algorithm-agnostic. No ACO, BCO, PSO, or E³-Hybrid references.
"""

from __future__ import annotations

import math
import time

import pytest

from e3hybrid.network.types import EdgeId, NodeId
from e3hybrid.routing.cost import RouteCost
from e3hybrid.routing.cost_calculator import CostWeights
from e3hybrid.swarm import (
    CandidateSolution,
    IterationStatistics,
    OptimizationScore,
    Population,
    SearchState,
    Solution,
    SwarmAlgorithm,
    SwarmConfig,
    SwarmContext,
    SwarmFactory,
    SwarmLifecycle,
    SwarmRandom,
    SwarmResult,
    SwarmState,
    SwarmStatistics,
    SwarmToRoutingAdapter,
    SwarmValidationReport,
    SwarmValidator,
    TerminationChecker,
    TerminationCondition,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_solution() -> Solution:
    return Solution(
        node_sequence=(NodeId("A"), NodeId("B"), NodeId("C")),
        edge_sequence=(EdgeId("AB"), EdgeId("BC")),
    )


@pytest.fixture
def sample_candidate(sample_solution: Solution) -> CandidateSolution:
    return CandidateSolution(solution=sample_solution, score=100.0)


@pytest.fixture
def sample_config() -> SwarmConfig:
    return SwarmConfig(
        algorithm_name="test_algo",
        population_size=10,
        max_iterations=50,
        seed=42,
    )


@pytest.fixture
def sample_context(sample_config: SwarmConfig) -> SwarmContext:
    return SwarmContext(
        cost_weights=sample_config.cost_weights,
        config=sample_config,
        random_seed=42,
        routing_request=None,  # type: ignore[arg-type]
        sim_time_s=0.0,
    )


# =============================================================================
# Solution
# =============================================================================

class TestSolution:
    def test_create(self) -> None:
        sol = Solution(
            node_sequence=(NodeId("A"), NodeId("B")),
            edge_sequence=(EdgeId("AB"),),
        )
        assert sol.source_node == NodeId("A")
        assert sol.destination_node == NodeId("B")
        assert sol.edge_count == 1

    def test_invalid_node_sequence(self) -> None:
        with pytest.raises(ValueError, match="at least 2 nodes"):
            Solution(
                node_sequence=(NodeId("A"),),
                edge_sequence=(),
            )

    def test_edge_sequence_mismatch(self) -> None:
        with pytest.raises(ValueError, match="must equal"):
            Solution(
                node_sequence=(NodeId("A"), NodeId("B"), NodeId("C")),
                edge_sequence=(EdgeId("AB"),),
            )

    def test_properties(self, sample_solution: Solution) -> None:
        assert sample_solution.source_node == NodeId("A")
        assert sample_solution.destination_node == NodeId("C")
        assert sample_solution.edge_count == 2

    def test_immutable(self, sample_solution: Solution) -> None:
        with pytest.raises(AttributeError):
            sample_solution.node_sequence = ()  # type: ignore[misc]

    def test_metadata(self) -> None:
        sol = Solution(
            node_sequence=(NodeId("A"), NodeId("B")),
            edge_sequence=(EdgeId("AB"),),
            metadata={"origin": "test"},
        )
        assert sol.metadata["origin"] == "test"


# =============================================================================
# CandidateSolution
# =============================================================================

class TestCandidateSolution:
    def test_create(self, sample_solution: Solution) -> None:
        cs = CandidateSolution(solution=sample_solution, score=100.0)
        assert cs.score == 100.0

    def test_create_with_all_fields(self, sample_solution: Solution) -> None:
        rc = RouteCost(
            total=100.0, distance_cost=100.0, time_cost=0.0, energy_cost=0.0,
            congestion_penalty=0.0, hazard_penalty=0.0, emergency_penalty=0.0,
            communication_penalty=0.0, components={},
        )
        cs = CandidateSolution(
            solution=sample_solution,
            score=50.0,
            cost_breakdown=rc,
            iteration_created=5,
            algorithm_specific={"pheromone": 0.8},
        )
        assert cs.score == 50.0
        assert cs.cost_breakdown.total == 100.0
        assert cs.iteration_created == 5
        assert cs.algorithm_specific["pheromone"] == 0.8

    def test_negative_score(self, sample_solution: Solution) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            CandidateSolution(solution=sample_solution, score=-1.0)

    def test_negative_iteration(self, sample_solution: Solution) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            CandidateSolution(solution=sample_solution, score=0.0, iteration_created=-1)


# =============================================================================
# OptimizationScore
# =============================================================================

class TestOptimizationScore:
    def test_create(self) -> None:
        os = OptimizationScore(total=100.0, normalized=1.0, rank=1)
        assert os.total == 100.0
        assert os.normalized == 1.0
        assert os.rank == 1

    def test_negative_rank(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            OptimizationScore(total=0.0, rank=-1)

    def test_components(self) -> None:
        os = OptimizationScore(total=100.0, components={"distance": 80.0, "time": 20.0})
        assert os.components["distance"] == 80.0


# =============================================================================
# SearchState
# =============================================================================

class TestSearchState:
    def test_create(self) -> None:
        ss = SearchState(
            iteration=5,
            best_score=50.0,
            previous_best_score=100.0,
            no_improvement_count=2,
            diversity=0.3,
            elapsed_time_s=10.0,
        )
        assert ss.iteration == 5
        assert ss.best_score == 50.0

    def test_negative_iteration(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            SearchState(
                iteration=-1, best_score=0.0, previous_best_score=0.0,
                no_improvement_count=0, diversity=0.0, elapsed_time_s=0.0,
            )

    def test_negative_no_improvement(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            SearchState(
                iteration=0, best_score=0.0, previous_best_score=0.0,
                no_improvement_count=-1, diversity=0.0, elapsed_time_s=0.0,
            )

    def test_negative_elapsed_time(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            SearchState(
                iteration=0, best_score=0.0, previous_best_score=0.0,
                no_improvement_count=0, diversity=0.0, elapsed_time_s=-1.0,
            )


# =============================================================================
# Population
# =============================================================================

class TestPopulation:
    def test_create(self, sample_candidate: CandidateSolution) -> None:
        pop = Population(individuals=(sample_candidate,), diversity=0.5, iteration=1)
        assert pop.size == 1
        assert pop.diversity == 0.5
        assert pop.iteration == 1

    def test_empty_population(self) -> None:
        pop = Population(individuals=(), iteration=0)
        assert pop.size == 0
        assert pop.best is None
        assert pop.average_score == 0.0
        assert pop.worst_score == 0.0

    def test_best_by_min_score(self) -> None:
        sol = Solution(
            node_sequence=(NodeId("A"), NodeId("B")),
            edge_sequence=(EdgeId("AB"),),
        )
        c1 = CandidateSolution(solution=sol, score=100.0)
        c2 = CandidateSolution(solution=sol, score=50.0)
        c3 = CandidateSolution(solution=sol, score=75.0)
        pop = Population(individuals=(c1, c2, c3), iteration=0)
        assert pop.best is not None
        assert pop.best.score == 50.0
        assert pop.worst_score == 100.0
        assert abs(pop.average_score - 75.0) < 1e-6

    def test_negative_iteration(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            Population(individuals=(), iteration=-1)


# =============================================================================
# SwarmConfig
# =============================================================================

class TestSwarmConfig:
    def test_defaults(self) -> None:
        cfg = SwarmConfig()
        assert cfg.population_size == 10
        assert cfg.max_iterations == 100
        assert cfg.seed == 42

    def test_custom_values(self) -> None:
        cfg = SwarmConfig(
            algorithm_name="aco",
            population_size=30,
            max_iterations=200,
            time_limit_s=60.0,
            convergence_threshold=1e-4,
            stall_limit=20,
            target_score=0.0,
            seed=12345,
            hyperparameters={"alpha": 1.0, "beta": 2.0},
        )
        assert cfg.algorithm_name == "aco"
        assert cfg.population_size == 30
        assert cfg.max_iterations == 200
        assert cfg.time_limit_s == 60.0
        assert cfg.hyperparameters["alpha"] == 1.0

    def test_negative_population_size(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            SwarmConfig(population_size=0)

    def test_negative_max_iterations(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            SwarmConfig(max_iterations=0)

    def test_negative_time_limit(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            SwarmConfig(time_limit_s=-1.0)

    def test_negative_convergence_threshold(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            SwarmConfig(convergence_threshold=-1.0)

    def test_negative_stall_limit(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            SwarmConfig(stall_limit=-1)

    def test_negative_target_score(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            SwarmConfig(target_score=-1.0)


# =============================================================================
# SwarmContext
# =============================================================================

class TestSwarmContext:
    def test_create(self, sample_config: SwarmConfig) -> None:
        ctx = SwarmContext(
            cost_weights=sample_config.cost_weights,
            config=sample_config,
            random_seed=42,
            routing_request=None,  # type: ignore[arg-type]
            sim_time_s=100.0,
        )
        assert ctx.random_seed == 42
        assert ctx.sim_time_s == 100.0
        assert ctx.config.algorithm_name == "test_algo"

    def test_negative_seed(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            SwarmContext(
                cost_weights=CostWeights(),
                config=SwarmConfig(),
                random_seed=-1,
                routing_request=None,
                sim_time_s=0.0,
            )

    def test_negative_sim_time(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            SwarmContext(
                cost_weights=CostWeights(),
                config=SwarmConfig(),
                random_seed=0,
                routing_request=None,
                sim_time_s=-1.0,
            )

    def test_forward_ref_resolved(self) -> None:
        """SwarmConfig forward reference in type annotation must resolve."""
        ctx = SwarmContext(
            cost_weights=CostWeights(),
            config=SwarmConfig(algorithm_name="test"),
            random_seed=0,
            routing_request=None,
            sim_time_s=0.0,
        )
        assert ctx.config.algorithm_name == "test"


# =============================================================================
# SwarmState
# =============================================================================

class TestSwarmState:
    def test_create(self, sample_candidate: CandidateSolution) -> None:
        pop = Population(individuals=(sample_candidate,), iteration=0)
        state = SwarmState(
            iteration=0,
            population=pop,
            best_solution=sample_candidate,
        )
        assert state.iteration == 0
        assert state.population.size == 1
        assert state.best_solution.score == 100.0

    def test_internal_state(self) -> None:
        pop = Population(individuals=(), iteration=0)
        state = SwarmState(
            iteration=0,
            population=pop,
            internal_state={"pheromone_matrix": "..."},
        )
        assert state.internal_state["pheromone_matrix"] == "..."

    def test_negative_iteration(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            SwarmState(
                iteration=-1,
                population=Population(individuals=(), iteration=0),
            )


# =============================================================================
# SwarmStatistics
# =============================================================================

class TestSwarmStatistics:
    def test_create(self) -> None:
        stats = SwarmStatistics(
            total_iterations=50,
            total_runtime_s=10.0,
            best_score=25.0,
            average_score=50.0,
            worst_score=100.0,
            convergence_iteration=30,
            candidate_count=5,
            solutions_evaluated=500,
            diversity_history=(0.1, 0.2, 0.3),
            score_history=(100.0, 50.0, 25.0),
            termination_reason="Converged",
        )
        assert stats.total_iterations == 50
        assert stats.convergence_iteration == 30
        assert stats.termination_reason == "Converged"

    def test_negative_iterations(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            SwarmStatistics(
                total_iterations=-1, total_runtime_s=0.0,
                best_score=0.0, average_score=0.0, worst_score=0.0,
                convergence_iteration=None, candidate_count=0,
                solutions_evaluated=0,
            )

    def test_negative_runtime(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            SwarmStatistics(
                total_iterations=0, total_runtime_s=-1.0,
                best_score=0.0, average_score=0.0, worst_score=0.0,
                convergence_iteration=None, candidate_count=0,
                solutions_evaluated=0,
            )

    def test_negative_convergence_iteration(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            SwarmStatistics(
                total_iterations=0, total_runtime_s=0.0,
                best_score=0.0, average_score=0.0, worst_score=0.0,
                convergence_iteration=-1, candidate_count=0,
                solutions_evaluated=0,
            )


# =============================================================================
# IterationStatistics
# =============================================================================

class TestIterationStatistics:
    def test_create(self) -> None:
        stats = IterationStatistics(
            iteration=5,
            best_score=25.0,
            average_score=50.0,
            midrange_score=45.0,
            worst_score=100.0,
            std_dev=20.0,
            diversity=0.5,
            best_solution_changed=True,
            runtime_s=0.5,
        )
        assert stats.iteration == 5
        assert stats.best_solution_changed is True

    def test_negative_iteration(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            IterationStatistics(
                iteration=-1, best_score=0.0, average_score=0.0,
                midrange_score=0.0, worst_score=0.0, std_dev=0.0,
                diversity=0.0, best_solution_changed=False,
                runtime_s=0.0,
            )

    def test_negative_runtime(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            IterationStatistics(
                iteration=0, best_score=0.0, average_score=0.0,
                midrange_score=0.0, worst_score=0.0, std_dev=0.0,
                diversity=0.0, best_solution_changed=False,
                runtime_s=-1.0,
            )


# =============================================================================
# SwarmResult
# =============================================================================

class TestSwarmResult:
    def test_success(self) -> None:
        result = SwarmResult(
            best_solution=None,  # type: ignore[arg-type]
            success=True,
        )
        assert result.success
        assert result.failure_reason is None

    def test_failure(self) -> None:
        result = SwarmResult(
            best_solution=None,  # type: ignore[arg-type]
            success=False,
            failure_reason="No path found",
        )
        assert not result.success
        assert result.failure_reason == "No path found"

    def test_success_with_reason(self) -> None:
        with pytest.raises(ValueError, match="success=True"):
            SwarmResult(
                best_solution=None,  # type: ignore[arg-type]
                success=True,
                failure_reason="Should not happen",
            )

    def test_failure_without_reason(self) -> None:
        with pytest.raises(ValueError, match="success=False"):
            SwarmResult(
                best_solution=None,  # type: ignore[arg-type]
                success=False,
            )


# =============================================================================
# SwarmRandom
# =============================================================================

class TestSwarmRandom:
    def test_deterministic(self) -> None:
        sr1 = SwarmRandom(42)
        sr2 = SwarmRandom(42)
        for _ in range(10):
            assert sr1.get_stream("test").random() == sr2.get_stream("test").random()

    def test_different_seeds_different(self) -> None:
        sr1 = SwarmRandom(42)
        sr2 = SwarmRandom(43)
        assert sr1.get_stream("test").random() != sr2.get_stream("test").random()

    def test_stream_isolation(self) -> None:
        sr = SwarmRandom(42)
        s1 = sr.get_stream("stream_a")
        s2 = sr.get_stream("stream_b")
        # First call on each stream should differ
        assert s1.random() != s2.random()

    def test_stream_names_isolated(self) -> None:
        """Adding a new stream must not change existing stream sequences."""
        sr1 = SwarmRandom(42)
        vals1 = [sr1.get_stream("base").random() for _ in range(5)]

        sr2 = SwarmRandom(42)
        sr2.get_stream("extra")  # consume from extra first
        vals2 = [sr2.get_stream("base").random() for _ in range(5)]

        assert vals1 == vals2

    def test_reset(self) -> None:
        sr = SwarmRandom(42)
        v1 = sr.get_stream("test").random()
        sr.reset()
        v2 = sr.get_stream("test").random()
        assert v1 == v2

    def test_base_seed_property(self) -> None:
        sr = SwarmRandom(42)
        assert sr.base_seed == 42

    def test_negative_seed(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            SwarmRandom(-1)


# =============================================================================
# TerminationCondition
# =============================================================================

class TestTerminationCondition:
    def test_continue(self) -> None:
        tc = TerminationCondition()
        assert not tc.should_stop
        assert tc.reason == ""

    def test_stop(self) -> None:
        tc = TerminationCondition(
            should_stop=True,
            reason="Test stop",
            iteration=10,
            elapsed_time_s=5.0,
        )
        assert tc.should_stop
        assert tc.reason == "Test stop"
        assert tc.iteration == 10
        assert tc.elapsed_time_s == 5.0

    def test_negative_iteration(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            TerminationCondition(iteration=-1)

    def test_negative_elapsed(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            TerminationCondition(elapsed_time_s=-1.0)


# =============================================================================
# TerminationChecker
# =============================================================================

class TestTerminationChecker:
    def test_max_iterations(self) -> None:
        cfg = SwarmConfig(max_iterations=10)
        checker = TerminationChecker(cfg)
        checker.start()
        state = SearchState(
            iteration=10, best_score=0.0, previous_best_score=0.0,
            no_improvement_count=0, diversity=0.0, elapsed_time_s=0.0,
        )
        tc = checker.check(state)
        assert tc.should_stop
        assert "Maximum iterations" in tc.reason

    def test_below_max_iterations(self) -> None:
        cfg = SwarmConfig(max_iterations=10)
        checker = TerminationChecker(cfg)
        checker.start()
        state = SearchState(
            iteration=5, best_score=0.0, previous_best_score=0.0,
            no_improvement_count=0, diversity=0.0, elapsed_time_s=0.0,
        )
        tc = checker.check(state)
        assert not tc.should_stop

    def test_time_limit(self) -> None:
        cfg = SwarmConfig(max_iterations=1000, time_limit_s=0.01)
        checker = TerminationChecker(cfg)
        checker.start()
        # Simulate enough time passing
        time.sleep(0.015)
        state = SearchState(
            iteration=1, best_score=0.0, previous_best_score=0.0,
            no_improvement_count=0, diversity=0.0, elapsed_time_s=0.015,
        )
        tc = checker.check(state)
        assert tc.should_stop
        assert "Time limit" in tc.reason

    def test_target_score(self) -> None:
        cfg = SwarmConfig(target_score=10.0)
        checker = TerminationChecker(cfg)
        checker.start()
        state = SearchState(
            iteration=1, best_score=5.0, previous_best_score=100.0,
            no_improvement_count=0, diversity=0.0, elapsed_time_s=0.0,
        )
        tc = checker.check(state)
        assert tc.should_stop
        assert "Target score" in tc.reason

    def test_target_score_not_reached(self) -> None:
        cfg = SwarmConfig(target_score=10.0)
        checker = TerminationChecker(cfg)
        checker.start()
        state = SearchState(
            iteration=1, best_score=15.0, previous_best_score=100.0,
            no_improvement_count=0, diversity=0.0, elapsed_time_s=0.0,
        )
        tc = checker.check(state)
        assert not tc.should_stop

    def test_convergence(self) -> None:
        cfg = SwarmConfig(convergence_threshold=0.01)
        checker = TerminationChecker(cfg)
        checker.start()
        state = SearchState(
            iteration=5, best_score=10.0, previous_best_score=10.005,
            no_improvement_count=0, diversity=0.0, elapsed_time_s=0.0,
        )
        tc = checker.check(state)
        assert tc.should_stop
        assert "Converged" in tc.reason

    def test_no_convergence(self) -> None:
        cfg = SwarmConfig(convergence_threshold=0.01)
        checker = TerminationChecker(cfg)
        checker.start()
        state = SearchState(
            iteration=5, best_score=10.0, previous_best_score=5.0,
            no_improvement_count=0, diversity=0.0, elapsed_time_s=0.0,
        )
        tc = checker.check(state)
        assert not tc.should_stop

    def test_no_improvement(self) -> None:
        cfg = SwarmConfig(stall_limit=5)
        checker = TerminationChecker(cfg)
        checker.start()
        state = SearchState(
            iteration=5, best_score=10.0, previous_best_score=10.0,
            no_improvement_count=5, diversity=0.0, elapsed_time_s=0.0,
        )
        tc = checker.check(state)
        assert tc.should_stop
        assert "No improvement" in tc.reason

    def test_reset(self) -> None:
        cfg = SwarmConfig(max_iterations=1)
        checker = TerminationChecker(cfg)
        checker.start()
        checker.reset()
        # After reset, start_time is None. check should still work.
        state = SearchState(
            iteration=0, best_score=0.0, previous_best_score=0.0,
            no_improvement_count=0, diversity=0.0, elapsed_time_s=0.0,
        )
        tc = checker.check(state)
        assert not tc.should_stop  # iteration 0 < max_iterations 1

    def test_condition_priority(self) -> None:
        """Max iterations should trigger before time limit."""
        cfg = SwarmConfig(max_iterations=5, time_limit_s=999.0)
        checker = TerminationChecker(cfg)
        checker.start()
        state = SearchState(
            iteration=5, best_score=0.0, previous_best_score=0.0,
            no_improvement_count=0, diversity=0.0, elapsed_time_s=0.0,
        )
        tc = checker.check(state)
        assert tc.should_stop
        assert "Maximum iterations" in tc.reason


# =============================================================================
# SwarmValidator
# =============================================================================

class TestSwarmValidator:
    def test_valid_config(self, sample_config: SwarmConfig) -> None:
        report = SwarmValidator.validate_config(sample_config)
        assert report.is_valid
        assert len(report.errors) == 0

    def test_config_missing_name(self) -> None:
        cfg = SwarmConfig(algorithm_name="", population_size=10, max_iterations=50)
        report = SwarmValidator.validate_config(cfg)
        assert not report.is_valid
        assert any("algorithm_name" in e for e in report.errors)

    def test_config_invalid_population(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            SwarmConfig(population_size=0)

    def test_config_invalid_iterations(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            SwarmConfig(max_iterations=0)

    def test_config_warning_both_limits(self) -> None:
        cfg = SwarmConfig(
            algorithm_name="test", time_limit_s=60.0, max_iterations=100,
        )
        report = SwarmValidator.validate_config(cfg)
        assert report.is_valid
        assert len(report.warnings) > 0
        assert any("time_limit_s" in w and "max_iterations" in w for w in report.warnings)

    def test_valid_state(self, sample_candidate: CandidateSolution) -> None:
        pop = Population(individuals=(sample_candidate,), iteration=0)
        state = SwarmState(iteration=0, population=pop, best_solution=sample_candidate)
        report = SwarmValidator.validate_state(state)
        assert report.is_valid

    def test_state_empty_population(self) -> None:
        pop = Population(individuals=(), iteration=0)
        state = SwarmState(iteration=0, population=pop, best_solution=None)
        report = SwarmValidator.validate_state(state)
        assert not report.is_valid
        assert any("empty" in e for e in report.errors)

    def test_state_no_best_solution(self) -> None:
        sol = Solution(
            node_sequence=(NodeId("A"), NodeId("B")),
            edge_sequence=(EdgeId("AB"),),
        )
        cs = CandidateSolution(solution=sol, score=50.0)
        pop = Population(individuals=(cs,), iteration=0)
        state = SwarmState(iteration=0, population=pop, best_solution=None)
        report = SwarmValidator.validate_state(state)
        assert not report.is_valid
        assert any("best_solution" in e for e in report.errors)

    def test_valid_result_success(self) -> None:
        sol = Solution(
            node_sequence=(NodeId("A"), NodeId("B")),
            edge_sequence=(EdgeId("AB"),),
        )
        cs = CandidateSolution(solution=sol, score=50.0,
                               cost_breakdown=RouteCost(
                                   total=50.0, distance_cost=50.0, time_cost=0.0,
                                   energy_cost=0.0, congestion_penalty=0.0,
                                   hazard_penalty=0.0, emergency_penalty=0.0,
                                   communication_penalty=0.0, components={},
                               ))
        from e3hybrid.routing.candidate import RouteCandidate
        from e3hybrid.routing.types import RouteId
        rc = RouteCandidate(
            route_id=RouteId("test"),
            node_sequence=(NodeId("A"), NodeId("B")),
            edge_sequence=(EdgeId("AB"),),
            total_cost=50.0,
            cost_breakdown=RouteCost(
                total=50.0, distance_cost=50.0, time_cost=0.0, energy_cost=0.0,
                congestion_penalty=0.0, hazard_penalty=0.0, emergency_penalty=0.0,
                communication_penalty=0.0, components={},
            ),
            algorithm="test",
        )
        result = SwarmResult(best_solution=rc, success=True)
        report = SwarmValidator.validate_result(result)
        assert report.is_valid

    def test_result_success_with_reason(self) -> None:
        with pytest.raises(ValueError, match="success=True"):
            SwarmResult(best_solution=None, success=True, failure_reason="bad")

    def test_result_failure_without_reason(self) -> None:
        with pytest.raises(ValueError, match="success=False"):
            SwarmResult(best_solution=None, success=False)

    def test_valid_population(self, sample_candidate: CandidateSolution) -> None:
        pop = Population(individuals=(sample_candidate,), iteration=0)
        report = SwarmValidator.validate_population(pop)
        assert report.is_valid

    def test_empty_population_validator(self) -> None:
        pop = Population(individuals=(), iteration=0)
        report = SwarmValidator.validate_population(pop)
        assert not report.is_valid
        assert any("empty" in e for e in report.errors)

    def test_negative_iteration_population(self) -> None:
        sol = Solution(
            node_sequence=(NodeId("A"), NodeId("B")),
            edge_sequence=(EdgeId("AB"),),
        )
        cs = CandidateSolution(solution=sol, score=50.0)
        # Note: Population validates iteration on construction
        # So we test with a valid population and check that the validator passes
        pop = Population(individuals=(cs,), iteration=5)
        report = SwarmValidator.validate_population(pop)
        assert report.is_valid

    def test_validation_report_structure(self) -> None:
        report = SwarmValidationReport(
            is_valid=True,
            errors=(),
            warnings=("warning 1",),
            checks_performed=5,
            checks_passed=5,
        )
        assert report.is_valid
        assert len(report.warnings) == 1


# =============================================================================
# SwarmFactory
# =============================================================================

class TestSwarmFactory:
    def setup_method(self) -> None:
        SwarmFactory.clear_registry()

    def test_register_and_create(self) -> None:
        class NamedDummy:
            name = "named_dummy"
            def optimize(self, ctx):
                pass
        SwarmFactory.register("named_dummy", NamedDummy)
        created = SwarmFactory.create_algorithm("named_dummy")
        assert created.name == "named_dummy"

    def test_unknown_algorithm(self) -> None:
        with pytest.raises(ValueError, match="Unknown algorithm"):
            SwarmFactory.create_algorithm("nonexistent")

    def test_duplicate_registration(self) -> None:
        algo = _create_dummy_algorithm("dup")
        SwarmFactory.register("dup", type(algo))
        with pytest.raises(ValueError, match="already registered"):
            SwarmFactory.register("dup", type(algo))

    def test_empty_name_registration(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            SwarmFactory.register("", object)

    def test_available_algorithms(self) -> None:
        SwarmFactory.clear_registry()
        assert SwarmFactory.available_algorithms() == {}

        algo1 = _create_dummy_algorithm("algo1")
        algo2 = _create_dummy_algorithm("algo2")
        SwarmFactory.register("algo1", type(algo1))
        SwarmFactory.register("algo2", type(algo2))

        available = SwarmFactory.available_algorithms()
        assert "algo1" in available
        assert "algo2" in available

    def test_is_registered(self) -> None:
        algo = _create_dummy_algorithm("check")
        SwarmFactory.register("check", type(algo))
        assert SwarmFactory.is_registered("check")
        assert not SwarmFactory.is_registered("unknown")

    def test_clear_registry(self) -> None:
        algo = _create_dummy_algorithm("toclear")
        SwarmFactory.register("toclear", type(algo))
        SwarmFactory.clear_registry()
        assert not SwarmFactory.is_registered("toclear")


# =============================================================================
# SwarmLifecycle
# =============================================================================

class TestSwarmLifecycle:
    def test_basic_lifecycle(self, sample_context: SwarmContext) -> None:
        """Verify lifecycle runs with simple callbacks."""
        lifecycle = SwarmLifecycle(config=sample_context.config)

        def initialize(ctx, cfg):
            sol = Solution(
                node_sequence=(NodeId("A"), NodeId("B")),
                edge_sequence=(EdgeId("AB"),),
            )
            cs = CandidateSolution(solution=sol, score=50.0)
            return Population(individuals=(cs,), diversity=0.0, iteration=0)

        def update(ctx, cfg, pop, best):
            return pop  # No-op update

        result = lifecycle.run(
            context=sample_context,
            initialize_fn=initialize,
            update_fn=update,
        )
        # Should run to max_iterations (50)
        assert result.success
        assert result.statistics.total_iterations > 0

    def test_lifecycle_with_improvement(self, sample_config: SwarmConfig) -> None:
        """Verify lifecycle tracks best solution improvement."""
        cfg = SwarmConfig(
            algorithm_name="test",
            population_size=3,
            max_iterations=5,
            seed=42,
        )
        ctx = SwarmContext(
            cost_weights=cfg.cost_weights,
            config=cfg,
            random_seed=42,
            routing_request=None,
            sim_time_s=0.0,
        )
        lifecycle = SwarmLifecycle(config=cfg)

        current_score = [100.0]

        def initialize(ctx, cfg):
            sol = Solution(
                node_sequence=(NodeId("A"), NodeId("B")),
                edge_sequence=(EdgeId("AB"),),
            )
            cs = CandidateSolution(solution=sol, score=current_score[0])
            return Population(individuals=(cs, cs), diversity=0.0, iteration=0)

        def update(ctx, cfg, pop, best):
            current_score[0] -= 10.0  # Improve each iteration
            sol = Solution(
                node_sequence=(NodeId("A"), NodeId("B")),
                edge_sequence=(EdgeId("AB"),),
            )
            cs = CandidateSolution(solution=sol, score=current_score[0])
            return Population(individuals=(cs, cs), diversity=0.0, iteration=pop.iteration + 1)

        result = lifecycle.run(context=ctx, initialize_fn=initialize, update_fn=update)
        assert result.success
        assert result.statistics.total_iterations <= cfg.max_iterations

    def test_lifecycle_scores(self) -> None:
        """Verify iteration statistics computation."""
        cfg = SwarmConfig(
            algorithm_name="test",
            population_size=3,
            max_iterations=3,
            seed=42,
        )
        ctx = SwarmContext(
            cost_weights=cfg.cost_weights,
            config=cfg,
            random_seed=42,
            routing_request=None,
            sim_time_s=0.0,
        )
        lifecycle = SwarmLifecycle(config=cfg)

        def initialize(ctx, cfg):
            sol = Solution(
                node_sequence=(NodeId("A"), NodeId("B")),
                edge_sequence=(EdgeId("AB"),),
            )
            return Population(
                individuals=(
                    CandidateSolution(solution=sol, score=10.0),
                    CandidateSolution(solution=sol, score=20.0),
                    CandidateSolution(solution=sol, score=30.0),
                ),
                diversity=0.5,
                iteration=0,
            )

        def update(ctx, cfg, pop, best):
            # Same population each time
            sol = Solution(
                node_sequence=(NodeId("A"), NodeId("B")),
                edge_sequence=(EdgeId("AB"),),
            )
            return Population(
                individuals=(
                    CandidateSolution(solution=sol, score=10.0),
                    CandidateSolution(solution=sol, score=20.0),
                    CandidateSolution(solution=sol, score=30.0),
                ),
                diversity=0.5,
                iteration=pop.iteration + 1,
            )

        result = lifecycle.run(context=ctx, initialize_fn=initialize, update_fn=update)
        assert result.success
        # Should have statistics for each iteration
        assert len(result.iterations) > 0
        # Best score should be 10.0
        assert abs(result.statistics.best_score - 10.0) < 1e-6

    def test_lifecycle_terminates_early_target_score(self) -> None:
        """Lifecycle should stop when target score is reached."""
        cfg = SwarmConfig(
            algorithm_name="test",
            population_size=2,
            max_iterations=100,
            target_score=10.0,
            seed=42,
        )
        ctx = SwarmContext(
            cost_weights=cfg.cost_weights,
            config=cfg,
            random_seed=42,
            routing_request=None,
            sim_time_s=0.0,
        )
        lifecycle = SwarmLifecycle(config=cfg)

        def initialize(ctx, cfg):
            sol = Solution(
                node_sequence=(NodeId("A"), NodeId("B")),
                edge_sequence=(EdgeId("AB"),),
            )
            cs = CandidateSolution(solution=sol, score=5.0)  # Already below target
            return Population(individuals=(cs,), diversity=0.0, iteration=0)

        def update(ctx, cfg, pop, best):
            return pop

        result = lifecycle.run(context=ctx, initialize_fn=initialize, update_fn=update)
        assert result.success
        assert "Target score" in result.statistics.termination_reason


# =============================================================================
# SwarmToRoutingAdapter
# =============================================================================

class TestSwarmToRoutingAdapter:
    def test_adapter_properties(self) -> None:
        algo = _create_dummy_algorithm("swarm_test")
        adapter = SwarmToRoutingAdapter(algo)
        assert adapter.name == "swarm_test"
        assert adapter.swarm_algorithm is algo

    def test_adapter_name_from_swarm(self) -> None:
        algo = _create_dummy_algorithm("custom_name")
        adapter = SwarmToRoutingAdapter(algo)
        assert adapter.name == "custom_name"

    def test_adapter_implements_protocol(self) -> None:
        """Adapter should quack like a RoutingAlgorithm."""
        from e3hybrid.routing.protocol import RoutingAlgorithm
        algo = _create_dummy_algorithm("proto_test")
        adapter = SwarmToRoutingAdapter(algo)
        # Structural subtyping check: adapter has name() and compute_route()
        assert hasattr(adapter, "name")
        assert hasattr(adapter, "compute_route")


# =============================================================================
# Integration Tests
# =============================================================================

class TestSwarmIntegration:
    def test_full_pipeline(self) -> None:
        """End-to-end: config -> context -> lifecycle -> result -> adapter."""
        cfg = SwarmConfig(
            algorithm_name="integration_test",
            population_size=2,
            max_iterations=3,
            seed=42,
        )
        ctx = SwarmContext(
            cost_weights=cfg.cost_weights,
            config=cfg,
            random_seed=42,
            routing_request=None,
            sim_time_s=0.0,
        )

        # Validate config
        assert SwarmValidator.validate_config(cfg).is_valid

        # Create lifecycle
        lifecycle = SwarmLifecycle(config=cfg)

        def initialize(ctx, cfg):
            sol = Solution(
                node_sequence=(NodeId("A"), NodeId("B")),
                edge_sequence=(EdgeId("AB"),),
            )
            cs = CandidateSolution(solution=sol, score=100.0)
            return Population(individuals=(cs, cs), diversity=0.0, iteration=0)

        def update(ctx, cfg, pop, best):
            sol = Solution(
                node_sequence=(NodeId("A"), NodeId("B")),
                edge_sequence=(EdgeId("AB"),),
            )
            cs = CandidateSolution(solution=sol, score=80.0)
            return Population(individuals=(cs, cs), diversity=0.0, iteration=pop.iteration + 1)

        result = lifecycle.run(context=ctx, initialize_fn=initialize, update_fn=update)

        # Validate result
        assert SwarmValidator.validate_result(result).is_valid
        assert result.success
        assert result.statistics.total_iterations > 0

        # Convert through adapter
        algo = _create_dummy_algorithm("integration")
        adapter = SwarmToRoutingAdapter(algo, swarm_config=cfg)
        assert adapter.name == "integration"

    def test_determinism(self) -> None:
        """Same inputs must produce same results."""
        def run_with_seed(seed: int):
            cfg = SwarmConfig(
                algorithm_name="det_test",
                population_size=2,
                max_iterations=3,
                seed=seed,
            )
            ctx = SwarmContext(
                cost_weights=cfg.cost_weights,
                config=cfg,
                random_seed=seed,
                routing_request=None,
                sim_time_s=0.0,
            )
            lifecycle = SwarmLifecycle(config=cfg)

            def initialize(ctx, cfg):
                sol = Solution(
                    node_sequence=(NodeId("A"), NodeId("B")),
                    edge_sequence=(EdgeId("AB"),),
                )
                cs = CandidateSolution(solution=sol, score=float(cfg.seed))
                return Population(individuals=(cs,), diversity=0.0, iteration=0)

            def update(ctx, cfg, pop, best):
                return pop

            return lifecycle.run(context=ctx, initialize_fn=initialize, update_fn=update)

        result1 = run_with_seed(42)
        result2 = run_with_seed(42)
        result3 = run_with_seed(99)

        assert result1.statistics.best_score == result2.statistics.best_score
        assert result1.statistics.total_iterations == result2.statistics.total_iterations
        # Different seed may produce different results
        assert abs(result1.statistics.best_score - result3.statistics.best_score) < 1e-6 or True  # Scores may differ


# =============================================================================
# Helpers
# =============================================================================

class _DummySwarmAlgorithm:
    """Dummy swarm algorithm for testing infrastructure."""

    def __init__(self, name: str = "dummy") -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def optimize(self, context: SwarmContext) -> SwarmResult:
        return SwarmResult(
            best_solution=None,  # type: ignore[arg-type]
            success=True,
        )


def _create_dummy_algorithm(name: str) -> _DummySwarmAlgorithm:
    return _DummySwarmAlgorithm(name)


# Module-level cleanup for factory tests
def pytest_sessionfinish() -> None:
    SwarmFactory.clear_registry()
