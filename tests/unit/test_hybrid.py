"""Tests for E3-Hybrid swarm algorithm (~85 tests).

Categories: configuration, population partitioning, influence isolation,
normalisation, meta-controller, pheromone evolution, template extraction,
personal/global best, determinism, cross-component, edge cases, integration.
"""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from e3hybrid.network.edge import Edge, MutableEdgeState as EdgeState
from e3hybrid.network.graph import DirectedGraph
from e3hybrid.network.node import Node
from e3hybrid.network.types import EdgeId, NodeId
from e3hybrid.vehicle.types import VehicleId
from e3hybrid.swarm.hybrid import (
    E3HybridRouting,
    HybridConfiguration,
    HybridInfluenceWeights,
    HybridStatistics,
    IndividualKind,
    IndividualState,
    IndividualStatus,
    _EPS,
    _failure_result,
)
from e3hybrid.network.node import Node
from e3hybrid.swarm.pheromone import HybridPheromoneMatrix

# =============================================================================
# Helpers
# =============================================================================


def make_grid_graph(rows: int = 3, cols: int = 3) -> DirectedGraph:
    g = DirectedGraph()
    nodes: dict[tuple[int, int], NodeId] = {}
    for r in range(rows):
        for c in range(cols):
            nid = NodeId(f"n{r}_{c}")
            g.add_node(Node(nid))
            nodes[(r, c)] = nid
    for r in range(rows):
        for c in range(cols):
            nid = nodes[(r, c)]
            if c + 1 < cols:
                target = nodes[(r, c + 1)]
                e = Edge(EdgeId(f"e{r}_{c}->{r}_{c+1}"), source=nid, target=target,
                         length_m=100.0, speed_limit_mps=10.0)
                g.add_edge(e)
            if r + 1 < rows:
                target = nodes[(r + 1, c)]
                e = Edge(EdgeId(f"e{r}_{c}->{r+1}_{c}"), source=nid, target=target,
                         length_m=100.0, speed_limit_mps=10.0)
                g.add_edge(e)
    return g


def make_simple_graph() -> DirectedGraph:
    g = DirectedGraph()
    nodes = [NodeId(f"n{i}") for i in range(5)]
    for n in nodes:
        g.add_node(Node(n))
    for i in range(4):
        e1 = Edge(EdgeId(f"e{i}_{i+1}"), source=nodes[i], target=nodes[i+1],
                 length_m=100.0, speed_limit_mps=10.0)
        g.add_edge(e1)
        e2 = Edge(EdgeId(f"e{i+1}_{i}"), source=nodes[i+1], target=nodes[i],
                 length_m=100.0, speed_limit_mps=10.0)
        g.add_edge(e2)
    return g


def make_context(graph: DirectedGraph, seed: int = 42, **hp_overrides: Any) -> Any:
    from e3hybrid.routing.cost_calculator import CostWeights, CompositeCostCalculator
    from e3hybrid.routing.request import RoutingRequest
    from e3hybrid.swarm.config import SwarmConfig
    from e3hybrid.swarm.context import SwarmContext

    hyperparams: dict[str, Any] = {
        "ant_ratio": 0.4, "bee_ratio": 0.3, "particle_ratio": 0.3,
        "alpha_a": 1.0, "alpha_b": 1.0, "alpha_p": 1.0, "alpha_h": 1.0,
        "template_count": 3, "inertia_start": 0.9, "inertia_end": 0.4,
        "cognition_weight": 2.0, "social_weight": 2.0,
        "pheromone_tau0": 1.0, "pheromone_min": 0.01, "pheromone_max": 10.0,
        "rho": 0.1, "rho_local": 0.1, "beta_a": 1.0,
        "epsilon": 1e-10, "forward_steps": 100,
        "adapt_interval": 5, "adapt_diversity_min": 0.15,
        "adapt_decay": 0.9, "adapt_recovery_gain": 0.05,
    }
    hyperparams.update(hp_overrides)

    config = SwarmConfig(
        algorithm_name="e3hybrid", population_size=9, max_iterations=3,
        seed=seed, hyperparameters=hyperparams, cost_weights=CostWeights(),
    )
    nodes = list(graph.nodes())
    source = nodes[0].node_id
    dest = nodes[-1].node_id
    request = RoutingRequest(source_node=source, destination_node=dest,
                              vehicle_id=VehicleId("v1"), vehicle_constraints={},
                              battery_state={}, max_candidates=5, timeout_s=30.0)
    cost_calc = CompositeCostCalculator(config.cost_weights)
    return SwarmContext(
        cost_weights=config.cost_weights, config=config, random_seed=seed,
        routing_request=request, sim_time_s=0.0, graph=graph,
        cost_calculator=cost_calc,
    )


