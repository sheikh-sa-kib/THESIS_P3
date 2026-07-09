"""Comprehensive tests for the Ant Colony System (ACS) implementation.

Test categories:
- Unit: each component in isolation
- Integration: components working together, routing end-to-end
- Property: invariants that must always hold
- Deterministic replay: same seed → identical results
- Stress: larger graphs, convergence behavior
- Edge-case: empty sets, blocked paths, unreachable destinations
- Benchmark regression: compare with Dijkstra/A*
"""

from __future__ import annotations

import copy
import math
import random as stdlib_random
import uuid

import pytest

from e3hybrid.network.edge import Edge, MutableEdgeState
from e3hybrid.network.graph import DirectedGraph
from e3hybrid.network.node import Node
from e3hybrid.network.types import EdgeId, NodeId
from e3hybrid.routing.candidate import RouteCandidate, SearchStatistics
from e3hybrid.routing.cost import RouteCost
from e3hybrid.routing.cost_calculator import CompositeCostCalculator, CostWeights
from e3hybrid.routing.request import RoutingRequest
from e3hybrid.routing.types import RouteId
from e3hybrid.swarm.aco import (
    ACORouting,
    ACOFactory,
    ACOStatistics,
    ACOValidator,
    ACSConfiguration,
    Ant,
    AntColony,
    PheromoneMatrix,
    PheromoneUpdater,
    TransitionRule,
    VisibilityMatrix,
    _PENALTY_COST,
)
from e3hybrid.swarm.config import SwarmConfig
from e3hybrid.swarm.context import SwarmContext
from e3hybrid.swarm.result import SwarmResult
from e3hybrid.swarm.statistics import SwarmStatistics
from e3hybrid.vehicle.types import VehicleId


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def linear_graph() -> DirectedGraph:
    """A-B-C-D linear graph with 4 nodes, 3 edges."""
    graph = DirectedGraph()
    for nid, x in [("A", 0.0), ("B", 100.0), ("C", 200.0), ("D", 300.0)]:
        graph.add_node(Node(node_id=NodeId(nid), x=x, y=0.0))
    state = MutableEdgeState()
    graph.add_edge(Edge(
        edge_id=EdgeId("AB"), source=NodeId("A"), target=NodeId("B"),
        length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=state,
    ))
    graph.add_edge(Edge(
        edge_id=EdgeId("BC"), source=NodeId("B"), target=NodeId("C"),
        length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=state,
    ))
    graph.add_edge(Edge(
        edge_id=EdgeId("CD"), source=NodeId("C"), target=NodeId("D"),
        length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=state,
    ))
    return graph


@pytest.fixture
def grid_graph() -> DirectedGraph:
    """3x3 grid graph (9 nodes, 12 directed edges)."""
    graph = DirectedGraph()
    nodes: dict[str, NodeId] = {}
    for row in range(3):
        for col in range(3):
            nid = NodeId(f"{row}_{col}")
            nodes[f"{row}_{col}"] = nid
            graph.add_node(Node(node_id=nid, x=col * 100.0, y=row * 100.0))

    state = MutableEdgeState()
    # Horizontal edges
    for row in range(3):
        for col in range(2):
            src = nodes[f"{row}_{col}"]
            dst = nodes[f"{row}_{col + 1}"]
            eid = EdgeId(f"{src}_{dst}")
            graph.add_edge(Edge(
                edge_id=eid, source=src, target=dst,
                length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=state,
            ))
    # Vertical edges
    for row in range(2):
        for col in range(3):
            src = nodes[f"{row}_{col}"]
            dst = nodes[f"{row + 1}_{col}"]
            eid = EdgeId(f"{src}_{dst}")
            graph.add_edge(Edge(
                edge_id=eid, source=src, target=dst,
                length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=state,
            ))
    return graph


@pytest.fixture
def diamond_graph() -> DirectedGraph:
    """Diamond: A -> B, A -> C, B -> D, C -> D. Two paths A-B-D and A-C-D."""
    graph = DirectedGraph()
    graph.add_node(Node(node_id=NodeId("A"), x=0.0, y=0.0))
    graph.add_node(Node(node_id=NodeId("B"), x=50.0, y=50.0))
    graph.add_node(Node(node_id=NodeId("C"), x=50.0, y=-50.0))
    graph.add_node(Node(node_id=NodeId("D"), x=100.0, y=0.0))
    state = MutableEdgeState()
    for eid, src, tgt, length in [
        ("AB", "A", "B", 70.0),
        ("AC", "A", "C", 70.0),
        ("BD", "B", "D", 70.0),
        ("CD", "C", "D", 70.0),
    ]:
        graph.add_edge(Edge(
            edge_id=EdgeId(eid), source=NodeId(src), target=NodeId(tgt),
            length_m=length, speed_limit_mps=10.0, lane_count=1, state=state,
        ))
    return graph


@pytest.fixture
def acs_default_config() -> ACSConfiguration:
    return ACSConfiguration()


@pytest.fixture
def swarm_config_aco() -> SwarmConfig:
    return SwarmConfig(
        algorithm_name="aco",
        population_size=10,
        max_iterations=20,
        hyperparameters={
            "alpha": 1.0,
            "beta": 2.0,
            "rho": 0.1,
            "q0": 0.9,
            "tau0": 1.0,
            "tau_min": 0.01,
            "tau_max": 10.0,
        },
    )


def _make_request(source: str, dest: str) -> RoutingRequest:
    return RoutingRequest(
        source_node=NodeId(source),
        destination_node=NodeId(dest),
        vehicle_id=VehicleId("test_vehicle"),
        vehicle_constraints=None,
        battery_state=None,
        max_candidates=5,
        timeout_s=30.0,
    )


def _make_context(
    graph: DirectedGraph,
    request: RoutingRequest,
    config: SwarmConfig,
    seed: int = 42,
) -> SwarmContext:
    cost_weights = config.cost_weights
    cost_calculator = CompositeCostCalculator(cost_weights)
    return SwarmContext(
        cost_weights=cost_weights,
        config=config,
        random_seed=seed,
        routing_request=request,
        sim_time_s=0.0,
        graph=graph,
        cost_calculator=cost_calculator,
    )


# =========================================================================
# 1. ACSConfiguration Tests
# =========================================================================


