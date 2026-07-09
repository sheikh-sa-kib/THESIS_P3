"""E³-Hybrid — triple-swarm integration for dynamic EV routing.

Combines ACO, BCO, and PSO into a single hybrid algorithm. All individuals
(ants, bees, particles) share the same weighted-edge-selection formula but each
subpopulation has its primary update rule.

All stochastic decisions use SwarmRandom named streams.
All configuration comes from YAML via SwarmConfig.hyperparameters.
No global state. No direct graph/emergency/communication module access.
No imports from aco.py, bco.py, or pso.py.

Design
------
- E³ = Embedded ACO + Embedded BCO + Embedded PSO
- Population partitioned into three subpopulations (deterministic).
- All individuals construct routes using a hybrid weighted edge-selection formula.
- Updates cross-pollinate: pheromone (ACO), templates (BCO), memory (PSO).
- Meta-controller adjusts influence weights based on per-subpopulation diversity.
"""

from __future__ import annotations

import math
import statistics
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from e3hybrid.network.types import EdgeId, NodeId
from e3hybrid.swarm.pheromone import HybridPheromoneMatrix
from e3hybrid.swarm.random import SwarmRandom

if TYPE_CHECKING:
    from e3hybrid.network.edge import Edge
    from e3hybrid.network.graph import DirectedGraph
    from e3hybrid.routing.candidate import RouteCandidate
    from e3hybrid.routing.cost import RouteCost
    from e3hybrid.routing.cost_calculator import CompositeCostCalculator
    from e3hybrid.routing.request import RoutingRequest
    from e3hybrid.routing.types import RouteId
    from e3hybrid.swarm.config import SwarmConfig
    from e3hybrid.swarm.context import SwarmContext
    from e3hybrid.swarm.result import SwarmResult
    from e3hybrid.swarm.statistics import IterationStatistics, SwarmStatistics

_EPS = 1e-10
_PENALTY_COST = 1e9


# =========================================================================
# IndividualKind
# =========================================================================


class IndividualKind(Enum):
    """Which subpopulation an individual belongs to."""
    ANT = "ant"
    BEE = "bee"
    PARTICLE = "particle"


# =========================================================================
# IndividualStatus
# =========================================================================


class IndividualStatus(Enum):
    """State of an individual after route construction."""
    CONSTRUCTING = "constructing"
    COMPLETE = "complete"
    FAILED = "failed"


# =========================================================================
# IndividualState
# =========================================================================


@dataclass
class IndividualState:
    """Mutable state of one individual in the hybrid swarm."""

    kind: IndividualKind
    route: list[EdgeId] = field(default_factory=list)
    cost: float = float("inf")
    p_best_route: list[EdgeId] = field(default_factory=list)
    p_best_cost: float = float("inf")
    visited: set[NodeId] = field(default_factory=set)
    state: IndividualStatus = IndividualStatus.CONSTRUCTING

    def reset_route(self) -> None:
        self.route = []
        self.cost = float("inf")
        self.visited = set()
        self.state = IndividualStatus.CONSTRUCTING


# =========================================================================
# HybridInfluenceWeights
# =========================================================================


@dataclass
class HybridInfluenceWeights:
    """Mutable influence weights for the four edge-selection components.

    alpha_a: ACO (pheromone) influence weight.
    alpha_b: BCO (recruitment template) influence weight.
    alpha_p: PSO (memory) influence weight.
    alpha_h: Heuristic (visibility) influence weight.
    """

    alpha_a: float = 1.0
    alpha_b: float = 1.0
    alpha_p: float = 1.0
    alpha_h: float = 1.0

    def __post_init__(self) -> None:
        for name, val in [("alpha_a", self.alpha_a), ("alpha_b", self.alpha_b),
                           ("alpha_p", self.alpha_p), ("alpha_h", self.alpha_h)]:
            if val < 0:
                raise ValueError(f"{name} must be >= 0, got {val}")


# =========================================================================
# HybridConfiguration
# =========================================================================