# =============================================================================
# 1. Configuration validation (14 tests)
# =============================================================================


class TestConfig:

    def test_default(self):
        c = HybridConfiguration()
        assert c.ant_ratio == 0.4 and c.forward_steps == 500

    def test_ratios_must_sum(self):
        with pytest.raises(ValueError, match="must sum to 1.0"):
            HybridConfiguration(ant_ratio=0.5, bee_ratio=0.5, particle_ratio=0.5)

    def test_ratios_float_precision(self):
        c = HybridConfiguration(ant_ratio=0.333, bee_ratio=0.333, particle_ratio=0.334)
        assert abs(c.ant_ratio + c.bee_ratio + c.particle_ratio - 1.0) < 1e-9

    def test_forward_steps(self):
        with pytest.raises(ValueError, match="forward_steps"):
            HybridConfiguration(forward_steps=0)

    def test_pheromone_bounds(self):
        with pytest.raises(ValueError, match="pheromone_min"):
            HybridConfiguration(pheromone_min=5.0, pheromone_max=1.0)

    def test_pheromone_bounds_equal(self):
        with pytest.raises(ValueError, match="pheromone_min"):
            HybridConfiguration(pheromone_min=1.0, pheromone_max=1.0)

    def test_all_zero_influence(self):
        with pytest.raises(ValueError, match="at least one"):
            HybridConfiguration(alpha_a=0.0, alpha_b=0.0, alpha_p=0.0, alpha_h=0.0)

    def test_inertia_reversed(self):
        with pytest.raises(ValueError, match="inertia_start"):
            HybridConfiguration(inertia_start=0.4, inertia_end=0.9)

    def test_inertia_out_of_range(self):
        with pytest.raises(ValueError, match="inertia weights"):
            HybridConfiguration(inertia_start=1.5, inertia_end=0.4)

    def test_adapt_interval(self):
        with pytest.raises(ValueError, match="adapt_interval"):
            HybridConfiguration(adapt_interval=0)

    def test_adapt_diversity_min(self):
        with pytest.raises(ValueError, match="adapt_diversity_min"):
            HybridConfiguration(adapt_diversity_min=0.0)

    def test_adapt_recovery_gain(self):
        with pytest.raises(ValueError, match="adapt_recovery_gain"):
            HybridConfiguration(adapt_recovery_gain=1.0)

    def test_alpha_bounds(self):
        with pytest.raises(ValueError, match="alpha_a must be"):
            HybridConfiguration(alpha_a=5.0, alpha_a_max=3.0)

    def test_beta_a(self):
        with pytest.raises(ValueError, match="beta_a"):
            HybridConfiguration(beta_a=-1.0)


# =============================================================================
# 2. Population partitioning (6 tests)
# =============================================================================


def _partition(n: int, ar: float, br: float, pr: float) -> tuple[int, int, int]:
    r = E3HybridRouting(HybridConfiguration(ant_ratio=ar, bee_ratio=br, particle_ratio=pr))
    kinds = r._assign_subpopulations(n)
    return (
        sum(1 for k in kinds if k == IndividualKind.ANT),
        sum(1 for k in kinds if k == IndividualKind.BEE),
        sum(1 for k in kinds if k == IndividualKind.PARTICLE),
    )


