"""Tests for SumoReroutingManager — reroute scheduling and application."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from e3hybrid.network.edge import Edge, MutableEdgeState
from e3hybrid.network.graph import DirectedGraph
from e3hybrid.network.node import Node
from e3hybrid.network.types import EdgeId, NodeId


@pytest.fixture
def mock_config():
    mc = MagicMock()
    mc.reroute_interval_steps = 10
    return mc


@pytest.fixture
def mock_connection():
    conn = MagicMock()
    conn.get_vehicle_position.return_value = (1.0, 2.0, "e1")
    conn.get_vehicle_route.return_value = ["e1", "e2"]
    return conn


@pytest.fixture
def small_graph():
    g = DirectedGraph()
    n1 = Node(NodeId("A"), x=0.0, y=0.0)
    n2 = Node(NodeId("B"), x=1.0, y=1.0)
    n3 = Node(NodeId("C"), x=2.0, y=2.0)
    g.add_node(n1)
    g.add_node(n2)
    g.add_node(n3)
    e1 = Edge(EdgeId("e1"), source=NodeId("A"), target=NodeId("B"), length_m=100.0, speed_limit_mps=15.0)
    e2 = Edge(EdgeId("e2"), source=NodeId("B"), target=NodeId("C"), length_m=100.0, speed_limit_mps=15.0)
    g.add_edge(e1)
    g.add_edge(e2)
    return g


@pytest.fixture
def mock_algorithm():
    algo = MagicMock()
    algo.name = "dijkstra"
    return algo


def _make_manager(mock_config, mock_connection, mock_algorithm, vehicle_ids=None):
    from e3hybrid.sumo.rerouting_manager import SumoReroutingManager

    return SumoReroutingManager(
        connection=mock_connection,
        config=mock_config,
        algorithm=mock_algorithm,
        vehicle_ids=vehicle_ids or ["veh_1"],
    )


class TestSumoReroutingManager:

    def test_initial_state(self, mock_config, mock_connection, mock_algorithm):
        mgr = _make_manager(mock_config, mock_connection, mock_algorithm)
        assert mgr.reroute_count == 0
        assert mgr.vehicle_ids == ["veh_1"]
        assert mgr.algorithm is mock_algorithm

    def test_vehicle_ids_returns_copy(self, mock_config, mock_connection, mock_algorithm):
        mgr = _make_manager(mock_config, mock_connection, mock_algorithm)
        ids = mgr.vehicle_ids
        ids.append("extra")
        assert mgr.vehicle_ids == ["veh_1"]

    def test_should_reroute_at_interval(self, mock_config, mock_connection, mock_algorithm):
        mgr = _make_manager(mock_config, mock_connection, mock_algorithm)
        assert not mgr.should_reroute(0)
        assert mgr.should_reroute(10)
        assert mgr.should_reroute(20)
        assert not mgr.should_reroute(5)

    def test_should_reroute_returns_false_when_interval_zero(
        self, mock_config, mock_connection, mock_algorithm
    ):
        mock_config.reroute_interval_steps = 0
        mgr = _make_manager(mock_config, mock_connection, mock_algorithm)
        assert not mgr.should_reroute(10)

    def test_apply_reroute_sets_route_and_increments_count(
        self, mock_config, mock_connection, mock_algorithm, small_graph
    ):
        mgr = _make_manager(mock_config, mock_connection, mock_algorithm)
        mgr.apply_reroute("veh_1", ["e1", "e2"])
        mock_connection.set_vehicle_route.assert_called_once_with("veh_1", ["e1", "e2"])
        # reroute_count tracks computed routes, not applied
        assert mgr.reroute_count == 0

    def test_apply_reroutes_batch(self, mock_config, mock_connection, mock_algorithm):
        mgr = _make_manager(mock_config, mock_connection, mock_algorithm, ["v1", "v2"])
        mgr.apply_reroutes([("v1", ["e1"]), ("v2", ["e2"])])
        assert mock_connection.set_vehicle_route.call_count == 2
        # reroute_count tracks computed routes, not applied
        assert mgr.reroute_count == 0

    def test_compute_reroute_returns_route(
        self, mock_config, mock_connection, mock_algorithm, small_graph
    ):
        from e3hybrid.routing.request import RoutingRequest

        fake_result = MagicMock()
        fake_result.success = True
        fake_result.primary_route.edge_sequence = [EdgeId("e2")]
        mock_algorithm.compute_route.return_value = fake_result

        mgr = _make_manager(mock_config, mock_connection, mock_algorithm)
        result = mgr.compute_reroute("veh_1", "e1", NodeId("C"), small_graph)
        assert result == ["e1", "e2"]

    def test_compute_reroute_returns_none_when_failure(
        self, mock_config, mock_connection, mock_algorithm, small_graph
    ):
        from e3hybrid.routing.result import RoutingResult
        from e3hybrid.routing.statistics import RoutingStatistics

        mock_algorithm.compute_route.return_value = RoutingResult(
            candidates=(),
            primary_route=None,
            success=False,
            failure_reason="no path",
            statistics=RoutingStatistics(0, 0, 0),
            runtime_s=0.0,
        )

        mgr = _make_manager(mock_config, mock_connection, mock_algorithm)
        result = mgr.compute_reroute("veh_1", "e1", NodeId("C"), small_graph)
        assert result is None

    def test_compute_reroute_returns_none_when_at_destination(
        self, mock_config, mock_connection, mock_algorithm, small_graph
    ):
        # vehicle on edge e1, whose target is B -> set destination to B
        mgr = _make_manager(mock_config, mock_connection, mock_algorithm)
        result = mgr.compute_reroute("veh_1", "e1", NodeId("B"), small_graph)
        assert result is None

    def test_compute_reroutes_returns_list(
        self, mock_config, mock_connection, mock_algorithm, small_graph
    ):
        from e3hybrid.routing.result import RoutingResult
        from e3hybrid.routing.statistics import RoutingStatistics

        mock_connection.get_vehicle_position.return_value = (1.0, 2.0, "e1")
        mock_connection.get_vehicle_route.return_value = ["e1", "e2"]
        mock_algorithm.compute_route.return_value = RoutingResult(
            candidates=(),
            primary_route=None,
            success=False,
            failure_reason="no path",
            statistics=RoutingStatistics(0, 0, 0),
            runtime_s=0.0,
        )

        mgr = _make_manager(mock_config, mock_connection, mock_algorithm, vehicle_ids=["v1"])
        results = mgr.compute_reroutes(small_graph)
        assert results == []

    def test_compute_reroutes_with_explicit_destinations(
        self, mock_config, mock_connection, mock_algorithm, small_graph
    ):
        from e3hybrid.routing.result import RoutingResult
        from e3hybrid.routing.statistics import RoutingStatistics

        mock_connection.get_vehicle_position.return_value = (1.0, 2.0, "e1")
        mock_algorithm.compute_route.return_value = RoutingResult(
            candidates=(),
            primary_route=None,
            success=False,
            failure_reason="fail",
            statistics=RoutingStatistics(0, 0, 0),
            runtime_s=0.0,
        )

        mgr = _make_manager(mock_config, mock_connection, mock_algorithm, vehicle_ids=["v1"])
        results = mgr.compute_reroutes(
            small_graph,
            vehicles_with_destinations={"v1": NodeId("C")},
        )
        assert results == []

    def test_vehicle_ids_from_constructor(self, mock_config, mock_connection, mock_algorithm):
        mgr = _make_manager(mock_config, mock_connection, mock_algorithm, vehicle_ids=["a", "b", "c"])
        assert mgr.vehicle_ids == ["a", "b", "c"]