@dataclass(frozen=True, slots=True)
class HybridConfiguration:
    """All E3-Hybrid hyperparameters with validated defaults."""

    # Population partitioning
    ant_ratio: float = 0.4
    bee_ratio: float = 0.3
    particle_ratio: float = 0.3

    # Influence weights (initial)
    alpha_a: float = 1.0
    alpha_a_min: float = 0.1
    alpha_a_max: float = 3.0
    alpha_b: float = 1.0
    alpha_b_min: float = 0.1
    alpha_b_max: float = 3.0
    alpha_p: float = 1.0
    alpha_p_min: float = 0.1
    alpha_p_max: float = 3.0
    alpha_h: float = 1.0

    # BCO templates
    template_count: int = 3

    # PSO inertia
    inertia_start: float = 0.9
    inertia_end: float = 0.4
    cognition_weight: float = 2.0
    social_weight: float = 2.0

    # Pheromone
    pheromone_tau0: float = 1.0
    pheromone_min: float = 0.01
    pheromone_max: float = 10.0
    rho: float = 0.1
    rho_local: float = 0.1
    beta_a: float = 1.0

    # General
    epsilon: float = _EPS
    forward_steps: int = 500

    # Meta-controller
    adapt_interval: int = 5
    adapt_diversity_min: float = 0.15
    adapt_decay: float = 0.9
    adapt_recovery_gain: float = 0.05

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        # Ratios must sum to 1.0
        total_ratio = self.ant_ratio + self.bee_ratio + self.particle_ratio
        if abs(total_ratio - 1.0) > 1e-9:
            raise ValueError(
                f"ant_ratio ({self.ant_ratio}) + bee_ratio ({self.bee_ratio}) + "
                f"particle_ratio ({self.particle_ratio}) = {total_ratio}, must sum to 1.0"
            )
        if self.ant_ratio < 0 or self.bee_ratio < 0 or self.particle_ratio < 0:
            raise ValueError("ratios must be non-negative")

        # Influence weights
        if self.alpha_a < 0 or self.alpha_b < 0 or self.alpha_p < 0 or self.alpha_h < 0:
            raise ValueError("influence weights must be >= 0")
        if self.alpha_a + self.alpha_b + self.alpha_p + self.alpha_h <= 0:
            raise ValueError("at least one influence weight must be > 0")
        if not (self.alpha_a_min <= self.alpha_a <= self.alpha_a_max):
            raise ValueError("alpha_a must be within [alpha_a_min, alpha_a_max]")
        if not (self.alpha_b_min <= self.alpha_b <= self.alpha_b_max):
            raise ValueError("alpha_b must be within [alpha_b_min, alpha_b_max]")
        if not (self.alpha_p_min <= self.alpha_p <= self.alpha_p_max):
            raise ValueError("alpha_p must be within [alpha_p_min, alpha_p_max]")
        if self.alpha_a_min < 0 or self.alpha_b_min < 0 or self.alpha_p_min < 0:
            raise ValueError("alpha_x_min must be >= 0")
        if self.alpha_a_max < self.alpha_a_min:
            raise ValueError("alpha_a_max must be >= alpha_a_min")
        if self.alpha_b_max < self.alpha_b_min:
            raise ValueError("alpha_b_max must be >= alpha_b_min")
        if self.alpha_p_max < self.alpha_p_min:
            raise ValueError("alpha_p_max must be >= alpha_p_min")

        # General params
        if self.forward_steps < 1:
            raise ValueError("forward_steps must be >= 1")
        if not 0.0 < self.epsilon <= 1.0:
            raise ValueError("epsilon must be in (0, 1]")

        # PSO inertia
        if self.inertia_start < self.inertia_end:
            raise ValueError("inertia_start must be >= inertia_end")
        if not 0.0 <= self.inertia_end <= self.inertia_start <= 1.0:
            raise ValueError("inertia weights must be in [0, 1] with start >= end")
        if self.cognition_weight < 0 or self.social_weight < 0:
            raise ValueError("cognition/social weights must be >= 0")

        # Pheromone
        if not 0 < self.pheromone_min < self.pheromone_max:
            raise ValueError("pheromone_min must be between 0 and pheromone_max")
        if self.pheromone_tau0 <= 0:
            raise ValueError("pheromone_tau0 must be > 0")
        if not 0 < self.rho < 1 or not 0 < self.rho_local < 1:
            raise ValueError("rho and rho_local must be in (0, 1)")
        if self.beta_a < 0:
            raise ValueError("beta_a must be >= 0")

        # Templates
        if self.template_count < 0:
            raise ValueError("template_count must be >= 0")

        # Meta-controller
        if self.adapt_interval < 1:
            raise ValueError("adapt_interval must be >= 1")
        if not 0.0 < self.adapt_diversity_min <= 1.0:
            raise ValueError("adapt_diversity_min must be in (0, 1]")
        if not 0.0 < self.adapt_decay < 1.0:
            raise ValueError("adapt_decay must be in (0, 1)")
        if not 0.0 <= self.adapt_recovery_gain < 1.0:
            raise ValueError("adapt_recovery_gain must be in [0, 1)")

    @classmethod
    def from_swarm_config(cls, swarm_config: SwarmConfig) -> HybridConfiguration:
        hp = dict(swarm_config.hyperparameters)
        return cls(
            ant_ratio=_hp_float(hp, "ant_ratio", 0.4),
            bee_ratio=_hp_float(hp, "bee_ratio", 0.3),
            particle_ratio=_hp_float(hp, "particle_ratio", 0.3),
            alpha_a=_hp_float(hp, "alpha_a", 1.0),
            alpha_a_min=_hp_float(hp, "alpha_a_min", 0.1),
            alpha_a_max=_hp_float(hp, "alpha_a_max", 3.0),
            alpha_b=_hp_float(hp, "alpha_b", 1.0),
            alpha_b_min=_hp_float(hp, "alpha_b_min", 0.1),
            alpha_b_max=_hp_float(hp, "alpha_b_max", 3.0),
            alpha_p=_hp_float(hp, "alpha_p", 1.0),
            alpha_p_min=_hp_float(hp, "alpha_p_min", 0.1),
            alpha_p_max=_hp_float(hp, "alpha_p_max", 3.0),
            alpha_h=_hp_float(hp, "alpha_h", 1.0),
            template_count=_hp_int(hp, "template_count", 3),
            inertia_start=_hp_float(hp, "inertia_start", 0.9),
            inertia_end=_hp_float(hp, "inertia_end", 0.4),
            cognition_weight=_hp_float(hp, "cognition_weight", 2.0),
            social_weight=_hp_float(hp, "social_weight", 2.0),
            pheromone_tau0=_hp_float(hp, "pheromone_tau0", 1.0),
            pheromone_min=_hp_float(hp, "pheromone_min", 0.01),
            pheromone_max=_hp_float(hp, "pheromone_max", 10.0),
            rho=_hp_float(hp, "rho", 0.1),
            rho_local=_hp_float(hp, "rho_local", 0.1),
            beta_a=_hp_float(hp, "beta_a", 1.0),
            epsilon=_hp_float(hp, "epsilon", _EPS),
            forward_steps=_hp_int(hp, "forward_steps", 500),
            adapt_interval=_hp_int(hp, "adapt_interval", 5),
            adapt_diversity_min=_hp_float(hp, "adapt_diversity_min", 0.15),
            adapt_decay=_hp_float(hp, "adapt_decay", 0.9),
            adapt_recovery_gain=_hp_float(hp, "adapt_recovery_gain", 0.05),
        )


