"""Bee Colony Optimization (BCO) implementation for dynamic EV routing.

Implements constructive BCO (Teodorovic, 2009) with forward pass/backward pass
structure, recruitment-based exploration, and no pheromone matrix.

All stochastic decisions use SwarmRandom named streams.
All configuration comes from YAML via SwarmConfig.hyperparameters.
No global state. No direct graph/emergency/communication module access.

Literature
----------
- Teodorovic, D. (2009). Bee colony optimization (BCO). In C. P. Lim, L. C. Jain,
  & S. Dehuri (Eds.), Innovations in Swarm Intelligence (pp. 39-60). Springer.
- Teodorovic, D., & Dell'Orco, M. (2005). Bee colony optimization - a cooperative
  learning approach to complex transportation problems. Advanced OR and AI Methods
  in Transportation, 51-60.
- Teodorovic, D., & Dell'Orco, M. (2008). Mitigating traffic congestion: solving
  the ride-matching problem by bee colony optimization. Transportation Planning
  and Technology, 31(2), 135-152.
- Lucic, P., & Teodorovic, D. (2001). Bee system: modeling combinatorial
  optimization transportation engineering problems by swarm intelligence.
  Preprints of the TRISTAN IV Triennial Symposium on Transportation Analysis,
  441-445.
- Lucic, P., & Teodorovic, D. (2003). Computing with bees: attacking complex
  transportation engineering problems. International Journal on Artificial
  Intelligence Tools, 12(3), 375-394.
"""

from __future__ import annotations

import math
import random
import statistics
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from e3hybrid.network.types import EdgeId, NodeId
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
# BeeStatus
# =========================================================================

class BeeStatus(Enum):
    """State flag sigma_k during the forward pass."""
    CONSTRUCTING = "constructing"
    COMPLETE = "complete"
    FAILED = "failed"


# =========================================================================
# BeeState
# =========================================================================

@dataclass
class BeeState:
    """Complete mutable state of one bee at a given iteration."""

    k: int
    route: list[EdgeId]
    cost: float
    quality: float
    norm_quality: float
    template: list[EdgeId] | None
    state: BeeStatus
    is_loyal: bool
    visited: set[NodeId]
    iteration_created: int


# =========================================================================
# ForwardPassResult
# =========================================================================

@dataclass
class ForwardPassResult:
    """Aggregated result of one complete forward pass across all bees."""
    routes: list[list[EdgeId]]
    costs: list[float]
    states: list[BeeStatus]
    iteration: int
    runtime_s: float


# =========================================================================
# BackwardPassResult
# =========================================================================

@dataclass
class BackwardPassResult:
    """Aggregated result of one complete backward pass."""
    loyal_indices: list[int]
    uncommitted_indices: list[int]
    best_cost: float
    best_route: list[EdgeId]
    global_best_cost: float
    global_best_route: list[EdgeId]
    diversity: float
    runtime_s: float


# =========================================================================
# BCOStatistics
# =========================================================================

@dataclass(frozen=True, slots=True)
class BCOStatistics:
    """Per-iteration statistics specific to BCO."""
    iteration: int
    best_cost: float
    avg_cost: float
    worst_cost: float
    loyal_count: int
    uncommitted_count: int
    diversity: float
    runtime_s: float


# =========================================================================
# VisibilityCache
# =========================================================================

@dataclass
class VisibilityCache:
    """Precomputed heuristic visibility for all edges."""

    values: dict[EdgeId, float]
    beta: float
    delta: float


# =========================================================================
# BCOConfiguration
# =========================================================================

@dataclass(frozen=True, slots=True)
class BCOConfiguration:
    """Type-safe extraction of BCO hyperparameters from SwarmConfig."""

    forward_steps: int
    beta: float
    delta: float
    elite_count: int

    @classmethod
    def from_config(cls, config: SwarmConfig) -> BCOConfiguration:
        hp = config.hyperparameters

        def _hp_float(key: str, default: float) -> float:
            if key not in hp:
                return default
            val = hp[key]
            if isinstance(val, (int, float)):
                return float(val)
            raise TypeError(
                f"hyperparameter '{key}' must be a number, "
                f"got {type(val).__name__}"
            )

        def _hp_int(key: str, default: int) -> int:
            if key not in hp:
                return default
            val = hp[key]
            if isinstance(val, int):
                return val
            if isinstance(val, float) and val == int(val):
                return int(val)
            raise TypeError(
                f"hyperparameter '{key}' must be an integer, "
                f"got {type(val).__name__}"
            )

        fs = _hp_int("forward_steps", 500)
        b = _hp_float("visibility_weight", 2.0)
        d = _hp_float("template_strength", 3.0)
        k = _hp_int("elite_count", 3)
        bc = BCOConfiguration(fs, b, d, k)
        bc._validate(config.population_size)
        return bc

    def _validate(self, population_size: int) -> None:
        if self.forward_steps < 1:
            raise ValueError("forward_steps must be >= 1")
        if self.beta < 0:
            raise ValueError("beta must be >= 0")
        if self.delta < 0:
            raise ValueError("delta must be >= 0")
        if population_size < 2:
            raise ValueError("population_size must be >= 2")
        if not 0 <= self.elite_count <= population_size:
            raise ValueError(
                f"elite_count ({self.elite_count}) must be between 0 and "
                f"population_size ({population_size})"
            )


