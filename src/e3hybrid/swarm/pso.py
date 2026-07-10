"""Constructive Discrete Particle Swarm Optimization (PSO) for dynamic EV routing.

Implements a constructive-discrete adaptation of PSO (Mohemmed et al., 2008)
for finding shortest paths in directed graphs. No continuous velocity vector
is maintained. Instead, the three PSO forces (inertia, cognitive, social) are
represented as probabilistic edge-selection weights during route construction.

All stochastic decisions use SwarmRandom named streams.
All configuration comes from YAML via SwarmConfig.hyperparameters.
No global state. No direct graph/emergency/communication module access.

Literature
----------
- Kennedy, J., & Eberhart, R. (1995). Particle swarm optimization. Proc. IEEE
  International Conference on Neural Networks, 1942-1948.
- Shi, Y., & Eberhart, R. C. (1998). A modified particle swarm optimizer. Proc.
  IEEE Congress on Evolutionary Computation, 69-73.
- Mohemmed, A. W., Sahoo, N. C., & Geok, T. K. (2008). Solving shortest path
  problem using particle swarm optimization. Applied Soft Computing, 8(4),
  1643-1653.
- Clerc, M. (2004). Discrete particle swarm optimization, illustrated by the
  traveling salesman problem. New Optimization Techniques in Engineering, 219-239.
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


# =========================================================================
# ParticleStatus
# =========================================================================


class ParticleStatus(Enum):
    """State of a particle after route construction."""
    CONSTRUCTING = "constructing"
    COMPLETE = "complete"
    FAILED = "failed"


# =========================================================================
# ParticleState
# =========================================================================


@dataclass
class ParticleState:
    """Complete mutable state of one particle at a given iteration."""

    k: int
    route: list[EdgeId]
    cost: float
    p_best_route: list[EdgeId]
    p_best_cost: float
    state: ParticleStatus
    visited: set[NodeId]


# =========================================================================
# PSOStatistics
# =========================================================================


@dataclass(frozen=True, slots=True)
class PSOStatistics:
    """Per-iteration statistics specific to PSO."""
    iteration: int
    best_cost: float
    avg_cost: float
    worst_cost: float
    inertia: float
    diversity: float
    runtime_s: float


# =========================================================================
# VisibilityCache
# =========================================================================


@dataclass
class VisibilityCache:
    """Precomputed heuristic visibility for all edges."""

    values: dict[EdgeId, float]


# =========================================================================
# PSOConfiguration
# =========================================================================


@dataclass(frozen=True, slots=True)
class PSOConfiguration:
    """Type-safe extraction of PSO hyperparameters from SwarmConfig."""

    inertia_start: float = 0.9
    inertia_end: float = 0.4
    cognition_weight: float = 2.0
    social_weight: float = 2.0
    visibility_weight: float = 1.0
    epsilon: float = 1e-10
    forward_steps: int = 100

    @classmethod
    def from_config(cls, config: SwarmConfig) -> PSOConfiguration:
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

        inertia_start = _hp_float("inertia_start", 0.9)
        inertia_end = _hp_float("inertia_end", 0.4)
        cognition = _hp_float("cognition_weight", 2.0)
        social = _hp_float("social_weight", 2.0)
        visibility = _hp_float("visibility_weight", 1.0)
        eps = _hp_float("epsilon", 1e-10)
        fs = _hp_int("forward_steps", 100)

        pc = PSOConfiguration(
            inertia_start=inertia_start,
            inertia_end=inertia_end,
            cognition_weight=cognition,
            social_weight=social,
            visibility_weight=visibility,
            epsilon=eps,
            forward_steps=fs,
        )
        pc._validate(config.population_size)
        return pc

    def _validate(self, population_size: int) -> None:
        if self.forward_steps < 1:
            raise ValueError("forward_steps must be >= 1")
        if not 0.0 <= self.epsilon <= 1.0:
            raise ValueError("epsilon must be in [0, 1]")
        if self.inertia_start < self.inertia_end:
            raise ValueError("inertia_start must be >= inertia_end")
        if not 0.0 <= self.inertia_end <= self.inertia_start <= 1.0:
            raise ValueError("inertia weights must be in [0, 1] with start >= end")
        if self.cognition_weight < 0:
            raise ValueError("cognition_weight must be >= 0")
        if self.social_weight < 0:
            raise ValueError("social_weight must be >= 0")
        if self.visibility_weight < 0:
            raise ValueError("visibility_weight must be >= 0")
        if population_size < 2:
            raise ValueError("population_size must be >= 2")
        if self.cognition_weight + self.social_weight + self.visibility_weight <= 0:
            raise ValueError(
                "at least one of cognition, social, or visibility weight must be > 0"
            )


# =========================================================================
# PSOValidator
# =========================================================================


class PSOValidator:
    """Validates PSO configuration and runtime context."""

    @staticmethod
    def validate_context(context: SwarmContext) -> list[str]:
        errors: list[str] = []
        if context.graph is None:
            errors.append("SwarmContext.graph is required for PSO")
        if context.cost_calculator is None:
            errors.append("SwarmContext.cost_calculator is required for PSO")
        if context.routing_request.source_node == context.routing_request.destination_node:
            errors.append("source and destination must differ")
        return errors


# =========================================================================
# PSORouting
# =========================================================================


class PSORouting:
    """Constructive Discrete Particle Swarm Optimization.

    Implements the SwarmAlgorithm Protocol. One instance can be reused
    across multiple optimize() calls. Internal state is fully reinitialised
    per call.

    No continuous velocity vector is maintained. The three PSO forces are
    represented as probabilistic edge-selection weights during construction:
    inertia (attraction to current route), cognitive (personal best), and
    social (global best), plus visibility heuristics.
    """

    def __init__(self) -> None:
        self._particles: list[ParticleState] = []
        self._visibility: VisibilityCache | None = None
        self._swarm_rng: SwarmRandom | None = None
        self._config: PSOConfiguration | None = None
        self._context: SwarmContext | None = None
        self._global_best_cost: float = float("inf")
        self._global_best_route: list[EdgeId] = []
        self._iteration_stats: list[PSOStatistics] = []
        self._graph: DirectedGraph | None = None
        self._cost_calculator: CompositeCostCalculator | None = None
        self._source: NodeId | None = None
        self._destination: NodeId | None = None
        self._source_edge_id: EdgeId | None = None

    @property
    def name(self) -> str:
        return "pso"

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
        ctx_errors = PSOValidator.validate_context(context)
        if ctx_errors:
            return self._failure_result("; ".join(ctx_errors))

        self._context = context
        self._graph = context.graph
        self._cost_calculator = context.cost_calculator
        self._source = context.routing_request.source_node
        self._destination = context.routing_request.destination_node
        self._source_edge_id: EdgeId | None = (
            EdgeId(str(context.routing_request.metadata["source_edge_id"]))
            if "source_edge_id" in context.routing_request.metadata
            else None
        )
        config = context.config

        # Build config
        self._config = PSOConfiguration.from_config(config)

        # Validate graph connectivity
        if not self._graph.has_node(self._source):
            return self._failure_result("Source node not in graph")
        if not self._graph.has_node(self._destination):
            return self._failure_result("Destination node not in graph")

        # Build visibility cache
        self._build_visibility()

        # Random streams
        self._swarm_rng = SwarmRandom(context.random_seed)

        # Particle population
        self._initialize()

        # Global best tracking
        self._global_best_cost = min(p.p_best_cost for p in self._particles)
        best_idx = min(
            range(len(self._particles)),
            key=lambda i: self._particles[i].p_best_cost,
        )
        self._global_best_route = list(self._particles[best_idx].p_best_route)
        self._iteration_stats = []

        # Termination checker
        checker = TerminationChecker(config)
        checker.start()

        start_time = time.perf_counter()

        # Iteration loop
        no_improvement_count = 0
        prev_best_score = self._global_best_cost

        for iteration in range(config.max_iterations):
            iteration_start = time.perf_counter()

            # Compute inertia weight (Eq 5)
            w = self._compute_inertia(iteration, config.max_iterations)

            # Forward pass
            fwd_routes, fwd_costs, fwd_states = self._forward_pass(iteration, w)

            # Backward pass
            bwd = self._backward_pass(fwd_routes, fwd_costs, fwd_states)

            # Update global best
            if bwd.best_cost < self._global_best_cost:
                self._global_best_cost = bwd.best_cost
                self._global_best_route = list(bwd.best_route)

            # Compute per-iteration stats
            costs_success = [p.cost for p in self._particles if p.state == ParticleStatus.COMPLETE]
            avg_cost = statistics.mean(costs_success) if costs_success else float("inf")
            worst_cost = max(costs_success) if costs_success else float("inf")

            self._iteration_stats.append(PSOStatistics(
                iteration=iteration,
                best_cost=bwd.best_cost,
                avg_cost=avg_cost,
                worst_cost=worst_cost,
                inertia=w,
                diversity=bwd.diversity,
                runtime_s=time.perf_counter() - iteration_start,
            ))

            # Update no_improvement_count
            current_best = self._global_best_cost
            if current_best >= prev_best_score:
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
        self._visibility = VisibilityCache(vis)

    def _edge_total_cost(self, edge: Edge) -> float:
        if edge.state.is_blocked:
            return float("inf")
        try:
            cost_val, _ = self._cost_calculator.compute_edge_cost(edge)
            return cost_val if math.isfinite(cost_val) and cost_val >= 0 else float("inf")
        except Exception:
            return float("inf")

    # ------------------------------------------------------------------
    # Inertia schedule (Eq 5)
    # ------------------------------------------------------------------

    def _compute_inertia(self, iteration: int, max_iterations: int) -> float:
        if max_iterations <= 1:
            return self._config.inertia_end
        return self._config.inertia_start - (
            self._config.inertia_start - self._config.inertia_end
        ) * iteration / (max_iterations - 1)

    # ------------------------------------------------------------------
    # Particle initialization
    # ------------------------------------------------------------------

    def _initialize(self) -> None:
        B = self._context.config.population_size
        init_stream = self._swarm_rng.get_stream("pso.init")
        self._particles = []

        for k in range(B):
            route = self._construct_route(
                current_route=[],
                p_best_route=[],
                g_best_route=[],
                w=0.0,
                c1=0.0,
                c2=0.0,
                c3=self._config.visibility_weight,
                stream=init_stream,
            )
            cost = self._compute_route_cost(route)

            self._particles.append(ParticleState(
                k=k,
                route=list(route),
                cost=cost,
                p_best_route=list(route),
                p_best_cost=cost,
                state=ParticleStatus.COMPLETE if route else ParticleStatus.FAILED,
                visited=set(),
            ))

    # ------------------------------------------------------------------
    # Forward pass
    # ------------------------------------------------------------------

    def _forward_pass(self, iteration: int, inertia: float) -> tuple[list[list[EdgeId]], list[float], list[ParticleStatus]]:
        B = len(self._particles)
        routes: list[list[EdgeId]] = [[] for _ in range(B)]
        costs: list[float] = [0.0] * B
        states: list[ParticleStatus] = [ParticleStatus.CONSTRUCTING] * B
        sel_stream = self._swarm_rng.get_stream("pso.selection")

        for k in range(B):
            particle = self._particles[k]

            new_route = self._construct_route(
                current_route=particle.route,
                p_best_route=particle.p_best_route,
                g_best_route=self._global_best_route,
                w=inertia,
                c1=self._config.cognition_weight,
                c2=self._config.social_weight,
                c3=self._config.visibility_weight,
                stream=sel_stream,
            )
            new_cost = self._compute_route_cost(new_route)

            particle.route = new_route
            particle.cost = new_cost

            reached = self._route_reaches_destination(new_route)
            if reached:
                particle.state = ParticleStatus.COMPLETE
            else:
                particle.state = ParticleStatus.FAILED

            routes[k] = new_route
            costs[k] = new_cost
            states[k] = particle.state

        return routes, costs, states

    def _compute_route_cost(self, route: list[EdgeId]) -> float:
        total = 0.0
        for eid in route:
            try:
                edge = self._graph.get_edge(eid)
                ec, _ = self._cost_calculator.compute_edge_cost(edge)
                if math.isfinite(ec) and ec >= 0:
                    total += ec
                else:
                    return float("inf")
            except Exception:
                return float("inf")
        return total

    def _route_reaches_destination(self, route: list[EdgeId]) -> bool:
        if not route:
            return False
        try:
            last_edge = self._graph.get_edge(route[-1])
            return last_edge.target == self._destination
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Route construction (Eq 6-12)
    # ------------------------------------------------------------------

    def _construct_route(
        self,
        current_route: list[EdgeId],
        p_best_route: list[EdgeId],
        g_best_route: list[EdgeId],
        w: float,
        c1: float,
        c2: float,
        c3: float,
        stream: random.Random,
    ) -> list[EdgeId]:
        current: NodeId = self._source
        current_edge: Edge | None = None
        prev: NodeId | None = None
        route: list[EdgeId] = []
        eps = self._config.epsilon
        max_steps = self._config.forward_steps

        for step in range(max_steps):
            if current == self._destination:
                break

            # Use lane-level successors if we have a previous edge,
            # or a source edge was provided (rerouting), otherwise fall
            # back to node-level outgoing edges (first step).
            if current_edge is not None:
                outgoing = self._graph.get_successors(current_edge.edge_id)
            elif current_edge is None and self._source_edge_id is not None:
                outgoing = self._graph.get_successors(self._source_edge_id)
            else:
                outgoing = self._graph.outgoing_edges(current)
            candidates: list[Edge] = []
            for e in outgoing:
                ec = self._edge_total_cost(e)
                if ec < float("inf"):
                    candidates.append(e)
            # Avoid immediate back-track only if forward options remain
            if len(candidates) > 1 and prev is not None:
                candidates = [e for e in candidates if e.target != prev]

            if not candidates:
                break
            # Prefer non-dead-end targets
            if len(candidates) > 1:
                alive = [e for e in candidates
                         if e.target == self._destination
                         or len(list(self._graph.outgoing_edges(e.target))) > 0]
                if alive:
                    candidates = alive

            weights: list[float] = []
            for e in candidates:
                I = 1.0 if step < len(current_route) and e.edge_id == current_route[step] else eps
                P = 1.0 if step < len(p_best_route) and e.edge_id == p_best_route[step] else eps
                G = 1.0 if step < len(g_best_route) and e.edge_id == g_best_route[step] else eps
                eta = self._visibility.values.get(e.edge_id, 0.0)
                w_total = w * I + c1 * P + c2 * G + c3 * eta
                weights.append(max(w_total, 0.0))

            total_w = sum(weights)
            if total_w <= 0.0:
                chosen = stream.choice(candidates)
            else:
                r = stream.random() * total_w
                cum = 0.0
                chosen = candidates[-1]
                for i, e in enumerate(candidates):
                    cum += weights[i]
                    if r <= cum:
                        chosen = e
                        break

            route.append(chosen.edge_id)
            prev = current
            current = chosen.target
            current_edge = chosen

        return route

    # ------------------------------------------------------------------
    # Backward pass
    # ------------------------------------------------------------------

    def _backward_pass(
        self,
        routes: list[list[EdgeId]],
        costs: list[float],
        states: list[ParticleStatus],
    ) -> BackwardPassResult:
        B = len(self._particles)

        # Personal best update (Eq 14)
        for i in range(B):
            if states[i] == ParticleStatus.COMPLETE and costs[i] < self._particles[i].p_best_cost:
                self._particles[i].p_best_route = list(routes[i])
                self._particles[i].p_best_cost = costs[i]

        # Global best update (Eq 15)
        best_idx = min(
            range(B),
            key=lambda i: self._particles[i].p_best_cost,
        )
        best_cost = self._particles[best_idx].p_best_cost
        best_route = self._particles[best_idx].p_best_route

        diversity = self._compute_diversity()

        return BackwardPassResult(
            best_cost=best_cost,
            best_route=list(best_route),
            diversity=diversity,
        )

    # ------------------------------------------------------------------
    # Diversity (Eq 16)
    # ------------------------------------------------------------------

    def _compute_diversity(self) -> float:
        templates = [p.p_best_route for p in self._particles if p.p_best_route]
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
        for p in self._particles:
            if p.state == ParticleStatus.COMPLETE and p.route:
                key = tuple(p.route)
                if key not in seen_routes:
                    seen_routes.add(key)
                    rc = self._route_to_candidate(p.route, runtime_s=total_time)
                    all_candidates.append(rc)

        scores = [p.cost for p in self._particles if p.state == ParticleStatus.COMPLETE]
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
            solutions_evaluated=len(self._iteration_stats) * len(self._particles),
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
            failure_reason=None if success else "No feasible route found by any particle",
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
                components={"pso_cost": 1e9},
            )
            return RouteCandidate(
                route_id=RouteId(f"pso_{uuid.uuid4().hex[:8]}"),
                node_sequence=(self._source, self._destination),
                edge_sequence=(EdgeId(""),),
                total_cost=1e9,
                cost_breakdown=inf_cost,
                algorithm="pso",
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
            route_id=RouteId(f"pso_{uuid.uuid4().hex[:8]}"),
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
                components={"pso_cost": total_cost_val},
            ),
            algorithm="pso",
            metadata={
                "inertia_start": self._config.inertia_start,
                "inertia_end": self._config.inertia_end,
                "cognition_weight": self._config.cognition_weight,
                "social_weight": self._config.social_weight,
                "visibility_weight": self._config.visibility_weight,
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
            best_solution=None,
            success=False,
            failure_reason=reason,
            statistics=SwarmStatistics(
                total_iterations=0, total_runtime_s=0.0,
                best_score=0.0, average_score=0.0, worst_score=0.0,
                convergence_iteration=None, candidate_count=0, solutions_evaluated=0,
            ),
        )


# =========================================================================
# BackwardPassResult
# =========================================================================


@dataclass
class BackwardPassResult:
    """Aggregated result of the backward pass."""
    best_cost: float
    best_route: list[EdgeId]
    diversity: float


# Auto-register with SwarmFactory
from e3hybrid.swarm.factory import SwarmFactory

SwarmFactory.register("pso", PSORouting)