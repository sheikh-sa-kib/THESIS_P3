"""Unit tests for the simulator-agnostic road-network core."""

from math import isinf

import pytest

from e3hybrid.core.exceptions import NetworkError
from e3hybrid.network.cost import DistanceCostProvider, TravelTimeCostProvider
from e3hybrid.network.edge import Edge, EdgeDynamicAttributes, MutableEdgeState
from e3hybrid.network.fixtures import create_synthetic_test_network
from e3hybrid.network.graph import CURRENT_SCHEMA_VERSION, DirectedGraph
from e3hybrid.network.node import Node
from e3hybrid.network.types import EdgeId, NodeId
from e3hybrid.network.validation import GraphValidationReport, GraphValidator


# ---------------------------------------------------------------------------
# Graph construction and structure
# ---------------------------------------------------------------------------


def test_directed_graph_stores_nodes_edges_and_neighbors() -> None:
    """The graph should preserve directed structure and neighbor queries."""

    graph = create_synthetic_test_network()

    assert graph.has_node(NodeId("A"))
    assert graph.has_edge(EdgeId("AB"))
    assert graph.neighbors(NodeId("A")) == (NodeId("B"), NodeId("C"))
    assert [edge.edge_id for edge in graph.outgoing_edges(NodeId("A"))] == [
        EdgeId("AB"),
        EdgeId("AC"),
    ]


def test_directed_graph_repr_includes_counts() -> None:
    """Graph repr should include node and edge counts."""

    graph = create_synthetic_test_network()
    r = repr(graph)
    assert "nodes=3" in r
    assert "edges=3" in r


def test_directed_graph_len_returns_node_count() -> None:
    """__len__ should return the number of nodes."""

    graph = create_synthetic_test_network()
    assert len(graph) == 3


def test_graph_rejects_duplicate_nodes_and_edges() -> None:
    """Duplicate graph entity identifiers should fail fast."""

    graph = DirectedGraph()
    graph.add_node(Node(NodeId("A")))
    with pytest.raises(NetworkError, match="duplicate node_id"):
        graph.add_node(Node(NodeId("A")))

    graph.add_node(Node(NodeId("B")))
    graph.add_edge(
        Edge(
            edge_id=EdgeId("AB"),
            source=NodeId("A"),
            target=NodeId("B"),
            length_m=1.0,
            speed_limit_mps=1.0,
        )
    )
    with pytest.raises(NetworkError, match="duplicate edge_id"):
        graph.add_edge(
            Edge(
                edge_id=EdgeId("AB"),
                source=NodeId("A"),
                target=NodeId("B"),
                length_m=1.0,
                speed_limit_mps=1.0,
            )
        )


def test_graph_rejects_edges_with_missing_target_node() -> None:
    """Edges should only connect nodes that already exist in the graph."""

    graph = DirectedGraph()
    graph.add_node(Node(NodeId("A")))

    with pytest.raises(NetworkError, match="target node"):
        graph.add_edge(
            Edge(
                edge_id=EdgeId("AB"),
                source=NodeId("A"),
                target=NodeId("B"),
                length_m=1.0,
                speed_limit_mps=1.0,
            )
        )


def test_graph_rejects_edges_with_missing_source_node() -> None:
    """Edges referencing an absent source node should be rejected."""

    graph = DirectedGraph()
    graph.add_node(Node(NodeId("B")))

    with pytest.raises(NetworkError, match="source node"):
        graph.add_edge(
            Edge(
                edge_id=EdgeId("AB"),
                source=NodeId("A"),
                target=NodeId("B"),
                length_m=1.0,
                speed_limit_mps=1.0,
            )
        )


# ---------------------------------------------------------------------------
# Mutable edge state
# ---------------------------------------------------------------------------


def test_mutable_edge_state_updates_costs() -> None:
    """Replacing edge state should change cost without changing topology."""

    graph = create_synthetic_test_network()
    provider = TravelTimeCostProvider()

    # AB: 100 m / 5 mps = 20 s base × congestion_factor 2.0 = 40 s
    graph.update_edge_state(
        EdgeId("AB"),
        MutableEdgeState(current_speed_mps=5.0, congestion_factor=2.0),
    )

    cost = provider.cost(graph.get_edge(EdgeId("AB")))

    assert cost.value == pytest.approx(40.0)
    assert not cost.is_blocked


