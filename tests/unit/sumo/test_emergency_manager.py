"""Tests for SumoEmergencyManager (direct graph state API)."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, PropertyMock, call, patch

from e3hybrid.network.edge import MutableEdgeState
from e3hybrid.sumo.emergency_manager import (
    _DEFAULT_EMERGENCY_PENALTY_S,
    _EMERGENCY_RADIUS_EDGES,
    SumoEmergencyManager,
)


@pytest.fixture
def mock_connection():
    conn = MagicMock()
    conn.get_vehicle_ids.return_value = []
    conn.get_simulation_time.return_value = 0
    return conn


@pytest.fixture
def mock_config():
    cfg = MagicMock()
    cfg.rerouting_interval = 5
    return cfg


@pytest.fixture
def mock_graph():
    graph = MagicMock()
    graph.has_edge.return_value = True
    return graph


@pytest.fixture
def manager(mock_connection, mock_config, mock_graph):
    return SumoEmergencyManager(
        connection=mock_connection,
        config=mock_config,
        graph=mock_graph,
    )


class TestSumoEmergencyManager:
    """Tests for the core SumoEmergencyManager class."""

    def test_initial_state(self, manager):
        assert manager.active_emergency_count == 0
        assert manager.active_emergency_vehicle_ids == frozenset()

    def test_no_emergency_vehicles_detected(self, mock_connection, manager):
        mock_connection.get_vehicle_ids.return_value = ["car1", "car2"]
        mock_connection.get_vehicle_type.side_effect = ["passenger", "passenger"]

        events = manager.check_and_respond(1000)
        assert events == []
        assert manager.active_emergency_count == 0

    def test_detects_emergency_vehicle(self, mock_connection, mock_graph, manager):
        mock_connection.get_vehicle_ids.return_value = ["emg1"]
        mock_connection.get_vehicle_type.return_value = "emergency"
        mock_connection.get_vehicle_route.return_value = ["e1", "e2", "e3", "e4", "e5"]
        mock_connection.get_vehicle_position.return_value = (0, 0, "e3")

        mock_graph.get_edge.return_value.state = MutableEdgeState(
            is_blocked=False,
            current_speed_mps=13.0,
            travel_time_override_s=None,
            congestion_factor=1.0,
            hazard_penalty_s=0.0,
            emergency_penalty_s=0.0,
            communication_penalty_s=0.0,
        )

        events = manager.check_and_respond(1000)
        assert events == ["emg1"]
        assert manager.active_emergency_count == 1

        expected_calls = [call(eid) for eid in ("e1", "e2", "e3", "e4", "e5")]
        mock_graph.has_edge.assert_has_calls(expected_calls, any_order=True)
        assert mock_graph.update_edge_state.call_count == 5

    def test_does_not_activate_twice(self, mock_connection, mock_graph, manager):
        mock_connection.get_vehicle_ids.return_value = ["emg1"]
        mock_connection.get_vehicle_type.return_value = "emergency"
        mock_connection.get_vehicle_route.return_value = ["e1", "e2", "e3"]
        mock_connection.get_vehicle_position.return_value = (0, 0, "e2")

        mock_graph.get_edge.return_value.state = MutableEdgeState(
            is_blocked=False,
            current_speed_mps=13.0,
            travel_time_override_s=None,
            congestion_factor=1.0,
            hazard_penalty_s=0.0,
            emergency_penalty_s=0.0,
            communication_penalty_s=0.0,
        )

        events1 = manager.check_and_respond(1000)
        assert events1 == ["emg1"]

        mock_graph.reset_mock()
        events2 = manager.check_and_respond(2000)
        assert events2 == []
        assert manager.active_emergency_count == 1
        mock_graph.update_edge_state.assert_not_called()

    def test_resolves_when_vehicle_disappears(self, mock_connection, mock_graph, manager):
        mock_connection.get_vehicle_ids.side_effect = [
            ["emg1"],
            [],
        ]
        mock_connection.get_vehicle_type.return_value = "emergency"
        mock_connection.get_vehicle_route.return_value = ["e1", "e2", "e3"]
        mock_connection.get_vehicle_position.return_value = (0, 0, "e2")
        mock_connection.get_simulation_time.return_value = 1000

        mock_graph.get_edge.return_value.state = MutableEdgeState(
            is_blocked=False,
            current_speed_mps=13.0,
            travel_time_override_s=None,
            congestion_factor=1.0,
            hazard_penalty_s=0.0,
            emergency_penalty_s=_DEFAULT_EMERGENCY_PENALTY_S,
            communication_penalty_s=0.0,
        )

        events1 = manager.check_and_respond(1000)
        assert events1 == ["emg1"]
        assert manager.active_emergency_count == 1

        mock_graph.reset_mock()
        events2 = manager.check_and_respond(2000)
        assert events2 == []
        assert manager.active_emergency_count == 0

        # Should have restored the edge states
        assert mock_graph.update_edge_state.call_count == 3

    def test_activates_network_effect(self, mock_connection, mock_graph, manager):
        mock_connection.get_vehicle_ids.return_value = ["emg1"]
        mock_connection.get_vehicle_type.return_value = "emergency"
        mock_connection.get_vehicle_route.return_value = ["e1", "e2", "e3"]
        mock_connection.get_vehicle_position.return_value = (0, 0, "e2")

        mock_graph.get_edge.return_value.state = MutableEdgeState(
            is_blocked=False,
            current_speed_mps=13.0,
            travel_time_override_s=None,
            congestion_factor=1.0,
            hazard_penalty_s=0.0,
            emergency_penalty_s=0.0,
            communication_penalty_s=0.0,
        )

        events = manager.check_and_respond(1000)
        assert events == ["emg1"]
        assert manager.active_emergency_count == 1

    def test_non_emergency_vehicle_skipped(self, mock_connection, manager):
        mock_connection.get_vehicle_ids.return_value = ["bus1"]
        mock_connection.get_vehicle_type.return_value = "bus"

        events = manager.check_and_respond(1000)
        assert events == []
        assert manager.active_emergency_count == 0

    def test_exception_handling_in_detection(self, mock_connection, manager):
        mock_connection.get_vehicle_ids.return_value = ["car1"]
        mock_connection.get_vehicle_type.side_effect = RuntimeError("TraCI error")

        events = manager.check_and_respond(1000)
        assert events == []
        assert manager.active_emergency_count == 0

    def test_active_emergency_default_penalty_applied(self, mock_connection, mock_graph, manager):
        mock_connection.get_vehicle_ids.return_value = ["emg1"]
        mock_connection.get_vehicle_type.return_value = "emergency"
        mock_connection.get_vehicle_route.return_value = ["e1", "e2", "e3"]
        mock_connection.get_vehicle_position.return_value = (0, 0, "e2")

        mock_edge = MagicMock()
        mock_edge.state = MutableEdgeState(
            is_blocked=False,
            current_speed_mps=13.0,
            travel_time_override_s=None,
            congestion_factor=1.0,
            hazard_penalty_s=0.0,
            emergency_penalty_s=0.0,
            communication_penalty_s=0.0,
        )

        original_get_edge = mock_graph.get_edge
        mock_graph.get_edge.side_effect = lambda eid: mock_edge

        events = manager.check_and_respond(1000)
        assert events == ["emg1"]

        # Verify update_edge_state was called with emergency_penalty_s added
        for call_args in mock_graph.update_edge_state.call_args_list:
            _eid, state = call_args[0]
            assert state.emergency_penalty_s == _DEFAULT_EMERGENCY_PENALTY_S

    def test_resolve_restores_network_state(self, mock_connection, mock_graph, manager):
        mock_connection.get_vehicle_ids.side_effect = [
            ["emg1"],
            []
        ]
        mock_connection.get_vehicle_type.return_value = "emergency"
        mock_connection.get_vehicle_route.return_value = ["e1", "e2", "e3"]
        mock_connection.get_vehicle_position.return_value = (0, 0, "e2")
        mock_connection.get_simulation_time.return_value = 1000

        mock_edge = MagicMock()
        mock_edge.state = MutableEdgeState(
            is_blocked=False,
            current_speed_mps=13.0,
            travel_time_override_s=None,
            congestion_factor=1.0,
            hazard_penalty_s=0.0,
            emergency_penalty_s=_DEFAULT_EMERGENCY_PENALTY_S,
            communication_penalty_s=0.0,
        )
        mock_graph.get_edge.side_effect = lambda eid: mock_edge

        events1 = manager.check_and_respond(1000)
        assert events1 == ["emg1"]

        mock_graph.reset_mock()
        events2 = manager.check_and_respond(2000)
        assert events2 == []
        assert manager.active_emergency_count == 0

        # Verify emergency penalty was restored to 0
        for call_args in mock_graph.update_edge_state.call_args_list:
            _eid, state = call_args[0]
            assert state.emergency_penalty_s == 0.0