# =========================================================================
# BCOValidator
# =========================================================================

class BCOValidator:
    """Validates BCO configuration and runtime context."""

    @staticmethod
    def validate_context(context: SwarmContext) -> list[str]:
        errors: list[str] = []
        if context.graph is None:
            errors.append("SwarmContext.graph is required for BCO")
        if context.cost_calculator is None:
            errors.append("SwarmContext.cost_calculator is required for BCO")
        if context.routing_request.source_node == context.routing_request.destination_node:
            errors.append("source and destination must differ")
        return errors


# =========================================================================
# BCORouting
# =========================================================================

class BCORouting:
    """Bee Colony Optimization implementing the SwarmAlgorithm Protocol.

    One instance can be reused across multiple optimize() calls.
    Internal state is fully reinitialized per call.
    """

    def __init__(self) -> None:
        self._bees: list[BeeState] = []
        self._visibility: VisibilityCache | None = None
        self._swarm_rng: SwarmRandom | None = None
        self._config: BCOConfiguration | None = None
        self._context: SwarmContext | None = None
        self._global_best_cost: float = float("inf")
        self._global_best_route: list[EdgeId] = []
        self._iteration_stats: list[BCOStatistics] = []
        self._graph: DirectedGraph | None = None
        self._cost_calculator: CompositeCostCalculator | None = None
        self._source: NodeId | None = None
        self._destination: NodeId | None = None

    @property
    def name(self) -> str:
        return "bco"

    def optimize(self, context: SwarmContext) -> SwarmResult:
        from e3hybrid.routing.candidate import RouteCandidate, SearchStatistics
        from e3hybrid.routing.cost import RouteCost
        from e3hybrid.routing.types import RouteId
        from e3hybrid.swarm.config import SwarmConfig
        from e3hybrid.swarm.models import SearchState
        from e3hybrid.swarm.result import SwarmResult
        from e3hybrid.swarm.statistics import SwarmStatistics
        from e3hybrid.swarm.termination import TerminationChecker

        # Validate
        ctx_errors = BCOValidator.validate_context(context)
        if ctx_errors:
            return self._failure_result("; ".join(ctx_errors))

        self._context = context
        self._graph = context.graph
        self._cost_calculator = context.cost_calculator
        self._source = context.routing_request.source_node
        self._destination = context.routing_request.destination_node
        config = context.config

        # Build config
        self._config = BCOConfiguration.from_config(config)

        # Validate graph connectivity
        if not self._graph.has_node(self._source):
            return self._failure_result("Source node not in graph")
        if not self._graph.has_node(self._destination):
            return self._failure_result("Destination node not in graph")

        # Build visibility cache
        self._build_visibility()

        # Random streams
        self._swarm_rng = SwarmRandom(context.random_seed)

        # Bee population
        B = config.population_size
        self._bees = []
        for k in range(B):
            self._bees.append(BeeState(
                k=k, route=[], cost=0.0, quality=0.0,
                norm_quality=0.0, template=None,
                state=BeeStatus.CONSTRUCTING, is_loyal=False,
                visited=set(), iteration_created=-1,
            ))

        # Global best tracking
        self._global_best_cost = float("inf")
        self._global_best_route = []
        self._iteration_stats = []

        # Termination checker
        checker = TerminationChecker(config)
        checker.start()

        start_time = time.perf_counter()

        # Iteration loop
        no_improvement_count = 0
        prev_best_score = float("inf")

        for iteration in range(config.max_iterations):
            iteration_start = time.perf_counter()

            # Forward pass
            fwd = self._forward_pass(iteration)

            # Backward pass
            bwd = self._backward_pass(fwd, iteration)

            # Update global best
            if bwd.best_cost < self._global_best_cost:
                self._global_best_cost = bwd.best_cost
                self._global_best_route = list(bwd.best_route)

            # Compute per-iteration stats
            costs_success = [b.cost for b in self._bees if b.state == BeeStatus.COMPLETE]
            avg_cost = statistics.mean(costs_success) if costs_success else float("inf")
            worst_cost = max(costs_success) if costs_success else float("inf")

            self._iteration_stats.append(BCOStatistics(
                iteration=iteration,
                best_cost=bwd.best_cost,
                avg_cost=avg_cost,
                worst_cost=worst_cost,
                loyal_count=len(bwd.loyal_indices),
                uncommitted_count=len(bwd.uncommitted_indices),
                diversity=bwd.diversity,
                runtime_s=time.perf_counter() - iteration_start,
            ))

            # Update no_improvement_count for termination
            current_best = self._global_best_cost
            if current_best == float("inf"):
                no_improvement_count = 0
            elif current_best >= prev_best_score:
                no_improvement_count += 1
            else:
                no_improvement_count = 0
            prev_best_score = current_best

            search_state = SearchState(
                iteration=iteration + 1,
                best_score=current_best,
                previous_best_score=prev_best_score if iteration > 0 else float("inf"),
                no_improvement_count=no_improvement_count,
                diversity=bwd.diversity,
                elapsed_time_s=time.perf_counter() - start_time,
            )

            # Check termination
            term = checker.check(search_state)
            if term.should_stop:
                total_time = time.perf_counter() - start_time
                return self._build_swarm_result(
                    total_time=total_time,
                    term_reason=term.reason,
                    term_iteration=term.iteration,
                )

        total_time = time.perf_counter() - start_time
        return self._build_swarm_result(
            total_time=total_time,
            term_reason=f"Maximum iterations reached ({config.max_iterations})",
            term_iteration=config.max_iterations,
        )

    # ------------------------------------------------------------------
    # Internal: visibility + cost helpers
    # ------------------------------------------------------------------

    def _build_visibility(self) -> None:
        vis: dict[EdgeId, float] = {}
        for edge in self._graph.edges():
            eid = edge.edge_id
            if edge.state.is_blocked:
                vis[eid] = 0.0
            else:
                try:
                    edge_cost, _ = self._cost_calculator.compute_edge_cost(edge)
                except Exception:
                    edge_cost = float("inf")
                if not math.isfinite(edge_cost) or edge_cost < 0:
                    vis[eid] = 0.0
                elif edge_cost == 0.0:
                    vis[eid] = 1.0 / _EPS
                else:
                    vis[eid] = 1.0 / (edge_cost + _EPS)
        self._visibility = VisibilityCache(vis, self._config.beta, self._config.delta)

    def _edge_total_cost(self, edge: Edge) -> float:
        if edge.state.is_blocked:
            return float("inf")
        try:
            cost_val, _ = self._cost_calculator.compute_edge_cost(edge)
            return cost_val if math.isfinite(cost_val) and cost_val >= 0 else float("inf")
        except Exception:
            return float("inf")

    # ------------------------------------------------------------------
    # Forward pass
    # ------------------------------------------------------------------

    def _forward_pass(self, iteration: int) -> ForwardPassResult:
        B = len(self._bees)
        routes: list[list[EdgeId]] = [[] for _ in range(B)]
        costs: list[float] = [0.0] * B
        states: list[BeeStatus] = [BeeStatus.CONSTRUCTING] * B
        sel_stream = self._swarm_rng.get_stream("bco.selection")
        t0 = time.perf_counter()

        for k in range(B):
            bee = self._bees[k]
            bee.route = []
            bee.visited = set()
            bee.state = BeeStatus.CONSTRUCTING

            current: NodeId = self._source
            prev_node: NodeId | None = None
            route_edges: list[EdgeId] = []
            total_cost: float = 0.0

            for _ in range(self._config.forward_steps):
                outgoing = self._graph.outgoing_edges(current)
                feasible: list[Edge] = []
                for e in outgoing:
                    ec = self._edge_total_cost(e)
                    if ec < float("inf"):
                        feasible.append(e)
                # Only filter back-track if forward options exist
                if len(feasible) > 1 and prev_node is not None:
                    feasible = [e for e in feasible if e.target != prev_node]
                if not feasible:
                    break
                # Prefer non-dead-end nodes, but fall back to dead-ends if necessary
                if len(feasible) > 1:
                    non_deadend = [
                        e for e in feasible
                        if e.target == self._destination
                        or len(list(self._graph.outgoing_edges(e.target))) > 0
                    ]
                    if non_deadend:
                        feasible = non_deadend

                probs = self._compute_selection_probs(feasible, bee.template)

                r = sel_stream.random()
                cum = 0.0
                chosen: Edge = feasible[-1]
                for i, p in enumerate(probs):
                    cum += p
                    if r <= cum:
                        chosen = feasible[i]
                        break

                route_edges.append(chosen.edge_id)
                edge_cost, _ = self._cost_calculator.compute_edge_cost(chosen)
                total_cost += edge_cost
                prev_node = current
                current = chosen.target

                if current == self._destination:
                    break

            routes[k] = route_edges
            costs[k] = total_cost
            if current == self._destination:
                states[k] = BeeStatus.COMPLETE
            else:
                states[k] = BeeStatus.FAILED

            bee.route = route_edges
            bee.state = states[k]
            bee.cost = total_cost
            bee.iteration_created = iteration

        t1 = time.perf_counter()
        return ForwardPassResult(routes, costs, states, iteration, t1 - t0)

    # ------------------------------------------------------------------
    # Selection probabilities
    # ------------------------------------------------------------------

    def _compute_selection_probs(
        self,
        feasible: list[Edge],
        template: list[EdgeId] | None,
    ) -> list[float]:
        probs: list[float] = []
        template_set: set[EdgeId] = set(template) if template else set()

        for e in feasible:
            eta = self._visibility.values.get(e.edge_id, 0.0)
            w = eta ** self._config.beta
            if e.edge_id in template_set:
                w *= 1.0 + self._config.delta
            probs.append(w)

        total = sum(probs)
        if total <= 0.0:
            p = 1.0 / len(feasible)
            return [p] * len(feasible)
        return [p / total for p in probs]

    # ------------------------------------------------------------------
    # Backward pass
    # ------------------------------------------------------------------

    def _backward_pass(self, forward: ForwardPassResult,
                       iteration: int) -> BackwardPassResult:
        t0 = time.perf_counter()

        # Phase 1: Evaluation
        B = len(self._bees)
        for bee in self._bees:
            if bee.state == BeeStatus.COMPLETE:
                bee.quality = 1.0 / (bee.cost + _EPS)
            else:
                bee.quality = 0.0
                bee.cost = float("inf")

        sorted_indices = sorted(
            range(B), key=lambda i: self._bees[i].quality, reverse=True
        )
        best_idx = sorted_indices[0]
        best_cost = self._bees[best_idx].cost
        best_route = self._bees[best_idx].route

        if best_cost < self._global_best_cost:
            self._global_best_cost = best_cost
            self._global_best_route = list(best_route)

        # Phase 2: Loyalty Decision
        K = self._config.elite_count
        elite_set: set[int] = set(sorted_indices[:K])
        loyal: list[int] = []
        uncommitted: list[int] = []
        loyal_stream = self._swarm_rng.get_stream("bco.loyalty")

        max_q = max(bee.quality for bee in self._bees) if B > 0 else 0.0
        for bee in self._bees:
            bee.norm_quality = bee.quality / max_q if max_q > 0 else 0.0

        for k, bee in enumerate(self._bees):
            if bee.state != BeeStatus.COMPLETE:
                uncommitted.append(k)
                bee.is_loyal = False
                continue
            if k in elite_set:
                loyal.append(k)
                bee.is_loyal = True
                continue
            if self._loyalty_decision(k, loyal_stream):
                loyal.append(k)
                bee.is_loyal = True
            else:
                uncommitted.append(k)
                bee.is_loyal = False

        # Phase 3: Recruitment
        rec_stream = self._swarm_rng.get_stream("bco.recruitment")
        if uncommitted and loyal:
            self._recruitment(uncommitted, loyal, rec_stream)

        self._update_templates()
        diversity = self._compute_diversity()

        t1 = time.perf_counter()
        return BackwardPassResult(
            loyal_indices=list(loyal),
            uncommitted_indices=list(uncommitted),
            best_cost=best_cost,
            best_route=list(best_route),
            global_best_cost=self._global_best_cost,
            global_best_route=list(self._global_best_route),
            diversity=diversity,
            runtime_s=t1 - t0,
        )

    # ------------------------------------------------------------------
    # Loyalty decision
    # ------------------------------------------------------------------

    def _loyalty_decision(self, bee_index: int,
                          stream: random.Random) -> bool:
        bee = self._bees[bee_index]
        p_loyal = bee.norm_quality
        rho = stream.random()
        return rho <= p_loyal

    # ------------------------------------------------------------------
    # Recruitment
    # ------------------------------------------------------------------

    def _recruitment(self, uncommitted: list[int],
                     loyal: list[int], stream: random.Random) -> None:
        total_o = sum(self._bees[j].quality for j in loyal)
        if total_o <= 0.0:
            for u_idx in uncommitted:
                recruiter = stream.choice(loyal)
                self._bees[u_idx].template = list(self._bees[recruiter].route)
            return

        loyal_indices = list(loyal)
        cum_probs: list[float] = []
        running = 0.0
        for j in loyal_indices:
            p = self._bees[j].quality / total_o
            running += p
            cum_probs.append(running)

        for u_idx in uncommitted:
            r = stream.random()
            lo, hi = 0, len(cum_probs)
            while lo < hi:
                mid = (lo + hi) // 2
                if r <= cum_probs[mid]:
                    hi = mid
                else:
                    lo = mid + 1
            idx = loyal_indices[lo] if lo < len(loyal_indices) else loyal_indices[-1]
            self._bees[u_idx].template = list(self._bees[idx].route)

    # ------------------------------------------------------------------
    # Template update
    # ------------------------------------------------------------------

    def _update_templates(self) -> None:
        for bee in self._bees:
            if bee.state == BeeStatus.FAILED:
                continue
            if bee.is_loyal and bee.state == BeeStatus.COMPLETE:
                bee.template = list(bee.route)

    # ------------------------------------------------------------------
    # Diversity
    # ------------------------------------------------------------------

    def _compute_diversity(self) -> float:
        templates = [bee.template for bee in self._bees if bee.template is not None]
        if len(templates) < 2:
            return 0.0

        total_sim = 0.0
        pairs = 0
        for i in range(len(templates)):
            ti = set(templates[i])
            for j in range(i + 1, len(templates)):
                tj = set(templates[j])
                union = len(ti | tj)
                if union > 0:
                    total_sim += len(ti & tj) / union
                pairs += 1
        avg_sim = total_sim / pairs if pairs > 0 else 0.0
        return 1.0 - avg_sim

    # ------------------------------------------------------------------
    # Result building
    # ------------------------------------------------------------------

    def _build_swarm_result(
        self,
        total_time: float,
        term_reason: str,
        term_iteration: int,
    ) -> SwarmResult:
        from e3hybrid.routing.candidate import RouteCandidate, SearchStatistics
        from e3hybrid.routing.cost import RouteCost
        from e3hybrid.routing.types import RouteId
        from e3hybrid.swarm.result import SwarmResult
        from e3hybrid.swarm.statistics import SwarmStatistics

        best_rc = self._route_to_candidate(self._global_best_route, runtime_s=total_time)

        all_candidates: list[RouteCandidate] = [best_rc]
        seen_routes: set[tuple[EdgeId, ...]] = {tuple(self._global_best_route)}
        for bee in self._bees:
            if bee.state == BeeStatus.COMPLETE and bee.route:
                key = tuple(bee.route)
                if key not in seen_routes:
                    seen_routes.add(key)
                    rc = self._route_to_candidate(bee.route, runtime_s=total_time)
                    all_candidates.append(rc)

        scores = [b.cost for b in self._bees if b.state == BeeStatus.COMPLETE]
        best_score = min(scores) if scores else float("inf")
        avg_score = statistics.mean(scores) if scores else float("inf")
        worst_score = max(scores) if scores else float("inf")

        diversity_history = tuple(s.diversity for s in self._iteration_stats)
        score_history = tuple(s.best_cost for s in self._iteration_stats)

        swarm_stats = SwarmStatistics(
            total_iterations=term_iteration,
            total_runtime_s=total_time,
            best_score=best_score if math.isfinite(best_score) else 0.0,
            average_score=avg_score if math.isfinite(avg_score) else 0.0,
            worst_score=worst_score if math.isfinite(worst_score) else 0.0,
            convergence_iteration=self._find_convergence_iteration(),
            candidate_count=len(all_candidates),
            solutions_evaluated=len(self._iteration_stats) * len(self._bees),
            diversity_history=diversity_history,
            score_history=score_history,
            termination_reason=term_reason,
        )

        success = len(self._global_best_route) > 0

        return SwarmResult(
            best_solution=best_rc,
            candidates=tuple(all_candidates),
            statistics=swarm_stats,
            iterations=tuple(self._build_iteration_stats()),
            success=success,
            failure_reason=None if success else "No feasible route found by any bee",
        )

    def _route_to_candidate(self, edges: list[EdgeId],
                            runtime_s: float = 0.0) -> RouteCandidate:
        from e3hybrid.routing.candidate import RouteCandidate, SearchStatistics
        from e3hybrid.routing.cost import RouteCost
        from e3hybrid.routing.types import RouteId

        if not edges:
            inf_cost = RouteCost(
                total=1e9, distance_cost=1e9, time_cost=0.0,
                energy_cost=0.0, congestion_penalty=0.0, hazard_penalty=0.0,
                emergency_penalty=0.0, communication_penalty=0.0,
                components={"bco_cost": 1e9},
            )
            return RouteCandidate(
                route_id=RouteId(f"bco_{uuid.uuid4().hex[:8]}"),
                node_sequence=(self._source, self._destination),
                edge_sequence=(EdgeId(""),),
                total_cost=1e9,
                cost_breakdown=inf_cost,
                algorithm="bco",
                metadata={"state": "failed"},
                runtime_s=runtime_s,
                search_statistics=SearchStatistics(),
            )

        nodes: list[NodeId] = [self._source]
        total_cost_val = 0.0

        for eid in edges:
            edge = self._graph.get_edge(eid)
            nodes.append(edge.target)
            try:
                cost_val, _ = self._cost_calculator.compute_edge_cost(edge)
            except Exception:
                cost_val = float("inf")
            total_cost_val += cost_val

        if not math.isfinite(total_cost_val):
            total_cost_val = float("inf")

        return RouteCandidate(
            route_id=RouteId(f"bco_{uuid.uuid4().hex[:8]}"),
            node_sequence=tuple(nodes),
            edge_sequence=tuple(edges),
            total_cost=total_cost_val,
            cost_breakdown=RouteCost(
                total=total_cost_val,
                distance_cost=total_cost_val,
                time_cost=0.0,
                energy_cost=0.0,
                congestion_penalty=0.0,
                hazard_penalty=0.0,
                emergency_penalty=0.0,
                communication_penalty=0.0,
                components={"bco_cost": total_cost_val},
            ),
            algorithm="bco",
            metadata={
                "forward_steps": self._config.forward_steps,
                "beta": self._config.beta,
                "delta": self._config.delta,
                "elite_count": self._config.elite_count,
            },
            runtime_s=runtime_s,
            search_statistics=SearchStatistics(
                iterations=len(self._iteration_stats),
                convergence=self._iteration_stats[-1].diversity if self._iteration_stats else 0.0,
                diversity=self._iteration_stats[-1].diversity if self._iteration_stats else 0.0,
            ),
        )

    def _build_iteration_stats(self) -> list[IterationStatistics]:
        from e3hybrid.swarm.statistics import IterationStatistics

        result: list[IterationStatistics] = []
        for s in self._iteration_stats:
            result.append(IterationStatistics(
                iteration=s.iteration,
                best_score=s.best_cost if math.isfinite(s.best_cost) else float("inf"),
                average_score=s.avg_cost if math.isfinite(s.avg_cost) else float("inf"),
                midrange_score=(
                    (s.best_cost + s.worst_cost) / 2.0
                    if math.isfinite(s.best_cost) and math.isfinite(s.worst_cost)
                    else float("inf")
                ),
                worst_score=s.worst_cost if math.isfinite(s.worst_cost) else float("inf"),
                std_dev=0.0,
                diversity=s.diversity,
                best_solution_changed=True,
                runtime_s=s.runtime_s,
            ))
        return result

    def _find_convergence_iteration(self) -> int | None:
        if not self._iteration_stats:
            return None
        for i in range(len(self._iteration_stats) - 1, -1, -1):
            if i == 0:
                continue
            if self._iteration_stats[i].best_cost < self._iteration_stats[i - 1].best_cost:
                return i
        return 0

    def _failure_result(self, reason: str) -> SwarmResult:
        from e3hybrid.swarm.result import SwarmResult
        from e3hybrid.swarm.statistics import SwarmStatistics

        return SwarmResult(
            best_solution=None,  # type: ignore[arg-type]
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

SwarmFactory.register("bco", BCORouting)
