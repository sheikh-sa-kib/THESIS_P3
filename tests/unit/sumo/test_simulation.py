"""Tests for SumoSimulation — step loop and graph state sync."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from e3hybrid.network.edge import Edge, MutableEdgeState
from e3hybrid.network.graph import DirectedGraph
from e3hybrid.network.node import Node
from e3hybrid.network.types import EdgeId, NodeId
from e3hybrid.sumo.simulation import SumoSimulation


@pytest.fixture
def mock_config():
    mc = MagicMock()
    mc.step_length_ms = 1000
    mc.reroute_interval_steps = 10
    mc.logging_interval_steps = 60
    return mc


@pytest.fixture
def mock_connection():
    conn = MagicMock()
    conn.step.return_value = 1000
    conn.get_edge_travel_time.return_value = 12.5
    conn.get_edge_mean_speed.return_value = 13.5
    conn.get_edge_occupancy.return_value = 0.3
    conn.get_edge_lane_count.return_value = 2
    conn.get_vehicle_ids.return_value = []
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


class TestSumoSimulation:

    def test_initial_state(self, mock_config, mock_connection, small_graph):
        sim = SumoSimulation(mock_connection, mock_config, small_graph)
        assert sim.step_count == 0
        assert not sim.is_running
        assert sim.graph is small_graph

    def test_step_increments_count_and_updates_state(
        self, mock_config, mock_connection, small_graph
    ):
        sim = SumoSimulation(mock_connection, mock_config, small_graph)
        result = sim.step()
        assert result == 1000
        assert sim.step_count == 1
        mock_connection.step.assert_called_once()

    def test_run_executes_total_steps(self, mock_config, mock_connection, small_graph):
        sim = SumoSimulation(mock_connection, mock_config, small_graph)
        sim.run(5)
        assert sim.step_count == 5
        assert mock_connection.step.call_count == 5
        assert not sim.is_running

    def test_run_sets_running_flag(self, mock_config, mock_connection, small_graph):
        sim = SumoSimulation(mock_connection, mock_config, small_graph)
        sim.run(3)
        assert not sim.is_running

    def test_is_running_during_run(self, mock_config, mock_connection, small_graph):
        sim = SumoSimulation(mock_connection, mock_config, small_graph)
        flag_values = []

        def capture_flag(_):
            flag_values.append(sim.is_running)

        sim.register_on_step(capture_flag)
        sim.run(3)
        assert all(flag_values)

    def test_register_on_step_callback_invoked(
        self, mock_config, mock_connection, small_graph
    ):
        sim = SumoSimulation(mock_connection, mock_config, small_graph)
        calls = []
        sim.register_on_step(lambda t: calls.append(t))
        sim.run(3)
        assert len(calls) == 3
        assert all(t == 1000 for t in calls)

    def test_multiple_callbacks(self, mock_config, mock_connection, small_graph):
        sim = SumoSimulation(mock_connection, mock_config, small_graph)
        c1, c2 = [], []
        sim.register_on_step(lambda t: c1.append(t))
        sim.register_on_step(lambda t: c2.append(t))
        sim.run(2)
        assert len(c1) == 2
        assert len(c2) == 2

    def test_update_graph_state_syncs_all_edges(
        self, mock_config, mock_connection, small_graph
    ):
        sim = SumoSimulation(mock_connection, mock_config, small_graph)
        sim.update_graph_state()
        for edge in small_graph.edges():
            assert edge.state.congestion_factor > 0

    def test_update_graph_state_congestion(
        self, mock_config, mock_connection, small_graph
    ):
        mock_connection.get_edge_occupancy.return_value = 0.5
        sim = SumoSimulation(mock_connection, mock_config, small_graph)
        sim.update_graph_state()
        for edge in small_graph.edges():
            # congestion = 1.0 + 0.5 / 2 = 1.25
            assert edge.state.congestion_factor == 1.25

    def test_update_graph_state_blocks_edge_with_huge_travel_time(
        self, mock_config, mock_connection, small_graph
    ):
        mock_connection.get_edge_travel_time.return_value = 1e12
        sim = SumoSimulation(mock_connection, mock_config, small_graph)
        sim.update_graph_state()
        for edge in small_graph.edges():
            assert edge.state.is_blocked

    def test_update_graph_state_does_not_block_normal_edge(
        self, mock_config, mock_connection, small_graph
    ):
        sim = SumoSimulation(mock_connection, mock_config, small_graph)
        sim.update_graph_state()
        for edge in small_graph.edges():
            assert not edge.state.is_blocked

    def test_update_graph_state_sets_travel_time(
        self, mock_config, mock_connection, small_graph
    ):
        mock_connection.get_edge_travel_time.return_value = 42.0
        sim = SumoSimulation(mock_connection, mock_config, small_graph)
        sim.update_graph_state()
        for edge in small_graph.edges():
            assert edge.state.travel_time_override_s == 42.0

    def test_update_graph_state_sets_mean_speed(
        self, mock_config, mock_connection, small_graph
    ):
        mock_connection.get_edge_mean_speed.return_value = 11.0
        sim = SumoSimulation(mock_connection, mock_config, small_graph)
        sim.update_graph_state()
        for edge in small_graph.edges():
            assert edge.state.current_speed_mps == 11.0

    def test_update_graph_state_preserves_other_state(
        self, mock_config, mock_connection, small_graph
    ):
        e1 = small_graph.get_edge(EdgeId("e1"))
        old_hazard = e1.state.hazard_penalty_s
        sim = SumoSimulation(mock_connection, mock_config, small_graph)
        sim.update_graph_state()
        updated = small_graph.get_edge(EdgeId("e1"))
        assert updated.state.hazard_penalty_s == old_hazard
        assert updated.state.emergency_penalty_s == 0.0

    def test_check_emergency_no_vehicles(self, mock_config, mock_connection, small_graph):
        mock_connection.get_vehicle_ids.return_value = []
        sim = SumoSimulation(mock_connection, mock_config, small_graph)
        assert sim.check_emergency() == []

    def test_check_emergency_detects_emergency_type(
        self, mock_config, mock_connection, small_graph
    ):
        mock_connection.get_vehicle_ids.return_value = ["amb1", "car1"]
        mock_connection.get_vehicle_type.side_effect = lambda vid: {
            "amb1": "emergency", "car1": "passenger"
        }.get(vid, "passenger")
        sim = SumoSimulation(mock_connection, mock_config, small_graph)
        result = sim.check_emergency()
        assert result == ["amb1"]

    def test_check_emergency_case_insensitive(
        self, mock_config, mock_connection, small_graph
    ):
        mock_connection.get_vehicle_ids.return_value = ["fire1"]
        mock_connection.get_vehicle_type.return_value = "Emergency"
        sim = SumoSimulation(mock_connection, mock_config, small_graph)
        result = sim.check_emergency()
        assert result == ["fire1"]

    def test_check_emergency_skips_exceptions(
        self, mock_config, mock_connection, small_graph
    ):
        mock_connection.get_vehicle_ids.return_value = ["bad_veh"]
        mock_connection.get_vehicle_type.side_effect = Exception("TraCI error")
        sim = SumoSimulation(mock_connection, mock_config, small_graph)
        assert sim.check_emergency() == []

    def test_graph_property_immutable(self, mock_config, mock_connection, small_graph):
        sim = SumoSimulation(mock_connection, mock_config, small_graph)
        assert sim.graph is small_graph

    def test_step_integrates_update_graph_state(self, mock_config, mock_connection, small_graph):
        sim = SumoSimulation(mock_connection, mock_config, small_graph)
        mock_connection.get_edge_travel_time.return_value = 99.0
        sim.step()
        for edge in small_graph.edges():
            assert edge.state.travel_time_override_s == 99.0