"""Simulator-agnostic road-network graph model.

The internal graph representation is the source of truth for the simulator.
External systems such as SUMO may later import from or export to this graph, but
the graph itself has no dependency on SUMO, TraCI, routing, vehicles, or
emergency modules.
"""

from e3hybrid.network.cost import (
    CostProvider,
    DistanceCostProvider,
    EdgeCost,
    TravelTimeCostProvider,
)
from e3hybrid.network.edge import Edge, EdgeDynamicAttributes, MutableEdgeState
from e3hybrid.network.graph import CURRENT_SCHEMA_VERSION, DirectedGraph
from e3hybrid.network.node import Node
from e3hybrid.network.validation import GraphValidationReport, GraphValidator

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "CostProvider",
    "DirectedGraph",
    "DistanceCostProvider",
    "Edge",
    "EdgeCost",
    # EdgeDynamicAttributes is the backward-compatible alias for MutableEdgeState
    "EdgeDynamicAttributes",
    "GraphValidationReport",
    "GraphValidator",
    "MutableEdgeState",
    "Node",
    "TravelTimeCostProvider",
]