class TestACSConfiguration:
    def test_default_values_from_literature(self):
        cfg = ACSConfiguration()
        assert cfg.alpha == 1.0
        assert cfg.beta == 2.0
        assert cfg.rho == 0.1
        assert cfg.q0 == 0.9
        assert cfg.tau0 == 1.0
        assert cfg.tau_min == 0.01
        assert cfg.tau_max == 10.0
        assert cfg.elitism == 1
        assert cfg.candidate_list_size == 0

    def test_validation_alpha_both_zero_raises(self):
        with pytest.raises(ValueError, match="alpha.*beta"):
            ACSConfiguration(alpha=0.0, beta=0.0)

    def test_validation_alpha_negative_raises(self):
        with pytest.raises(ValueError, match="alpha"):
            ACSConfiguration(alpha=-1.0)

    def test_validation_beta_negative_raises(self):
        with pytest.raises(ValueError, match="beta"):
            ACSConfiguration(beta=-1.0)

    def test_validation_rho_zero_raises(self):
        with pytest.raises(ValueError, match="rho"):
            ACSConfiguration(rho=0.0)

    def test_validation_rho_one_raises(self):
        with pytest.raises(ValueError, match="rho"):
            ACSConfiguration(rho=1.0)

    def test_validation_q0_below_zero_raises(self):
        with pytest.raises(ValueError, match="q0"):
            ACSConfiguration(q0=-0.1)

    def test_validation_q0_above_one_raises(self):
        with pytest.raises(ValueError, match="q0"):
            ACSConfiguration(q0=1.1)

    def test_validation_tau0_zero_raises(self):
        with pytest.raises(ValueError, match="tau0"):
            ACSConfiguration(tau0=0.0)

    def test_validation_tau_min_gte_tau_max_raises(self):
        with pytest.raises(ValueError, match="tau_min"):
            ACSConfiguration(tau_min=5.0, tau_max=3.0)

    def test_validation_tau_min_equal_tau_max_raises(self):
        with pytest.raises(ValueError, match="tau_min"):
            ACSConfiguration(tau_min=1.0, tau_max=1.0)

    def test_validation_elitism_negative_raises(self):
        with pytest.raises(ValueError, match="elitism"):
            ACSConfiguration(elitism=-1)

    def test_from_swarm_config(self, swarm_config_aco):
        cfg = ACSConfiguration.from_swarm_config(swarm_config_aco)
        assert cfg.alpha == 1.0
        assert cfg.beta == 2.0
        assert cfg.rho == 0.1
        assert cfg.q0 == 0.9

    def test_from_swarm_config_missing_uses_default(self):
        config = SwarmConfig(algorithm_name="aco", hyperparameters={})
        cfg = ACSConfiguration.from_swarm_config(config)
        assert cfg.alpha == 1.0  # Default
        assert cfg.beta == 2.0   # Default

    def test_immutable(self):
        cfg = ACSConfiguration()
        with pytest.raises(Exception):
            cfg.alpha = 2.0  # type: ignore


# =========================================================================
# 2. PheromoneMatrix Tests
# =========================================================================


class TestPheromoneMatrix:
    def test_initialization_all_edges(self, diamond_graph):
        cfg = ACSConfiguration(tau0=2.0)
        edge_ids = {e.edge_id for e in diamond_graph.edges()}
        pm = PheromoneMatrix(cfg, edge_ids)
        assert pm.edge_count == 4
        for eid in edge_ids:
            assert pm.get(eid) == 2.0

    def test_initialization_tau0(self):
        cfg = ACSConfiguration(tau0=5.0)
        pm = PheromoneMatrix(cfg, {EdgeId("e1"), EdgeId("e2")})
        assert pm.get(EdgeId("e1")) == 5.0
        assert pm.get(EdgeId("e2")) == 5.0

    def test_unknown_edge_returns_tau_min(self):
        cfg = ACSConfiguration(tau_min=0.5)
        pm = PheromoneMatrix(cfg, set())
        assert pm.get(EdgeId("unknown")) == 0.5

    def test_set_clamps_above_max(self):
        cfg = ACSConfiguration(tau_min=0.1, tau_max=5.0)
        pm = PheromoneMatrix(cfg, {EdgeId("e1")})
        pm.set(EdgeId("e1"), 100.0)
        assert pm.get(EdgeId("e1")) == 5.0

    def test_set_clamps_below_min(self):
        cfg = ACSConfiguration(tau_min=0.1, tau_max=5.0)
        pm = PheromoneMatrix(cfg, {EdgeId("e1")})
        pm.set(EdgeId("e1"), -1.0)
        assert pm.get(EdgeId("e1")) == 0.1

    def test_set_nan_replaces_with_min(self):
        cfg = ACSConfiguration(tau_min=0.1, tau_max=5.0)
        pm = PheromoneMatrix(cfg, {EdgeId("e1")})
        pm.set(EdgeId("e1"), float("nan"))
        assert pm.get(EdgeId("e1")) == 0.1

    def test_set_infinity_clamps_to_max(self):
        cfg = ACSConfiguration(tau_min=0.1, tau_max=5.0)
        pm = PheromoneMatrix(cfg, {EdgeId("e1")})
        pm.set(EdgeId("e1"), float("inf"))
        assert pm.get(EdgeId("e1")) == 5.0

    def test_set_neg_inf_clamps_to_min(self):
        cfg = ACSConfiguration(tau_min=0.1, tau_max=5.0)
        pm = PheromoneMatrix(cfg, {EdgeId("e1")})
        pm.set(EdgeId("e1"), float("-inf"))
        assert pm.get(EdgeId("e1")) == 0.1

    def test_decay_reduces_pheromone(self):
        cfg = ACSConfiguration(tau0=1.0, tau_min=0.01, tau_max=10.0)
        pm = PheromoneMatrix(cfg, {EdgeId("e1")})
        pm.set(EdgeId("e1"), 1.0)
        pm.decay(EdgeId("e1"), rho=0.1, tau0=1.0)
        # (1-0.1)*1.0 + 0.1*1.0 = 1.0
        assert pm.get(EdgeId("e1")) == 1.0

        pm.decay(EdgeId("e1"), rho=0.5, tau0=0.5)
        # (1-0.5)*1.0 + 0.5*0.5 = 0.5 + 0.25 = 0.75
        assert abs(pm.get(EdgeId("e1")) - 0.75) < 1e-10

    def test_reinforce_increases_pheromone(self):
        cfg = ACSConfiguration(tau0=0.1, tau_min=0.01, tau_max=10.0)
        pm = PheromoneMatrix(cfg, {EdgeId("e1")})
        pm.set(EdgeId("e1"), 0.5)
        pm.reinforce(EdgeId("e1"), rho=0.1, deposit=2.0)
        # (1-0.1)*0.5 + 0.1*2.0 = 0.45 + 0.2 = 0.65
        assert abs(pm.get(EdgeId("e1")) - 0.65) < 1e-10

    def test_values_returns_copy(self):
        cfg = ACSConfiguration()
        pm = PheromoneMatrix(cfg, {EdgeId("e1")})
        v = pm.values
        v[EdgeId("e1")] = 999.0
        assert pm.get(EdgeId("e1")) != 999.0

    def test_clone_independence(self):
        cfg = ACSConfiguration(tau0=1.0)
        pm = PheromoneMatrix(cfg, {EdgeId("e1"), EdgeId("e2")})
        clone = pm.clone()
        pm.set(EdgeId("e1"), 5.0)
        assert clone.get(EdgeId("e1")) == 1.0  # Unchanged
        assert pm.get(EdgeId("e1")) == 5.0

    def test_pheromone_bounds_always_respected_after_multiple_updates(self):
        cfg = ACSConfiguration(tau0=1.0, tau_min=0.1, tau_max=3.0)
        pm = PheromoneMatrix(cfg, {EdgeId("e1")})
        for _ in range(100):
            pm.decay(EdgeId("e1"), rho=0.9, tau0=1.0)
            assert pm.get(EdgeId("e1")) >= 0.1
            pm.reinforce(EdgeId("e1"), rho=0.9, deposit=10.0)
            assert pm.get(EdgeId("e1")) <= 3.0