def test_backward_compat_update_edge_dynamic_attributes() -> None:
    """The legacy update_edge_dynamic_attributes alias must still work."""

    graph = create_synthetic_test_network()
    graph.update_edge_dynamic_attributes(
        EdgeId("AB"),
        EdgeDynamicAttributes(current_speed_mps=5.0, congestion_factor=2.0),
    )
    cost = TravelTimeCostProvider().cost(graph.get_edge(EdgeId("AB")))
    assert cost.value == pytest.approx(40.0)


def test_edge_dynamic_property_alias_returns_state() -> None:
    """The backward-compatible .dynamic property should return edge state."""

    graph = create_synthetic_test_network()
    edge = graph.get_edge(EdgeId("AB"))
    assert edge.dynamic is edge.state


def test_blocked_edges_produce_infinite_travel_time_cost() -> None:
    """Blocked edges should be represented as inf by cost providers."""

    graph = create_synthetic_test_network()
    provider = TravelTimeCostProvider()

    graph.update_edge_state(
        EdgeId("AB"), MutableEdgeState(is_blocked=True)
    )
    cost = provider.cost(graph.get_edge(EdgeId("AB")))

    assert cost.is_blocked
    assert isinf(cost.value)


def test_blocked_edges_produce_infinite_distance_cost() -> None:
    """Blocked edges should be reported as blocked by DistanceCostProvider."""

    graph = create_synthetic_test_network()
    graph.update_edge_state(EdgeId("AB"), MutableEdgeState(is_blocked=True))
    cost = DistanceCostProvider().cost(graph.get_edge(EdgeId("AB")))
    assert cost.is_blocked
    assert isinf(cost.value)


def test_travel_time_cost_includes_all_penalty_components() -> None:
    """TravelTimeCostProvider should sum all mutable penalty fields."""

    graph = create_synthetic_test_network()
    graph.update_edge_state(
        EdgeId("AB"),
        MutableEdgeState(
            hazard_penalty_s=5.0,
            emergency_penalty_s=3.0,
            communication_penalty_s=2.0,
        ),
    )
    cost = TravelTimeCostProvider().cost(graph.get_edge(EdgeId("AB")))
    # base time = 100/10 = 10 s; plus 5+3+2 = 10 penalty => total 20
    assert cost.value == pytest.approx(20.0)
    assert "hazard_penalty_s" in cost.components
    assert "emergency_penalty_s" in cost.components
    assert "communication_penalty_s" in cost.components


def test_distance_cost_provider_ignores_speed_and_penalties() -> None:
    """DistanceCostProvider should return pure segment length."""

    graph = create_synthetic_test_network()
    cost = DistanceCostProvider().cost(graph.get_edge(EdgeId("AB")))
    assert cost.value == pytest.approx(100.0)
    assert not cost.is_blocked


# ---------------------------------------------------------------------------
# Edge model
# ---------------------------------------------------------------------------


def test_edge_model_rejects_non_positive_length() -> None:
    """Edge must reject zero and negative length_m values."""

    with pytest.raises(NetworkError, match="length_m"):
        Edge(
            edge_id=EdgeId("AB"),
            source=NodeId("A"),
            target=NodeId("B"),
            length_m=0.0,
            speed_limit_mps=1.0,
        )


def test_edge_model_rejects_non_positive_speed_limit() -> None:
    """Edge must reject zero and negative speed_limit_mps values."""

    with pytest.raises(NetworkError, match="speed_limit_mps"):
        Edge(
            edge_id=EdgeId("AB"),
            source=NodeId("A"),
            target=NodeId("B"),
            length_m=1.0,
            speed_limit_mps=0.0,
        )


def test_edge_model_rejects_non_positive_lane_count() -> None:
    """Edge must reject zero and negative lane_count values."""

    with pytest.raises(NetworkError, match="lane_count"):
        Edge(
            edge_id=EdgeId("AB"),
            source=NodeId("A"),
            target=NodeId("B"),
            length_m=1.0,
            speed_limit_mps=1.0,
            lane_count=0,
        )