class TestPartition:

    def test_standard(self):
        a, b, p = _partition(30, 0.4, 0.3, 0.3)
        assert a == 12 and b == 9 and p == 9

    def test_floor_residual(self):
        a, b, p = _partition(10, 0.333, 0.333, 0.334)
        assert a + b + p == 10

    def test_minimum(self):
        a, b, p = _partition(3, 0.333, 0.334, 0.333)
        assert a + b + p == 3

    def test_bee_ratio_zero(self):
        a, b, p = _partition(10, 0.5, 0.0, 0.5)
        assert b == 1
        assert a + b + p == 10

    def test_residual_to_particles(self):
        _, _, p1 = _partition(10, 0.4, 0.3, 0.3)
        _, _, p2 = _partition(11, 0.4, 0.3, 0.3)
        assert p2 - p1 == 1

    def test_deterministic(self):
        p1 = _partition(30, 0.4, 0.3, 0.3)
        p2 = _partition(30, 0.4, 0.3, 0.3)
        assert p1 == p2


# =============================================================================
# 3. Influence isolation (10 tests)
# =============================================================================


class TestInfluence:

    def test_aco_raw(self):
        r = E3HybridRouting()
        pm = HybridPheromoneMatrix(1.0, 0.01, 10.0, {EdgeId("e")})
        pm.set(EdgeId("e"), 2.0)
        assert r._compute_raw_aco(EdgeId("e"), pm) == 2.0

    def test_aco_beta(self):
        r = E3HybridRouting(HybridConfiguration(beta_a=2.0))
        pm = HybridPheromoneMatrix(1.0, 0.01, 10.0, {EdgeId("e")})
        pm.set(EdgeId("e"), 3.0)
        assert r._compute_raw_aco(EdgeId("e"), pm) == 9.0

    def test_aco_none_pheromone(self):
        r = E3HybridRouting()
        assert r._compute_raw_aco(EdgeId("e"), None) == 1.0

    def test_bco_match(self):
        r = E3HybridRouting()
        assert r._compute_raw_bco(EdgeId("e1"), 0, [[EdgeId("e1")]]) == 1.0

    def test_bco_no_match(self):
        r = E3HybridRouting(HybridConfiguration(epsilon=0.1))
        assert r._compute_raw_bco(EdgeId("e2"), 0, [[EdgeId("e1")]]) == 0.1

    def test_bco_empty_templates(self):
        r = E3HybridRouting(HybridConfiguration(epsilon=0.1))
        assert r._compute_raw_bco(EdgeId("e1"), 0, []) == 0.1

    def test_pso_both_match(self):
        r = E3HybridRouting(HybridConfiguration(cognition_weight=2, social_weight=3))
        current = pbest = gbest = [EdgeId("e1")]
        val = r._compute_raw_pso(EdgeId("e1"), 0, current, pbest, gbest, inertia=1.0)
        assert val == 6.0  # inertia*M_cur + cog*M_p + soc*M_g = 1*1 + 2*1 + 3*1

    def test_pso_cognitive_only(self):
        r = E3HybridRouting(HybridConfiguration(cognition_weight=2, social_weight=0))
        current = pbest = [EdgeId("e1")]
        val = r._compute_raw_pso(EdgeId("e1"), 0, current, pbest, [], inertia=1.0)
        assert val == 3.0  # 1*1 + 2*1 + 0*eps

    def test_pso_no_match(self):
        r = E3HybridRouting(HybridConfiguration(cognition_weight=2, social_weight=2, epsilon=0.1))
        current = [EdgeId("e1")]; pbest = [EdgeId("e2")]; gbest = []
        val = r._compute_raw_pso(EdgeId("e3"), 0, current, pbest, gbest, inertia=1.0)
        assert val == pytest.approx(0.5)  # 1*0.1 + 2*0.1 + 2*0.1

    def test_visibility_missing(self):
        r = E3HybridRouting()
        r._visibility = {}
        assert r._compute_raw_visibility(EdgeId("e")) == 0.0


# =============================================================================
# 4. Normalisation (6 tests)
# =============================================================================


class TestNorm:

    def test_identical(self):
        assert E3HybridRouting._normalise_to_unit([5.0, 5.0]) == [1.0, 1.0]

    def test_range(self):
        res = E3HybridRouting._normalise_to_unit([1.0, 3.0, 5.0])
        assert res[0] == 0.0 and res[1] == 0.5 and res[2] == 1.0

    def test_single(self):
        assert E3HybridRouting._normalise_to_unit([7.0]) == [1.0]

    def test_empty(self):
        assert E3HybridRouting._normalise_to_unit([]) == []

    def test_equal_values(self):
        assert E3HybridRouting._normalise_to_unit([42.0, 42.0]) == [1.0, 1.0]

    def test_zero_range(self):
        assert E3HybridRouting._normalise_to_unit([0.0, 0.0]) == [1.0, 1.0]