def _hp_float(hp: dict[str, object], key: str, default: float) -> float:
    if key not in hp:
        return default
    val = hp[key]
    if isinstance(val, (int, float)):
        return float(val)
    raise TypeError(
        f"hyperparameter '{key}' must be a number, got {type(val).__name__}"
    )


def _hp_int(hp: dict[str, object], key: str, default: int) -> int:
    if key not in hp:
        return default
    val = hp[key]
    if isinstance(val, int):
        return val
    if isinstance(val, float) and val == int(val):
        return int(val)
    raise TypeError(
        f"hyperparameter '{key}' must be an integer, got {type(val).__name__}"
    )


# =========================================================================
# HybridStatistics
# =========================================================================


@dataclass(frozen=True, slots=True)
class HybridStatistics:
    """Per-iteration hybrid-specific metrics."""

    iteration: int
    best_cost: float
    avg_cost: float
    worst_cost: float
    diversity: float
    alpha_a: float
    alpha_b: float
    alpha_p: float
    alpha_h: float
    template_count: int
    runtime_s: float

    def __post_init__(self) -> None:
        if self.iteration < 0:
            raise ValueError("iteration must be non-negative")
        if self.runtime_s < 0:
            raise ValueError("runtime_s must be non-negative")


# =========================================================================
# E3HybridRouting — main algorithm class
# =========================================================================