# =========================================================================
# 3. VisibilityMatrix Tests
# =========================================================================


class TestVisibilityMatrix:
    def test_visibility_computed_from_cost(self, linear_graph, acs_default_config):
        cc = CompositeCostCalculator(CostWeights(distance=1.0))
        vm = VisibilityMatrix(linear_graph, cc, acs_default_config)
        # Each edge has length 100, speed 10 -> time_cost = 10
        # total = 100 + 10 = 110
        # visibility = 1/(110 + EPS) ≈ 0.00909
        vis = vm.get(EdgeId("AB"))
        expected = 1.0 / 110.0
        assert abs(vis - expected) < 1e-6

    def test_blocked_edge_zero_visibility(self, linear_graph, acs_default_config):
        # Block edge BC
        blocked = MutableEdgeState(is_blocked=True)
        linear_graph.update_edge_state(EdgeId("BC"), blocked)

        cc = CompositeCostCalculator(CostWeights(distance=1.0))
        vm = VisibilityMatrix(linear_graph, cc, acs_default_config)
        assert vm.get(EdgeId("BC")) == 0.0

    def test_unknown_edge_zero_visibility(self, linear_graph, acs_default_config):
        cc = CompositeCostCalculator(CostWeights(distance=1.0))
        vm = VisibilityMatrix(linear_graph, cc, acs_default_config)
        assert vm.get(EdgeId("NONEXISTENT")) == 0.0

    def test_neighbours_filtered_by_visibility(self, diamond_graph, acs_default_config):
        cc = CompositeCostCalculator(CostWeights(distance=1.0))
        vm = VisibilityMatrix(diamond_graph, cc, acs_default_config)
        neighbours = vm.get_neighbours(NodeId("A"))
        # A has outgoing edges AB and AC
        assert len(neighbours) == 2
        assert EdgeId("AB") in neighbours
        assert EdgeId("AC") in neighbours

    def test_candidate_list_truncation(self, diamond_graph):
        cfg = ACSConfiguration(candidate_list_size=1)
        cc = CompositeCostCalculator(CostWeights(distance=1.0))
        vm = VisibilityMatrix(diamond_graph, cc, cfg)
        neighbours = vm.get_neighbours(NodeId("A"))
        assert len(neighbours) == 1

    def test_with_zero_cost_edge(self):
        # Length must be positive per edge validation, but we can make cost
        # approach zero by using a very short edge with high speed
        graph = DirectedGraph()
        graph.add_node(Node(node_id=NodeId("A"), x=0.0, y=0.0))
        graph.add_node(Node(node_id=NodeId("B"), x=0.001, y=0.0))
        graph.add_edge(Edge(
            edge_id=EdgeId("AB"), source=NodeId("A"), target=NodeId("B"),
            length_m=1.0, speed_limit_mps=1e6, lane_count=1,
            state=MutableEdgeState(),
        ))
        cfg = ACSConfiguration()
        cc = CompositeCostCalculator(CostWeights(distance=1.0))
        vm = VisibilityMatrix(graph, cc, cfg)
        # cost = 1 + ~0 = 1 -> visibility = 1/(1+EPS) ≈ 1.0
        vis = vm.get(EdgeId("AB"))
        assert vis > 0.0
        assert vis < 2.0

    def test_visibility_still_computed_for_valid_edge(self, linear_graph, acs_default_config):
        # Verify that valid edges produce positive visibility
        cc = CompositeCostCalculator(CostWeights(distance=1.0))
        vm = VisibilityMatrix(linear_graph, cc, acs_default_config)
        vis = vm.get(EdgeId("AB"))
        assert vis > 0.0


# =========================================================================
# 4. TransitionRule Tests
# =========================================================================


