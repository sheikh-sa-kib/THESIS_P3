"""Tests for SumoRoutingAdapter — RoutingAlgorithm wrapper for SUMO."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from e3hybrid.network.edge import Edge, MutableEdgeState
from e3hybrid.network.graph import DirectedGraph
from e3hybrid.network.node import Node
from e3hybrid.network.types import EdgeId, NodeId
from e3hybrid.sumo.adapters import SumoRoutingAdapter


@pytest.fixture
def mock_algorithm():
    algo = MagicMock()
    algo.name = "mock_algo"
    return algo


@pytest.fixture
def small_graph():
    g = DirectedGraph()
    n1 = Node(NodeId("A"), x=0.0, y=0.0)
    n2 = Node(NodeId("B"), x=1.0, y=1.0)
    g.add_node(n1)
    g.add_node(n2)
    e1 = Edge(EdgeId("e1"), source=NodeId("A"), target=NodeId("B"), length_m=100.0, speed_limit_mps=15.0)
    g.add_edge(e1)
    return g


class TestSumoRoutingAdapter:

    def test_name_delegates_to_wrapped_algo(self, mock_algorithm):
        adapter = SumoRoutingAdapter(mock_algorithm)
        assert adapter.name == "mock_algo"

    def test_compute_route_delegates_to_wrapped_algo(
        self, mock_algorithm, small_graph
    ):
        from e3hybrid.routing.request import RoutingRequest

        request = RoutingRequest(
            source_node=NodeId("A"),
            destination_node=NodeId("B"),
            vehicle_id=MagicMock(),
            vehicle_constraints={},
            battery_state={},
            max_candidates=1,
            timeout_s=30.0,
        )

        adapter = SumoRoutingAdapter(mock_algorithm)
        adapter.compute_route(request, graph=small_graph)
        mock_algorithm.compute_route.assert_called_once_with(request, graph=small_graph)

    def test_compute_route_passes_result_through(
        self, mock_algorithm, small_graph
    ):
        from e3hybrid.routing.request import RoutingRequest

        fake_result = MagicMock()
        mock_algorithm.compute_route.return_value = fake_result

        request = RoutingRequest(
            source_node=NodeId("A"),
            destination_node=NodeId("B"),
            vehicle_id=MagicMock(),
            vehicle_constraints={},
            battery_state={},
            max_candidates=1,
            timeout_s=30.0,
        )

        adapter = SumoRoutingAdapter(mock_algorithm)
        result = adapter.compute_route(request, graph=small_graph)
        assert result is fake_result

    def test_works_with_dijkstra(self):
        from e3hybrid.routing.dijkstra import DijkstraRouting
        from e3hybrid.routing.request import RoutingRequest

        g = DirectedGraph()
        n1 = Node(NodeId("A"), x=0.0, y=0.0)
        n2 = Node(NodeId("B"), x=1.0, y=0.0)
        g.add_node(n1)
        g.add_node(n2)
        e = Edge(EdgeId("e1"), source=NodeId("A"), target=NodeId("B"), length_m=100.0, speed_limit_mps=15.0)
        g.add_edge(e)

        dijkstra = DijkstraRouting()
        adapter = SumoRoutingAdapter(dijkstra)
        assert adapter.name == "dijkstra"

        request = RoutingRequest(
            source_node=NodeId("A"),
            destination_node=NodeId("B"),
            vehicle_id=MagicMock(),
            vehicle_constraints={},
            battery_state={},
            max_candidates=1,
            timeout_s=30.0,
        )
        result = adapter.compute_route(request, graph=g)
        assert result.success
        assert result.primary_route is not None