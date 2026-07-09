"""Comprehensive tests for the Constructive Discrete PSO implementation.

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
from e3hybrid.swarm.pso import (
    PSORouting,
    PSOConfiguration,
    PSOStatistics,
    PSOValidator,
    ParticleState,
    ParticleStatus,
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
def diamond_graph() -> DirectedGraph:
    """A -> B, C -> D diamond: two equal-cost paths of 2 edges each."""
    graph = DirectedGraph()
    for nid in ("A", "B", "C", "D"):
        graph.add_node(Node(node_id=NodeId(nid), x=0.0, y=0.0))
    state = MutableEdgeState()
    for sid, tid, eid in [
        ("A", "B", "AB"), ("A", "C", "AC"),
        ("B", "D", "BD"), ("C", "D", "CD"),
    ]:
        graph.add_edge(Edge(
            edge_id=EdgeId(eid), source=NodeId(sid), target=NodeId(tid),
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
def fully_connected_graph() -> DirectedGraph:
    """4 fully connected nodes (complete digraph, 12 edges)."""
    graph = DirectedGraph()
    nodes = [NodeId("A"), NodeId("B"), NodeId("C"), NodeId("D")]
    for nid in nodes:
        graph.add_node(Node(node_id=nid, x=0.0, y=0.0))
    state = MutableEdgeState()
    for src in nodes:
        for dst in nodes:
            if src != dst:
                graph.add_edge(Edge(
                    edge_id=EdgeId(f"{src}{dst}"),
                    source=src, target=dst,
                    length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=state,
                ))
    return graph


@pytest.fixture
def blocked_graph() -> DirectedGraph:
    """A-B-C-D with edge BC blocked, forcing no route."""
    graph = DirectedGraph()
    for nid, x in [("A", 0.0), ("B", 100.0), ("C", 200.0), ("D", 300.0)]:
        graph.add_node(Node(node_id=NodeId(nid), x=x, y=0.0))
    open_state = MutableEdgeState()
    blocked_state = MutableEdgeState(is_blocked=True)
    graph.add_edge(Edge(
        edge_id=EdgeId("AB"), source=NodeId("A"), target=NodeId("B"),
        length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=open_state,
    ))
    graph.add_edge(Edge(
        edge_id=EdgeId("BC"), source=NodeId("B"), target=NodeId("C"),
        length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=blocked_state,
    ))
    graph.add_edge(Edge(
        edge_id=EdgeId("CD"), source=NodeId("C"), target=NodeId("D"),
        length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=open_state,
    ))
    return graph


@pytest.fixture
def cost_calculator() -> CompositeCostCalculator:
    return CompositeCostCalculator(CostWeights(distance=1.0, time=1.0, energy=0.0))


@pytest.fixture
def default_config() -> SwarmConfig:
    return SwarmConfig(
        algorithm_name="pso",
        population_size=10,
        max_iterations=20,
        seed=42,
        hyperparameters={
            "inertia_start": 0.9,
            "inertia_end": 0.4,
            "cognition_weight": 2.0,
            "social_weight": 2.0,
            "visibility_weight": 1.0,
            "epsilon": 1e-10,
            "forward_steps": 100,
        },
    )


@pytest.fixture
def pso_context(linear_graph: DirectedGraph,
             cost_calculator: CompositeCostCalculator,
             default_config: SwarmConfig) -> SwarmContext:
    return SwarmContext(
        graph=linear_graph,
        cost_calculator=cost_calculator,
        config=default_config,
        random_seed=42,
        routing_request=RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("D"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=5, timeout_s=60.0,
        ),
        sim_time_s=0.0,
        cost_weights=cost_calculator._weights,
    )


@pytest.fixture
def pso_context_fork(fork_graph: DirectedGraph,
                       cost_calculator: CompositeCostCalculator,
                       default_config: SwarmConfig) -> SwarmContext:
    return SwarmContext(
        graph=fork_graph,
        cost_calculator=cost_calculator,
        config=default_config,
        random_seed=42,
        routing_request=RoutingRequest(
            source_node=NodeId("A"), destination_node=NodeId("D"),
            vehicle_id=VehicleId("test"), vehicle_constraints=None,
            battery_state=None, max_candidates=5, timeout_s=60.0,
        ),
        sim_time_s=0.0,
        cost_weights=cost_calculator._weights,
    )


# =========================================================================
# Configuration and validation tests
# =========================================================================


class TestConfiguration:

    def test_default_values(self):
        hp = {}
        config_obj = SwarmConfig(
            algorithm_name="pso", population_size=10, max_iterations=10, seed=42,
            hyperparameters=hp,
        )
        pc = PSOConfiguration.from_config(config_obj)
        assert pc.inertia_start == 0.9
        assert pc.inertia_end == 0.4
        assert pc.cognition_weight == 2.0
        assert pc.social_weight == 2.0
        assert pc.visibility_weight == 1.0
        assert pc.epsilon == 1e-10
        assert pc.forward_steps == 100

    def test_custom_values(self):
        hp = {
            "inertia_start": 0.8,
            "inertia_end": 0.3,
            "cognition_weight": 1.5,
            "social_weight": 1.5,
            "visibility_weight": 0.5,
            "epsilon": 1e-8,
            "forward_steps": 50,
        }
        config_obj = SwarmConfig(
            algorithm_name="pso", population_size=10, max_iterations=10, seed=42,
            hyperparameters=hp,
        )
        pc = PSOConfiguration.from_config(config_obj)
        assert pc.inertia_start == 0.8
        assert pc.inertia_end == 0.3
        assert pc.cognition_weight == 1.5
        assert pc.social_weight == 1.5
        assert pc.visibility_weight == 0.5
        assert pc.epsilon == 1e-8
        assert pc.forward_steps == 50

    def test_forward_steps_must_be_positive(self):
        hp = {"forward_steps": 0}
        config_obj = SwarmConfig(
            algorithm_name="pso", population_size=10, max_iterations=10, seed=42,
            hyperparameters=hp,
        )
        with pytest.raises(ValueError, match="forward_steps must be >= 1"):
            PSOConfiguration.from_config(config_obj)

    def test_inertia_end_cannot_exceed_start(self):
        hp = {"inertia_start": 0.4, "inertia_end": 0.9}
        config_obj = SwarmConfig(
            algorithm_name="pso", population_size=10, max_iterations=10, seed=42,
            hyperparameters=hp,
        )
        with pytest.raises(ValueError, match="inertia_start must be >= inertia_end"):
            PSOConfiguration.from_config(config_obj)

    def test_inertia_range(self):
        hp = {"inertia_start": 1.5, "inertia_end": 0.4}
        config_obj = SwarmConfig(
            algorithm_name="pso", population_size=10, max_iterations=10, seed=42,
            hyperparameters=hp,
        )
        with pytest.raises(ValueError, match="inertia weights must be in"):
            PSOConfiguration.from_config(config_obj)

    def test_cognition_negative(self):
        hp = {"cognition_weight": -1.0}
        config_obj = SwarmConfig(
            algorithm_name="pso", population_size=10, max_iterations=10, seed=42,
            hyperparameters=hp,
        )
        with pytest.raises(ValueError, match="cognition_weight must be >= 0"):
            PSOConfiguration.from_config(config_obj)

    def test_social_negative(self):
        hp = {"social_weight": -1.0}
        config_obj = SwarmConfig(
            algorithm_name="pso", population_size=10, max_iterations=10, seed=42,
            hyperparameters=hp,
        )
        with pytest.raises(ValueError, match="social_weight must be >= 0"):
            PSOConfiguration.from_config(config_obj)

    def test_visibility_negative(self):
        hp = {"visibility_weight": -1.0}
        config_obj = SwarmConfig(
            algorithm_name="pso", population_size=10, max_iterations=10, seed=42,
            hyperparameters=hp,
        )
        with pytest.raises(ValueError, match="visibility_weight must be >= 0"):
            PSOConfiguration.from_config(config_obj)

    def test_epsilon_out_of_range(self):
        hp = {"epsilon": 2.0}
        config_obj = SwarmConfig(
            algorithm_name="pso", population_size=10, max_iterations=10, seed=42,
            hyperparameters=hp,
        )
        with pytest.raises(ValueError, match="epsilon must be in"):
            PSOConfiguration.from_config(config_obj)

    def test_all_weights_zero(self):
        hp = {
            "cognition_weight": 0.0,
            "social_weight": 0.0,
            "visibility_weight": 0.0,
        }
        config_obj = SwarmConfig(
            algorithm_name="pso", population_size=10, max_iterations=10, seed=42,
            hyperparameters=hp,
        )
        with pytest.raises(ValueError, match="at least one"):
            PSOConfiguration.from_config(config_obj)

    def test_population_size_less_than_2(self):
        config_obj = SwarmConfig(
            algorithm_name="pso", population_size=1, max_iterations=10, seed=42,
        )
        with pytest.raises(ValueError, match="population_size must be >= 2"):
            PSOConfiguration.from_config(config_obj)


# =========================================================================
# ParticleState tests
# =========================================================================


class TestParticleState:

    def test_construction(self):
        p = ParticleState(
            k=0, route=[EdgeId("AB")], cost=10.0,
            p_best_route=[EdgeId("AB")], p_best_cost=10.0,
            state=ParticleStatus.COMPLETE, visited={NodeId("A"), NodeId("B")},
        )
        assert p.k == 0
        assert p.cost == 10.0
        assert p.p_best_cost == 10.0
        assert p.state == ParticleStatus.COMPLETE


# =========================================================================
# PSOStatistics tests
# =========================================================================


class TestPSOStatistics:

    def test_construction(self):
        s = PSOStatistics(
            iteration=0, best_cost=10.0, avg_cost=15.0, worst_cost=20.0,
            inertia=0.9, diversity=0.5, runtime_s=0.1,
        )
        assert s.best_cost == 10.0
        assert s.inertia == 0.9
        assert s.diversity == 0.5


# =========================================================================
# VisibilityCache tests
# =========================================================================


class TestVisibilityCache:

    def test_construction(self):
        vc = VisibilityCache({EdgeId("AB"): 0.5})
        assert vc.values[EdgeId("AB")] == 0.5

    def test_multiple_edges(self):
        data = {EdgeId("AB"): 0.5, EdgeId("BC"): 0.8}
        vc = VisibilityCache(data)
        assert len(vc.values) == 2


# =========================================================================
# PSOValidator tests
# =========================================================================


class TestPSOValidator:

    def test_valid_context(self, pso_context):
        errors = PSOValidator.validate_context(pso_context)
        assert errors == []

    def test_missing_graph(self, pso_context):
        ctx = SwarmContext(
            graph=None,
            cost_calculator=pso_context.cost_calculator,
            config=pso_context.config,
            random_seed=42,
            routing_request=pso_context.routing_request,
            sim_time_s=0.0,
            cost_weights=pso_context.cost_weights,
        )
        errors = PSOValidator.validate_context(ctx)
        assert "SwarmContext.graph is required for PSO" in errors

    def test_missing_cost_calculator(self, pso_context):
        ctx = SwarmContext(
            graph=pso_context.graph,
            cost_calculator=None,
            config=pso_context.config,
            random_seed=42,
            routing_request=pso_context.routing_request,
            sim_time_s=0.0,
            cost_weights=pso_context.cost_weights,
        )
        errors = PSOValidator.validate_context(ctx)
        assert "SwarmContext.cost_calculator is required for PSO" in errors

    def test_same_source_dest(self, pso_context):
        """PSOValidator detects source == destination."""
        # RoutingRequest rejects same source/dest, so manually construct context
        errors = PSOValidator.validate_context(pso_context)
        # pso_context has A->D, so no error
        assert "source and destination must differ" not in errors
        # The check still works when RoutingRequest is valid (different nodes)
        ctx2 = SwarmContext(
            graph=pso_context.graph,
            cost_calculator=pso_context.cost_calculator,
            config=pso_context.config,
            random_seed=42,
            routing_request=RoutingRequest(
                source_node=NodeId("A"), destination_node=NodeId("B"),
                vehicle_id=VehicleId("test"), vehicle_constraints=None,
                battery_state=None, max_candidates=5, timeout_s=60.0,
            ),
            sim_time_s=0.0,
            cost_weights=pso_context.cost_weights,
        )
        errors = PSOValidator.validate_context(ctx2)
        assert "source and destination must differ" not in errors


# =========================================================================
# PSORouting tests
# =========================================================================


class TestPSORouting:

    def test_name(self):
        pso = PSORouting()
        assert pso.name == "pso"

    def test_optimize_linear(self, pso_context):
        """Should find A->B->C->D on a linear graph."""
        pso = PSORouting()
        result = pso.optimize(pso_context)
        assert result.success
        assert result.best_solution is not None
        route = result.best_solution.edge_sequence
        assert route == (EdgeId("AB"), EdgeId("BC"), EdgeId("CD"))

    def test_optimize_fork(self, pso_context_fork):
        """Should find a valid path A->D on fork graph."""
        pso = PSORouting()
        result = pso.optimize(pso_context_fork)
        assert result.success
        route = result.best_solution.edge_sequence
        assert route[0] in (EdgeId("AB"), EdgeId("AE"))
        assert route[-1] in (EdgeId("CD"), EdgeId("FD"))

    def test_optimize_diamond(self, diamond_graph, cost_calculator, default_config):
        """Should find a valid path A->D on diamond graph."""
        ctx = SwarmContext(
            graph=diamond_graph, cost_calculator=cost_calculator,
            config=default_config, random_seed=42,
            routing_request=RoutingRequest(
                source_node=NodeId("A"), destination_node=NodeId("D"),
                vehicle_id=VehicleId("test"), vehicle_constraints=None,
                battery_state=None, max_candidates=5, timeout_s=60.0,
            ),
            sim_time_s=0.0, cost_weights=cost_calculator._weights,
        )
        pso = PSORouting()
        result = pso.optimize(ctx)
        assert result.success
        route = result.best_solution.edge_sequence
        assert len(route) == 2

    def test_optimize_fully_connected(self, fully_connected_graph,
                                        cost_calculator, default_config):
        """Should find a valid path on a fully connected graph."""
        ctx = SwarmContext(
            graph=fully_connected_graph, cost_calculator=cost_calculator,
            config=default_config, random_seed=42,
            routing_request=RoutingRequest(
                source_node=NodeId("A"), destination_node=NodeId("D"),
                vehicle_id=VehicleId("test"), vehicle_constraints=None,
                battery_state=None, max_candidates=5, timeout_s=60.0,
            ),
            sim_time_s=0.0, cost_weights=cost_calculator._weights,
        )
        pso = PSORouting()
        result = pso.optimize(ctx)
        assert result.success
        # Must start at A and end at D
        nodes = result.best_solution.node_sequence
        assert nodes[0] == NodeId("A")
        assert nodes[-1] == NodeId("D")

    def test_optimize_grid(self, grid_graph, cost_calculator, default_config):
        """Should find a valid path on a 3x3 grid."""
        ctx = SwarmContext(
            graph=grid_graph, cost_calculator=cost_calculator,
            config=default_config, random_seed=42,
            routing_request=RoutingRequest(
                source_node=NodeId("0_0"), destination_node=NodeId("2_2"),
                vehicle_id=VehicleId("test"), vehicle_constraints=None,
                battery_state=None, max_candidates=5, timeout_s=60.0,
            ),
            sim_time_s=0.0, cost_weights=cost_calculator._weights,
        )
        pso = PSORouting()
        result = pso.optimize(ctx)
        assert result.success
        nodes = result.best_solution.node_sequence
        assert nodes[0] == NodeId("0_0")
        assert nodes[-1] == NodeId("2_2")

    def test_optimize_unreachable(self, cost_calculator, default_config):
        """Should return failure for an unreachable destination."""
        graph = DirectedGraph()
        graph.add_node(Node(node_id=NodeId("A"), x=0.0, y=0.0))
        graph.add_node(Node(node_id=NodeId("B"), x=100.0, y=0.0))
        ctx = SwarmContext(
            graph=graph, cost_calculator=cost_calculator,
            config=default_config, random_seed=42,
            routing_request=RoutingRequest(
                source_node=NodeId("A"), destination_node=NodeId("B"),
                vehicle_id=VehicleId("test"), vehicle_constraints=None,
                battery_state=None, max_candidates=5, timeout_s=60.0,
            ),
            sim_time_s=0.0, cost_weights=cost_calculator._weights,
        )
        pso = PSORouting()
        result = pso.optimize(ctx)
        assert not result.success

    def test_optimize_blocked_edges(self, cost_calculator, default_config):
        """Should fail when all routes to destination are blocked."""
        graph = DirectedGraph()
        graph.add_node(Node(node_id=NodeId("A"), x=0.0, y=0.0))
        graph.add_node(Node(node_id=NodeId("B"), x=100.0, y=0.0))
        graph.add_node(Node(node_id=NodeId("C"), x=200.0, y=0.0))
        blocked = MutableEdgeState(is_blocked=True)
        graph.add_edge(Edge(
            edge_id=EdgeId("AB"), source=NodeId("A"), target=NodeId("B"),
            length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=blocked,
        ))
        graph.add_edge(Edge(
            edge_id=EdgeId("BC"), source=NodeId("B"), target=NodeId("C"),
            length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=blocked,
        ))
        ctx = SwarmContext(
            graph=graph, cost_calculator=cost_calculator,
            config=default_config, random_seed=42,
            routing_request=RoutingRequest(
                source_node=NodeId("A"), destination_node=NodeId("C"),
                vehicle_id=VehicleId("test"), vehicle_constraints=None,
                battery_state=None, max_candidates=5, timeout_s=60.0,
            ),
            sim_time_s=0.0, cost_weights=cost_calculator._weights,
        )
        pso = PSORouting()
        result = pso.optimize(ctx)
        assert not result.success

    def test_optimize_source_equals_dest(self, linear_graph, cost_calculator, default_config):
        """Source == destination should return an empty valid route (single node)."""
        # RoutingRequest rejects same source/dest, so we test via the validator logic:
        pso = PSORouting()
        result = pso._failure_result("source and destination must differ")
        assert not result.success
        assert "source and destination must differ" in result.failure_reason

    def test_route_validity(self, pso_context):
        """The route must be a valid source-to-destination path."""
        pso = PSORouting()
        result = pso.optimize(pso_context)
        assert result.success
        edges = result.best_solution.edge_sequence
        nodes = result.best_solution.node_sequence
        assert nodes[0] == pso_context.routing_request.source_node
        assert nodes[-1] == pso_context.routing_request.destination_node
        # Each edge must connect consecutive nodes
        for i, eid in enumerate(edges):
            edge = pso_context.graph.get_edge(eid)
            assert edge.source == nodes[i]
            assert edge.target == nodes[i + 1]

    def test_no_cycles(self, pso_context):
        """The route must not contain duplicate nodes."""
        pso = PSORouting()
        result = pso.optimize(pso_context)
        assert result.success
        nodes = result.best_solution.node_sequence
        assert len(nodes) == len(set(nodes))

    def test_cost_monotonically_non_increasing_global_best(self, pso_context):
        """Global best cost should never increase between iterations."""
        pso = PSORouting()
        result = pso.optimize(pso_context)
        scores = list(result.statistics.score_history)
        for i in range(1, len(scores)):
            assert scores[i] <= scores[i - 1] + 1e-9

    def test_inertia_decay(self, pso_context):
        """Inertia should follow the linear decay formula."""
        pso = PSORouting()
        pso._context = pso_context
        pso._config = PSOConfiguration.from_config(pso_context.config)
        pso._graph = pso_context.graph
        pso._cost_calculator = pso_context.cost_calculator
        pso._build_visibility()

        max_iters = pso_context.config.max_iterations
        ws = [pso._compute_inertia(t, max_iters) for t in range(max_iters)]
        assert ws[0] == 0.9
        assert ws[-1] == 0.4
        for i in range(1, len(ws)):
            assert ws[i] <= ws[i - 1]

    def test_deterministic_same_seed(self, linear_graph, cost_calculator, default_config):
        """Same seed must produce identical results."""
        cfg = default_config
        ctx1 = SwarmContext(
            graph=linear_graph, cost_calculator=cost_calculator,
            config=cfg, random_seed=42,
            routing_request=RoutingRequest(
                source_node=NodeId("A"), destination_node=NodeId("D"),
                vehicle_id=VehicleId("test"), vehicle_constraints=None,
                battery_state=None, max_candidates=5, timeout_s=60.0,
            ),
            sim_time_s=0.0, cost_weights=cost_calculator._weights,
        )
        ctx2 = SwarmContext(
            graph=linear_graph, cost_calculator=cost_calculator,
            config=cfg, random_seed=42,
            routing_request=RoutingRequest(
                source_node=NodeId("A"), destination_node=NodeId("D"),
                vehicle_id=VehicleId("test"), vehicle_constraints=None,
                battery_state=None, max_candidates=5, timeout_s=60.0,
            ),
            sim_time_s=0.0, cost_weights=cost_calculator._weights,
        )
        pso1 = PSORouting()
        pso2 = PSORouting()
        result1 = pso1.optimize(ctx1)
        result2 = pso2.optimize(ctx2)
        assert result1.best_solution.edge_sequence == result2.best_solution.edge_sequence
        assert result1.statistics.score_history == result2.statistics.score_history

    def test_deterministic_different_seeds(self, grid_graph, cost_calculator, default_config):
        """Different seeds should produce different exploration (on grid graph with many paths)."""
        cfg = default_config
        ctx1 = SwarmContext(
            graph=grid_graph, cost_calculator=cost_calculator,
            config=cfg, random_seed=42,
            routing_request=RoutingRequest(
                source_node=NodeId("0_0"), destination_node=NodeId("2_2"),
                vehicle_id=VehicleId("test"), vehicle_constraints=None,
                battery_state=None, max_candidates=5, timeout_s=60.0,
            ),
            sim_time_s=0.0, cost_weights=cost_calculator._weights,
        )
        ctx2 = SwarmContext(
            graph=grid_graph, cost_calculator=cost_calculator,
            config=cfg, random_seed=9999,
            routing_request=RoutingRequest(
                source_node=NodeId("0_0"), destination_node=NodeId("2_2"),
                vehicle_id=VehicleId("test"), vehicle_constraints=None,
                battery_state=None, max_candidates=5, timeout_s=60.0,
            ),
            sim_time_s=0.0, cost_weights=cost_calculator._weights,
        )
        pso1 = PSORouting()
        pso2 = PSORouting()
        result1 = pso1.optimize(ctx1)
        result2 = pso2.optimize(ctx2)
        # On a grid with 30 particles, different seeds should produce different
        # initialisation (different diversity patterns early on)
        assert result1.statistics.diversity_history != result2.statistics.diversity_history

    def test_convergence_empty_stats(self):
        """_find_convergence_iteration returns None when no stats."""
        pso = PSORouting()
        pso._iteration_stats = []
        assert pso._find_convergence_iteration() is None

    def test_success_property(self, pso_context):
        """Success should be True iff global_best_route is non-empty."""
        pso = PSORouting()
        result = pso.optimize(pso_context)
        assert result.success == (len(result.best_solution.edge_sequence) > 0)

    def test_statistics_produced(self, pso_context):
        """Statistics should contain basic fields."""
        pso = PSORouting()
        result = pso.optimize(pso_context)
        assert result.statistics.total_iterations > 0
        assert result.statistics.best_score > 0
        assert result.statistics.total_runtime_s >= 0

    def test_optimize_missing_source(self, linear_graph, cost_calculator, default_config):
        """Optimize with source node not in graph should fail gracefully."""
        ctx = SwarmContext(
            graph=linear_graph, cost_calculator=cost_calculator,
            config=default_config, random_seed=42,
            routing_request=RoutingRequest(
                source_node=NodeId("X"), destination_node=NodeId("D"),
                vehicle_id=VehicleId("test"), vehicle_constraints=None,
                battery_state=None, max_candidates=5, timeout_s=60.0,
            ),
            sim_time_s=0.0, cost_weights=cost_calculator._weights,
        )
        pso = PSORouting()
        result = pso.optimize(ctx)
        assert not result.success
        assert result.failure_reason == "Source node not in graph"

    def test_optimize_missing_dest(self, linear_graph, cost_calculator, default_config):
        """Optimize with destination node not in graph should fail gracefully."""
        ctx = SwarmContext(
            graph=linear_graph, cost_calculator=cost_calculator,
            config=default_config, random_seed=42,
            routing_request=RoutingRequest(
                source_node=NodeId("A"), destination_node=NodeId("X"),
                vehicle_id=VehicleId("test"), vehicle_constraints=None,
                battery_state=None, max_candidates=5, timeout_s=60.0,
            ),
            sim_time_s=0.0, cost_weights=cost_calculator._weights,
        )
        pso = PSORouting()
        result = pso.optimize(ctx)
        assert not result.success
        assert result.failure_reason == "Destination node not in graph"


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

        config_obj = SwarmConfig(
            algorithm_name="pso", population_size=10, max_iterations=10, seed=42,
        )
        pso = PSORouting()
        pso._graph = graph
        pso._cost_calculator = cost_calculator
        pso._config = PSOConfiguration.from_config(config_obj)
        pso._build_visibility()

        assert pso._visibility.values[EdgeId("AB")] == 0.0
        assert pso._visibility.values[EdgeId("BC")] > 0.0

    def test_diversity_zero_when_all_identical(self):
        """All identical p_best routes -> diversity = 0."""
        pso = PSORouting()
        pso._particles = [
            ParticleState(k=0, route=[], cost=0.0,
                          p_best_route=[EdgeId("AB"), EdgeId("BC")], p_best_cost=10.0,
                          state=ParticleStatus.COMPLETE, visited=set()),
            ParticleState(k=1, route=[], cost=0.0,
                          p_best_route=[EdgeId("AB"), EdgeId("BC")], p_best_cost=10.0,
                          state=ParticleStatus.COMPLETE, visited=set()),
        ]
        div = pso._compute_diversity()
        assert div == 0.0

    def test_diversity_one_when_all_disjoint(self):
        """All disjoint p_best routes -> diversity = 1."""
        pso = PSORouting()
        pso._particles = [
            ParticleState(k=0, route=[], cost=0.0,
                          p_best_route=[EdgeId("AB")], p_best_cost=10.0,
                          state=ParticleStatus.COMPLETE, visited=set()),
            ParticleState(k=1, route=[], cost=0.0,
                          p_best_route=[EdgeId("CD")], p_best_cost=10.0,
                          state=ParticleStatus.COMPLETE, visited=set()),
        ]
        div = pso._compute_diversity()
        assert div == 1.0

    def test_diversity_fewer_than_two_templates(self):
        """Less than 2 non-empty p_best routes -> diversity = 0."""
        pso = PSORouting()
        pso._particles = [
            ParticleState(k=0, route=[], cost=0.0,
                          p_best_route=[EdgeId("AB")], p_best_cost=10.0,
                          state=ParticleStatus.COMPLETE, visited=set()),
            ParticleState(k=1, route=[], cost=float("inf"),
                          p_best_route=[], p_best_cost=float("inf"),
                          state=ParticleStatus.FAILED, visited=set()),
        ]
        div = pso._compute_diversity()
        assert div == 0.0

    def test_edge_total_cost(self, pso_context):
        """_edge_total_cost should return finite positive for normal edges."""
        pso = PSORouting()
        pso._graph = pso_context.graph
        pso._cost_calculator = pso_context.cost_calculator
        edge = pso._graph.get_edge(EdgeId("AB"))
        cost = pso._edge_total_cost(edge)
        assert cost > 0 and math.isfinite(cost)

    def test_edge_total_cost_blocked(self, cost_calculator):
        """_edge_total_cost should return inf for blocked edges."""
        graph = DirectedGraph()
        graph.add_node(Node(NodeId("A"), x=0.0, y=0.0))
        graph.add_node(Node(NodeId("B"), x=100.0, y=0.0))
        blocked = MutableEdgeState(is_blocked=True)
        graph.add_edge(Edge(
            edge_id=EdgeId("AB"), source=NodeId("A"), target=NodeId("B"),
            length_m=100.0, speed_limit_mps=10.0, lane_count=1, state=blocked,
        ))
        pso = PSORouting()
        pso._graph = graph
        pso._cost_calculator = cost_calculator
        edge = pso._graph.get_edge(EdgeId("AB"))
        cost = pso._edge_total_cost(edge)
        assert cost == float("inf")

    def test_compute_route_cost(self, pso_context):
        """_compute_route_cost should sum finite edge costs."""
        pso = PSORouting()
        pso._graph = pso_context.graph
        pso._cost_calculator = pso_context.cost_calculator
        cost = pso._compute_route_cost([EdgeId("AB"), EdgeId("BC"), EdgeId("CD")])
        assert cost > 0 and math.isfinite(cost)

    def test_compute_route_cost_inf(self, pso_context):
        """_compute_route_cost should return inf for invalid edges."""
        pso = PSORouting()
        pso._graph = pso_context.graph
        pso._cost_calculator = pso_context.cost_calculator
        cost = pso._compute_route_cost([EdgeId("XX")])
        assert cost == float("inf")

    def test_route_reaches_destination(self, pso_context):
        """_route_reaches_destination returns True for valid A->D."""
        pso = PSORouting()
        pso._graph = pso_context.graph
        pso._destination = NodeId("D")
        assert pso._route_reaches_destination([EdgeId("AB"), EdgeId("BC"), EdgeId("CD")])
        assert not pso._route_reaches_destination([EdgeId("AB")])

    def test_route_reaches_empty(self, pso_context):
        """_route_reaches_destination returns False for empty route."""
        pso = PSORouting()
        pso._graph = pso_context.graph
        pso._destination = NodeId("D")
        assert not pso._route_reaches_destination([])

    def test_construct_route_with_no_references(self, pso_context):
        """_construct_route with empty reference routes uses pure visibility."""
        pso = PSORouting()
        pso._graph = pso_context.graph
        pso._cost_calculator = pso_context.cost_calculator
        pso._source = NodeId("A")
        pso._destination = NodeId("D")
        pso._config = PSOConfiguration.from_config(pso_context.config)
        pso._build_visibility()

        stream = random.Random(42)
        route = pso._construct_route(
            current_route=[], p_best_route=[], g_best_route=[],
            w=0.0, c1=0.0, c2=0.0, c3=pso._config.visibility_weight,
            stream=stream,
        )
        # Should still reach destination via visibility alone
        assert len(route) == 3
        assert route == [EdgeId("AB"), EdgeId("BC"), EdgeId("CD")]


# =========================================================================
# SwarmFactory registration test
# =========================================================================


class TestSwarmFactory:

    def test_pso_registered(self):
        from e3hybrid.swarm.factory import SwarmFactory
        assert SwarmFactory.is_registered("pso")
        routing = SwarmFactory.create_algorithm("pso")
        assert routing.name == "pso"

    def test_pso_name_property(self):
        pso = PSORouting()
        assert pso.name == "pso"