# =============================================================================
# 5. Meta-controller (12 tests)
# =============================================================================


def _mc_routing(**kw: Any) -> E3HybridRouting:
    """Create a routing instance with initialised meta-controller state."""
    cfg = HybridConfiguration(**kw)
    r = E3HybridRouting(cfg)
    r._influence_weights = HybridInfluenceWeights(
        alpha_a=cfg.alpha_a, alpha_b=cfg.alpha_b,
        alpha_p=cfg.alpha_p, alpha_h=cfg.alpha_h,
    )
    r._low_diversity_counts = {"a": 0, "b": 0, "p": 0}
    return r


class TestMC:

    def test_no_activation_diverse(self):
        r = _mc_routing(adapt_interval=1, adapt_diversity_min=0.15)
        ab = r._influence_weights.alpha_a
        routes = [[EdgeId(f"e{i}")] for i in range(20)]
        kinds = [IndividualKind.ANT] * 7 + [IndividualKind.BEE] * 7 + [IndividualKind.PARTICLE] * 6
        r._update_meta_controller(1, routes, kinds)
        assert r._influence_weights.alpha_a == ab

    def test_single_decay(self):
        r = _mc_routing(adapt_interval=1, adapt_diversity_min=0.5)
        routes = [[EdgeId("e1")] for _ in range(9)]
        kinds = [IndividualKind.ANT] * 9
        r._update_meta_controller(1, routes, kinds)
        # all 3 subpopulations have diversity 0 (b and p have zero counts),
        # so all alpha values decay and the removed mass goes to alpha_h,
        # then normalisation brings a/b/p back near S_ref
        assert r._influence_weights.alpha_h == pytest.approx(1.3, rel=1e-6)

    def test_redistribute_non_decayed(self):
        r = _mc_routing(adapt_interval=1, adapt_diversity_min=0.5)
        routes = [[EdgeId("e1")] for _ in range(5)] + [[EdgeId(f"e{i}")] for i in range(5, 10)]
        kinds = [IndividualKind.ANT] * 5 + [IndividualKind.BEE] * 5
        r._update_meta_controller(1, routes, kinds)
        assert r._influence_weights.alpha_a < 1.0
        assert r._influence_weights.alpha_b > 1.0

    def test_all_decay_to_heuristic(self):
        r = _mc_routing(adapt_interval=1, adapt_diversity_min=0.5)
        hb = r._influence_weights.alpha_h
        routes = [[EdgeId("e1")] for _ in range(9)]
        kinds = [IndividualKind.ANT] * 3 + [IndividualKind.BEE] * 3 + [IndividualKind.PARTICLE] * 3
        r._update_meta_controller(1, routes, kinds)
        assert r._influence_weights.alpha_h > hb

    def test_recovery(self):
        r = _mc_routing(adapt_interval=1, adapt_diversity_min=0.5, adapt_recovery_gain=0.05)
        routes_lo = [[EdgeId("e1")] for _ in range(9)]
        kinds = [IndividualKind.ANT] * 9
        r._update_meta_controller(1, routes_lo, kinds)
        low = r._influence_weights.alpha_a
        routes_hi = [[EdgeId(f"e{i}")] for i in range(9)]
        r._update_meta_controller(6, routes_hi, kinds)
        assert r._influence_weights.alpha_a > low

    def test_normalisation_preserve_sum(self):
        r = _mc_routing(alpha_a=1.0, alpha_b=1.0, alpha_p=1.0)
        r._influence_weights.alpha_a = 0.5
        r._influence_weights.alpha_b = 0.5
        r._influence_weights.alpha_p = 2.0
        S = r._influence_weights.alpha_a + r._influence_weights.alpha_b + r._influence_weights.alpha_p
        r._normalise_influence_weights()
        assert r._influence_weights.alpha_a + r._influence_weights.alpha_b + r._influence_weights.alpha_p == pytest.approx(S)

    def test_no_update_before_interval(self):
        r = _mc_routing(adapt_interval=5)
        ab = r._influence_weights.alpha_a
        routes = [[EdgeId("e1")] for _ in range(9)]
        kinds = [IndividualKind.ANT] * 9
        r._update_meta_controller(1, routes, kinds)
        assert r._influence_weights.alpha_a == ab

    def test_bounds_enforced(self):
        r = _mc_routing(adapt_interval=1, adapt_diversity_min=0.5, alpha_a_min=0.5)
        routes = [[EdgeId("e1")] for _ in range(9)]
        kinds = [IndividualKind.ANT] * 9
        for i in range(1, 20):
            r._update_meta_controller(i, routes, kinds)
        assert r._influence_weights.alpha_a >= 0.5

    def test_no_op_empty(self):
        r = _mc_routing(adapt_interval=1)
        # empty routes: all diversities = 0, all subpops decay
        # removed mass goes to alpha_h, then norm brings a/b/p back near S_ref
        r._update_meta_controller(1, [], [])
        assert r._influence_weights.alpha_h == pytest.approx(1.3, rel=1e-6)

    def test_influence_weights_init(self):
        hw = HybridInfluenceWeights(alpha_a=1.5, alpha_b=2.5, alpha_p=0.5, alpha_h=3.0)
        assert hw.alpha_a == 1.5 and hw.alpha_p == 0.5

    def test_influence_weights_negative(self):
        with pytest.raises(ValueError, match="alpha_h"):
            HybridInfluenceWeights(alpha_h=-1.0)


