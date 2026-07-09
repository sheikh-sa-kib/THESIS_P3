"""Unit tests for ObservationAssembler."""

from __future__ import annotations

from unittest.mock import Mock, MagicMock

import pytest

from e3hybrid.decision.config import DecisionConfig
from e3hybrid.decision.observation_assembler import ObservationAssembler
from e3hybrid.network.types import EdgeId, NodeId
from e3hybrid.vehicle.types import VehicleId


def test_observation_assembler_initialization():
    """Test ObservationAssembler initialization."""
    config = DecisionConfig.default()
    assembler = ObservationAssembler(config=config)
    
    assert assembler.config == config


def test_observation_assembler_build_battery_snapshot():
    """Test building battery snapshot."""
    config = DecisionConfig.default()
    assembler = ObservationAssembler(config=config)
    
    battery = Mock()
    battery.soc_kwh = 40.0
    battery.capacity_kwh = 50.0
    battery.soc_fraction = 0.8
    
    snapshot = assembler._build_battery_snapshot(battery)
    
    assert snapshot.soc_kwh == 40.0
    assert snapshot.capacity_kwh == 50.0
    assert snapshot.soc_fraction == 0.8


def test_observation_assembler_build_graph_snapshot_no_current_edge():
    """Test building graph snapshot when vehicle has no current edge."""
    config = DecisionConfig.default()
    assembler = ObservationAssembler(config=config)
    
    graph = Mock()
    
    snapshot = assembler._build_graph_snapshot(graph, None, 2)
    
    assert snapshot.current_edge is None
    assert snapshot.neighbour_edges == ()
    assert snapshot.blocked_edge_ids == frozenset()


def test_observation_assembler_build_edge_snapshot():
    """Test building edge snapshot."""
    config = DecisionConfig.default()
    assembler = ObservationAssembler(config=config)
    
    edge = Mock()
    edge.edge_id = EdgeId("e1")
    edge.source = NodeId("n1")
    edge.target = NodeId("n2")
    edge.length_m = 100.0
    edge.speed_limit_mps = 13.89
    edge.is_blocked = False
    edge.congestion_factor = 1.0
    edge.hazard_penalty_s = 0.0
    edge.emergency_penalty_s = 0.0
    edge.communication_penalty_s = 0.0
    edge.estimated_cost = 10.0
    
    snapshot = assembler._build_edge_snapshot(edge)
    
    assert snapshot.edge_id == EdgeId("e1")
    assert snapshot.source == NodeId("n1")
    assert snapshot.target == NodeId("n2")
    assert snapshot.length_m == 100.0
    assert snapshot.is_blocked is False


def test_observation_assemble():
    """Test full observation assembly."""
    config = DecisionConfig.default()
    assembler = ObservationAssembler(config=config)
    
    # Mock vehicle
    vehicle = Mock()
    vehicle.vehicle_id = VehicleId("v1")
    vehicle.state = Mock()
    vehicle.state.current_edge_id = EdgeId("e1")
    vehicle.state.current_node_id = NodeId("n1")
    vehicle.destination_node_id = NodeId("n3")
    vehicle.battery = Mock()
    vehicle.battery.soc_kwh = 40.0
    vehicle.battery.capacity_kwh = 50.0
    vehicle.battery.soc_fraction = 0.8
    vehicle.constraints = Mock()
    vehicle.route = None
    
    # Mock graph
    graph = Mock()
    edge = Mock()
    edge.edge_id = EdgeId("e1")
    edge.source = NodeId("n1")
    edge.target = NodeId("n2")
    edge.length_m = 100.0
    edge.speed_limit_mps = 13.89
    edge.is_blocked = False
    edge.congestion_factor = 1.0
    edge.hazard_penalty_s = 0.0
    edge.emergency_penalty_s = 0.0
    edge.communication_penalty_s = 0.0
    edge.estimated_cost = 10.0
    graph.get_edge = Mock(return_value=edge)
    graph.get_outgoing_edges = Mock(return_value=[])
    
    # Mock route candidate source
    route_source = Mock()
    route_source.get_candidates = Mock(return_value=())
    
    observation = assembler.assemble(
        vehicle=vehicle,
        graph=graph,
        route_candidate_source=route_source,
        sim_time_s=10.0,
        active_events=(),
        inbox_messages=(),
    )
    
    assert observation.vehicle_id == VehicleId("v1")
    assert observation.sim_time_s == 10.0
    assert observation.battery.soc_kwh == 40.0
    assert observation.routing_candidates == ()
