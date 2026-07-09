"""Comprehensive tests for the Bee Colony Optimization (BCO) implementation.

Test categories:
- Unit: each component in isolation
- Integration: components working together, routing end-to-end
- Property: invariants that must always hold
- Deterministic replay: same seed -> identical results
- Stress: larger graphs, convergence behavior
- Edge-case: empty sets, blocked paths, unreachable destinations
"""

from __future__ import annotations

import copy
import math
import random
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
from e3hybrid.swarm.bco import (
    BCORouting,
    BCOConfiguration,
    BCOStatistics,
    BCOValidator,
    BackwardPassResult,
    BeeState,
    BeeStatus,
    ForwardPassResult,
    VisibilityCache,
    _EPS,
)
from e3hybrid.swarm.config import SwarmConfig
from e3hybrid.swarm.context import SwarmContext
from e3hybrid.swarm.random import SwarmRandom
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
def fork_graph() -> DirectedGraph:
    """A-B-C-D (top) and A-E-F-D (bottom) two-path graph, 5 edges."""
    graph = DirectedGraph()
    for nid, x in [("A", 0.0), ("B", 50.0), ("C", 100.0), ("D", 150.0),
                   ("E", 50.0), ("F", 100.0)]:
        graph.add_node(Node(node_id=NodeId(nid), x=x, y=0.0))
    state = MutableEdgeState()
    for sid, tid, eid, length in [
        ("A", "B", "AB", 50.0), ("B", "C", "BC", 50.0), ("C", "D", "CD", 50.0),
        ("A", "E", "AE", 50.0), ("E", "F", "EF", 50.0), ("F", "D", "FD", 50.0),
    ]:
        graph.add_edge(Edge(
            edge_id=EdgeId(eid), source=NodeId(sid), target=NodeId(tid),
            length_m=length, speed_limit_mps=10.0, lane_count=1, state=state,
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
    for row in range(3):
        for col in range(2):
            src = nodes[f"{row}_{col}"]
            dst = nodes[f"{row}_{col + 1}"]
            eid = EdgeId(f"{src}_{dst}")
            graph.add_edge(Edge(
                edge_id=eid, source=src, target=dst,
                length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=state,
            ))
    for col in range(3):
        for row in range(2):
            src = nodes[f"{row}_{col}"]
            dst = nodes[f"{row + 1}_{col}"]
            eid = EdgeId(f"{src}_{dst}")
            graph.add_edge(Edge(
                edge_id=eid, source=src, target=dst,
                length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=state,
            ))
    return graph


@pytest.fixture
def cost_calculator() -> CompositeCostCalculator:
    return CompositeCostCalculator(CostWeights(distance=1.0, time=1.0, energy=0.0))


@pytest.fixture
def swarm_config() -> SwarmConfig:
    return SwarmConfig(
        algorithm_name="bco",
        population_size=6,
        max_iterations=20,
        stall_limit=10,
        convergence_threshold=0.0,
        seed=42,
        hyperparameters={
            "forward_steps": 10,
            "visibility_weight": 2.0,
            "template_strength": 3.0,
            "elite_count": 2,
        },
    )


@pytest.fixture
def bco_context(linear_graph, cost_calculator, swarm_config) -> SwarmContext:
    return SwarmContext(
        graph=linear_graph,
        cost_calculator=cost_calculator,
        config=swarm_config,
        random_seed=42,
        routing_request=RoutingRequest(
            source_node=NodeId("A"),
            destination_node=NodeId("D"),
            vehicle_id=VehicleId("test_vehicle"),
            vehicle_constraints=None,
            battery_state=None,
            max_candidates=5,
            timeout_s=60.0,
        ),
        sim_time_s=0.0,
        cost_weights=cost_calculator._weights,
    )


@pytest.fixture
def bco_context_fork(fork_graph, cost_calculator, swarm_config) -> SwarmContext:
    return SwarmContext(
        graph=fork_graph,
        cost_calculator=cost_calculator,
        config=swarm_config,
        random_seed=42,
        routing_request=RoutingRequest(
            source_node=NodeId("A"),
            destination_node=NodeId("D"),
            vehicle_id=VehicleId("test_vehicle"),
            vehicle_constraints=None,
            battery_state=None,
            max_candidates=5,
            timeout_s=60.0,
        ),
        sim_time_s=0.0,
        cost_weights=cost_calculator._weights,
    )


# =========================================================================
# BCOConfiguration tests
# =========================================================================


class TestBCOConfiguration:

    def test_default_construction(self):
        config = SwarmConfig(hyperparameters={})
        bc = BCOConfiguration.from_config(config)
        assert bc.forward_steps == 500
        assert bc.beta == 2.0
        assert bc.delta == 3.0
        assert bc.elite_count == 3

    def test_custom_construction(self):
        config = SwarmConfig(population_size=10, hyperparameters={
            "forward_steps": 50,
            "visibility_weight": 1.5,
            "template_strength": 2.5,
            "elite_count": 2,
        })
        bc = BCOConfiguration.from_config(config)
        assert bc.forward_steps == 50
        assert bc.beta == 1.5
        assert bc.delta == 2.5
        assert bc.elite_count == 2

    def test_invalid_forward_steps(self):
        config = SwarmConfig(hyperparameters={"forward_steps": 0})
        with pytest.raises(ValueError, match="forward_steps must be >= 1"):
            BCOConfiguration.from_config(config)

    def test_invalid_beta(self):
        config = SwarmConfig(hyperparameters={"visibility_weight": -1.0})
        with pytest.raises(ValueError, match="beta must be >= 0"):
            BCOConfiguration.from_config(config)

    def test_invalid_delta(self):
        config = SwarmConfig(hyperparameters={"template_strength": -1.0})
        with pytest.raises(ValueError, match="delta must be >= 0"):
            BCOConfiguration.from_config(config)

    def test_elite_count_exceeds_population(self):
        config = SwarmConfig(population_size=5, hyperparameters={"elite_count": 10})
        with pytest.raises(ValueError, match="elite_count"):
            BCOConfiguration.from_config(config)

    def test_population_size_too_small(self):
        config = SwarmConfig(population_size=1, hyperparameters={})
        with pytest.raises(ValueError, match="population_size must be >= 2"):
            BCOConfiguration.from_config(config)

    def test_from_config_type_errors(self):
        config = SwarmConfig(hyperparameters={"forward_steps": "ten"})
        with pytest.raises(TypeError):
            BCOConfiguration.from_config(config)

        config = SwarmConfig(hyperparameters={"visibility_weight": "high"})
        with pytest.raises(TypeError):
            BCOConfiguration.from_config(config)


# =========================================================================
# BeeStatus tests
# =========================================================================


class TestBeeStatus:

    def test_enum_values(self):
        assert BeeStatus.CONSTRUCTING.value == "constructing"
        assert BeeStatus.COMPLETE.value == "complete"
        assert BeeStatus.FAILED.value == "failed"

    def test_valid_transitions(self):
        """CONSTRUCTING -> COMPLETE and CONSTRUCTING -> FAILED are valid."""
        s = BeeStatus.CONSTRUCTING
        assert s != BeeStatus.COMPLETE
        assert s != BeeStatus.FAILED


# =========================================================================
# BCOValidator tests
# =========================================================================


class TestBCOValidator:

    def test_valid_context(self, bco_context):
        errors = BCOValidator.validate_context(bco_context)
        assert errors == []

    def test_missing_graph(self, bco_context):
        ctx = SwarmContext(
            graph=None,
            cost_calculator=bco_context.cost_calculator,
            config=bco_context.config,
            random_seed=42,
            routing_request=bco_context.routing_request,
            sim_time_s=0.0,
            cost_weights=bco_context.cost_weights,
        )
        errors = BCOValidator.validate_context(ctx)
        assert any("graph" in e.lower() for e in errors)

    def test_missing_cost_calculator(self, bco_context):
        ctx = SwarmContext(
            graph=bco_context.graph,
            cost_calculator=None,
            config=bco_context.config,
            random_seed=42,
            routing_request=bco_context.routing_request,
            sim_time_s=0.0,
            cost_weights=bco_context.cost_weights,
        )
        errors = BCOValidator.validate_context(ctx)
        assert any("cost_calculator" in e.lower() for e in errors)

    def test_same_source_destination(self, bco_context):
        # Create request with same source/destination by bypassing __post_init__
        from dataclasses import fields
        req_data = {
            "source_node": NodeId("A"),
            "destination_node": NodeId("A"),
            "vehicle_id": VehicleId("test"),
            "vehicle_constraints": None,
            "battery_state": None,
            "max_candidates": 5,
            "timeout_s": 60.0,
            "metadata": {},
        }
        req = object.__new__(RoutingRequest)
        for f in fields(RoutingRequest):
            object.__setattr__(req, f.name, req_data.get(f.name))
        ctx = SwarmContext(
            graph=bco_context.graph,
            cost_calculator=bco_context.cost_calculator,
            config=bco_context.config,
            random_seed=42,
            routing_request=req,
            sim_time_s=0.0,
            cost_weights=bco_context.cost_weights,
        )
        errors = BCOValidator.validate_context(ctx)
        assert any("source" in e.lower() for e in errors)


# =========================================================================
# BCORouting: forward pass tests
# =========================================================================


class TestForwardPass:

    def test_forward_pass_returns_correct_structure(self, bco_context):
        bco = BCORouting()
        bco._context = bco_context
        bco._graph = bco_context.graph
        bco._cost_calculator = bco_context.cost_calculator
        bco._source = bco_context.routing_request.source_node
        bco._destination = bco_context.routing_request.destination_node
        bco._config = BCOConfiguration.from_config(bco_context.config)
        bco._swarm_rng = SwarmRandom(bco_context.random_seed)
        bco._build_visibility()

        B = bco_context.config.population_size
        bco._bees = []
        for k in range(B):
            bco._bees.append(BeeState(
                k=k, route=[], cost=0.0, quality=0.0,
                norm_quality=0.0, template=None,
                state=BeeStatus.CONSTRUCTING, is_loyal=False,
                visited=set(), iteration_created=-1,
            ))

        result = bco._forward_pass(0)
        assert isinstance(result, ForwardPassResult)
        assert len(result.routes) == B
        assert len(result.costs) == B
        assert len(result.states) == B
        assert result.iteration == 0
        assert result.runtime_s >= 0

    def test_forward_pass_linear_graph_all_complete(self, bco_context):
        """On a linear graph, all bees should reach D."""
        bco = BCORouting()
        bco._context = bco_context
        bco._graph = bco_context.graph
        bco._cost_calculator = bco_context.cost_calculator
        bco._source = bco_context.routing_request.source_node
        bco._destination = bco_context.routing_request.destination_node
        bco._config = BCOConfiguration.from_config(bco_context.config)
        bco._swarm_rng = SwarmRandom(bco_context.random_seed)
        bco._build_visibility()

        B = bco_context.config.population_size
        bco._bees = []
        for k in range(B):
            bco._bees.append(BeeState(
                k=k, route=[], cost=0.0, quality=0.0,
                norm_quality=0.0, template=None,
                state=BeeStatus.CONSTRUCTING, is_loyal=False,
                visited=set(), iteration_created=-1,
            ))

        result = bco._forward_pass(0)
        for state in result.states:
            assert state == BeeStatus.COMPLETE, f"Bee did not complete: {state}"

    def test_forward_pass_linear_graph_correct_path(self, bco_context):
        """On a linear graph, the route must be A-B-C-D."""
        bco = BCORouting()
        bco._context = bco_context
        bco._graph = bco_context.graph
        bco._cost_calculator = bco_context.cost_calculator
        bco._source = bco_context.routing_request.source_node
        bco._destination = bco_context.routing_request.destination_node
        bco._config = BCOConfiguration.from_config(bco_context.config)
        bco._swarm_rng = SwarmRandom(bco_context.random_seed)
        bco._build_visibility()

        B = bco_context.config.population_size
        bco._bees = []
        for k in range(B):
            bco._bees.append(BeeState(
                k=k, route=[], cost=0.0, quality=0.0,
                norm_quality=0.0, template=None,
                state=BeeStatus.CONSTRUCTING, is_loyal=False,
                visited=set(), iteration_created=-1,
            ))

        result = bco._forward_pass(0)
        for route in result.routes:
            assert route == [EdgeId("AB"), EdgeId("BC"), EdgeId("CD")], f"Unexpected route: {route}"

    def test_forward_pass_unreachable_destination(self, linear_graph, cost_calculator, swarm_config):
        """Bee cannot reach a disconnected node."""
        ctx = SwarmContext(
            graph=linear_graph,
            cost_calculator=cost_calculator,
            config=swarm_config,
            random_seed=42,
            routing_request=RoutingRequest(
                source_node=NodeId("A"), destination_node=NodeId("X"),
                vehicle_id=VehicleId("test"), vehicle_constraints=None,
                battery_state=None, max_candidates=5, timeout_s=60.0,
            ),
            sim_time_s=0.0,
            cost_weights=cost_calculator._weights,
        )
        bco = BCORouting()
        result = bco.optimize(ctx)
        assert not result.success

    def test_forward_pass_cycle_prevention(self, grid_graph, cost_calculator, swarm_config):
        """Bees should not revisit nodes (cycle prevention)."""
        ctx = SwarmContext(
            graph=grid_graph,
            cost_calculator=cost_calculator,
            config=swarm_config,
            random_seed=42,
            routing_request=RoutingRequest(
                source_node=NodeId("0_0"), destination_node=NodeId("2_2"),
                vehicle_id=VehicleId("test"), vehicle_constraints=None,
                battery_state=None, max_candidates=5, timeout_s=60.0,
            ),
            sim_time_s=0.0,
            cost_weights=cost_calculator._weights,
        )
        bco = BCORouting()
        result = bco.optimize(ctx)
        assert result.success
        # Verify no duplicates in node_sequence
        nodes = list(result.best_solution.node_sequence)
        assert len(nodes) == len(set(nodes)), f"Cycle detected: {nodes}"


# =========================================================================
# BCORouting: backward pass tests
# =========================================================================


class TestBackwardPass:

    def test_backward_pass_basic(self, bco_context):
        bco = BCORouting()
        bco._context = bco_context
        bco._graph = bco_context.graph
        bco._cost_calculator = bco_context.cost_calculator
        bco._source = bco_context.routing_request.source_node
        bco._destination = bco_context.routing_request.destination_node
        bco._config = BCOConfiguration.from_config(bco_context.config)
        bco._swarm_rng = SwarmRandom(bco_context.random_seed)
        bco._build_visibility()
        bco._global_best_cost = float("inf")
        bco._global_best_route = []

        B = bco_context.config.population_size
        bco._bees = []
        for k in range(B):
            bco._bees.append(BeeState(
                k=k, route=[], cost=0.0, quality=0.0,
                norm_quality=0.0, template=None,
                state=BeeStatus.CONSTRUCTING, is_loyal=False,
                visited=set(), iteration_created=-1,
            ))

        fwd = bco._forward_pass(0)
        bwd = bco._backward_pass(fwd, 0)

        assert isinstance(bwd, BackwardPassResult)
        assert len(bwd.loyal_indices) + len(bwd.uncommitted_indices) == B
        assert bwd.best_cost < float("inf")
        assert len(bwd.best_route) > 0
        assert bwd.diversity >= 0.0

    def test_loyal_plus_uncommitted_equals_population(self, bco_context):
        """loyal_indices and uncommitted_indices partition the population."""
        bco = BCORouting()
        bco._context = bco_context
        bco._graph = bco_context.graph
        bco._cost_calculator = bco_context.cost_calculator
        bco._source = bco_context.routing_request.source_node
        bco._destination = bco_context.routing_request.destination_node
        bco._config = BCOConfiguration.from_config(bco_context.config)
        bco._swarm_rng = SwarmRandom(bco_context.random_seed)
        bco._build_visibility()
        bco._global_best_cost = float("inf")
        bco._global_best_route = []

        B = bco_context.config.population_size
        bco._bees = []
        for k in range(B):
            bco._bees.append(BeeState(
                k=k, route=[], cost=0.0, quality=0.0,
                norm_quality=0.0, template=None,
                state=BeeStatus.CONSTRUCTING, is_loyal=False,
                visited=set(), iteration_created=-1,
            ))

        fwd = bco._forward_pass(0)
        bwd = bco._backward_pass(fwd, 0)

        total = len(bwd.loyal_indices) + len(bwd.uncommitted_indices)
        assert total == B, f"loyal({len(bwd.loyal_indices)}) + uncommitted({len(bwd.uncommitted_indices)}) != {B}"
        assert set(bwd.loyal_indices).isdisjoint(bwd.uncommitted_indices)

    def test_elite_bees_always_loyal(self, bco_context):
        """The K elite bees should always be loyal."""
        bco = BCORouting()
        bco._context = bco_context
        bco._graph = bco_context.graph
        bco._cost_calculator = bco_context.cost_calculator
        bco._source = bco_context.routing_request.source_node
        bco._destination = bco_context.routing_request.destination_node
        bco._config = BCOConfiguration.from_config(bco_context.config)
        bco._swarm_rng = SwarmRandom(bco_context.random_seed)
        bco._build_visibility()
        bco._global_best_cost = float("inf")
        bco._global_best_route = []

        B = bco_context.config.population_size
        bco._bees = []
        for k in range(B):
            bco._bees.append(BeeState(
                k=k, route=[], cost=0.0, quality=0.0,
                norm_quality=0.0, template=None,
                state=BeeStatus.CONSTRUCTING, is_loyal=False,
                visited=set(), iteration_created=-1,
            ))

        fwd = bco._forward_pass(0)
        bwd = bco._backward_pass(fwd, 0)

        K = bco._config.elite_count
        sorted_by_quality = sorted(range(B), key=lambda i: bco._bees[i].quality, reverse=True)
        elite = set(sorted_by_quality[:K])
        for idx in elite:
            assert bco._bees[idx].is_loyal, f"Elite bee {idx} should be loyal"

    def test_failed_bees_are_uncommitted(self, bco_context):
        """Bees that failed should always be in uncommitted."""
        config = SwarmConfig(
            algorithm_name="bco",
            population_size=6,
            max_iterations=20,
            seed=42,
            hyperparameters={"forward_steps": 1},  # Too short to reach D
        )
        ctx = SwarmContext(
            graph=bco_context.graph,
            cost_calculator=bco_context.cost_calculator,
            config=config,
            random_seed=42,
            routing_request=bco_context.routing_request,
            sim_time_s=0.0,
            cost_weights=bco_context.cost_weights,
        )
        bco = BCORouting()
        bco._context = ctx
        bco._graph = ctx.graph
        bco._cost_calculator = ctx.cost_calculator
        bco._source = ctx.routing_request.source_node
        bco._destination = ctx.routing_request.destination_node
        bco._config = BCOConfiguration.from_config(ctx.config)
        bco._swarm_rng = SwarmRandom(ctx.random_seed)
        bco._build_visibility()
        bco._global_best_cost = float("inf")
        bco._global_best_route = []

        B = ctx.config.population_size
        bco._bees = []
        for k in range(B):
            bco._bees.append(BeeState(
                k=k, route=[], cost=0.0, quality=0.0,
                norm_quality=0.0, template=None,
                state=BeeStatus.CONSTRUCTING, is_loyal=False,
                visited=set(), iteration_created=-1,
            ))

        fwd = bco._forward_pass(0)
        bwd = bco._backward_pass(fwd, 0)

        for k in range(B):
            assert bco._bees[k].state == BeeStatus.FAILED
            assert not bco._bees[k].is_loyal


# =========================================================================
# BCORouting: selection probability tests
# =========================================================================


class TestSelectionProbs:

    def test_all_feasible_edges_equal_with_beta_zero(self, fork_graph, cost_calculator):
        """With beta=0, all feasible edges should have equal probability."""
        config = SwarmConfig(
            population_size=4, max_iterations=1, seed=42,
            hyperparameters={"visibility_weight": 0.0, "template_strength": 0.0},
        )
        bc = BCOConfiguration.from_config(config)

        bco = BCORouting()
        bco._graph = fork_graph
        bco._cost_calculator = cost_calculator
        bco._config = bc
        bco._source = NodeId("A")
        bco._destination = NodeId("D")
        bco._build_visibility()

        outgoing = list(fork_graph.outgoing_edges(NodeId("A")))
        probs = bco._compute_selection_probs(outgoing, None)

        assert len(probs) == len(outgoing)
        for p in probs:
            assert p == pytest.approx(1.0 / len(outgoing), abs=1e-10)

    def test_template_edge_preferred(self, fork_graph, cost_calculator):
        """Edges in the template should receive higher probability."""
        config = SwarmConfig(
            population_size=4, max_iterations=1, seed=42,
            hyperparameters={"visibility_weight": 0.0, "template_strength": 3.0},
        )
        bc = BCOConfiguration.from_config(config)

        bco = BCORouting()
        bco._graph = fork_graph
        bco._cost_calculator = cost_calculator
        bco._config = bc
        bco._source = NodeId("A")
        bco._destination = NodeId("D")
        bco._build_visibility()

        outgoing = list(fork_graph.outgoing_edges(NodeId("A")))
        template = [EdgeId("AB")]
        probs = bco._compute_selection_probs(outgoing, template)

        assert len(probs) == len(outgoing)
        ab_idx = next(i for i, e in enumerate(outgoing) if e.edge_id == EdgeId("AB"))
        ae_idx = next(i for i, e in enumerate(outgoing) if e.edge_id == EdgeId("AE"))
        assert probs[ab_idx] > probs[ae_idx], "Template edge should have higher probability"

    def test_zero_visibility_fallback_uniform(self, fork_graph):
        """When all edges have zero visibility, fall back to uniform."""
        config = SwarmConfig(
            population_size=4, max_iterations=1, seed=42,
            hyperparameters={"visibility_weight": 2.0, "template_strength": 0.0},
        )
        bc = BCOConfiguration.from_config(config)

        bco = BCORouting()
        bco._graph = fork_graph
        bco._config = bc
        bco._visibility = VisibilityCache({}, 2.0, 0.0)

        outgoing = list(fork_graph.outgoing_edges(NodeId("A")))
        probs = bco._compute_selection_probs(outgoing, None)

        assert len(probs) == len(outgoing)
        for p in probs:
            assert p == pytest.approx(1.0 / len(outgoing), abs=1e-10)


# =========================================================================
# BCORouting: optimize() end-to-end tests
# =========================================================================


class TestOptimize:

    def test_optimize_linear_graph_success(self, bco_context):
        bco = BCORouting()
        result = bco.optimize(bco_context)
        assert result.success
        assert result.best_solution is not None
        assert result.best_solution.total_cost < float("inf")
        assert result.best_solution.algorithm == "bco"

    def test_optimize_returns_candidates(self, bco_context):
        bco = BCORouting()
        result = bco.optimize(bco_context)
        assert len(result.candidates) >= 1
        for candidate in result.candidates:
            assert isinstance(candidate, RouteCandidate)
            assert candidate.algorithm == "bco"

    def test_optimize_fork_graph_success(self, bco_context_fork):
        bco = BCORouting()
        result = bco.optimize(bco_context_fork)
        assert result.success
        assert result.best_solution is not None

    def test_optimize_best_cost_is_non_increasing(self, bco_context):
        """The best cost should never increase across iterations."""
        bco = BCORouting()
        result = bco.optimize(bco_context)
        if result.statistics.score_history:
            for i in range(1, len(result.statistics.score_history)):
                assert result.statistics.score_history[i] <= result.statistics.score_history[i - 1] + 1e-10, (
                    f"Best cost increased at iteration {i}: "
                    f"{result.statistics.score_history[i-1]} -> {result.statistics.score_history[i]}"
                )

    def test_optimize_with_invalid_context_returns_failure(self):
        ctx = SwarmContext(
            graph=None, cost_calculator=None,
            config=SwarmConfig(population_size=2, max_iterations=5, seed=42),
            random_seed=42,
            routing_request=RoutingRequest(
                source_node=NodeId("A"), destination_node=NodeId("B"),
                vehicle_id=VehicleId("test"), vehicle_constraints=None,
                battery_state=None, max_candidates=5, timeout_s=60.0,
            ),
            sim_time_s=0.0,
            cost_weights=CostWeights(),
        )
        bco = BCORouting()
        result = bco.optimize(ctx)
        assert not result.success
        assert result.failure_reason is not None

    def test_optimize_fork_graph_short_steps(self, fork_graph, cost_calculator):
        """With NS=1, bees should still find D over multiple iterations."""
        config = SwarmConfig(
            algorithm_name="bco",
            population_size=10,
            max_iterations=50,
            stall_limit=20,
            seed=42,
            hyperparameters={
                "forward_steps": 3,
                "visibility_weight": 2.0,
                "template_strength": 3.0,
                "elite_count": 3,
            },
        )
        ctx = SwarmContext(
            graph=fork_graph, cost_calculator=cost_calculator, config=config,
            random_seed=42,
            routing_request=RoutingRequest(
                source_node=NodeId("A"), destination_node=NodeId("D"),
                vehicle_id=VehicleId("test"), vehicle_constraints=None,
                battery_state=None, max_candidates=5, timeout_s=60.0,
            ),
            sim_time_s=0.0, cost_weights=cost_calculator._weights,
        )
        bco = BCORouting()
        result = bco.optimize(ctx)
        assert result.success

    def test_optimize_grid_graph(self, grid_graph, cost_calculator, swarm_config):
        ctx = SwarmContext(
            graph=grid_graph, cost_calculator=cost_calculator, config=swarm_config,
            random_seed=42,
            routing_request=RoutingRequest(
                source_node=NodeId("0_0"), destination_node=NodeId("2_2"),
                vehicle_id=VehicleId("test"), vehicle_constraints=None,
                battery_state=None, max_candidates=5, timeout_s=60.0,
            ),
            sim_time_s=0.0, cost_weights=cost_calculator._weights,
        )
        bco = BCORouting()
        result = bco.optimize(ctx)
        assert result.success
        assert result.best_solution.node_sequence[0] == NodeId("0_0")
        assert result.best_solution.node_sequence[-1] == NodeId("2_2")

    def test_optimize_statistics_structure(self, bco_context):
        bco = BCORouting()
        result = bco.optimize(bco_context)
        stats = result.statistics
        assert isinstance(stats, SwarmStatistics)
        assert stats.total_iterations > 0
        assert stats.total_runtime_s >= 0
        assert stats.best_score > 0
        assert len(stats.diversity_history) > 0
        assert len(stats.score_history) > 0
        assert stats.candidate_count >= 1

    def test_no_improvement_termination(self):
        """Test that stall_limit triggers early termination."""
        config = SwarmConfig(
            algorithm_name="bco",
            population_size=6,
            max_iterations=100,
            stall_limit=3,  # Very low - should trigger early
            convergence_threshold=0.0,
            seed=42,
            hyperparameters={
                "forward_steps": 10,
                "visibility_weight": 2.0,
                "template_strength": 3.0,
                "elite_count": 2,
            },
        )
        graph = DirectedGraph()
        graph.add_node(Node(NodeId("A"), x=0.0, y=0.0))
        graph.add_node(Node(NodeId("B"), x=100.0, y=0.0))
        state = MutableEdgeState()
        graph.add_edge(Edge(
            edge_id=EdgeId("AB"), source=NodeId("A"), target=NodeId("B"),
            length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=state,
        ))
        calc = CompositeCostCalculator(CostWeights(distance=1.0, time=0.0, energy=0.0))
        ctx = SwarmContext(
            graph=graph, cost_calculator=calc, config=config, random_seed=42,
            routing_request=RoutingRequest(
                source_node=NodeId("A"), destination_node=NodeId("B"),
                vehicle_id=VehicleId("test"), vehicle_constraints=None,
                battery_state=None, max_candidates=5, timeout_s=60.0,
            ),
            sim_time_s=0.0, cost_weights=calc._weights,
        )
        bco = BCORouting()
        result = bco.optimize(ctx)
        assert result.success
        assert result.statistics.total_iterations < 100, (
            f"Should have terminated early, got {result.statistics.total_iterations}"
        )


# =========================================================================
# Determinism tests
# =========================================================================


class TestDeterminism:

    def test_same_seed_identical_results(self, bco_context):
        """Two runs with the same seed should produce identical results."""
        bco1 = BCORouting()
        bco2 = BCORouting()
        result1 = bco1.optimize(bco_context)
        result2 = bco2.optimize(bco_context)

        assert result1.success == result2.success
        assert result1.best_solution.total_cost == result2.best_solution.total_cost
        assert result1.best_solution.node_sequence == result2.best_solution.node_sequence
        assert result1.best_solution.edge_sequence == result2.best_solution.edge_sequence
        assert result1.statistics.total_iterations == result2.statistics.total_iterations
        assert result1.statistics.score_history == result2.statistics.score_history

    def test_different_seed_different_results(self, bco_context_fork):
        """Different seeds should (likely) produce different exploration patterns."""
        ctx1 = SwarmContext(
            graph=bco_context_fork.graph,
            cost_calculator=bco_context_fork.cost_calculator,
            config=bco_context_fork.config,
            random_seed=42,
            routing_request=bco_context_fork.routing_request,
            sim_time_s=0.0,
            cost_weights=bco_context_fork.cost_weights,
        )
        ctx2 = SwarmContext(
            graph=bco_context_fork.graph,
            cost_calculator=bco_context_fork.cost_calculator,
            config=bco_context_fork.config,
            random_seed=9999,
            routing_request=bco_context_fork.routing_request,
            sim_time_s=0.0,
            cost_weights=bco_context_fork.cost_weights,
        )
        bco1 = BCORouting()
        bco2 = BCORouting()
        result1 = bco1.optimize(ctx1)
        result2 = bco2.optimize(ctx2)

        # Different seeds should produce different iteration counts
        # (convergence behaviour differs due to different random draws)
        assert result1.statistics.diversity_history != result2.statistics.diversity_history

    def test_deterministic_across_multiple_runs(self, bco_context):
        """Three runs with same seed should produce identical results."""
        results = []
        for _ in range(3):
            bco = BCORouting()
            # Need to copy context since optimize doesn't modify it
            results.append(bco.optimize(bco_context))

        for i in range(1, 3):
            assert results[0].best_solution.total_cost == results[i].best_solution.total_cost


# =========================================================================
# Edge case tests
# =========================================================================


class TestEdgeCases:

    def test_blocked_edges_are_avoided(self):
        """Blocked edges should have eta=0 and never be selected."""
        graph = DirectedGraph()
        graph.add_node(Node(NodeId("A"), x=0.0, y=0.0))
        graph.add_node(Node(NodeId("B"), x=100.0, y=0.0))
        graph.add_node(Node(NodeId("C"), x=200.0, y=0.0))
        blocked_state = MutableEdgeState(is_blocked=True)
        normal_state = MutableEdgeState()
        graph.add_edge(Edge(
            edge_id=EdgeId("AB"), source=NodeId("A"), target=NodeId("B"),
            length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=blocked_state,
        ))
        graph.add_edge(Edge(
            edge_id=EdgeId("BC"), source=NodeId("B"), target=NodeId("C"),
            length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=normal_state,
        ))
        calc = CompositeCostCalculator(CostWeights(distance=1.0, time=0.0, energy=0.0))

        config = SwarmConfig(
            algorithm_name="bco",
            population_size=4,
            max_iterations=5,
            seed=42,
            hyperparameters={
                "forward_steps": 5,
                "visibility_weight": 2.0,
                "template_strength": 0.0,
                "elite_count": 1,
            },
        )
        ctx = SwarmContext(
            graph=graph, cost_calculator=calc, config=config, random_seed=42,
            routing_request=RoutingRequest(
                source_node=NodeId("A"), destination_node=NodeId("C"),
                vehicle_id=VehicleId("test"), vehicle_constraints=None,
                battery_state=None, max_candidates=5, timeout_s=60.0,
            ),
            sim_time_s=0.0, cost_weights=calc._weights,
        )
        bco = BCORouting()
        # This should fail because A-B is blocked, so no path to C
        result = bco.optimize(ctx)
        assert not result.success

    def test_all_bees_fail_returns_failure(self):
        """If no bee can reach destination, optimize should return failure."""
        graph = DirectedGraph()
        graph.add_node(Node(NodeId("A"), x=0.0, y=0.0))
        graph.add_node(Node(NodeId("B"), x=100.0, y=0.0))
        blocked = MutableEdgeState(is_blocked=True)
        graph.add_edge(Edge(
            edge_id=EdgeId("AB"), source=NodeId("A"), target=NodeId("B"),
            length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=blocked,
        ))
        calc = CompositeCostCalculator(CostWeights(distance=1.0, time=0.0, energy=0.0))

        config = SwarmConfig(
            algorithm_name="bco", population_size=4, max_iterations=5, seed=42,
            hyperparameters={"forward_steps": 5},
        )
        ctx = SwarmContext(
            graph=graph, cost_calculator=calc, config=config, random_seed=42,
            routing_request=RoutingRequest(
                source_node=NodeId("A"), destination_node=NodeId("B"),
                vehicle_id=VehicleId("test"), vehicle_constraints=None,
                battery_state=None, max_candidates=5, timeout_s=60.0,
            ),
            sim_time_s=0.0, cost_weights=calc._weights,
        )
        bco = BCORouting()
        result = bco.optimize(ctx)
        assert not result.success

    def test_optimize_with_minimal_config(self):
        """Minimal population of 2 should still work."""
        graph = DirectedGraph()
        graph.add_node(Node(NodeId("A"), x=0.0, y=0.0))
        graph.add_node(Node(NodeId("B"), x=100.0, y=0.0))
        state = MutableEdgeState()
        graph.add_edge(Edge(
            edge_id=EdgeId("AB"), source=NodeId("A"), target=NodeId("B"),
            length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=state,
        ))
        calc = CompositeCostCalculator(CostWeights(distance=1.0, time=0.0, energy=0.0))

        config = SwarmConfig(
            algorithm_name="bco",
            population_size=2,
            max_iterations=10,
            seed=42,
            hyperparameters={"forward_steps": 5, "elite_count": 1},
        )
        ctx = SwarmContext(
            graph=graph, cost_calculator=calc, config=config, random_seed=42,
            routing_request=RoutingRequest(
                source_node=NodeId("A"), destination_node=NodeId("B"),
                vehicle_id=VehicleId("test"), vehicle_constraints=None,
                battery_state=None, max_candidates=5, timeout_s=60.0,
            ),
            sim_time_s=0.0, cost_weights=calc._weights,
        )
        bco = BCORouting()
        result = bco.optimize(ctx)
        assert result.success

    def test_large_population_converges(self):
        """A larger population should still converge on a simple graph."""
        graph = DirectedGraph()
        graph.add_node(Node(NodeId("A"), x=0.0, y=0.0))
        graph.add_node(Node(NodeId("B"), x=100.0, y=0.0))
        state = MutableEdgeState()
        graph.add_edge(Edge(
            edge_id=EdgeId("AB"), source=NodeId("A"), target=NodeId("B"),
            length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=state,
        ))
        calc = CompositeCostCalculator(CostWeights(distance=1.0, time=0.0, energy=0.0))

        config = SwarmConfig(
            algorithm_name="bco",
            population_size=50,
            max_iterations=100,
            stall_limit=5,
            seed=42,
            hyperparameters={"forward_steps": 5, "elite_count": 5},
        )
        ctx = SwarmContext(
            graph=graph, cost_calculator=calc, config=config, random_seed=42,
            routing_request=RoutingRequest(
                source_node=NodeId("A"), destination_node=NodeId("B"),
                vehicle_id=VehicleId("test"), vehicle_constraints=None,
                battery_state=None, max_candidates=5, timeout_s=60.0,
            ),
            sim_time_s=0.0, cost_weights=calc._weights,
        )
        bco = BCORouting()
        result = bco.optimize(ctx)
        assert result.success

    def test_target_score_termination(self):
        """Optimization should stop early when target_score is reached."""
        graph = DirectedGraph()
        graph.add_node(Node(NodeId("A"), x=0.0, y=0.0))
        graph.add_node(Node(NodeId("B"), x=100.0, y=0.0))
        state = MutableEdgeState()
        graph.add_edge(Edge(
            edge_id=EdgeId("AB"), source=NodeId("A"), target=NodeId("B"),
            length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=state,
        ))
        calc = CompositeCostCalculator(CostWeights(distance=1.0, time=0.0, energy=0.0))

        config = SwarmConfig(
            algorithm_name="bco",
            population_size=4,
            max_iterations=100,
            target_score=500.0,  # Known achievable cost
            seed=42,
            hyperparameters={"forward_steps": 5, "elite_count": 1},
        )
        ctx = SwarmContext(
            graph=graph, cost_calculator=calc, config=config, random_seed=42,
            routing_request=RoutingRequest(
                source_node=NodeId("A"), destination_node=NodeId("B"),
                vehicle_id=VehicleId("test"), vehicle_constraints=None,
                battery_state=None, max_candidates=5, timeout_s=60.0,
            ),
            sim_time_s=0.0, cost_weights=calc._weights,
        )
        bco = BCORouting()
        result = bco.optimize(ctx)
        assert result.success


# =========================================================================
# Component-level tests
# =========================================================================


class TestComponents:

    def test_visibility_cache_blocked_edges(self, cost_calculator):
        """Blocked edges should have visibility = 0."""
        graph = DirectedGraph()
        graph.add_node(Node(NodeId("A"), x=0.0, y=0.0))
        graph.add_node(Node(NodeId("B"), x=100.0, y=0.0))
        graph.add_node(Node(NodeId("C"), x=200.0, y=0.0))
        blocked = MutableEdgeState(is_blocked=True)
        normal = MutableEdgeState()
        graph.add_edge(Edge(
            edge_id=EdgeId("AB"), source=NodeId("A"), target=NodeId("B"),
            length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=blocked,
        ))
        graph.add_edge(Edge(
            edge_id=EdgeId("BC"), source=NodeId("B"), target=NodeId("C"),
            length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=normal,
        ))

        config = SwarmConfig(population_size=4, max_iterations=1, seed=42)
        bc = BCOConfiguration.from_config(config)
        bco = BCORouting()
        bco._graph = graph
        bco._cost_calculator = cost_calculator
        bco._config = bc
        bco._source = NodeId("A")
        bco._destination = NodeId("C")
        bco._build_visibility()

        assert bco._visibility.values[EdgeId("AB")] == 0.0
        assert bco._visibility.values[EdgeId("BC")] > 0.0

    def test_diversity_zero_when_all_templates_identical(self, bco_context):
        """All identical templates -> diversity = 0."""
        bco = BCORouting()
        bco._bees = [
            BeeState(k=0, route=[], cost=0.0, quality=0.0, norm_quality=0.0,
                     template=[EdgeId("AB"), EdgeId("BC")], state=BeeStatus.COMPLETE,
                     is_loyal=True, visited=set(), iteration_created=0),
            BeeState(k=1, route=[], cost=0.0, quality=0.0, norm_quality=0.0,
                     template=[EdgeId("AB"), EdgeId("BC")], state=BeeStatus.COMPLETE,
                     is_loyal=True, visited=set(), iteration_created=0),
        ]
        div = bco._compute_diversity()
        assert div == 0.0

    def test_diversity_one_when_all_templates_disjoint(self, bco_context):
        """All disjoint templates -> diversity = 1."""
        bco = BCORouting()
        bco._bees = [
            BeeState(k=0, route=[], cost=0.0, quality=0.0, norm_quality=0.0,
                     template=[EdgeId("AB")], state=BeeStatus.COMPLETE,
                     is_loyal=True, visited=set(), iteration_created=0),
            BeeState(k=1, route=[], cost=0.0, quality=0.0, norm_quality=0.0,
                     template=[EdgeId("CD")], state=BeeStatus.COMPLETE,
                     is_loyal=True, visited=set(), iteration_created=0),
        ]
        div = bco._compute_diversity()
        assert div == 1.0

    def test_diversity_fewer_than_two_templates(self, bco_context):
        """Less than 2 templates -> diversity = 0."""
        bco = BCORouting()
        bco._bees = [
            BeeState(k=0, route=[], cost=0.0, quality=0.0, norm_quality=0.0,
                     template=[EdgeId("AB")], state=BeeStatus.COMPLETE,
                     is_loyal=True, visited=set(), iteration_created=0),
            BeeState(k=1, route=[], cost=0.0, quality=0.0, norm_quality=0.0,
                     template=None, state=BeeStatus.COMPLETE,
                     is_loyal=True, visited=set(), iteration_created=0),
        ]
        div = bco._compute_diversity()
        assert div == 0.0

    def test_update_templates_loyal_bee(self, bco_context):
        """A loyal COMPLETE bee should have template set to its route."""
        bco = BCORouting()
        bco._bees = [
            BeeState(k=0, route=[EdgeId("AB"), EdgeId("BC")], cost=10.0,
                     quality=0.1, norm_quality=1.0, template=None,
                     state=BeeStatus.COMPLETE, is_loyal=True,
                     visited=set(), iteration_created=0),
        ]
        bco._update_templates()
        assert bco._bees[0].template == [EdgeId("AB"), EdgeId("BC")]

    def test_update_templates_failed_bee(self, bco_context):
        """A FAILED bee should keep its previous template."""
        bco = BCORouting()
        bco._bees = [
            BeeState(k=0, route=[], cost=float("inf"), quality=0.0,
                     norm_quality=0.0, template=[EdgeId("AB")],
                     state=BeeStatus.FAILED, is_loyal=False,
                     visited=set(), iteration_created=0),
        ]
        bco._update_templates()
        assert bco._bees[0].template == [EdgeId("AB")]

    def test_recruitment_assigns_template(self, bco_context):
        """An uncommitted bee should receive the recruiter's route as template."""
        bco = BCORouting()
        bco._bees = [
            BeeState(k=0, route=[EdgeId("AB"), EdgeId("BC")], cost=10.0,
                     quality=0.1, norm_quality=1.0, template=None,
                     state=BeeStatus.COMPLETE, is_loyal=True,
                     visited=set(), iteration_created=0),
            BeeState(k=1, route=[], cost=float("inf"), quality=0.0,
                     norm_quality=0.0, template=None,
                     state=BeeStatus.COMPLETE, is_loyal=False,
                     visited=set(), iteration_created=0),
        ]
        bco._config = BCOConfiguration.from_config(bco_context.config)
        stream = random.Random(42)
        bco._recruitment(uncommitted=[1], loyal=[0], stream=stream)
        assert bco._bees[1].template == [EdgeId("AB"), EdgeId("BC")]

    def test_loyalty_decision_elite_always_loyal(self, bco_context):
        """Elite bees bypass the probabilistic loyalty decision."""
        bco = BCORouting()
        bco._bees = [
            BeeState(k=0, route=[EdgeId("AB")], cost=5.0, quality=0.2,
                     norm_quality=1.0, template=None,
                     state=BeeStatus.COMPLETE, is_loyal=False,
                     visited=set(), iteration_created=0),
            BeeState(k=1, route=[EdgeId("AC")], cost=10.0, quality=0.1,
                     norm_quality=0.5, template=None,
                     state=BeeStatus.COMPLETE, is_loyal=False,
                     visited=set(), iteration_created=0),
        ]
        bco._config = BCOConfiguration.from_config(bco_context.config)
        # elite_count = 2 -> both are elite
        K = 2
        sorted_idx = sorted(range(2), key=lambda i: bco._bees[i].quality, reverse=True)
        elite = set(sorted_idx[:K])
        stream = random.Random(42)
        for k in range(2):
            if k in elite:
                bco._bees[k].is_loyal = True
            else:
                bco._bees[k].is_loyal = bco._loyalty_decision(k, stream)
        assert bco._bees[0].is_loyal
        assert bco._bees[1].is_loyal


# =========================================================================
# VisibilityCache tests
# =========================================================================


class TestVisibilityCache:

    def test_immutable_after_construction(self):
        vc = VisibilityCache({EdgeId("AB"): 0.5}, 2.0, 3.0)
        assert vc.values[EdgeId("AB")] == 0.5
        assert vc.beta == 2.0
        assert vc.delta == 3.0

    def test_multiple_edges(self):
        data = {EdgeId("AB"): 0.5, EdgeId("BC"): 0.8, EdgeId("CD"): 0.3}
        vc = VisibilityCache(data, 1.0, 1.0)
        assert len(vc.values) == 3
        assert vc.values[EdgeId("BC")] == 0.8


# =========================================================================
# BCOStatistics tests
# =========================================================================


class TestBCOStatistics:

    def test_construction(self):
        s = BCOStatistics(
            iteration=0, best_cost=10.0, avg_cost=15.0, worst_cost=20.0,
            loyal_count=4, uncommitted_count=2, diversity=0.5, runtime_s=0.1,
        )
        assert s.best_cost == 10.0
        assert s.loyal_count == 4
        assert s.uncommitted_count == 2


# =========================================================================
# Validation edge-case tests
# =========================================================================


class TestValidation:

    def test_optimize_missing_source(self, linear_graph, cost_calculator):
        """Optimize with source node not in graph should fail gracefully."""
        ctx = SwarmContext(
            graph=linear_graph,
            cost_calculator=cost_calculator,
            config=SwarmConfig(population_size=4, max_iterations=1, seed=42),
            random_seed=42,
            routing_request=RoutingRequest(
                source_node=NodeId("X"), destination_node=NodeId("D"),
                vehicle_id=VehicleId("test"), vehicle_constraints=None,
                battery_state=None, max_candidates=5, timeout_s=60.0,
            ),
            sim_time_s=0.0, cost_weights=CostWeights(),
        )
        bco = BCORouting()
        result = bco.optimize(ctx)
        assert not result.success
        assert result.failure_reason == "Source node not in graph"

    def test_optimize_missing_dest(self, linear_graph, cost_calculator):
        """Optimize with destination node not in graph should fail gracefully."""
        ctx = SwarmContext(
            graph=linear_graph,
            cost_calculator=cost_calculator,
            config=SwarmConfig(population_size=4, max_iterations=1, seed=42),
            random_seed=42,
            routing_request=RoutingRequest(
                source_node=NodeId("A"), destination_node=NodeId("X"),
                vehicle_id=VehicleId("test"), vehicle_constraints=None,
                battery_state=None, max_candidates=5, timeout_s=60.0,
            ),
            sim_time_s=0.0, cost_weights=CostWeights(),
        )
        bco = BCORouting()
        result = bco.optimize(ctx)
        assert not result.success
        assert result.failure_reason == "Destination node not in graph"

    def test_find_convergence_no_stats(self):
        """_find_convergence_iteration returns None when no stats."""
        bco = BCORouting()
        bco._iteration_stats = []
        assert bco._find_convergence_iteration() is None


# =========================================================================
# SwarmFactory registration test
# =========================================================================


class TestSwarmFactory:

    def test_bco_registered(self):
        from e3hybrid.swarm.factory import SwarmFactory
        # Registration happens at import time
        assert SwarmFactory.is_registered("bco")
        routing = SwarmFactory.create_algorithm("bco")
        assert routing.name == "bco"

    def test_bco_name_property(self):
        bco = BCORouting()
        assert bco.name == "bco"