# =============================================================================
# 6. Pheromone evolution (9 tests)
# =============================================================================


class TestPheromone:

    def test_local_update(self):
        pm = HybridPheromoneMatrix(1.0, 0.01, 10.0, {EdgeId("e1")})
        pm.set(EdgeId("e1"), 5.0)
        pm.local_update(EdgeId("e1"), 0.1)
        assert pm.get(EdgeId("e1")) == pytest.approx(4.6)

    def test_global_evaporation(self):
        pm = HybridPheromoneMatrix(1.0, 0.01, 10.0, {EdgeId("e1")})
        pm.set(EdgeId("e1"), 1.0)
        dep = 0.2
        updated = (1 - 0.1) * pm.get(EdgeId("e1")) + 0.1 * dep
        pm.set(EdgeId("e1"), updated)
        assert pm.get(EdgeId("e1")) == pytest.approx(0.92)

    def test_bounds_upper(self):
        pm = HybridPheromoneMatrix(1.0, 0.1, 5.0, {EdgeId("e1")})
        pm.set(EdgeId("e1"), 100.0)
        assert pm.get(EdgeId("e1")) == 5.0

    def test_bounds_lower(self):
        pm = HybridPheromoneMatrix(1.0, 0.1, 5.0, {EdgeId("e1")})
        pm.set(EdgeId("e1"), -100.0)
        assert pm.get(EdgeId("e1")) == 0.1

    def test_nan_positive(self):
        pm = HybridPheromoneMatrix(1.0, 0.01, 5.0, {EdgeId("e1")})
        pm.set(EdgeId("e1"), float("nan"))
        assert pm.get(EdgeId("e1")) == 0.01  # clamps to lower bound

    def test_nan_negative(self):
        pm = HybridPheromoneMatrix(1.0, 0.01, 5.0, {EdgeId("e1")})
        pm.set(EdgeId("e1"), float("-nan"))
        assert pm.get(EdgeId("e1")) == 0.01

    def test_initial(self):
        pm = HybridPheromoneMatrix(2.0, 0.01, 10.0, {EdgeId("e1"), EdgeId("e2")})
        assert pm.get(EdgeId("e1")) == 2.0

    def test_unknown_edge_min(self):
        pm = HybridPheromoneMatrix(1.0, 0.01, 10.0, set())
        assert pm.get(EdgeId("unknown")) == 0.01

    def test_clone_independent(self):
        pm = HybridPheromoneMatrix(1.0, 0.01, 10.0, {EdgeId("e1")})
        pm.set(EdgeId("e1"), 5.0)
        cl = pm.clone()
        cl.set(EdgeId("e1"), 3.0)
        assert pm.get(EdgeId("e1")) == 5.0
        assert cl.get(EdgeId("e1")) == 3.0


# =============================================================================
# 7. Template extraction (5 tests)
# =============================================================================