class E3HybridRouting:
    """E3-Hybrid swarm algorithm implementing the SwarmAlgorithm Protocol.

    Combines ACO pheromone memory, BCO recruitment templates, and PSO
    cognitive/social memory into a single hybrid search.

    Parameters
    ----------
    config:
        Hybrid configuration (optional, uses defaults if None).
    """

    def __init__(self, config: HybridConfiguration | None = None) -> None:
        self._config = config or HybridConfiguration()
        self._individuals: list[IndividualState] = []
        self._visibility: dict[EdgeId, float] = {}
        self._swarm_rng: SwarmRandom | None = None
        self._context: SwarmContext | None = None
        self._graph: DirectedGraph | None = None
        self._cost_calculator: CompositeCostCalculator | None = None
        self._source: NodeId | None = None
        self._destination: NodeId | None = None
        self._global_best_cost: float = float("inf")
        self._global_best_route: list[EdgeId] = []
        self._templates: list[list[EdgeId]] = []
        self._influence_weights: HybridInfluenceWeights | None = None
        self._low_diversity_counts: dict[str, int] | None = None
        self._iteration_stats: list[HybridStatistics] = []
        self._diversity_history: list[float] = []
        self._score_history: list[float] = []
        self._no_improvement_count: int = 0

    @property
    def name(self) -> str:
        return "e3hybrid"

    # =====================================================================
    # optimize() — Lifecycle
    # =====================================================================

    def optimize(self, context: SwarmContext) -> SwarmResult:
        from e3hybrid.swarm.result import SwarmResult
        from e3hybrid.swarm.statistics import SwarmStatistics
        from e3hybrid.swarm.models import SearchState
        from e3hybrid.swarm.termination import TerminationChecker

        # 1. Validate context
        ctx_errors = _validate_context(context)
        if ctx_errors:
            return _failure_result("; ".join(ctx_errors))

        self._context = context
        self._graph = context.graph
        self._cost_calculator = context.cost_calculator
        self._source = context.routing_request.source_node
        self._destination = context.routing_request.destination_node
        swarm_config = context.config

        # 2. Build config
        self._config = HybridConfiguration.from_swarm_config(swarm_config)

        # 3. Validate graph connectivity
        if self._graph is None or self._source is None or self._destination is None:
            return _failure_result("Missing graph, source, or destination")

        if not self._graph.has_node(self._source):
            return _failure_result("Source node not in graph")
        if not self._graph.has_node(self._destination):
            return _failure_result("Destination node not in graph")

        # 4. Build visibility cache
        self._build_visibility()

        # 5. Build pheromone matrix
        all_edge_ids = {e.edge_id for e in self._graph.edges()}
        pheromones = HybridPheromoneMatrix(
            tau0=self._config.pheromone_tau0,
            tau_min=self._config.pheromone_min,
            tau_max=self._config.pheromone_max,
            edge_ids=all_edge_ids,
        )

        # 6. Random streams
        self._swarm_rng = SwarmRandom(context.random_seed)

        # 7. Initialize population
        self._initialize_population()

        # 8. Hybrid tracking state
        self._global_best_cost = float("inf")
        self._global_best_route = []
        self._templates = []
        self._influence_weights = HybridInfluenceWeights(
            alpha_a=self._config.alpha_a,
            alpha_b=self._config.alpha_b,
            alpha_p=self._config.alpha_p,
            alpha_h=self._config.alpha_h,
        )
        self._low_diversity_counts = {"a": 0, "b": 0, "p": 0}
        self._iteration_stats = []
        self._diversity_history = []
        self._score_history = []

        # 9. Termination checker
        checker = TerminationChecker(swarm_config)
        checker.start()

        # 10. Iteration loop
        prev_best_score = float("inf")
        start_time = time.perf_counter()

        for iteration in range(swarm_config.max_iterations):
            iter_start = time.perf_counter()

            # PSO inertia
            w = self._compute_inertia(iteration, swarm_config.max_iterations)

            # Forward pass
            routes, costs, kinds, states = self._forward_pass(
                iteration, pheromones, w,
            )

            # Backward pass
            best_cost, best_route = self._backward_pass(
                routes, costs, kinds, states, pheromones,
            )

            # Update global best
            if best_cost < self._global_best_cost:
                self._global_best_cost = best_cost
                self._global_best_route = list(best_route) if best_route else []

            # Update templates
            self._templates = self._extract_templates(routes, costs)

            # Compute diversity
            diversity = self._compute_diversity(routes)

            # Record per-iteration stats
            success_costs = [c for c, s in zip(costs, states)
                           if s == IndividualStatus.COMPLETE and c < float("inf")]
            avg_cost = statistics.mean(success_costs) if success_costs else float("inf")
            worst_cost = max(success_costs) if success_costs else float("inf")

            iter_stats = HybridStatistics(
                iteration=iteration,
                best_cost=best_cost,
                avg_cost=avg_cost,
                worst_cost=worst_cost,
                diversity=diversity,
                alpha_a=self._influence_weights.alpha_a,
                alpha_b=self._influence_weights.alpha_b,
                alpha_p=self._influence_weights.alpha_p,
                alpha_h=self._influence_weights.alpha_h,
                template_count=len(self._templates),
                runtime_s=time.perf_counter() - iter_start,
            )
            self._iteration_stats.append(iter_stats)
            self._diversity_history.append(diversity)
            self._score_history.append(best_cost)

            # Meta-controller
            self._update_meta_controller(iteration, routes, kinds)

            # Update no-improvement count
            if self._global_best_cost == float("inf"):
                no_improvement_count = 0
            elif self._global_best_cost >= prev_best_score:
                no_improvement_count = (getattr(self, '_no_improvement_count', 0) + 1)
            else:
                no_improvement_count = 0
            self._no_improvement_count = no_improvement_count
            prev_best_score = self._global_best_cost

            # Check termination
            search_state = SearchState(
                iteration=iteration + 1,
                best_score=self._global_best_cost if self._global_best_cost < float("inf") else 0.0,
                previous_best_score=prev_best_score if iteration > 0 else float("inf"),
                no_improvement_count=no_improvement_count,
                diversity=diversity,
                elapsed_time_s=time.perf_counter() - start_time,
            )
            term = checker.check(search_state)
            if term.should_stop:
                return self._build_swarm_result(
                    total_time=time.perf_counter() - start_time,
                    term_reason=term.reason,
                    term_iteration=term.iteration,
                )

        # Max iterations reached
        return self._build_swarm_result(
            total_time=time.perf_counter() - start_time,
            term_reason=f"Maximum iterations reached ({swarm_config.max_iterations})",
            term_iteration=swarm_config.max_iterations,
        )

    # =====================================================================
    # Initialisation
    # =====================================================================

    def _assign_subpopulations(self, population_size: int) -> list[IndividualKind]:
        cfg = self._config
        total_ratio = cfg.ant_ratio + cfg.bee_ratio + cfg.particle_ratio
        N_a = max(1, int(population_size * cfg.ant_ratio / total_ratio))
        N_b = max(1, int(population_size * cfg.bee_ratio / total_ratio))
        N_p = population_size - N_a - N_b

        kinds: list[IndividualKind] = []
        for i in range(N_a):
            kinds.append(IndividualKind.ANT)
        for i in range(N_b):
            kinds.append(IndividualKind.BEE)
        for i in range(N_p):
            kinds.append(IndividualKind.PARTICLE)
        return kinds

    def _initialize_population(self) -> None:
        cfg = self._config
        N = self._context.config.population_size

        kinds = self._assign_subpopulations(N)

        self._individuals = [
            IndividualState(kind=k) for k in kinds
        ]

        # Build initial routes using pure visibility
        init_stream = self._swarm_rng.get_stream("e3hybrid.init") if self._swarm_rng else None

        for ind in self._individuals:
            route = self._construct_route(
                source=self._source,
                destination=self._destination,
                current_route=[],
                p_best_route=[],
                templates=[],
                g_best=[],
                pheromones=None,
                alpha_a=0.0,
                alpha_b=0.0,
                alpha_p=0.0,
                alpha_h=1.0,
                stream=init_stream,
            )
            cost_val = sum(self._edge_total_cost(self._graph.get_edge(eid))
                          for eid in route) if route else float("inf")
            reached = bool(route) and self._graph.get_edge(route[-1]).target == self._destination
            ind.route = route
            ind.cost = cost_val
            ind.p_best_route = list(route)
            ind.p_best_cost = cost_val
            ind.state = IndividualStatus.COMPLETE if reached else IndividualStatus.FAILED

    def _build_visibility(self) -> None:
        self._visibility = {}
        if self._graph is None or self._cost_calculator is None:
            return
        for edge in self._graph.edges():
            if edge.state.is_blocked:
                self._visibility[edge.edge_id] = 0.0
            else:
                try:
                    cost_val, _ = self._cost_calculator.compute_edge_cost(edge)
                except Exception:
                    cost_val = float("inf")
                if not math.isfinite(cost_val) or cost_val < 0:
                    self._visibility[edge.edge_id] = 0.0
                elif cost_val == 0.0:
                    self._visibility[edge.edge_id] = 1.0 / _EPS
                else:
                    self._visibility[edge.edge_id] = 1.0 / (cost_val + _EPS)

    def _edge_total_cost(self, edge: Edge) -> float:
        if edge.state.is_blocked:
            return float("inf")
        try:
            cost_val, _ = self._cost_calculator.compute_edge_cost(edge)
            return cost_val if math.isfinite(cost_val) and cost_val >= 0 else float("inf")
        except Exception:
            return float("inf")

    def _compute_inertia(self, iteration: int, max_iters: int) -> float:
        if max_iters <= 0:
            return self._config.inertia_end
        return self._config.inertia_start - (
            self._config.inertia_start - self._config.inertia_end
        ) * iteration / max_iters

    # =====================================================================
    # Route Construction — Hybrid Weighted Selection
    # =====================================================================

    def _construct_route(
        self,
        source: NodeId,
        destination: NodeId,
        current_route: list[EdgeId],
        p_best_route: list[EdgeId],
        templates: list[list[EdgeId]],
        g_best: list[EdgeId],
        pheromones: HybridPheromoneMatrix | None,
        alpha_a: float,
        alpha_b: float,
        alpha_p: float,
        alpha_h: float,
        stream: Any | None,  # random.Random
    ) -> list[EdgeId]:
        current = source
        prev: NodeId | None = None
        route: list[EdgeId] = []

        for step in range(self._config.forward_steps):
            if current == destination:
                break

            # Gather candidates (Eq. 1)
            candidates: list[Edge] = []
            for edge in self._graph.outgoing_edges(current):
                ec = self._edge_total_cost(edge)
                if ec < float("inf"):
                    candidates.append(edge)
            # Avoid immediate back-tracking only if forward options remain
            if len(candidates) > 1 and prev is not None:
                candidates = [e for e in candidates if e.target != prev]

            if not candidates:
                break
            # Prefer non-dead-end nodes, fall back to dead-ends if necessary
            if len(candidates) > 1:
                non_deadend = [
                    e for e in candidates
                    if e.target == destination
                    or len(list(self._graph.outgoing_edges(e.target))) > 0
                ]
                if non_deadend:
                    candidates = non_deadend

            # Compute raw influence values
            raw_A = [self._compute_raw_aco(e.edge_id, pheromones) for e in candidates]
            raw_B = [self._compute_raw_bco(e.edge_id, step, templates) for e in candidates]
            raw_P = [self._compute_raw_pso(e.edge_id, step, p_best_route, g_best) for e in candidates]
            raw_H = [self._compute_raw_visibility(e.edge_id) for e in candidates]

            # Normalisation to [0, 1] (Eqs. 8-11)
            norm_A = self._normalise_to_unit(raw_A)
            norm_B = self._normalise_to_unit(raw_B)
            norm_P = self._normalise_to_unit(raw_P)
            norm_H = self._normalise_to_unit(raw_H)

            # Total weights (Eq. 2)
            weights_arr: list[float] = []
            for j in range(len(candidates)):
                w = (alpha_a * norm_A[j] +
                     alpha_b * norm_B[j] +
                     alpha_p * norm_P[j] +
                     alpha_h * norm_H[j])
                weights_arr.append(max(w, 0.0))

            # Roulette selection (Eq. 7)
            total = sum(weights_arr)
            if total <= 0.0:
                chosen = stream.choice(candidates)
            else:
                r = stream.random() * total
                cum = 0.0
                chosen = candidates[-1]
                for j, e in enumerate(candidates):
                    cum += weights_arr[j]
                    if r <= cum:
                        chosen = e
                        break

            route.append(chosen.edge_id)
            prev = current
            current = chosen.target

        return route

    def _compute_raw_aco(
        self,
        edge_id: EdgeId,
        pheromones: HybridPheromoneMatrix | None,
    ) -> float:
        if pheromones is None:
            return 1.0
        tau = pheromones.get(edge_id)
        return tau ** self._config.beta_a

    def _compute_raw_bco(
        self,
        edge_id: EdgeId,
        step: int,
        templates: list[list[EdgeId]],
    ) -> float:
        if not templates:
            return self._config.epsilon
        for tmpl in templates:
            if step < len(tmpl) and edge_id == tmpl[step]:
                return 1.0
        return self._config.epsilon

    def _compute_raw_pso(
        self,
        edge_id: EdgeId,
        step: int,
        p_best_route: list[EdgeId],
        g_best: list[EdgeId],
    ) -> float:
        M_p = 1.0 if step < len(p_best_route) and edge_id == p_best_route[step] else self._config.epsilon
        M_g = 1.0 if step < len(g_best) and edge_id == g_best[step] else self._config.epsilon
        return self._config.cognition_weight * M_p + self._config.social_weight * M_g

    def _compute_raw_visibility(self, edge_id: EdgeId) -> float:
        return self._visibility.get(edge_id, 0.0)

    @staticmethod
    def _normalise_to_unit(raw_values: list[float]) -> list[float]:
        if not raw_values:
            return []
        min_v = min(raw_values)
        max_v = max(raw_values)
        if max_v - min_v < _EPS:
            return [1.0] * len(raw_values)
        return [(v - min_v) / (max_v - min_v) for v in raw_values]

    # =====================================================================
    # Forward Pass
    # =====================================================================

    def _forward_pass(
        self,
        iteration: int,
        pheromones: HybridPheromoneMatrix,
        inertia: float,
    ) -> tuple[list[list[EdgeId]], list[float], list[IndividualKind], list[IndividualStatus]]:
        P = len(self._individuals)
        routes: list[list[EdgeId]] = []
        costs: list[float] = []
        kinds: list[IndividualKind] = []
        states: list[IndividualStatus] = []

        for i in range(P):
            ind = self._individuals[i]
            ind.reset_route()
            kinds.append(ind.kind)

            # Select stream by kind
            if ind.kind == IndividualKind.ANT:
                stream = self._swarm_rng.get_stream("e3hybrid.ant.selection")
            elif ind.kind == IndividualKind.BEE:
                stream = self._swarm_rng.get_stream("e3hybrid.bee.selection")
            elif ind.kind == IndividualKind.PARTICLE:
                stream = self._swarm_rng.get_stream("e3hybrid.particle.selection")

            alpha_a_eff = self._influence_weights.alpha_a
            alpha_b_eff = self._influence_weights.alpha_b
            alpha_p_eff = self._influence_weights.alpha_p
            alpha_h_eff = self._influence_weights.alpha_h

            new_route = self._construct_route(
                source=self._source,
                destination=self._destination,
                current_route=ind.route,
                p_best_route=ind.p_best_route,
                templates=self._templates,
                g_best=self._global_best_route,
                pheromones=pheromones,
                alpha_a=alpha_a_eff,
                alpha_b=alpha_b_eff,
                alpha_p=alpha_p_eff,
                alpha_h=alpha_h_eff,
                stream=stream,
            )

            new_cost_val = sum(
                self._edge_total_cost(self._graph.get_edge(eid))
                for eid in new_route
            ) if new_route else float("inf")

            reached_dest = bool(new_route) and self._graph.get_edge(new_route[-1]).target == self._destination
            ind.route = new_route
            ind.cost = new_cost_val
            ind.state = IndividualStatus.COMPLETE if reached_dest else IndividualStatus.FAILED

            # Local pheromone update for ants (Eq. 13)
            if ind.kind == IndividualKind.ANT:
                for eid in new_route:
                    pheromones.local_update(eid, self._config.rho_local)

            routes.append(new_route)
            costs.append(new_cost_val)
            states.append(ind.state)

        return routes, costs, kinds, states

    # =====================================================================
    # Backward Pass
    # =====================================================================

    def _backward_pass(
        self,
        routes: list[list[EdgeId]],
        costs: list[float],
        kinds: list[IndividualKind],
        states: list[IndividualStatus],
        pheromones: HybridPheromoneMatrix,
    ) -> tuple[float, list[EdgeId]]:
        P = len(self._individuals)

        # Personal best update (Eq. 18) — all individuals
        for i in range(P):
            if states[i] == IndividualStatus.COMPLETE and costs[i] < self._individuals[i].p_best_cost:
                self._individuals[i].p_best_route = list(routes[i])
                self._individuals[i].p_best_cost = costs[i]

        # Find best complete route this iteration
        valid = [(costs[i], i) for i in range(P) if states[i] == IndividualStatus.COMPLETE]
        if valid:
            best_cost, best_idx = min(valid, key=lambda x: x[0])
            best_route = routes[best_idx]
        else:
            best_cost = float("inf")
            best_route = []

        # Global pheromone update using best over all subpopulations (Eqs. 14-16)
        if best_route and best_cost < float("inf"):
            deposit = 1.0 / best_cost
            for eid in best_route:
                current = pheromones.get(eid)
                updated = (1.0 - self._config.rho) * current + self._config.rho * deposit
                pheromones.set(eid, updated)

        return best_cost, best_route

    def _extract_templates(
        self,
        routes: list[list[EdgeId]],
        costs: list[float],
    ) -> list[list[EdgeId]]:
        L = self._config.template_count
        if L <= 0:
            return []

        # Pair routes with costs, filter complete routes
        valid = [(r, c) for r, c in zip(routes, costs) if r and c < float("inf")]
        if not valid:
            return []

        # Sort by cost ascending, take top L
        valid.sort(key=lambda x: x[1])
        return [list(r) for r, _ in valid[:L]]

    def _compute_diversity(self, routes: list[list[EdgeId]]) -> float:
        """Jaccard-based diversity (Eq. 21)."""
        if len(routes) < 2:
            return 0.0

        edge_sets = [set(r) for r in routes]
        total_pairs = 0
        similarity_sum = 0.0

        for i in range(len(edge_sets)):
            for j in range(i + 1, len(edge_sets)):
                total_pairs += 1
                union = edge_sets[i] | edge_sets[j]
                if union:
                    similarity_sum += len(edge_sets[i] & edge_sets[j]) / len(union)

        if total_pairs == 0:
            return 0.0

        avg_jaccard = similarity_sum / total_pairs
        return 1.0 - avg_jaccard

    # =====================================================================
    # Meta-Controller
    # =====================================================================

    def _update_meta_controller(
        self,
        iteration: int,
        routes: list[list[EdgeId]],
        kinds: list[IndividualKind],
    ) -> None:
        K = self._config.adapt_interval
        if iteration == 0 or iteration % K != 0:
            return

        # Group edges by subpopulation
        edges_by_kind: dict[str, set[EdgeId]] = {"a": set(), "b": set(), "p": set()}
        kind_to_key = {
            IndividualKind.ANT: "a",
            IndividualKind.BEE: "b",
            IndividualKind.PARTICLE: "p",
        }
        counts: dict[str, int] = {"a": 0, "b": 0, "p": 0}

        for i, r in enumerate(routes):
            key = kind_to_key.get(kinds[i], "p")
            edges_by_kind[key] |= set(r)
            counts[key] += 1

        # Compute per-subpopulation diversity (Eq. 22)
        total_avg_len = statistics.mean([len(r) for r in routes]) if routes else 0
        diversities: dict[str, float] = {}
        for key in ("a", "b", "p"):
            n = max(counts[key], 1)
            max_possible = n * max(total_avg_len, 1.0)
            if max_possible > 0:
                diversities[key] = len(edges_by_kind[key]) / max_possible
            else:
                diversities[key] = 1.0

        # Decide which subpopulations have low diversity
        decayed_keys: list[str] = []
        for key, div in diversities.items():
            if div < self._config.adapt_diversity_min:
                self._low_diversity_counts[key] += 1
                if self._low_diversity_counts[key] >= 1:
                    decayed_keys.append(key)
            else:
                # Recovery (Eq. 24)
                if self._low_diversity_counts[key] > 0:
                    self._low_diversity_counts[key] = 0
                    current = getattr(self._influence_weights, f"alpha_{key}")
                    max_attr = getattr(self._config, f"alpha_{key}_max")
                    new_val = min(max_attr, current + self._config.adapt_recovery_gain)
                    setattr(self._influence_weights, f"alpha_{key}", new_val)

        # Apply decay (Eq. 23) for low-diversity subpopulations
        total_removed = 0.0
        for key in decayed_keys:
            current = getattr(self._influence_weights, f"alpha_{key}")
            min_attr = getattr(self._config, f"alpha_{key}_min")
            new_val = max(min_attr, current * self._config.adapt_decay)
            removed = current - new_val
            setattr(self._influence_weights, f"alpha_{key}", new_val)
            total_removed += removed

        # Redistribute to non-decayed components
        non_decayed = [k for k in ("a", "b", "p") if k not in decayed_keys]
        if non_decayed and total_removed > 0:
            per_gain = total_removed / len(non_decayed)
            for key in non_decayed:
                current = getattr(self._influence_weights, f"alpha_{key}")
                max_attr = getattr(self._config, f"alpha_{key}_max")
                new_val = min(max_attr, current + per_gain)
                setattr(self._influence_weights, f"alpha_{key}", new_val)
        elif not non_decayed and total_removed > 0:
            self._influence_weights.alpha_h += total_removed

        # Normalise (Eq. 25)
        self._normalise_influence_weights()

    def _normalise_influence_weights(self) -> None:
        S_ref = self._config.alpha_a + self._config.alpha_b + self._config.alpha_p
        a = self._influence_weights.alpha_a
        b = self._influence_weights.alpha_b
        p = self._influence_weights.alpha_p
        S = a + b + p

        if S > 0 and abs(S - S_ref) > _EPS:
            factor = S_ref / S
            self._influence_weights.alpha_a = max(self._config.alpha_a_min,
                                                  min(self._config.alpha_a_max, a * factor))
            self._influence_weights.alpha_b = max(self._config.alpha_b_min,
                                                  min(self._config.alpha_b_max, b * factor))
            self._influence_weights.alpha_p = max(self._config.alpha_p_min,
                                                  min(self._config.alpha_p_max, p * factor))

    # =====================================================================
    # Result Building
    # =====================================================================

    def _build_swarm_result(
        self,
        total_time: float,
        term_reason: str,
        term_iteration: int,
    ) -> SwarmResult:
        from e3hybrid.swarm.result import SwarmResult
        from e3hybrid.swarm.statistics import SwarmStatistics

        candidates = []
        if self._global_best_route and self._global_best_cost < float("inf"):
            candidate = self._route_to_candidate(self._global_best_route, total_time)
            candidates.append(candidate)

        scores = [s.best_cost for s in self._iteration_stats if s.best_cost > 0]
        avg = statistics.mean(scores) if scores else 0.0
        worst = max(scores) if scores else 0.0
        conv_iter = self._find_convergence_iteration()

        swarm_stats = SwarmStatistics(
            total_iterations=term_iteration,
            total_runtime_s=total_time,
            best_score=self._global_best_cost if self._global_best_cost < float("inf") else 0.0,
            average_score=avg,
            worst_score=worst,
            convergence_iteration=conv_iter,
            candidate_count=len(candidates),
            solutions_evaluated=term_iteration * len(self._individuals),
            diversity_history=tuple(self._diversity_history),
            score_history=tuple(self._score_history),
            termination_reason=term_reason,
        )

        return SwarmResult(
            best_solution=candidates[0] if candidates else None,
            candidates=tuple(candidates),
            statistics=swarm_stats,
            iterations=tuple(self._build_iteration_stats()),
            success=len(candidates) > 0,
            failure_reason=None if candidates else "No feasible route found by any individual",
        )

    def _route_to_candidate(
        self,
        edges: list[EdgeId],
        runtime: float,
    ) -> RouteCandidate:
        from e3hybrid.routing.candidate import RouteCandidate, SearchStatistics
        from e3hybrid.routing.cost import RouteCost
        from e3hybrid.routing.types import RouteId

        nodes = [self._source]
        for eid in edges:
            edge = self._graph.get_edge(eid)
            nodes.append(edge.target)

        total_cost = sum(self._edge_total_cost(self._graph.get_edge(eid)) for eid in edges)

        route_cost = RouteCost(
            total=total_cost, distance_cost=total_cost, time_cost=0.0,
            energy_cost=0.0, congestion_penalty=0.0, hazard_penalty=0.0,
            emergency_penalty=0.0, communication_penalty=0.0,
            components={"e3hybrid_cost": total_cost},
        )

        return RouteCandidate(
            route_id=RouteId(f"e3hybrid_{uuid.uuid4().hex[:8]}"),
            node_sequence=tuple(nodes),
            edge_sequence=tuple(edges),
            total_cost=total_cost,
            cost_breakdown=route_cost,
            algorithm="e3hybrid",
            metadata={
                "alpha_a": self._influence_weights.alpha_a,
                "alpha_b": self._influence_weights.alpha_b,
                "alpha_p": self._influence_weights.alpha_p,
                "alpha_h": self._influence_weights.alpha_h,
                "template_count": len(self._templates),
                "ant_count": sum(1 for ind in self._individuals
                                 if ind.kind == IndividualKind.ANT),
                "bee_count": sum(1 for ind in self._individuals
                                if ind.kind == IndividualKind.BEE),
                "particle_count": sum(1 for ind in self._individuals
                                     if ind.kind == IndividualKind.PARTICLE),
            },
            runtime_s=runtime,
            search_statistics=SearchStatistics(
                iterations=len(self._iteration_stats),
                convergence=self._diversity_history[-1] if self._diversity_history else 0.0,
                diversity=self._diversity_history[-1] if self._diversity_history else 0.0,
            ),
        )

    def _build_iteration_stats(self) -> list[IterationStatistics]:
        from e3hybrid.swarm.statistics import IterationStatistics

        result: list[IterationStatistics] = []
        for s in self._iteration_stats:
            result.append(IterationStatistics(
                iteration=s.iteration,
                best_score=s.best_cost,
                average_score=s.avg_cost,
                midrange_score=(s.best_cost + s.worst_cost) / 2.0,
                worst_score=s.worst_cost,
                std_dev=0.0,
                diversity=s.diversity,
                best_solution_changed=True,
                runtime_s=s.runtime_s,
            ))
        return result

    def _find_convergence_iteration(self) -> int | None:
        for i in range(len(self._iteration_stats) - 1, -1, -1):
            if i == 0 or self._iteration_stats[i].best_cost < self._iteration_stats[i - 1].best_cost:
                return i
        return None

    def _failure_result(self, reason: str) -> SwarmResult:
        return _failure_result(reason)