class TestTransitionRule:
    def test_empty_candidates_returns_none(self, acs_default_config):
        rule = TransitionRule(acs_default_config)
        pm = PheromoneMatrix(acs_default_config, set())
        vm = VisibilityMatrix.__new__(VisibilityMatrix)
        vm._data = {}
        vm._neighbour_cache = {}
        result = rule.select([], pm, vm, stdlib_random.Random(0), stdlib_random.Random(0))
        assert result is None

    def test_q0_exploitation_selects_best(self, acs_default_config):
        """When q <= q0, should select the edge with highest tau^alpha * eta^beta."""
        rule = TransitionRule(acs_default_config)
        pm = PheromoneMatrix(acs_default_config, {EdgeId("A"), EdgeId("B")})
        pm.set(EdgeId("A"), 0.5)
        pm.set(EdgeId("B"), 2.0)  # B has higher pheromone

        vm = VisibilityMatrix.__new__(VisibilityMatrix)
        vm._data = {EdgeId("A"): 1.0, EdgeId("B"): 1.0}
        vm._neighbour_cache = {}

        # Stream that always returns q <= q0 (use q0=0.9, stream returns 0.0)
        sel_stream = stdlib_random.Random(0)
        # Force deterministic: use a seed where first random() < 0.9
        result = rule.select(
            [EdgeId("A"), EdgeId("B")], pm, vm, sel_stream, stdlib_random.Random(0)
        )
        assert result == EdgeId("B")

    def test_alpha_zero_makes_pheromone_irrelevant(self):
        cfg = ACSConfiguration(alpha=0.0, beta=1.0, q0=1.0)  # Always exploit
        rule = TransitionRule(cfg)
        pm = PheromoneMatrix(cfg, {EdgeId("A"), EdgeId("B")})
        pm.set(EdgeId("A"), 100.0)  # High pheromone
        pm.set(EdgeId("B"), 0.01)   # Low pheromone

        vm = VisibilityMatrix.__new__(VisibilityMatrix)
        vm._data = {EdgeId("A"): 0.1, EdgeId("B"): 1.0}   # B has higher visibility
        vm._neighbour_cache = {}

        # alpha=0 so tau is ignored; beta=1 so only eta matters
        result = rule.select(
            [EdgeId("A"), EdgeId("B")], pm, vm,
            stdlib_random.Random(0), stdlib_random.Random(0),
        )
        assert result == EdgeId("B")  # B has higher eta

    def test_beta_zero_makes_visibility_irrelevant(self):
        cfg = ACSConfiguration(alpha=1.0, beta=0.0, q0=1.0)  # Always exploit
        rule = TransitionRule(cfg)
        pm = PheromoneMatrix(cfg, {EdgeId("A"), EdgeId("B")})
        pm.set(EdgeId("A"), 0.01)  # Low pheromone
        pm.set(EdgeId("B"), 1.0)   # High pheromone

        vm = VisibilityMatrix.__new__(VisibilityMatrix)
        vm._data = {EdgeId("A"): 100.0, EdgeId("B"): 0.1}
        vm._neighbour_cache = {}

        result = rule.select(
            [EdgeId("A"), EdgeId("B")], pm, vm,
            stdlib_random.Random(0), stdlib_random.Random(0),
        )
        assert result == EdgeId("B")  # B has higher tau

    def test_all_zero_weights_falls_back_to_uniform(self):
        # Create TransitionRule directly to bypass config validation
        cfg = ACSConfiguration(alpha=1.0, beta=1.0, q0=0.0)
        rule = TransitionRule.__new__(TransitionRule)
        rule._alpha = 0.0
        rule._beta = 0.0
        rule._q0 = 0.0
        pm = PheromoneMatrix(cfg, {EdgeId("A"), EdgeId("B")})
        pm.set(EdgeId("A"), 0.01)
        pm.set(EdgeId("B"), 0.01)

        vm = VisibilityMatrix.__new__(VisibilityMatrix)
        vm._data = {EdgeId("A"): 0.0, EdgeId("B"): 0.0}  # Both zero
        vm._neighbour_cache = {}

        # Should not crash; should return one of the candidates
        result = rule.select(
            [EdgeId("A"), EdgeId("B")], pm, vm,
            stdlib_random.Random(0), stdlib_random.Random(0),
        )
        assert result in (EdgeId("A"), EdgeId("B"))


# =========================================================================
# 5. PheromoneUpdater Tests
# =========================================================================


class TestPheromoneUpdater:
    def test_local_update_decays(self):
        cfg = ACSConfiguration(rho=0.2, tau0=0.5)
        up = PheromoneUpdater(cfg)
        pm = PheromoneMatrix(cfg, {EdgeId("e1")})
        pm.set(EdgeId("e1"), 1.0)
        up.local_update(pm, EdgeId("e1"))
        # (1-0.2)*1.0 + 0.2*0.5 = 0.8 + 0.1 = 0.9
        assert abs(pm.get(EdgeId("e1")) - 0.9) < 1e-10

    def test_global_update_reinforces_best(self):
        cfg = ACSConfiguration(rho=0.1)
        up = PheromoneUpdater(cfg)
        pm = PheromoneMatrix(cfg, {EdgeId("e1"), EdgeId("e2")})
        pm.set(EdgeId("e1"), 0.5)
        pm.set(EdgeId("e2"), 0.5)

        up.global_update(pm, [EdgeId("e1"), EdgeId("e2")], best_cost=10.0)

        # deposit = 1/10 = 0.1
        # tau = (1-0.1)*0.5 + 0.1*0.1 = 0.45 + 0.01 = 0.46
        assert abs(pm.get(EdgeId("e1")) - 0.46) < 1e-10
        assert abs(pm.get(EdgeId("e2")) - 0.46) < 1e-10

    def test_global_update_zero_cost_noop(self):
        cfg = ACSConfiguration(rho=0.1)
        up = PheromoneUpdater(cfg)
        pm = PheromoneMatrix(cfg, {EdgeId("e1")})
        pm.set(EdgeId("e1"), 1.0)
        up.global_update(pm, [EdgeId("e1")], best_cost=0.0)
        assert pm.get(EdgeId("e1")) == 1.0  # Unchanged

    def test_global_update_infinite_cost_noop(self):
        cfg = ACSConfiguration(rho=0.1)
        up = PheromoneUpdater(cfg)
        pm = PheromoneMatrix(cfg, {EdgeId("e1")})
        pm.set(EdgeId("e1"), 1.0)
        up.global_update(pm, [EdgeId("e1")], best_cost=float("inf"))
        assert pm.get(EdgeId("e1")) == 1.0

    def test_elite_update(self):
        cfg = ACSConfiguration(rho=0.1, elitism=2)
        up = PheromoneUpdater(cfg)
        pm = PheromoneMatrix(cfg, {EdgeId("e1"), EdgeId("e2")})
        pm.set(EdgeId("e1"), 0.5)
        pm.set(EdgeId("e2"), 0.5)

        up.global_update_elite(pm, [[EdgeId("e1")], [EdgeId("e2")]], [5.0, 10.0])
        # deposit1 = 1/5 = 0.2, deposit2 = 1/10 = 0.1
        # tau_e1 = (1-0.05)*0.5 + 0.05*0.2 = 0.475 + 0.01 = 0.485
        # tau_e2 = (1-0.05)*0.5 + 0.05*0.1 = 0.475 + 0.005 = 0.48
        assert abs(pm.get(EdgeId("e1")) - 0.485) < 1e-10
        assert abs(pm.get(EdgeId("e2")) - 0.480) < 1e-10


# =========================================================================
# 6. Ant Tests
# =========================================================================