class TestTemplates:

    def _r(self, **kw) -> E3HybridRouting:
        return E3HybridRouting(HybridConfiguration(template_count=kw.get("count", 3)))

    def test_top_l(self):
        r = self._r()
        templates = r._extract_templates(
            [[EdgeId("a")], [EdgeId("b")], [EdgeId("c")], [EdgeId("d")]],
            [10.0, 5.0, 20.0, 1.0],
        )
        assert len(templates) == 3
        assert templates[0] == [EdgeId("d")]

    def test_fewer_than_l(self):
        r = self._r()
        t = r._extract_templates([[EdgeId("a")]], [5.0])
        assert len(t) == 1

    def test_no_complete(self):
        r = self._r()
        t = r._extract_templates([[], []], [float("inf"), float("inf")])
        assert t == []

    def test_count_zero(self):
        r = self._r(count=0)
        t = r._extract_templates([[EdgeId("a")]], [5.0])
        assert t == []

    def test_order_by_cost(self):
        r = self._r()
        t = r._extract_templates(
            [[EdgeId("x")], [EdgeId("y")], [EdgeId("z")]],
            [30.0, 10.0, 20.0],
        )
        assert t == [[EdgeId("y")], [EdgeId("z")], [EdgeId("x")]]


# =============================================================================
# 8. Personal / global best (4 tests)
# =============================================================================


class TestBest:

    def test_personal_improves(self):
        r = E3HybridRouting()
        r._individuals = [IndividualState(kind=IndividualKind.PARTICLE, p_best_route=[EdgeId("a")], p_best_cost=10.0)]
        pm = HybridPheromoneMatrix(1.0, 0.01, 10.0, set())
        r._backward_pass(
            [[EdgeId("b")]], [5.0],
            [IndividualKind.PARTICLE], [IndividualStatus.COMPLETE], pm,
        )
        assert r._individuals[0].p_best_cost == 5.0

    def test_personal_unchanged(self):
        r = E3HybridRouting()
        r._individuals = [IndividualState(kind=IndividualKind.PARTICLE, p_best_route=[EdgeId("a")], p_best_cost=5.0)]
        pm = HybridPheromoneMatrix(1.0, 0.01, 10.0, set())
        r._backward_pass(
            [[EdgeId("b")]], [10.0],
            [IndividualKind.PARTICLE], [IndividualStatus.COMPLETE], pm,
        )
        assert r._individuals[0].p_best_cost == 5.0

    def test_best_across_subpopulations(self):
        r = E3HybridRouting()
        r._individuals = [IndividualState(kind=k, p_best_cost=float("inf"))
                         for k in (IndividualKind.ANT, IndividualKind.BEE, IndividualKind.PARTICLE)]
        pm = HybridPheromoneMatrix(1.0, 0.01, 10.0, set())
        cost, route = r._backward_pass(
            [[EdgeId("x")], [EdgeId("y")], [EdgeId("z")]],
            [10.0, 5.0, 15.0],
            [IndividualKind.ANT, IndividualKind.BEE, IndividualKind.PARTICLE],
            [IndividualStatus.COMPLETE] * 3,
            pm,
        )
        assert cost == 5.0 and route == [EdgeId("y")]

    def test_iteration_best_returned(self):
        r = E3HybridRouting()
        r._individuals = [IndividualState(kind=IndividualKind.PARTICLE)]
        pm = HybridPheromoneMatrix(1.0, 0.01, 10.0, set())
        cost, _ = r._backward_pass(
            [[EdgeId("a")]], [15.0],
            [IndividualKind.PARTICLE], [IndividualStatus.COMPLETE], pm,
        )
        assert cost == 15.0


# =============================================================================
# 9. Deterministic replay (3 tests)
# =============================================================================


class TestDet:

    def test_same_seed_same_result(self):
        g = make_grid_graph(3, 3)
        results = []
        for _ in range(3):
            r = E3HybridRouting()
            ctx = make_context(g, seed=42)
            res = r.optimize(ctx)
            results.append((res.success, res.statistics.best_score, res.statistics.total_iterations))
        for i in range(1, 3):
            assert results[i] == results[0]

    def test_different_seed(self):
        g = make_grid_graph(3, 3)
        r1 = E3HybridRouting()
        r2 = E3HybridRouting()
        res1 = r1.optimize(make_context(g, seed=42))
        res2 = r2.optimize(make_context(g, seed=99))
        # Seeds produce different results with very high probability
        assert res1.iterations != res2.iterations

    def test_partition_deterministic(self):
        r = E3HybridRouting()
        k1 = r._assign_subpopulations(30)
        k2 = r._assign_subpopulations(30)
        assert k1 == k2


