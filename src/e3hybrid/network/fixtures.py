"""Internal synthetic network fixtures for unit tests only."""

from __future__ import annotations

from e3hybrid.network.edge import Edge
from e3hybrid.network.graph import DirectedGraph
from e3hybrid.network.node import Node
from e3hybrid.network.types import EdgeId, NodeId


def create_synthetic_test_network() -> DirectedGraph:
    """Create a small deterministic graph for unit tests.

    This fixture is not research data and must not be used to report thesis
    metrics. It exists only to verify graph behavior.
    """

    graph = DirectedGraph()
    graph.add_node(Node(NodeId("A"), x=0.0, y=0.0))
    graph.add_node(Node(NodeId("B"), x=1.0, y=0.0))
    graph.add_node(Node(NodeId("C"), x=2.0, y=0.0))
    graph.add_edge(
        Edge(
            edge_id=EdgeId("AB"),
            source=NodeId("A"),
            target=NodeId("B"),
            length_m=100.0,
            speed_limit_mps=10.0,
        )
    )
    graph.add_edge(
        Edge(
            edge_id=EdgeId("BC"),
            source=NodeId("B"),
            target=NodeId("C"),
            length_m=150.0,
            speed_limit_mps=15.0,
        )
    )
    graph.add_edge(
        Edge(
            edge_id=EdgeId("AC"),
            source=NodeId("A"),
            target=NodeId("C"),
            length_m=300.0,
            speed_limit_mps=20.0,
        )
    )
    return graph