def test_mutable_state_rejects_invalid_values() -> None:
    """MutableEdgeState should reject invalid numeric values."""

    with pytest.raises(NetworkError, match="current_speed_mps"):
        MutableEdgeState(current_speed_mps=0.0)
    with pytest.raises(NetworkError, match="travel_time_override_s"):
        MutableEdgeState(travel_time_override_s=0.0)
    with pytest.raises(NetworkError, match="congestion_factor"):
        MutableEdgeState(congestion_factor=0.0)
    with pytest.raises(NetworkError, match="hazard_penalty_s"):
        MutableEdgeState(hazard_penalty_s=-1.0)
    with pytest.raises(NetworkError, match="emergency_penalty_s"):
        MutableEdgeState(emergency_penalty_s=-1.0)
    with pytest.raises(NetworkError, match="communication_penalty_s"):
        MutableEdgeState(communication_penalty_s=-1.0)


def test_edge_dynamic_attributes_alias_accepts_congestion_factor() -> None:
    """EdgeDynamicAttributes alias must work as MutableEdgeState."""

    # The alias should be identical to MutableEdgeState.
    state = EdgeDynamicAttributes(congestion_factor=1.5)
    assert state.congestion_factor == 1.5


# ---------------------------------------------------------------------------
# Node model
# ---------------------------------------------------------------------------


def test_node_deserialization_rejects_missing_identifier() -> None:
    """Serialized nodes must include identifiers."""

    with pytest.raises(NetworkError, match="node_id"):
        Node.from_dict({})


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def test_edge_deserialization_rejects_missing_fields() -> None:
    """Serialized edges must include all required static fields."""

    with pytest.raises(NetworkError, match="missing field"):
        Edge.from_dict({"edge_id": "AB"})


def test_graph_deserialization_rejects_invalid_nodes_field() -> None:
    """Serialized graph nodes field must be iterable."""

    with pytest.raises(NetworkError, match="nodes"):
        DirectedGraph.from_dict({"nodes": "bad", "edges": []})


def test_graph_serialization_round_trip() -> None:
    """Serialized graph data should reconstruct the same internal structure."""

    graph = create_synthetic_test_network()
    restored = DirectedGraph.from_dict(graph.to_dict())

    assert [node.node_id for node in restored.nodes()] == [
        NodeId("A"),
        NodeId("B"),
        NodeId("C"),
    ]
    assert [edge.edge_id for edge in restored.edges()] == [
        EdgeId("AB"),
        EdgeId("BC"),
        EdgeId("AC"),
    ]


def test_serialized_graph_includes_schema_version_and_timestamp() -> None:
    """Serialized graph envelope must include versioning fields."""

    graph = create_synthetic_test_network()
    data = graph.to_dict()

    assert data["schema_version"] == CURRENT_SCHEMA_VERSION
    assert "created_at" in data
    assert "metadata" in data
    assert "validation_status" in data


def test_serialization_preserves_validation_status() -> None:
    """The caller-supplied validation_status should appear in the envelope."""

    graph = create_synthetic_test_network()
    assert graph.to_dict(validation_status="valid")["validation_status"] == "valid"
    assert graph.to_dict(validation_status="invalid")["validation_status"] == "invalid"
    assert graph.to_dict(validation_status="unvalidated")["validation_status"] == "unvalidated"


def test_serialization_rejects_unknown_validation_status() -> None:
    """to_dict should reject unrecognised validation_status values."""

    graph = create_synthetic_test_network()
    with pytest.raises(NetworkError, match="validation_status"):
        graph.to_dict(validation_status="maybe")


def test_deserialization_rejects_future_schema_version() -> None:
    """Graphs serialized with a future schema version must be rejected."""

    with pytest.raises(NetworkError, match="schema_version"):
        DirectedGraph.from_dict(
            {"schema_version": 9999, "nodes": [], "edges": []}
        )


def test_deserialization_accepts_legacy_graph_without_schema_version() -> None:
    """Legacy graphs without schema_version should be accepted as version 0."""

    graph = create_synthetic_test_network()
    raw = graph.to_dict()
    del raw["schema_version"]  # type: ignore[misc]
    restored = DirectedGraph.from_dict(raw)
    assert len(restored.nodes()) == 3