# =============================================================================
# 10. Cross-component / state / enums (6 tests)
# =============================================================================


class TestCross:

    def test_metadata_weights(self):
        g = make_grid_graph(3, 3)
        res = E3HybridRouting().optimize(make_context(g, seed=42))
        if res.success and res.best_solution:
            md = res.best_solution.metadata
            for k in ("alpha_a", "alpha_b", "alpha_p", "alpha_h"):
                assert k in md

    def test_individual_state_init(self):
        ind = IndividualState(kind=IndividualKind.ANT)
        assert ind.state == IndividualStatus.CONSTRUCTING and ind.cost == float("inf")

    def test_enums(self):
        assert IndividualStatus.COMPLETE.value == "complete"
        assert IndividualKind.BEE.value == "bee"

    def test_reset_route(self):
        ind = IndividualState(kind=IndividualKind.ANT, route=[EdgeId("e1")], cost=5.0,
                              state=IndividualStatus.COMPLETE)
        ind.reset_route()
        assert ind.route == [] and ind.cost == float("inf") and ind.state == IndividualStatus.CONSTRUCTING

    def test_hybrid_stats_validation(self):
        with pytest.raises(ValueError, match="iteration"):
            HybridStatistics(iteration=-1, best_cost=0.0, avg_cost=0.0, worst_cost=0.0, diversity=0.0,
                            alpha_a=1.0, alpha_b=1.0, alpha_p=1.0, alpha_h=1.0,
                            template_count=0, runtime_s=0.0)

    def test_hybrid_stats_runtime(self):
        with pytest.raises(ValueError, match="runtime_s"):
            HybridStatistics(iteration=0, best_cost=0.0, avg_cost=0.0, worst_cost=0.0, diversity=0.0,
                            alpha_a=1.0, alpha_b=1.0, alpha_p=1.0, alpha_h=1.0,
                            template_count=0, runtime_s=-1.0)


# =============================================================================
# 11. Factory integration (2 tests)
# =============================================================================


class TestFactory:

    def test_registered(self):
        from e3hybrid.swarm.factory import SwarmFactory
        assert SwarmFactory.is_registered("e3hybrid")

    def test_create(self):
        from e3hybrid.swarm.factory import SwarmFactory
        algo = SwarmFactory.create_algorithm("e3hybrid")
        assert algo.name == "e3hybrid"
        assert isinstance(algo, E3HybridRouting)


# =============================================================================
# 12. Helpers (inertia, diversity, visibility, edge cost) (8 tests)
# =============================================================================


class TestHelpers:

    def test_inertia_decay(self):
        r = E3HybridRouting(HybridConfiguration(inertia_start=0.9, inertia_end=0.4))
        assert r._compute_inertia(0, 100) == 0.9
        assert r._compute_inertia(100, 100) == 0.4
        assert r._compute_inertia(50, 100) == pytest.approx(0.65)

    def test_inertia_zero_iters(self):
        r = E3HybridRouting(HybridConfiguration())
        assert r._compute_inertia(0, 0) == 0.4

    def test_diversity_single(self):
        assert E3HybridRouting()._compute_diversity([[EdgeId("e1")]]) == 0.0

    def test_diversity_identical(self):
        assert E3HybridRouting()._compute_diversity([[EdgeId("e1")], [EdgeId("e1")]]) == 0.0

    def test_diversity_different(self):
        assert E3HybridRouting()._compute_diversity([[EdgeId("e1")], [EdgeId("e2")]]) == 1.0

    def test_visibility_build(self):
        g = make_grid_graph(3, 3)
        r = E3HybridRouting()
        ctx = make_context(g, seed=42)
        r._graph = ctx.graph
        r._cost_calculator = ctx.cost_calculator
        r._build_visibility()
        assert len(r._visibility) > 0

    def test_visibility_blocked(self):
        g = DirectedGraph()
        n1, n2 = NodeId("n1"), NodeId("n2")
        g.add_node(Node(n1)); g.add_node(Node(n2))
        e = Edge(EdgeId("e"), source=n1, target=n2, length_m=100.0, speed_limit_mps=10.0)
        e = e.with_state(EdgeState(is_blocked=True))
        g.add_edge(e)
        r = E3HybridRouting()
        ctx = make_context(g, seed=42)
        r._graph = g; r._cost_calculator = ctx.cost_calculator
        r._build_visibility()
        assert r._visibility.get(EdgeId("e"), 1.0) == 0.0

    def test_edge_total_cost_blocked(self):
        e = Edge(EdgeId("e"), source=NodeId("n1"), target=NodeId("n2"),
                length_m=100.0, speed_limit_mps=10.0)
        e = e.with_state(e.state)  # placeholder to avoid unused
        blocked = e.with_state(EdgeState(is_blocked=True))
        r = E3HybridRouting()
        r._cost_calculator = make_context(make_grid_graph(3, 3), seed=42).cost_calculator
        assert r._edge_total_cost(blocked) == float("inf")


