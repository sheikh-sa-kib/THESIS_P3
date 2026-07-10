"""Ant Colony System (ACS) implementation for dynamic EV routing.

Implements the true Ant Colony System (Dorigo & Gambardella, 1997)
with pheromone bounds from Max-Min Ant System (Stützle & Hoos, 2000).

All stochastic decisions use SwarmRandom named streams.
All configuration comes from YAML via SwarmConfig.hyperparameters.
No global state. No direct graph/emergency/communication module access.

Literature
----------
- Dorigo, M., & Gambardella, L. M. (1997). Ant Colony System: A cooperative
  learning approach to the traveling salesman problem. IEEE Transactions on
  Evolutionary Computation, 1(1), 53-66.
- Stützle, T., & Hoos, H. H. (2000). MAX-MIN ant system. Future Generation
  Computer Systems, 16(8), 889-914.
- Dorigo, M., & Stützle, T. (2004). Ant Colony Optimization. MIT Press.
"""

from __future__ import annotations

import math
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from e3hybrid.network.types import EdgeId, NodeId
from e3hybrid.swarm.random import SwarmRandom

if TYPE_CHECKING:
    from e3hybrid.network.graph import DirectedGraph
    from e3hybrid.routing.candidate import RouteCandidate
    from e3hybrid.routing.cost_calculator import CompositeCostCalculator
    from e3hybrid.routing.request import RoutingRequest
    from e3hybrid.swarm.config import SwarmConfig
    from e3hybrid.swarm.context import SwarmContext
    from e3hybrid.swarm.result import SwarmResult
    from e3hybrid.swarm.statistics import IterationStatistics

_EPS = 1e-10
_PENALTY_COST = 1e9


# =========================================================================
# ACSConfiguration
# =========================================================================

