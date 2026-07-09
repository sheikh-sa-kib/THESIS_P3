"""Tests for SumoTraciConnection (mocked TraCI)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from e3hybrid.sumo.config import SumoConfig
from e3hybrid.sumo.connection import SumoTraciConnection
from e3hybrid.sumo.network_importer import SumoNetworkImporter


@pytest.fixture
def config() -> SumoConfig:
    return SumoConfig(
        sumo_net_file=Path("net.xml"),
        sumo_route_file=Path("rou.xml"),
        sumo_seed=42,
        use_libsumo=False,
    )


@pytest.fixture
def mock_traci() -> MagicMock:
    """Patch the traci module at import time by faking the start methods."""
    mock_traci_mod = MagicMock()
    mock_traci_mod.edge.getIDList.return_value = ["e1", "e2"]
    mock_traci_mod.edge.getTraveltime.return_value = 12.5
    mock_traci_mod.edge.getLastStepMeanSpeed.return_value = 8.0
    mock_traci_mod.edge.getLastStepOccupancy.return_value = 0.3
    mock_traci_mod.edge.getLaneNumber.return_value = 2
    mock_traci_mod.lane.getLength.return_value = 100.0
    mock_traci_mod.lane.getMaxSpeed.return_value = 13.89
    mock_traci_mod.edge.getFromJunction.return_value = "j1"
    mock_traci_mod.edge.getToJunction.return_value = "j2"
    mock_traci_mod.junction.getIDList.return_value = ["j1", "j2"]
    mock_traci_mod.junction.getPosition.return_value = (10.0, 20.0)
    mock_traci_mod.vehicle.getIDList.return_value = ["v1"]
    mock_traci_mod.vehicle.getRoute.return_value = ["e1", "e2"]
    mock_traci_mod.vehicle.getPosition.return_value = (15.0, 25.0)
    mock_traci_mod.vehicle.getRoadID.return_value = "e1"
    mock_traci_mod.vehicle.getSpeed.return_value = 5.0
    mock_traci_mod.vehicle.getTypeID.return_value = "DEFAULT_VEHTYPE"
    mock_traci_mod.vehicle.getEmissionParameter.return_value = {"CO2": 2.5}
    mock_traci_mod.simulation.getTime.return_value = 1000.0
    mock_traci_mod.simulation.getMinExpectedNumber.return_value = 10

    # Patch the import inside SumoTraciConnection._start_traci
    # We need to make 'traci' available to the module
    with patch.dict("sys.modules", {"traci": mock_traci_mod}):
        yield mock_traci_mod


class TestConnectionLifecycle:
    def test_start_and_stop(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        assert not conn.is_connected
        conn.start()
        assert conn.is_connected
        conn.stop()
        assert not conn.is_connected

    def test_double_start_is_noop(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        conn.start()  # should not raise
        assert conn.is_connected

    def test_double_stop_is_noop(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        conn.stop()
        conn.stop()  # should not raise
        assert not conn.is_connected

    def test_step_returns_time(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        t = conn.step()
        assert t == 1000


class TestConnectionEdgeQueries:
    def test_get_edge_ids(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        ids = conn.get_edge_ids()
        assert ids == ["e1", "e2"]

    def test_get_edge_travel_time(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        tt = conn.get_edge_travel_time("e1")
        assert tt == 12.5

    def test_get_edge_mean_speed(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        spd = conn.get_edge_mean_speed("e1")
        assert spd == 8.0

    def test_get_edge_occupancy(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        occ = conn.get_edge_occupancy("e1")
        assert occ == 0.3

    def test_get_edge_lane_count(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        assert conn.get_edge_lane_count("e1") == 2

    def test_get_edge_length(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        assert conn.get_edge_length("e1") == 100.0

    def test_get_edge_speed_limit(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        assert conn.get_edge_speed_limit("e1") == 13.89

    def test_get_edge_from_to_junction(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        assert conn.get_edge_from_junction("e1") == "j1"
        assert conn.get_edge_to_junction("e1") == "j2"


class TestConnectionJunctionQueries:
    def test_get_junction_ids(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        ids = conn.get_junction_ids()
        assert ids == ["j1", "j2"]

    def test_get_junction_position(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        x, y = conn.get_junction_position("j1")
        assert x == 10.0
        assert y == 20.0


class TestConnectionVehicleQueries:
    def test_get_vehicle_ids(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        assert conn.get_vehicle_ids() == ["v1"]

    def test_get_vehicle_route(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        assert conn.get_vehicle_route("v1") == ["e1", "e2"]

    def test_get_vehicle_position(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        x, y, eid = conn.get_vehicle_position("v1")
        assert x == 15.0
        assert y == 25.0
        assert eid == "e1"

    def test_get_vehicle_speed(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        assert conn.get_vehicle_speed("v1") == 5.0

    def test_get_vehicle_type(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        assert conn.get_vehicle_type("v1") == "DEFAULT_VEHTYPE"

    def test_set_vehicle_route(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        conn.set_vehicle_route("v1", ["e1", "e2"])
        mock_traci.vehicle.setRoute.assert_called_once_with("v1", ["e1", "e2"])


class TestConnectionSimulationQueries:
    def test_get_simulation_time(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        assert conn.get_simulation_time() == 1000

    def test_get_min_expected_vehicles(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        assert conn.get_min_expected_number_vehicles() == 10