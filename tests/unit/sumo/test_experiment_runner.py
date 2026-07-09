"""Tests for SumoExperimentRunner — full experiment orchestration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from e3hybrid.network.edge import Edge, MutableEdgeState
from e3hybrid.network.graph import DirectedGraph
from e3hybrid.network.node import Node
from e3hybrid.network.types import EdgeId, NodeId


@pytest.fixture
def sumo_config():
    mc = MagicMock()
    mc.step_length_ms = 1000
    mc.reroute_interval_steps = 10
    mc.logging_interval_steps = 60
    mc.sumo_net_file = MagicMock()
    mc.sumo_route_file = MagicMock()
    mc.sumo_seed = 42
    mc.use_gui = False
    mc.traci_port = 8813
    mc.use_libsumo = True
    mc.algorithm_names = ("dijkstra",)
    mc.algorithm_split = (("dijkstra", 1.0),)
    return mc


@pytest.fixture
def mock_algorithms():
    algo = MagicMock()
    algo.name = "dijkstra"
    return {"dijkstra": algo}


@pytest.fixture
def vehicle_map():
    return {"dijkstra": ["veh_1", "veh_2"]}


class TestSumoExperimentRunner:
    """Tests for SumoExperimentRunner."""

    @patch("e3hybrid.sumo.experiment_runner.SumoTraciConnection")
    @patch("e3hybrid.sumo.experiment_runner.SumoNetworkImporter")
    def test_run_returns_result(
        self, mock_importer_cls, mock_conn_cls, sumo_config, mock_algorithms, vehicle_map
    ):
        mock_connection = MagicMock()
        mock_connection.get_simulation_time.return_value = 3600000
        mock_conn_cls.return_value = mock_connection

        g = DirectedGraph()
        g.add_node(Node(NodeId("A"), x=0.0, y=0.0))
        g.add_node(Node(NodeId("B"), x=1.0, y=1.0))
        g.add_edge(Edge(EdgeId("e1"), source=NodeId("A"), target=NodeId("B"), length_m=100.0, speed_limit_mps=15.0))
        mock_importer = MagicMock()
        mock_importer.import_graph.return_value = g
        mock_conn_cls.return_value = mock_connection

        from e3hybrid.sumo.experiment_runner import SumoExperimentRunner

        runner = SumoExperimentRunner(sumo_config)
        result = runner.run(mock_algorithms, vehicle_map, total_steps=10)

        assert result.total_steps == 10
        assert result.total_vehicles == 2
        assert result.simulation_time_ms == 3600000
        assert result.algorithm_names == ("dijkstra",)

    @patch("e3hybrid.sumo.experiment_runner.SumoTraciConnection")
    @patch("e3hybrid.sumo.experiment_runner.SumoNetworkImporter")
    def test_run_cleans_up_on_success(
        self, mock_importer_cls, mock_conn_cls, sumo_config, mock_algorithms, vehicle_map
    ):
        mock_connection = MagicMock()
        mock_connection.get_simulation_time.return_value = 10000
        mock_conn_cls.return_value = mock_connection

        g = DirectedGraph()
        g.add_node(Node(NodeId("A"), x=0.0, y=0.0))
        g.add_node(Node(NodeId("B"), x=1.0, y=1.0))
        g.add_edge(Edge(EdgeId("e1"), source=NodeId("A"), target=NodeId("B"), length_m=100.0, speed_limit_mps=15.0))
        mock_importer = MagicMock()
        mock_importer.import_graph.return_value = g

        from e3hybrid.sumo.experiment_runner import SumoExperimentRunner

        runner = SumoExperimentRunner(sumo_config)
        runner.run(mock_algorithms, vehicle_map, total_steps=5)

        mock_connection.stop.assert_called_once()

    @patch("e3hybrid.sumo.experiment_runner.SumoTraciConnection")
    @patch("e3hybrid.sumo.experiment_runner.SumoNetworkImporter")
    def test_properties(
        self, mock_importer_cls, mock_conn_cls, sumo_config, mock_algorithms, vehicle_map
    ):
        mock_connection = MagicMock()
        mock_connection.get_simulation_time.return_value = 5000
        mock_conn_cls.return_value = mock_connection

        g = DirectedGraph()
        g.add_node(Node(NodeId("A"), x=0.0, y=0.0))
        g.add_node(Node(NodeId("B"), x=1.0, y=1.0))
        g.add_edge(Edge(EdgeId("e1"), source=NodeId("A"), target=NodeId("B"), length_m=100.0, speed_limit_mps=15.0))
        mock_importer = MagicMock()
        mock_importer.import_graph.return_value = g

        from e3hybrid.sumo.experiment_runner import SumoExperimentRunner

        runner = SumoExperimentRunner(sumo_config)
        assert runner.config is sumo_config
        assert runner.result is None
        assert runner.simulation is None

        result = runner.run(mock_algorithms, vehicle_map, total_steps=3)
        assert runner.result is result
        assert runner.result.total_steps == 3