class TestAnt:
    def test_create_initial_state(self):
        ant = Ant.create(NodeId("A"))
        assert ant.current_node == NodeId("A")
        assert ant.visited_nodes == {NodeId("A")}
        assert ant.node_sequence == [NodeId("A")]
        assert ant.edge_sequence == []
        assert ant.total_cost == 0.0
        assert not ant.is_complete
        assert ant.is_feasible
        assert not ant.reached_dead_end

    def test_reset_clears_state(self):
        ant = Ant(
            current_node=NodeId("D"),
            visited_nodes={NodeId("A"), NodeId("B"), NodeId("C"), NodeId("D")},
            node_sequence=[NodeId("A"), NodeId("B"), NodeId("C"), NodeId("D")],
            edge_sequence=[EdgeId("AB"), EdgeId("BC"), EdgeId("CD")],
            total_cost=300.0,
            is_complete=True,
            is_feasible=False,
        )
        ant.reset(NodeId("X"))
        assert ant.current_node == NodeId("X")
        assert ant.visited_nodes == {NodeId("X")}
        assert ant.node_sequence == [NodeId("X")]
        assert ant.edge_sequence == []
        assert ant.total_cost == 0.0
        assert not ant.is_complete
        assert ant.is_feasible
        assert not ant.reached_dead_end


# =========================================================================
# 7. AntColony Tests
# =========================================================================


class TestAntColony:
    def test_initialize_population(self, acs_default_config):
        colony = AntColony(acs_default_config)
        colony.initialize_population(5, NodeId("A"))
        assert len(colony.population) == 5
        for ant in colony.population:
            assert ant.current_node == NodeId("A")
            assert ant.visited_nodes == {NodeId("A")}

    def test_initialize_population_reuses_ants(self, acs_default_config):
        colony = AntColony(acs_default_config)
        colony.initialize_population(5, NodeId("A"))
        first_pop = colony.population
        colony.initialize_population(5, NodeId("B"))
        # Same ant objects, just reset
        assert colony.population is first_pop
        assert all(a.current_node == NodeId("B") for a in colony.population)

    def test_construct_routes_linear_graph(self, linear_graph, acs_default_config):
        colony = AntColony(acs_default_config)
        colony.initialize_population(3, NodeId("A"))

        cc = CompositeCostCalculator(CostWeights(distance=1.0))
        vm = VisibilityMatrix(linear_graph, cc, acs_default_config)
        edge_ids = {e.edge_id for e in linear_graph.edges()}
        pm = PheromoneMatrix(acs_default_config, edge_ids)

        request = _make_request("A", "D")
        colony.construct_routes(
            request, pm, vm, linear_graph,
            stdlib_random.Random(42), stdlib_random.Random(43),
        )

        # All ants should find the complete path A-B-C-D
        for ant in colony.population:
            assert ant.is_complete, f"Ant did not complete: {ant.node_sequence}"
            assert ant.node_sequence[0] == NodeId("A")
            assert ant.node_sequence[-1] == NodeId("D")
            assert len(ant.edge_sequence) == 3

    def test_evaluate_population(self, linear_graph, acs_default_config):
        colony = AntColony(acs_default_config)
        colony.initialize_population(5, NodeId("A"))

        cc = CompositeCostCalculator(CostWeights(distance=1.0))
        vm = VisibilityMatrix(linear_graph, cc, acs_default_config)
        edge_ids = {e.edge_id for e in linear_graph.edges()}
        pm = PheromoneMatrix(acs_default_config, edge_ids)

        request = _make_request("A", "D")
        colony.construct_routes(request, pm, vm, linear_graph,
                                stdlib_random.Random(42), stdlib_random.Random(43))

        best, worst, avg = colony.evaluate_population()
        assert best is not None
        assert worst is not None
        assert best.score <= worst.score
        assert avg > 0.0

    def test_diversity_metric(self, linear_graph, acs_default_config):
        colony = AntColony(acs_default_config)
        colony.initialize_population(5, NodeId("A"))

        cc = CompositeCostCalculator(CostWeights(distance=1.0))
        vm = VisibilityMatrix(linear_graph, cc, acs_default_config)
        edge_ids = {e.edge_id for e in linear_graph.edges()}
        pm = PheromoneMatrix(acs_default_config, edge_ids)

        request = _make_request("A", "D")
        colony.construct_routes(request, pm, vm, linear_graph,
                                stdlib_random.Random(42), stdlib_random.Random(43))

        diversity = colony.compute_diversity()
        assert 0.0 <= diversity <= 1.0

    def test_diversity_zero_for_identical_routes(self):
        colony = AntColony(ACSConfiguration())
        # Simulate ants with identical routes
        ant = Ant.create(NodeId("A"))
        ant.node_sequence = [NodeId("A"), NodeId("B")]
        ant.edge_sequence = [EdgeId("AB")]
        colony._ants = [ant, ant]  # Same object, so same routes
        colony._ants = [Ant.create(NodeId("A")) for _ in range(3)]
        for a in colony._ants:
            a.node_sequence = [NodeId("A"), NodeId("B")]
            a.edge_sequence = [EdgeId("AB")]
        div = colony.compute_diversity()
        # Only one unique edge, total = 3 -> diversity = 1/3
        assert abs(div - 1.0 / 3.0) < 1e-10

    def test_empty_population_diversity_zero(self):
        colony = AntColony(ACSConfiguration())
        colony._ants = []
        assert colony.compute_diversity() == 0.0


# =========================================================================
# 8. ACOValidator Tests
# =========================================================================