def test_graph_metadata_survives_serialization_round_trip() -> None:
    """Graph-level metadata should survive a serialization round-trip."""

    graph = create_synthetic_test_network()
    graph.set_metadata("source", "test_fixture")
    graph.set_metadata("city", "testville")

    restored = DirectedGraph.from_dict(graph.to_dict())

    assert restored.get_metadata("source") == "test_fixture"
    assert restored.get_metadata("city") == "testville"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_graph_validator_reports_empty_graph_error() -> None:
    """Graph validation should report invalid empty graphs."""

    report = GraphValidator().validate(DirectedGraph())

    assert not report.is_valid
    assert "at least one node" in report.errors[0]


def test_graph_validator_raise_mode_returns_report() -> None:
    """validate_or_raise should return the report on a valid graph."""

    graph = create_synthetic_test_network()
    report = GraphValidator().validate_or_raise(graph)
    assert isinstance(report, GraphValidationReport)
    assert report.is_valid


def test_graph_validator_raise_mode_raises_on_empty_graph() -> None:
    """Graph validation should raise NetworkError on hard errors."""

    with pytest.raises(NetworkError, match="at least one node"):
        GraphValidator().validate_or_raise(DirectedGraph())


def test_graph_validator_detects_self_loops_by_default() -> None:
    """Self-loops should be rejected by default."""

    graph = DirectedGraph()
    graph.add_node(Node(NodeId("A")))
    graph.add_edge(
        Edge(
            edge_id=EdgeId("AA"),
            source=NodeId("A"),
            target=NodeId("A"),
            length_m=1.0,
            speed_limit_mps=1.0,
        )
    )
    report = GraphValidator().validate(graph)
    assert not report.is_valid
    assert any("self-loop" in e for e in report.errors)


def test_graph_validator_allows_self_loops_when_permitted() -> None:
    """Self-loops should pass validation when allow_self_loops=True."""

    graph = DirectedGraph()
    graph.add_node(Node(NodeId("A")))
    graph.add_edge(
        Edge(
            edge_id=EdgeId("AA"),
            source=NodeId("A"),
            target=NodeId("A"),
            length_m=1.0,
            speed_limit_mps=1.0,
        )
    )
    report = GraphValidator(allow_self_loops=True).validate(graph)
    # No self-loop error — may still have an isolated-node warning.
    assert not any("self-loop" in e for e in report.errors)


def test_graph_validator_warns_about_isolated_nodes() -> None:
    """Isolated nodes should produce a warning, not a hard error."""

    graph = DirectedGraph()
    graph.add_node(Node(NodeId("A")))
    graph.add_node(Node(NodeId("B")))
    graph.add_node(Node(NodeId("C")))  # isolated
    graph.add_edge(
        Edge(
            edge_id=EdgeId("AB"),
            source=NodeId("A"),
            target=NodeId("B"),
            length_m=1.0,
            speed_limit_mps=1.0,
        )
    )
    report = GraphValidator().validate(graph)
    # Hard errors only come from self-loop on AB node edges; graph is valid here.
    assert report.is_valid
    assert any("isolated" in w for w in report.warnings)


def test_graph_validator_report_includes_counts() -> None:
    """Validation report must include node and edge counts."""

    graph = create_synthetic_test_network()
    report = GraphValidator().validate(graph)
    assert report.node_count == 3
    assert report.edge_count == 3
    assert report.is_valid


# ---------------------------------------------------------------------------
# Unknown lookups
# ---------------------------------------------------------------------------


def test_graph_unknown_node_lookup_raises_network_error() -> None:
    """Unknown node lookups should raise network errors."""

    graph = create_synthetic_test_network()
    with pytest.raises(NetworkError, match="unknown node_id"):
        graph.get_node(NodeId("missing"))


def test_graph_unknown_edge_lookup_raises_network_error() -> None:
    """Unknown edge lookups should raise network errors."""

    graph = create_synthetic_test_network()
    with pytest.raises(NetworkError, match="unknown edge_id"):
        graph.get_edge(EdgeId("missing"))