# =========================================================================
# Module-level helpers
# =========================================================================


def _validate_context(context: SwarmContext) -> list[str]:
    errors: list[str] = []
    if context.graph is None:
        errors.append("SwarmContext.graph is required for E3Hybrid")
    if context.cost_calculator is None:
        errors.append("SwarmContext.cost_calculator is required for E3Hybrid")
    if context.routing_request.source_node == context.routing_request.destination_node:
        errors.append("source and destination must differ")
    return errors


def _failure_result(reason: str) -> SwarmResult:
    from e3hybrid.swarm.result import SwarmResult
    from e3hybrid.swarm.statistics import SwarmStatistics

    return SwarmResult(
        best_solution=None,
        success=False,
        failure_reason=reason,
        statistics=SwarmStatistics(
            total_iterations=0, total_runtime_s=0.0,
            best_score=0.0, average_score=0.0, worst_score=0.0,
            convergence_iteration=None, candidate_count=0, solutions_evaluated=0,
        ),
    )


# Auto-register with SwarmFactory
from e3hybrid.swarm.factory import SwarmFactory
SwarmFactory.register("e3hybrid", E3HybridRouting)

__all__ = [
    "E3HybridRouting",
    "HybridConfiguration",
    "HybridStatistics",
    "HybridInfluenceWeights",
    "IndividualKind",
    "IndividualState",
]