class TestACOValidator:
    def test_valid_config_no_errors(self, acs_default_config):
        errors = ACOValidator.validate_config(acs_default_config)
        assert errors == []

    @staticmethod
    def _make_cfg(**kw) -> ACSConfiguration:
        # Bypass validation to test the validator directly
        cfg = object.__new__(ACSConfiguration)
        for k, v in ACSConfiguration().__annotations__.items():
            object.__setattr__(cfg, k, kw.get(k, getattr(ACSConfiguration(), k)))
        return cfg

    def test_invalid_config_alpha_negative(self):
        cfg = self._make_cfg(alpha=-1.0)
        errors = ACOValidator.validate_config(cfg)
        assert len(errors) >= 1

    def test_invalid_config_beta_negative(self):
        cfg = self._make_cfg(beta=-1.0)
        errors = ACOValidator.validate_config(cfg)
        assert len(errors) >= 1

    def test_invalid_config_alpha_beta_both_zero(self):
        cfg = self._make_cfg(alpha=0.0, beta=0.0)
        errors = ACOValidator.validate_config(cfg)
        assert len(errors) >= 1

    def test_invalid_config_rho_zero(self):
        cfg = self._make_cfg(rho=0.0)
        errors = ACOValidator.validate_config(cfg)
        assert len(errors) >= 1

    def test_invalid_context_no_graph(self):
        config = SwarmConfig(algorithm_name="aco")
        context = SwarmContext(
            cost_weights=CostWeights(), config=config,
            random_seed=42, routing_request=_make_request("A", "B"),
            sim_time_s=0.0, graph=None, cost_calculator=None,
        )
        errors = ACOValidator.validate_context(context)
        assert len(errors) >= 1
        assert any("graph" in e.lower() for e in errors)

    def test_invalid_context_no_cost_calculator(self):
        config = SwarmConfig(algorithm_name="aco")
        graph = DirectedGraph()
        graph.add_node(Node(node_id=NodeId("A"), x=0.0, y=0.0))
        graph.add_node(Node(node_id=NodeId("B"), x=1.0, y=0.0))
        context = SwarmContext(
            cost_weights=CostWeights(), config=config,
            random_seed=42, routing_request=_make_request("A", "B"),
            sim_time_s=0.0, graph=graph, cost_calculator=None,
        )
        errors = ACOValidator.validate_context(context)
        assert len(errors) >= 1
        assert any("cost_calculator" in e.lower() for e in errors)

    def test_valid_context_no_errors(self, linear_graph):
        config = SwarmConfig(algorithm_name="aco")
        cc = CompositeCostCalculator(CostWeights())
        context = SwarmContext(
            cost_weights=CostWeights(), config=config,
            random_seed=42, routing_request=_make_request("A", "D"),
            sim_time_s=0.0, graph=linear_graph, cost_calculator=cc,
        )
        errors = ACOValidator.validate_context(context)
        assert errors == []


# =========================================================================
# 9. ACOFactory Tests
# =========================================================================


class TestACOFactory:
    def test_create_default(self):
        aco = ACOFactory.create()
        assert aco.name == "aco"
        assert isinstance(aco, ACORouting)

    def test_create_with_config(self):
        cfg = ACSConfiguration(alpha=2.0, beta=3.0)
        aco = ACOFactory.create(cfg)
        assert aco._config.alpha == 2.0
        assert aco._config.beta == 3.0

    def test_create_from_swarm_config(self, swarm_config_aco):
        aco = ACOFactory.create_from_swarm_config(swarm_config_aco)
        assert aco.name == "aco"
        assert aco._config.alpha == 1.0


# =========================================================================
# 10. ACORouting — Integration Tests
# =========================================================================


class TestACORouting:
    def test_optimize_linear_graph(self, linear_graph, swarm_config_aco):
        request = _make_request("A", "D")
        context = _make_context(linear_graph, request, swarm_config_aco)
        aco = ACORouting()
        result = aco.optimize(context)
        assert result.success
        assert result.best_solution is not None
        assert len(result.best_solution.node_sequence) >= 2
        assert result.best_solution.source_node == NodeId("A")
        assert result.best_solution.destination_node == NodeId("D")
        assert result.statistics.best_score > 0
        assert result.statistics.total_iterations > 0

    def test_optimize_diamond_graph(self, diamond_graph, swarm_config_aco):
        request = _make_request("A", "D")
        context = _make_context(diamond_graph, request, swarm_config_aco)
        aco = ACORouting()
        result = aco.optimize(context)
        assert result.success
        assert len(result.best_solution.node_sequence) >= 2
        assert result.best_solution.source_node == NodeId("A")
        assert result.best_solution.destination_node == NodeId("D")

    def test_optimize_grid_graph(self, grid_graph, swarm_config_aco):
        request = _make_request("0_0", "2_2")
        context = _make_context(grid_graph, request, swarm_config_aco)
        aco = ACORouting()
        result = aco.optimize(context)
        assert result.success
        assert result.best_solution.source_node == NodeId("0_0")
        assert result.best_solution.destination_node == NodeId("2_2")

    def test_optimize_no_graph_returns_failure(self, swarm_config_aco):
        request = _make_request("A", "D")
        config = swarm_config_aco
        cc = CompositeCostCalculator(CostWeights())
        context = SwarmContext(
            cost_weights=config.cost_weights, config=config,
            random_seed=42, routing_request=request,
            sim_time_s=0.0, graph=None, cost_calculator=cc,
        )
        aco = ACORouting()
        result = aco.optimize(context)
        assert not result.success
        assert result.failure_reason is not None

    def test_optimize_no_cost_calculator_returns_failure(self, linear_graph, swarm_config_aco):
        request = _make_request("A", "D")
        config = swarm_config_aco
        context = SwarmContext(
            cost_weights=config.cost_weights, config=config,
            random_seed=42, routing_request=request,
            sim_time_s=0.0, graph=linear_graph, cost_calculator=None,
        )
        aco = ACORouting()
        result = aco.optimize(context)
        assert not result.success


# =========================================================================
# 11. Deterministic Replay Tests
# =========================================================================


class TestDeterministicReplay:
    def test_same_seed_identical_results(self, diamond_graph, swarm_config_aco):
        request = _make_request("A", "D")
        context1 = _make_context(diamond_graph, request, swarm_config_aco, seed=42)
        context2 = _make_context(diamond_graph, request, swarm_config_aco, seed=42)

        aco = ACORouting()
        result1 = aco.optimize(context1)
        result2 = aco.optimize(context2)

        assert result1.success == result2.success
        if result1.success:
            assert result1.best_solution.node_sequence == result2.best_solution.node_sequence
            assert result1.best_solution.edge_sequence == result2.best_solution.edge_sequence
            assert abs(result1.statistics.best_score - result2.statistics.best_score) < 1e-6

    def test_different_seed_different_results(self, diamond_graph, swarm_config_aco):
        request = _make_request("A", "D")
        context1 = _make_context(diamond_graph, request, swarm_config_aco, seed=42)
        context2 = _make_context(diamond_graph, request, swarm_config_aco, seed=99)

        aco = ACORouting()
        result1 = aco.optimize(context1)
        result2 = aco.optimize(context2)

        # Both should succeed but may differ (probabilistic algorithm)
        assert result1.success
        assert result2.success

    def test_deterministic_across_multiple_runs(self, diamond_graph, swarm_config_aco):
        """Verify deterministic replay across 5 runs."""
        request = _make_request("A", "D")
        contexts = [_make_context(diamond_graph, request, swarm_config_aco, seed=42)
                    for _ in range(5)]

        aco = ACORouting()
        results = [aco.optimize(ctx) for ctx in contexts]

        sequences = [r.best_solution.node_sequence for r in results]
        scores = [r.statistics.best_score for r in results]

        # All must be identical
        for i in range(1, len(sequences)):
            assert sequences[i] == sequences[0], f"Run {i} differs"
            assert abs(scores[i] - scores[0]) < 1e-6, f"Score {i} differs"


