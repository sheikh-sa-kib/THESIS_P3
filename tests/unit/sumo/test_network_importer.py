"""Tests for SumoNetworkImporter (mocked TraCI)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from e3hybrid.network.types import NodeId, EdgeId
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
    mock_traci_mod = MagicMock()
    mock_traci_mod.junction.getIDList.return_value = ["j1", "j2", "j3"]
    mock_traci_mod.junction.getPosition.side_effect = [
        (0.0, 0.0),
        (100.0, 0.0),
        (200.0, 0.0),
    ]
    mock_traci_mod.edge.getIDList.return_value = ["e1", "e2", ":internal_1"]
    mock_traci_mod.lane.getLength.side_effect = lambda e: {"e1_0": 100.0, "e2_0": 100.0}.get(e, 0)
    mock_traci_mod.lane.getMaxSpeed.side_effect = lambda e: {"e1_0": 13.89, "e2_0": 13.89}.get(e, 0)
    mock_traci_mod.edge.getFromJunction.side_effect = lambda e: {"e1": "j1", "e2": "j2"}.get(e, "")
    mock_traci_mod.edge.getToJunction.side_effect = lambda e: {"e1": "j2", "e2": "j3"}.get(e, "")
    mock_traci_mod.edge.getLaneNumber.side_effect = lambda e: {"e1": 2, "e2": 1}.get(e, 0)

    with patch.dict("sys.modules", {"traci": mock_traci_mod}):
        yield mock_traci_mod


class TestNetworkImporter:
    def test_import_graph(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        importer = SumoNetworkImporter(conn)
        graph = importer.import_graph()
        assert graph is not None

    def test_imported_node_count(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        importer = SumoNetworkImporter(conn)
        graph = importer.import_graph()
        nodes = list(graph.nodes())
        assert len(nodes) == 3

    def test_imported_node_positions(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        importer = SumoNetworkImporter(conn)
        graph = importer.import_graph()
        n1 = graph.get_node(NodeId("j1"))
        assert n1 is not None
        assert n1.x == 0.0
        assert n1.y == 0.0
        n2 = graph.get_node(NodeId("j2"))
        assert n2 is not None
        assert n2.x == 100.0

    def test_imported_edge_count(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        importer = SumoNetworkImporter(conn)
        graph = importer.import_graph()
        edges = list(graph.edges())
        # Internal edge "e3" (actually ":internal_1") should be skipped
        assert len(edges) == 2

    def test_imported_edge_attributes(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        importer = SumoNetworkImporter(conn)
        graph = importer.import_graph()
        e1 = graph.get_edge(EdgeId("e1"))
        assert e1 is not None
        assert e1.length_m == 100.0
        assert e1.speed_limit_mps == 13.89
        assert e1.lane_count == 2
        assert e1.source == NodeId("j1")
        assert e1.target == NodeId("j2")

    def test_internal_edges_skipped(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        importer = SumoNetworkImporter(conn)
        graph = importer.import_graph()
        from e3hybrid.core.exceptions import NetworkError
        with pytest.raises(NetworkError):
            graph.get_edge(EdgeId(":internal_1"))

    def test_metadata_passed_through(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        importer = SumoNetworkImporter(conn)
        graph = importer.import_graph(graph_metadata={"source": "sumo"})
        assert graph.get_metadata("source") == "sumo"

    def test_edge_state_defaults(self, config: SumoConfig, mock_traci: MagicMock) -> None:
        conn = SumoTraciConnection(config)
        conn.start()
        importer = SumoNetworkImporter(conn)
        graph = importer.import_graph()
        e1 = graph.get_edge(EdgeId("e1"))
        assert e1 is not None
        assert e1.state.is_blocked is False
        assert e1.state.congestion_factor == 1.0