"""SumoNetworkImporter — converts a SUMO network into an E3-Hybrid DirectedGraph."""

from __future__ import annotations

from e3hybrid.network.edge import Edge, MutableEdgeState
from e3hybrid.network.graph import DirectedGraph
from e3hybrid.network.node import Node
from e3hybrid.network.types import EdgeId, NodeId
from e3hybrid.sumo.connection import SumoTraciConnection


class SumoNetworkImporter:
    """Converts a SUMO network into an E3-Hybrid DirectedGraph.

    Called once at startup. Produces a static graph (nodes + edges without
    dynamic state). Dynamic state is updated per timestep by SumoSimulation.

    Usage::

        connection = SumoTraciConnection(config)
        connection.start()
        importer = SumoNetworkImporter(connection)
        graph = importer.import_graph()
    """

    def __init__(self, connection: SumoTraciConnection) -> None:
        self._connection = connection

    def import_graph(
        self,
        graph_metadata: dict[str, object] | None = None,
    ) -> DirectedGraph:
        """Build a complete DirectedGraph from the SUMO network.

        Iterates all junctions → Node objects.
        Iterates all edges → Edge objects (static attributes only).

        Edge state is initialized with defaults. Dynamic state is updated
        by the calling simulation loop.

        Parameters
        ----------
        graph_metadata:
            Optional metadata to attach to the graph.

        Returns
        -------
        DirectedGraph
            A fully populated graph matching the SUMO network topology.
        """
        conn = self._connection
        graph = DirectedGraph()

        if graph_metadata:
            for key, value in graph_metadata.items():
                graph.set_metadata(key, value)

        # 1. Import junctions as nodes (skip internal junctions starting with ':')
        junction_ids = conn.get_junction_ids()
        id_to_node: dict[str, Node] = {}

        for jid in junction_ids:
            if jid.startswith(":"):
                continue
            x, y = conn.get_junction_position(jid)
            nid = NodeId(jid)
            node = Node(node_id=nid, x=x, y=y)
            graph.add_node(node)
            id_to_node[jid] = node

        # 2. Import edges
        edge_ids = conn.get_edge_ids()

        for eid_str in edge_ids:
            # Skip internal edges (TraCI marks them with a leading colon)
            if eid_str.startswith(":"):
                continue

            try:
                length = conn.get_edge_length(eid_str)
                speed_limit = conn.get_edge_speed_limit(eid_str)
                from_junction = conn.get_edge_from_junction(eid_str)
                to_junction = conn.get_edge_to_junction(eid_str)
                lane_count = conn.get_edge_lane_count(eid_str)
            except Exception:
                continue

            if from_junction not in id_to_node or to_junction not in id_to_node:
                continue

            source_nid = NodeId(from_junction)
            target_nid = NodeId(to_junction)
            eid = EdgeId(eid_str)
            state = MutableEdgeState()
            edge = Edge(
                edge_id=eid,
                source=source_nid,
                target=target_nid,
                length_m=length,
                speed_limit_mps=speed_limit,
                lane_count=lane_count,
                state=state,
            )
            graph.add_edge(edge)

        return graph