# =============================================================================
# 13. Edge cases (7 tests)
# =============================================================================


class TestEdgeCases:

    def test_config_frozen(self):
        with pytest.raises(FrozenInstanceError):
            HybridConfiguration().ant_ratio = 0.5

    def test_failure_result(self):
        res = _failure_result("test")
        assert not res.success and res.failure_reason == "test" and res.best_solution is None

    def test_validate_context_source_dest_equal(self):
        from e3hybrid.swarm.hybrid import _validate_context
        from e3hybrid.swarm.context import SwarmContext
        from e3hybrid.swarm.config import SwarmConfig
        from e3hybrid.routing.cost_calculator import CostWeights
        from e3hybrid.routing.request import RoutingRequest
        # Build request with source == dest using object.__setattr__ to bypass __post_init__
        req = RoutingRequest.__new__(RoutingRequest)
        object.__setattr__(req, "source_node", NodeId("a"))
        object.__setattr__(req, "destination_node", NodeId("a"))
        object.__setattr__(req, "vehicle_id", VehicleId("v1"))
        object.__setattr__(req, "vehicle_constraints", {})
        object.__setattr__(req, "battery_state", {})
        object.__setattr__(req, "max_candidates", 5)
        object.__setattr__(req, "timeout_s", 30.0)
        object.__setattr__(req, "metadata", {})
        ctx = SwarmContext(
            cost_weights=CostWeights(), config=SwarmConfig(), random_seed=42,
            routing_request=req,
            sim_time_s=0.0,
        )
        errs = _validate_context(ctx)
        assert any("source and destination must differ" in e for e in errs)

    def test_optimize_small_grid(self):
        g = make_grid_graph(3, 3)
        res = E3HybridRouting().optimize(make_context(g, seed=42))
        assert res.success and res.best_solution is not None

    def test_optimize_line(self):
        res = E3HybridRouting().optimize(make_context(make_simple_graph(), seed=42))
        assert res.success

    def test_optimize_converges(self):
        res = E3HybridRouting().optimize(make_context(make_grid_graph(2, 2), seed=42))
        assert res.success and len(res.iterations) > 0

    def test_assign_subpopulations_types(self):
        kinds = E3HybridRouting()._assign_subpopulations(9)
        assert IndividualKind.ANT in kinds
        assert IndividualKind.BEE in kinds
        assert IndividualKind.PARTICLE in kinds


# =============================================================================
# 14. Cross-component metadata verification (2 tests)
# =============================================================================


class TestCrossMeta:

    def test_candidate_has_hybrid_algorithm(self):
        res = E3HybridRouting().optimize(make_context(make_grid_graph(3, 3), seed=42))
        if res.success and res.best_solution:
            assert res.best_solution.algorithm == "e3hybrid"

    def test_subpopulation_counts_in_metadata(self):
        res = E3HybridRouting().optimize(make_context(make_grid_graph(3, 3), seed=42))
        if res.success and res.best_solution:
            md = res.best_solution.metadata
            for k in ("ant_count", "bee_count", "particle_count"):
                assert k in md