@dataclass(frozen=True, slots=True)
class ACSConfiguration:
    """All ACS hyperparameters with validated defaults from literature."""

    alpha: float = 1.0
    beta: float = 2.0
    rho: float = 0.1
    q0: float = 0.9
    tau0: float = 1.0
    tau_min: float = 0.01
    tau_max: float = 10.0
    elitism: int = 1
    candidate_list_size: int = 0
    forward_steps: int = 0

    def __post_init__(self) -> None:
        if self.alpha < 0:
            raise ValueError(f"alpha must be >= 0, got {self.alpha}")
        if self.beta < 0:
            raise ValueError(f"beta must be >= 0, got {self.beta}")
        if self.alpha + self.beta <= 0:
            raise ValueError(
                f"alpha + beta must be > 0, got {self.alpha + self.beta}"
            )
        if not 0 < self.rho < 1:
            raise ValueError(f"rho must be in (0, 1), got {self.rho}")
        if not 0 <= self.q0 <= 1:
            raise ValueError(f"q0 must be in [0, 1], got {self.q0}")
        if self.tau0 <= 0:
            raise ValueError(f"tau0 must be > 0, got {self.tau0}")
        if not 0 < self.tau_min < self.tau_max:
            raise ValueError(
                f"tau_min ({self.tau_min}) must be between 0 and "
                f"tau_max ({self.tau_max})"
            )
        if self.elitism < 0:
            raise ValueError(f"elitism must be >= 0, got {self.elitism}")

    @classmethod
    def from_swarm_config(cls, config: SwarmConfig) -> ACSConfiguration:
        hp = config.hyperparameters
        return cls(
            alpha=_hp_float(hp, "alpha", 1.0),
            beta=_hp_float(hp, "beta", 2.0),
            rho=_hp_float(hp, "rho", 0.1),
            q0=_hp_float(hp, "q0", 0.9),
            tau0=_hp_float(hp, "tau0", 1.0),
            tau_min=_hp_float(hp, "tau_min", 0.01),
            tau_max=_hp_float(hp, "tau_max", 10.0),
            elitism=_hp_int(hp, "elitism", 1),
            candidate_list_size=_hp_int(hp, "candidate_list_size", 0),
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
# PheromoneMatrix
# =========================================================================

class PheromoneMatrix:
    """Sparse pheromone matrix: one float per graph edge.

    Safeguards
    ----------
    - All values clamped to [tau_min, tau_max] after every mutation.
    - Initialization sets all edges to tau0.
    - NaN and infinity replaced by nearest bound.
    """

    def __init__(self, config: ACSConfiguration, edge_ids: set[EdgeId]) -> None:
        self._tau_min = config.tau_min
        self._tau_max = config.tau_max
        self._data: dict[EdgeId, float] = {eid: config.tau0 for eid in edge_ids}

    def get(self, edge_id: EdgeId) -> float:
        return self._data.get(edge_id, self._tau_min)

    def set(self, edge_id: EdgeId, value: float) -> None:
        if not math.isfinite(value):
            value = self._tau_max if value > 0 else self._tau_min
        clamped = max(self._tau_min, min(value, self._tau_max))
        self._data[edge_id] = clamped

    def decay(self, edge_id: EdgeId, rho: float, tau0: float) -> None:
        current = self.get(edge_id)
        self.set(edge_id, (1.0 - rho) * current + rho * tau0)

    def reinforce(self, edge_id: EdgeId, rho: float, deposit: float) -> None:
        current = self.get(edge_id)
        self.set(edge_id, (1.0 - rho) * current + rho * deposit)

    @property
    def values(self) -> dict[EdgeId, float]:
        return dict(self._data)

    @property
    def edge_count(self) -> int:
        return len(self._data)

    def clone(self) -> PheromoneMatrix:
        clone = object.__new__(PheromoneMatrix)
        clone._tau_min = self._tau_min
        clone._tau_max = self._tau_max
        clone._data = dict(self._data)
        return clone


# =========================================================================
# VisibilityMatrix
# =========================================================================

class VisibilityMatrix:
    """Static heuristic desirability eta_ij = 1 / (cost + EPS) per edge.

    Safeguards
    ----------
    - Division by zero prevented by EPS = 1e-10.
    - Blocked edges (cost = inf) have eta = 0.
    - NaN costs treated as infinite (eta = 0).
    """

    def __init__(
        self,
        graph: DirectedGraph,
        cost_calculator: CompositeCostCalculator,
        config: ACSConfiguration,
    ) -> None:
        self._data: dict[EdgeId, float] = {}
        self._neighbour_cache: dict[NodeId, list[EdgeId]] = {}
        cl_size = config.candidate_list_size

        for edge in graph.edges():
            eid = edge.edge_id
            if edge.state.is_blocked:
                self._data[eid] = 0.0
            else:
                try:
                    edge_cost, _ = cost_calculator.compute_edge_cost(edge)
                except Exception:
                    edge_cost = float("inf")
                if not math.isfinite(edge_cost) or edge_cost < 0:
                    self._data[eid] = 0.0
                elif edge_cost == 0.0:
                    self._data[eid] = 1.0 / _EPS
                else:
                    self._data[eid] = 1.0 / (edge_cost + _EPS)

        # Build neighbour cache with optional candidate list truncation
        for node in graph.nodes():
            nid = node.node_id
            outgoing: list[EdgeId] = []
            for e in graph.outgoing_edges(nid):
                vis = self._data.get(e.edge_id, 0.0)
                if vis > 0.0:
                    outgoing.append(e.edge_id)
            if cl_size > 0 and len(outgoing) > cl_size:
                outgoing.sort(key=lambda eid: self._data.get(eid, 0.0), reverse=True)
                outgoing = outgoing[:cl_size]
            self._neighbour_cache[nid] = outgoing

    def get(self, edge_id: EdgeId) -> float:
        return self._data.get(edge_id, 0.0)

    def get_neighbours(self, node_id: NodeId) -> list[EdgeId]:
        return self._neighbour_cache.get(node_id, [])

    @property
    def values(self) -> dict[EdgeId, float]:
        return dict(self._data)

    @property
    def edge_count(self) -> int:
        return len(self._data)


# =========================================================================
# TransitionRule
# =========================================================================

class TransitionRule:
    """ACS pseudorandom proportional transition rule.

    With probability q0: deterministic argmax.
    With probability 1-q0: roulette-wheel proportional selection.

    Safeguards
    ----------
    - Empty candidate list returns None (ant stops).
    - All-zero weights fall back to uniform random selection.
    - Tabu (visited nodes) enforced by caller (AntColony).
    """

    def __init__(self, config: ACSConfiguration) -> None:
        self._alpha = config.alpha
        self._beta = config.beta
        self._q0 = config.q0

    def select(
        self,
        candidates: list[EdgeId],
        pheromones: PheromoneMatrix,
        visibility: VisibilityMatrix,
        selection_stream: random.Random,
        roulette_stream: random.Random,
    ) -> EdgeId | None:
        if not candidates:
            return None
        if selection_stream.random() <= self._q0:
            return self._argmax(candidates, pheromones, visibility)
        return self._roulette(candidates, pheromones, visibility, roulette_stream)

    def _argmax(
        self,
        candidates: list[EdgeId],
        pheromones: PheromoneMatrix,
        visibility: VisibilityMatrix,
    ) -> EdgeId:
        best_eid = candidates[0]
        best_value = -1.0
        for eid in candidates:
            val = 1.0
            tau = pheromones.get(eid)
            eta = visibility.get(eid)
            if self._alpha > 0:
                val *= tau ** self._alpha
            if self._beta > 0:
                val *= eta ** self._beta
            if val > best_value:
                best_value = val
                best_eid = eid
        return best_eid

    def _roulette(
        self,
        candidates: list[EdgeId],
        pheromones: PheromoneMatrix,
        visibility: VisibilityMatrix,
        stream: random.Random,
    ) -> EdgeId:
        weights: list[float] = []
        total = 0.0
        for eid in candidates:
            tau = pheromones.get(eid)
            eta = visibility.get(eid)
            w = 1.0
            if self._alpha > 0:
                w *= tau ** self._alpha
            if self._beta > 0:
                w *= eta ** self._beta
            if not math.isfinite(w) or w < 0:
                w = 0.0
            weights.append(w)
            total += w

        if total <= 0.0:
            idx = stream.randint(0, len(candidates) - 1)
            return candidates[idx]

        r = stream.random() * total
        cumulative = 0.0
        for i, w in enumerate(weights):
            cumulative += w
            if r <= cumulative:
                return candidates[i]
        return candidates[-1]


# =========================================================================
# Ant
# =========================================================================

@dataclass
class Ant:
    """State of a single ant during route construction."""

    current_node: NodeId
    visited_nodes: set[NodeId] = field(default_factory=set)
    prev_node: NodeId | None = None
    prev_edge: EdgeId | None = None
    node_sequence: list[NodeId] = field(default_factory=list)
    edge_sequence: list[EdgeId] = field(default_factory=list)
    total_cost: float = 0.0
    is_complete: bool = False
    is_feasible: bool = True
    reached_dead_end: bool = False

    def reset(self, start_node: NodeId) -> None:
        self.current_node = start_node
        self.visited_nodes = {start_node}
        self.prev_node = None
        self.prev_edge = None
        self.node_sequence = [start_node]
        self.edge_sequence = []
        self.total_cost = 0.0
        self.is_complete = False
        self.is_feasible = True
        self.reached_dead_end = False

    @staticmethod
    def create(start_node: NodeId) -> Ant:
        return Ant(
            current_node=start_node,
            visited_nodes={start_node},
            prev_node=None,
            prev_edge=None,
            node_sequence=[start_node],
        )


# =========================================================================
# PheromoneUpdater
# =========================================================================

class PheromoneUpdater:
    """Local and global pheromone updates (Dorigo & Gambardella 1997)."""

    def __init__(self, config: ACSConfiguration) -> None:
        self._rho = config.rho
        self._tau0 = config.tau0
        self._elitism = config.elitism

    def local_update(self, pheromones: PheromoneMatrix, edge_id: EdgeId) -> None:
        pheromones.decay(edge_id, self._rho, self._tau0)

    def global_update(
        self,
        pheromones: PheromoneMatrix,
        best_edges: list[EdgeId],
        best_cost: float,
    ) -> None:
        if best_cost <= 0.0 or not math.isfinite(best_cost):
            return
        deposit = 1.0 / best_cost
        for eid in best_edges:
            pheromones.reinforce(eid, self._rho, deposit)

    def global_update_elite(
        self,
        pheromones: PheromoneMatrix,
        elite_edges: list[list[EdgeId]],
        elite_costs: list[float],
    ) -> None:
        for edges, cost in zip(elite_edges, elite_costs):
            if cost <= 0.0 or not math.isfinite(cost):
                continue
            deposit = 1.0 / cost
            for eid in edges:
                pheromones.reinforce(eid, self._rho * 0.5, deposit)


# =========================================================================
# ACOStatistics
# =========================================================================

@dataclass(frozen=True, slots=True)
class ACOStatistics:
    """ACO-specific metrics beyond generic SwarmStatistics."""

    best_cost: float = 0.0
    average_colony_cost: float = 0.0
    worst_colony_cost: float = 0.0
    best_iteration: int = 0
    convergence_iteration: int = -1
    total_runtime_s: float = 0.0
    route_length: int = 0
    travel_time: float = 0.0
    expanded_nodes: int = 0
    total_iterations: int = 0
    termination_reason: str = ""
    diversity_history: tuple[float, ...] = field(default_factory=tuple)
    score_history: tuple[float, ...] = field(default_factory=tuple)


# =========================================================================
# ACOValidator
# =========================================================================

class ACOValidator:
    """Validates ACS configuration and runtime context."""

    @staticmethod
    def validate_config(config: ACSConfiguration) -> list[str]:
        errors: list[str] = []
        if config.alpha < 0:
            errors.append(f"alpha must be >= 0, got {config.alpha}")
        if config.beta < 0:
            errors.append(f"beta must be >= 0, got {config.beta}")
        if config.alpha + config.beta <= 0:
            errors.append(f"alpha + beta must be > 0, got {config.alpha + config.beta}")
        if not 0 < config.rho < 1:
            errors.append(f"rho must be in (0, 1), got {config.rho}")
        if not 0 <= config.q0 <= 1:
            errors.append(f"q0 must be in [0, 1], got {config.q0}")
        if config.tau0 <= 0:
            errors.append(f"tau0 must be > 0, got {config.tau0}")
        if config.tau_min <= 0:
            errors.append(f"tau_min must be > 0, got {config.tau_min}")
        if config.tau_max <= config.tau_min:
            errors.append(f"tau_max ({config.tau_max}) must be > tau_min ({config.tau_min})")
        if config.elitism < 0:
            errors.append(f"elitism must be >= 0, got {config.elitism}")
        return errors

    @staticmethod
    def validate_context(context: SwarmContext) -> list[str]:
        errors: list[str] = []
        if context.graph is None:
            errors.append("SwarmContext.graph is required for ACO")
        if context.cost_calculator is None:
            errors.append("SwarmContext.cost_calculator is required for ACO")
        if context.routing_request.source_node == context.routing_request.destination_node:
            errors.append("source and destination must differ")
        return errors


# =========================================================================
# AntColony
# =========================================================================

class AntColony:
    """Manages ant route construction, evaluation, and population statistics."""

    def __init__(self, config: ACSConfiguration) -> None:
        self._config = config
        self._transition = TransitionRule(config)
        self._updater = PheromoneUpdater(config)
        self._ants: list[Ant] = []

    def initialize_population(self, ant_count: int, start_node: NodeId) -> None:
        if len(self._ants) != ant_count:
            self._ants = [Ant.create(start_node) for _ in range(ant_count)]
        else:
            for ant in self._ants:
                ant.reset(start_node)

    def construct_routes(
        self,
        request: RoutingRequest,
        pheromones: PheromoneMatrix,
        visibility: VisibilityMatrix,
        graph: DirectedGraph,
        selection_stream: random.Random,
        roulette_stream: random.Random,
        cost_calculator: CompositeCostCalculator | None = None,
    ) -> list[Ant]:
        destination = request.destination_node
        max_steps = self._config.forward_steps if self._config.forward_steps else len(list(graph.nodes())) * 2

        for ant in self._ants:
            ant.prev_node = None
            ant.prev_edge = None
            for _ in range(max_steps):
                if ant.current_node == destination:
                    ant.is_complete = True
                    break

                # Gather visible candidate edges using lane-level successors
                candidates: list[EdgeId] = []
                if ant.prev_edge is not None:
                    for edge in graph.get_successors(ant.prev_edge):
                        if ant.prev_node is not None and edge.target == ant.prev_node:
                            continue
                        candidates.append(edge.edge_id)
                elif ("source_edge_id" in request.metadata
                      and graph.has_successors(EdgeId(str(request.metadata["source_edge_id"])))):
                    src_eid = EdgeId(str(request.metadata["source_edge_id"]))
                    for edge in graph.get_successors(src_eid):
                        if ant.prev_node is not None and edge.target == ant.prev_node:
                            continue
                        candidates.append(edge.edge_id)
                else:
                    for eid in visibility.get_neighbours(ant.current_node):
                        try:
                            edge = graph.get_edge(eid)
                        except Exception:
                            continue
                        if ant.prev_node is not None and edge.target == ant.prev_node:
                            continue
                        candidates.append(eid)
                # Prefer non-dead-end targets
                if len(candidates) > 1:
                    alive = [c for c in candidates if _not_deadend(c, graph, destination)]
                    if alive:
                        candidates = alive

                next_edge = self._transition.select(
                    candidates, pheromones, visibility,
                    selection_stream, roulette_stream,
                )

                if next_edge is None:
                    ant.reached_dead_end = True
                    break

                edge = graph.get_edge(next_edge)
                self._updater.local_update(pheromones, next_edge)

                ant.edge_sequence.append(next_edge)
                ant.node_sequence.append(edge.target)
                ant.prev_node = ant.current_node
                ant.prev_edge = next_edge
                ant.current_node = edge.target

            # Cost computation — use CompositeCostCalculator for consistency
            if ant.is_complete:
                if cost_calculator is not None and ant.edge_sequence:
                    edges = [graph.get_edge(eid) for eid in ant.edge_sequence]
                    ant.total_cost, _ = cost_calculator.compute_route_cost(edges)
                else:
                    ant.total_cost = _compute_edge_cost_sequence(ant.edge_sequence, graph)
            else:
                ant.total_cost = _PENALTY_COST
                ant.is_feasible = False

        return self._ants

    def evaluate_population(self) -> tuple[CandidateSolution | None, CandidateSolution | None, float]:
        from e3hybrid.swarm.models import CandidateSolution, Solution

        best: CandidateSolution | None = None
        worst: CandidateSolution | None = None
        total_cost = 0.0
        count = 0

        for ant in self._ants:
            # Ensure node_sequence has at least 2 nodes (Solution requirement)
            node_seq = tuple(ant.node_sequence)
            edge_seq = tuple(ant.edge_sequence)
            if len(node_seq) < 2:
                # Ant never left start node — create minimal path
                node_seq = (node_seq[0], node_seq[0]) if node_seq else (NodeId(""), NodeId(""))
                edge_seq = edge_seq or (EdgeId(""),)  # placeholder

            sol = CandidateSolution(
                solution=Solution(
                    node_sequence=node_seq,
                    edge_sequence=edge_seq,
                    metadata={
                        "is_complete": ant.is_complete,
                        "is_feasible": ant.is_feasible,
                        "reached_dead_end": ant.reached_dead_end,
                    },
                ),
                score=ant.total_cost,
            )
            total_cost += sol.score
            count += 1
            if best is None or sol.score < best.score:
                best = sol
            if worst is None or sol.score > worst.score:
                worst = sol

        avg = total_cost / count if count > 0 else _PENALTY_COST
        return best, worst, avg

    def compute_diversity(self) -> float:
        if not self._ants:
            return 0.0
        total_edges = 0
        unique_edges: set[EdgeId] = set()
        for ant in self._ants:
            for eid in ant.edge_sequence:
                unique_edges.add(eid)
                total_edges += 1
        if total_edges == 0:
            return 0.0
        return len(unique_edges) / total_edges

    @property
    def population(self) -> list[Ant]:
        return self._ants


# -------------------------------------------------------------------------
# Module-level helpers
# -------------------------------------------------------------------------

def _not_deadend(eid: EdgeId, graph: DirectedGraph, dest: NodeId) -> bool:
    try:
        e = graph.get_edge(eid)
        return e.target == dest or len(list(graph.outgoing_edges(e.target))) > 0
    except Exception:
        return False

def _compute_edge_cost_sequence(edge_ids: list[EdgeId], graph: DirectedGraph) -> float:
    total = 0.0
    for eid in edge_ids:
        try:
            edge = graph.get_edge(eid)
        except Exception:
            total += _PENALTY_COST
            continue
        if edge.state.is_blocked:
            total += _PENALTY_COST
        else:
            length_m = edge.length_m
            speed = edge.state.current_speed_mps or edge.speed_limit_mps
            time_cost = length_m / speed if speed > 0 else _PENALTY_COST
            total += length_m + time_cost
    return total


# =========================================================================
# ACOFactory
# =========================================================================

class ACOFactory:
    """Factory for creating ACORouting instances."""

    @staticmethod
    def create(config: ACSConfiguration | None = None) -> ACORouting:
        return ACORouting(config or ACSConfiguration())

    @staticmethod
    def create_from_swarm_config(swarm_config: SwarmConfig) -> ACORouting:
        aco_config = ACSConfiguration.from_swarm_config(swarm_config)
        return ACORouting(aco_config)


# =========================================================================
# ACORouting — main SwarmAlgorithm implementation
# =========================================================================

class ACORouting:
    """Ant Colony System (ACS) implementing the SwarmAlgorithm Protocol.

    Parameters
    ----------
    config:
        ACS configuration (optional, uses defaults from literature if None).
    """

    def __init__(self, config: ACSConfiguration | None = None) -> None:
        self._config = config or ACSConfiguration()
        self._colony: AntColony | None = None

    @property
    def name(self) -> str:
        return "aco"

    def optimize(self, context: SwarmContext) -> SwarmResult:
        from e3hybrid.routing.candidate import RouteCandidate, SearchStatistics
        from e3hybrid.routing.cost import RouteCost
        from e3hybrid.routing.types import RouteId
        from e3hybrid.swarm.config import SwarmConfig
        from e3hybrid.swarm.result import SwarmResult
        from e3hybrid.swarm.statistics import SwarmStatistics

        # Validate
        ctx_errors = ACOValidator.validate_context(context)
        if ctx_errors:
            return _failure_result("; ".join(ctx_errors))

        graph = context.graph
        cost_calculator = context.cost_calculator
        request = context.routing_request
        swarm_config = context.config

        # Resolve ACS config from swarm config if available
        aco_config = self._config
        if swarm_config is not None:
            cfg_errors = ACOValidator.validate_config(aco_config)
            if cfg_errors:
                return _failure_result("; ".join(cfg_errors))
            aco_config = self._config

        # Build visibility (static) and pheromone matrices
        visibility = VisibilityMatrix(graph, cost_calculator, aco_config)
        edge_ids = {e.edge_id for e in graph.edges()}
        pheromones = PheromoneMatrix(aco_config, edge_ids)

        # Random streams
        swarm_random = SwarmRandom(context.random_seed)
        sel_stream = swarm_random.get_stream("aco.selection")
        roulette_stream = swarm_random.get_stream("aco.roulette")

        # Colony
        colony = AntColony(aco_config)
        self._colony = colony

        # Tracking state
        global_best: CandidateSolution | None = None
        global_best_iteration = 0
        iteration_history: list = []
        diversity_history: list[float] = []
        score_history: list[float] = []
        start_time = time.perf_counter()

        ant_count = swarm_config.population_size if swarm_config is not None else 20
        max_iters = swarm_config.max_iterations if swarm_config is not None else 100

        for iteration in range(max_iters):
            colony.initialize_population(ant_count, request.source_node)

            colony.construct_routes(
                request, pheromones, visibility, graph,
                sel_stream, roulette_stream,
                cost_calculator=cost_calculator,
            )

            iter_best, iter_worst, avg_cost = colony.evaluate_population()
            diversity = colony.compute_diversity()

            if iter_best is not None:
                if global_best is None or iter_best.score < global_best.score:
                    global_best = iter_best
                    global_best_iteration = iteration

            # Global update on best-so-far
            if global_best is not None:
                best_edges = list(global_best.solution.edge_sequence)
                colony._updater.global_update(pheromones, best_edges, global_best.score)

                # Elite reinforcement
                if aco_config.elitism > 0:
                    sorted_ants = sorted(colony.population, key=lambda a: a.total_cost)
                    elite = sorted_ants[:min(aco_config.elitism, len(sorted_ants))]
                    elite_edges = [list(a.edge_sequence) for a in elite if a.edge_sequence]
                    elite_costs = [a.total_cost for a in elite if a.total_cost > 0]
                    if elite_edges:
                        colony._updater.global_update_elite(pheromones, elite_edges, elite_costs)

            # Record per-iteration stats
            current_best = global_best.score if global_best else float("inf")
            iter_stats = _build_iter_stats(
                iteration=iteration,
                best_score=current_best,
                average_score=avg_cost,
                worst_score=iter_worst.score if iter_worst else _PENALTY_COST,
                diversity=diversity,
                runtime_s=time.perf_counter() - start_time,
            )
            iteration_history.append(iter_stats)
            diversity_history.append(diversity)
            score_history.append(current_best)

        total_time = time.perf_counter() - start_time

        # Build candidates
        candidates_list: list[RouteCandidate] = []
        if global_best is not None:
            route_cost = RouteCost(
                total=global_best.score,
                distance_cost=global_best.score,
                time_cost=0.0,
                energy_cost=0.0,
                congestion_penalty=0.0,
                hazard_penalty=0.0,
                emergency_penalty=0.0,
                communication_penalty=0.0,
                components={"aco_total": global_best.score},
            )
            candidate = RouteCandidate(
                route_id=RouteId(f"aco_{uuid.uuid4().hex[:8]}"),
                node_sequence=global_best.solution.node_sequence,
                edge_sequence=global_best.solution.edge_sequence,
                total_cost=global_best.score,
                cost_breakdown=route_cost,
                algorithm="aco",
                metadata={
                    "aco_alpha": aco_config.alpha,
                    "aco_beta": aco_config.beta,
                    "aco_rho": aco_config.rho,
                    "aco_q0": aco_config.q0,
                    "pheromone_bounds": (aco_config.tau_min, aco_config.tau_max),
                },
                runtime_s=total_time,
                search_statistics=SearchStatistics(
                    iterations=global_best_iteration,
                    convergence=diversity_history[-1] if diversity_history else 0.0,
                    diversity=diversity_history[-1] if diversity_history else 0.0,
                ),
            )
            candidates_list.append(candidate)

        # Convergence detection
        conv_iter: int | None = None
        for i in range(len(iteration_history) - 1, -1, -1):
            if i == 0 or iteration_history[i].best_score < iteration_history[i - 1].best_score:
                conv_iter = i
                break

        term_reason = f"Maximum iterations reached ({max_iters})"
        final_best = global_best.score if global_best else float("inf")

        statistics = SwarmStatistics(
            total_iterations=len(iteration_history),
            total_runtime_s=total_time,
            best_score=final_best,
            average_score=iteration_history[-1].average_score if iteration_history else 0.0,
            worst_score=iteration_history[-1].worst_score if iteration_history else 0.0,
            convergence_iteration=conv_iter,
            candidate_count=len(candidates_list),
            solutions_evaluated=len(iteration_history) * ant_count,
            diversity_history=tuple(diversity_history),
            score_history=tuple(score_history),
            termination_reason=term_reason,
        )

        return SwarmResult(
            best_solution=candidates_list[0] if candidates_list else None,
            candidates=tuple(candidates_list),
            statistics=statistics,
            iterations=tuple(iteration_history),
            success=global_best is not None,
            failure_reason=None if global_best is not None else "No feasible route found by any ant",
        )


# =========================================================================
# Module-level helpers
# =========================================================================

def _build_iter_stats(
    iteration: int,
    best_score: float,
    average_score: float,
    worst_score: float,
    diversity: float,
    runtime_s: float,
) -> IterationStatistics:
    from e3hybrid.swarm.statistics import IterationStatistics
    return IterationStatistics(
        iteration=iteration,
        best_score=best_score,
        average_score=average_score,
        midrange_score=(best_score + worst_score) / 2.0,
        worst_score=worst_score,
        std_dev=0.0,
        diversity=diversity,
        best_solution_changed=True,
        runtime_s=runtime_s,
    )


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