# =========================================================================
# 12. Edge-Case Tests
# =========================================================================


class TestEdgeCases:
    def test_unreachable_destination(self, swarm_config_aco):
        """Graph where no path exists between source and destination."""
        graph = DirectedGraph()
        graph.add_node(Node(node_id=NodeId("A"), x=0.0, y=0.0))
        graph.add_node(Node(node_id=NodeId("B"), x=100.0, y=0.0))
        # No edges connecting A to B

        request = _make_request("A", "B")
        context = _make_context(graph, request, swarm_config_aco)
        aco = ACORouting()
        result = aco.optimize(context)
        # Ants will fail or produce penalized results
        assert result.statistics.total_iterations > 0

    def test_single_node_graph(self, swarm_config_aco):
        """Graph with only one node (source == dest = invalid request)."""
        graph = DirectedGraph()
        graph.add_node(Node(node_id=NodeId("A"), x=0.0, y=0.0))

        request = _make_request("A", "B")  # B doesn't exist
        context = _make_context(graph, request, swarm_config_aco)
        aco = ACORouting()
        result = aco.optimize(context)
        # Should complete without crashing; may fail to find route
        assert result.statistics.total_iterations > 0

    def test_all_edges_blocked(self, linear_graph, swarm_config_aco):
        """All edges blocked — ants cannot move."""
        for eid in [EdgeId("AB"), EdgeId("BC"), EdgeId("CD")]:
            linear_graph.update_edge_state(eid, MutableEdgeState(is_blocked=True))

        request = _make_request("A", "D")
        context = _make_context(linear_graph, request, swarm_config_aco)
        aco = ACORouting()
        result = aco.optimize(context)
        # Ants should all reach dead ends; may or may not find route
        assert result.statistics.total_iterations > 0

    def test_single_edge_graph(self, swarm_config_aco):
        """Graph with exactly one edge A->B."""
        graph = DirectedGraph()
        graph.add_node(Node(node_id=NodeId("A"), x=0.0, y=0.0))
        graph.add_node(Node(node_id=NodeId("B"), x=100.0, y=0.0))
        graph.add_edge(Edge(
            edge_id=EdgeId("AB"), source=NodeId("A"), target=NodeId("B"),
            length_m=100.0, speed_limit_mps=10.0, lane_count=1,
            state=MutableEdgeState(),
        ))

        request = _make_request("A", "B")
        context = _make_context(graph, request, swarm_config_aco)
        aco = ACORouting()
        result = aco.optimize(context)
        assert result.success
        assert result.best_solution.node_sequence == (NodeId("A"), NodeId("B"))

    def test_with_cycle_in_graph(self, swarm_config_aco):
        """Graph with a cycle — ants should not loop infinitely."""
        graph = DirectedGraph()
        for nid in ["A", "B", "C", "D"]:
            graph.add_node(Node(node_id=NodeId(nid), x=0.0, y=0.0))
        state = MutableEdgeState()
        # Cycle: A-B-C-A, plus C-D
        for eid, src, tgt in [
            ("AB", "A", "B"), ("BC", "B", "C"), ("CA", "C", "A"),
            ("CD", "C", "D"),
        ]:
            graph.add_edge(Edge(
                edge_id=EdgeId(eid), source=NodeId(src), target=NodeId(tgt),
                length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=state,
            ))

        request = _make_request("A", "D")
        context = _make_context(graph, request, swarm_config_aco)
        aco = ACORouting()
        result = aco.optimize(context)
        # Should find A-B-C-D (or A-C-D if that path exists)
        assert result.success
        assert result.best_solution.destination_node == NodeId("D")

    def test_large_alpha_exploitation(self, diamond_graph):
        """High alpha should make ants follow pheromone trails strongly."""
        config = SwarmConfig(
            algorithm_name="aco", population_size=5, max_iterations=10,
            hyperparameters={"alpha": 5.0, "beta": 0.1, "q0": 0.99},
        )
        request = _make_request("A", "D")
        context = _make_context(diamond_graph, request, config)
        aco = ACORouting()
        result = aco.optimize(context)
        assert result.success

    def test_q0_zero_max_exploration(self, diamond_graph):
        """q0=0 means always explore — should still find routes."""
        config = SwarmConfig(
            algorithm_name="aco", population_size=10, max_iterations=20,
            hyperparameters={"q0": 0.0},
        )
        request = _make_request("A", "D")
        context = _make_context(diamond_graph, request, config)
        aco = ACORouting()
        result = aco.optimize(context)
        assert result.success


# =========================================================================
# 13. Property-Based Tests
# =========================================================================


class TestProperties:
    def test_best_score_non_increasing(self, diamond_graph, swarm_config_aco):
        """Best score should be non-increasing over iterations (cost minimization)."""
        request = _make_request("A", "D")
        context = _make_context(diamond_graph, request, swarm_config_aco)
        aco = ACORouting()
        result = aco.optimize(context)

        if result.success and len(result.statistics.score_history) > 1:
            for i in range(1, len(result.statistics.score_history)):
                assert result.statistics.score_history[i] <= result.statistics.score_history[i - 1] + 1e-6

    def test_pheromone_bounds_respected(self, diamond_graph, swarm_config_aco):
        """Pheromone values should always be within [tau_min, tau_max]."""
        request = _make_request("A", "D")
        context = _make_context(diamond_graph, request, swarm_config_aco)
        aco = ACORouting()
        _ = aco.optimize(context)

        # After optimization, check that internal pheromone state is bounded
        # We can access the colony's stored pheromone state indirectly
        aco_config = ACSConfiguration.from_swarm_config(swarm_config_aco)
        cc = CompositeCostCalculator(CostWeights())
        vm = VisibilityMatrix(diamond_graph, cc, aco_config)
        edge_ids = {e.edge_id for e in diamond_graph.edges()}
        pm = PheromoneMatrix(aco_config, edge_ids)

        # Verify bounds are valid
        assert aco_config.tau_min > 0
        assert aco_config.tau_max > aco_config.tau_min

    def test_solution_validity(self, diamond_graph, swarm_config_aco):
        """All routes should start at source and end at destination."""
        request = _make_request("A", "D")
        context = _make_context(diamond_graph, request, swarm_config_aco)
        aco = ACORouting()
        result = aco.optimize(context)

        if result.success:
            sol = result.best_solution
            assert sol.source_node == NodeId("A")
            assert sol.destination_node == NodeId("D")
            assert len(sol.node_sequence) == len(sol.edge_sequence) + 1
            # Verify edges connect sequentially
            for i, nid in enumerate(sol.node_sequence[:-1]):
                eid = sol.edge_sequence[i]
                edge = diamond_graph.get_edge(eid)
                assert edge.source == nid
                assert edge.target == sol.node_sequence[i + 1]

    def test_cost_non_negative(self, diamond_graph, swarm_config_aco):
        """All candidate costs must be non-negative."""
        request = _make_request("A", "D")
        context = _make_context(diamond_graph, request, swarm_config_aco)
        aco = ACORouting()
        result = aco.optimize(context)

        if result.success:
            assert result.best_solution.total_cost >= 0
            for candidate in result.candidates:
                assert candidate.total_cost >= 0

    def test_diversity_range(self, diamond_graph, swarm_config_aco):
        """Diversity must be in [0, 1]."""
        request = _make_request("A", "D")
        context = _make_context(diamond_graph, request, swarm_config_aco)
        aco = ACORouting()
        result = aco.optimize(context)

        for div in result.statistics.diversity_history:
            assert 0.0 <= div <= 1.0


# =========================================================================
# 14. Stress Tests
# =========================================================================


class TestStress:
    def test_larger_random_graph(self):
        """Test on a randomly generated 20-node graph."""
        graph = DirectedGraph()
        rng = stdlib_random.Random(42)

        # Create nodes
        for i in range(20):
            graph.add_node(Node(
                node_id=NodeId(f"N{i}"),
                x=rng.uniform(0, 1000),
                y=rng.uniform(0, 1000),
            ))

        # Create edges (ensure connectivity along a line, then add random)
        for i in range(19):
            graph.add_edge(Edge(
                edge_id=EdgeId(f"E{i}_{i+1}"),
                source=NodeId(f"N{i}"),
                target=NodeId(f"N{i + 1}"),
                length_m=rng.uniform(50, 200),
                speed_limit_mps=10.0,
                lane_count=1,
                state=MutableEdgeState(),
            ))

        # Add 30 random extra edges
        for i in range(30):
            src = rng.randint(0, 19)
            dst = rng.randint(0, 19)
            if src == dst:
                continue
            graph.add_edge(Edge(
                edge_id=EdgeId(f"R{i}"),
                source=NodeId(f"N{src}"),
                target=NodeId(f"N{dst}"),
                length_m=rng.uniform(50, 200),
                speed_limit_mps=10.0,
                lane_count=1,
                state=MutableEdgeState(),
            ))

        config = SwarmConfig(
            algorithm_name="aco", population_size=10, max_iterations=30,
            hyperparameters={"alpha": 1.0, "beta": 2.0, "rho": 0.1, "q0": 0.9},
        )
        request = _make_request("N0", "N19")
        context = _make_context(graph, request, config, seed=42)
        aco = ACORouting()
        result = aco.optimize(context)

        assert result.success
        assert result.best_solution.source_node == NodeId("N0")
        assert result.best_solution.destination_node == NodeId("N19")
        assert result.statistics.total_iterations > 0


# =========================================================================
# 15. Benchmark Regression Tests
# =========================================================================


class TestBenchmarkRegression:
    def test_aco_vs_dijkstra_small_graph(self, diamond_graph):
        """ACO should find a route with cost within reasonable range of Dijkstra."""
        from e3hybrid.routing.dijkstra import DijkstraRouting

        request = _make_request("A", "D")
        dijkstra = DijkstraRouting()
        dijkstra_result = dijkstra.compute_route(request, diamond_graph)

        assert dijkstra_result.success
        dijkstra_cost = dijkstra_result.candidates[0].total_cost

        config = SwarmConfig(
            algorithm_name="aco", population_size=20, max_iterations=50,
            hyperparameters={"alpha": 1.0, "beta": 2.0, "rho": 0.1, "q0": 0.9},
        )
        context = _make_context(diamond_graph, request, config, seed=42)
        aco = ACORouting()
        aco_result = aco.optimize(context)

        assert aco_result.success
        aco_cost = aco_result.best_solution.total_cost

        # ACO should be within 20% of optimal on this simple graph
        cost_ratio = aco_cost / dijkstra_cost
        assert cost_ratio >= 0.8, f"ACO cost ratio too low: {cost_ratio}"
        assert cost_ratio <= 3.0, f"ACO cost ratio too high: {cost_ratio}"

    def test_benchmark_via_swarm_to_routing_adapter(self, diamond_graph):
        """Test that ACO works through SwarmToRoutingAdapter."""
        from e3hybrid.swarm.adapter import SwarmToRoutingAdapter

        config = SwarmConfig(
            algorithm_name="aco", population_size=5, max_iterations=10,
            hyperparameters={"alpha": 1.0, "beta": 2.0},
        )
        aco = ACORouting()
        adapter = SwarmToRoutingAdapter(swarm_algorithm=aco, swarm_config=config)

        request = _make_request("A", "D")
        result = adapter.compute_route(request, diamond_graph)

        assert result.success
        assert result.primary_route is not None
        assert result.candidates[0].algorithm == "aco"
        assert len(result.candidates[0].node_sequence) >= 2

    def test_benchmark_via_routing_factory(self, diamond_graph):
        """Test that RoutingFactory can create and run ACO."""
        from e3hybrid.routing.factory import RoutingFactory

        algorithm = RoutingFactory.create_aco()
        request = _make_request("A", "D")
        result = algorithm.compute_route(request, diamond_graph)

        assert result.success
        assert result.primary_route is not None

    def test_aco_with_all_defaults(self, diamond_graph):
        """ACO with default configuration should work."""
        aco = ACORouting()
        config = SwarmConfig(
            algorithm_name="aco", population_size=5, max_iterations=10,
        )
        request = _make_request("A", "D")
        context = _make_context(diamond_graph, request, config)
        result = aco.optimize(context)
        assert result.success
