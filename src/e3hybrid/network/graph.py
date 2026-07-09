"""Directed graph representation for the internal road network.

Storage model
-------------
The graph uses four parallel dictionaries:

  _nodes     : NodeId  → Node          – all nodes, insertion-ordered
  _edges     : EdgeId  → Edge          – all edges, insertion-ordered
  _outgoing  : NodeId  → list[EdgeId]  – adjacency list (source → edges)
  _incoming  : NodeId  → list[EdgeId]  – reverse adjacency (target → edges)

Insertion order is preserved in all four structures so that graph traversal
is deterministic across Python runs (CPython 3.7+ dict guarantee).

Complexity summary (V = nodes, E = edges)
-----------------------------------------
add_node          O(1)  amortised dict insert
add_edge          O(1)  amortised dict insert + 2× list append
has_node          O(1)  dict lookup
has_edge          O(1)  dict lookup
get_node          O(1)  dict lookup
get_edge          O(1)  dict lookup
nodes()           O(V)  tuple construction
edges()           O(E)  tuple construction
outgoing_edges    O(deg(v))  tuple construction over adjacency list
incoming_edges    O(deg(v))  tuple construction over reverse adjacency list
neighbors         O(deg(v))  derives from outgoing_edges
update_state      O(1)  dict assign after get_edge

Serialization
-------------
``to_dict()`` returns a versioned envelope:

  {
    "schema_version": 1,
    "created_at": "<ISO-8601 UTC>",
    "metadata": { ... },
    "validation_status": "unvalidated" | "valid" | "invalid",
    "nodes": [ ... ],
    "edges": [ ... ],
  }

``from_dict()`` accepts any schema_version ≤ CURRENT_SCHEMA_VERSION and raises
``NetworkError`` for future versions it cannot interpret.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from e3hybrid.core.exceptions import NetworkError
from e3hybrid.network.edge import Edge, MutableEdgeState
from e3hybrid.network.node import Node
from e3hybrid.network.types import EdgeId, NodeId

CURRENT_SCHEMA_VERSION: int = 1


@dataclass(slots=True)
class DirectedGraph:
    """Mutable directed graph of nodes and road-segment edges.

    Construction
    ------------
    Always use ``add_node`` before ``add_edge``.  Edges are validated against
    existing nodes at insertion time; an edge referencing an unknown node raises
    ``NetworkError`` immediately.

    Mutation
    --------
    Only simulation-time edge state (``MutableEdgeState``) can be updated after
    construction via ``update_edge_state``.  Node and edge structural attributes
    are immutable; replace the whole edge if a structural change is needed.
    """

    _nodes: dict[NodeId, Node] = field(default_factory=dict)
    _edges: dict[EdgeId, Edge] = field(default_factory=dict)
    _outgoing: dict[NodeId, list[EdgeId]] = field(
        default_factory=lambda: defaultdict(list)
    )
    _incoming: dict[NodeId, list[EdgeId]] = field(
        default_factory=lambda: defaultdict(list)
    )
    _graph_metadata: dict[str, object] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_node(self, node: Node) -> None:
        """Add a node.  Raises ``NetworkError`` on duplicate ``node_id``."""

        if node.node_id in self._nodes:
            raise NetworkError(f"duplicate node_id: '{node.node_id}'")
        self._nodes[node.node_id] = node
        self._outgoing.setdefault(node.node_id, [])
        self._incoming.setdefault(node.node_id, [])

    def add_edge(self, edge: Edge) -> None:
        """Add a directed edge.

        Raises ``NetworkError`` on:
        - duplicate edge_id
        - source node not present
        - target node not present
        """

        if edge.edge_id in self._edges:
            raise NetworkError(f"duplicate edge_id: '{edge.edge_id}'")
        if edge.source not in self._nodes:
            raise NetworkError(
                f"edge '{edge.edge_id}': source node '{edge.source}' does not exist"
            )
        if edge.target not in self._nodes:
            raise NetworkError(
                f"edge '{edge.edge_id}': target node '{edge.target}' does not exist"
            )
        self._edges[edge.edge_id] = edge
        self._outgoing[edge.source].append(edge.edge_id)
        self._incoming[edge.target].append(edge.edge_id)

    def update_edge_state(
        self, edge_id: EdgeId, state: MutableEdgeState
    ) -> None:
        """Replace the mutable state of an existing edge.

        The immutable structural fields of the edge are never touched.
        Raises ``NetworkError`` if ``edge_id`` does not exist.
        """

        edge = self.get_edge(edge_id)
        self._edges[edge_id] = edge.with_state(state)

    # Backward-compatible alias used by existing tests and callers.
    def update_edge_dynamic_attributes(
        self, edge_id: EdgeId, dynamic: MutableEdgeState
    ) -> None:
        """Backward-compatible alias for ``update_edge_state``."""

        self.update_edge_state(edge_id, dynamic)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def has_node(self, node_id: NodeId) -> bool:
        """Return True if a node with ``node_id`` exists."""

        return node_id in self._nodes

    def has_edge(self, edge_id: EdgeId) -> bool:
        """Return True if an edge with ``edge_id`` exists."""

        return edge_id in self._edges

    def get_node(self, node_id: NodeId) -> Node:
        """Return the node for ``node_id``.  Raises ``NetworkError`` if absent."""

        try:
            return self._nodes[node_id]
        except KeyError as error:
            raise NetworkError(f"unknown node_id: '{node_id}'") from error

    def get_edge(self, edge_id: EdgeId) -> Edge:
        """Return the edge for ``edge_id``.  Raises ``NetworkError`` if absent."""

        try:
            return self._edges[edge_id]
        except KeyError as error:
            raise NetworkError(f"unknown edge_id: '{edge_id}'") from error

    def nodes(self) -> tuple[Node, ...]:
        """Return all nodes in deterministic insertion order."""

        return tuple(self._nodes.values())

    def edges(self) -> tuple[Edge, ...]:
        """Return all edges in deterministic insertion order."""

        return tuple(self._edges.values())

    def outgoing_edges(self, node_id: NodeId) -> tuple[Edge, ...]:
        """Return directed edges leaving ``node_id``.

        Raises ``NetworkError`` if ``node_id`` does not exist.
        """

        self.get_node(node_id)
        return tuple(self._edges[eid] for eid in self._outgoing[node_id])

    def incoming_edges(self, node_id: NodeId) -> tuple[Edge, ...]:
        """Return directed edges entering ``node_id``.

        Raises ``NetworkError`` if ``node_id`` does not exist.
        """

        self.get_node(node_id)
        return tuple(self._edges[eid] for eid in self._incoming[node_id])

    def neighbors(self, node_id: NodeId) -> tuple[NodeId, ...]:
        """Return target node IDs reachable via outgoing edges from ``node_id``."""

        return tuple(edge.target for edge in self.outgoing_edges(node_id))

    # ------------------------------------------------------------------
    # Graph-level metadata
    # ------------------------------------------------------------------

    def set_metadata(self, key: str, value: object) -> None:
        """Attach an arbitrary metadata entry to the graph envelope."""

        self._graph_metadata[key] = value

    def get_metadata(self, key: str) -> object | None:
        """Return a graph metadata value, or ``None`` if not set."""

        return self._graph_metadata.get(key)

    # ------------------------------------------------------------------
    # Versioned serialization
    # ------------------------------------------------------------------

    def to_dict(
        self,
        *,
        validation_status: str = "unvalidated",
    ) -> dict[str, object]:
        """Serialize the graph to a versioned, JSON-compatible dictionary.

        Parameters
        ----------
        validation_status:
            One of ``"unvalidated"``, ``"valid"``, or ``"invalid"``.
            Callers that run ``GraphValidator`` before serializing should pass
            the appropriate status so the envelope records it.
        """

        allowed_statuses = {"unvalidated", "valid", "invalid"}
        if validation_status not in allowed_statuses:
            raise NetworkError(
                f"validation_status must be one of: "
                f"{', '.join(sorted(allowed_statuses))}"
            )

        return {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "created_at": datetime.now(UTC).isoformat(),
            "metadata": dict(self._graph_metadata),
            "validation_status": validation_status,
            "nodes": [node.to_dict() for node in self.nodes()],
            "edges": [edge.to_dict() for edge in self.edges()],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "DirectedGraph":
        """Deserialize a graph from a versioned dictionary.

        Raises ``NetworkError`` if:
        - ``schema_version`` is missing or exceeds ``CURRENT_SCHEMA_VERSION``.
        - ``nodes`` or ``edges`` fields are absent or not iterable.
        - Any node or edge record fails its own deserialization.
        """

        schema_version = data.get("schema_version")
        if schema_version is None:
            # Accept legacy graphs that predate versioning (schema_version 0).
            schema_version = 0
        if not isinstance(schema_version, int) or schema_version < 0:
            raise NetworkError(
                f"schema_version must be a non-negative integer,"
                f" got: {schema_version!r}"
            )
        if schema_version > CURRENT_SCHEMA_VERSION:
            raise NetworkError(
                f"Cannot deserialize graph with schema_version {schema_version};"
                f" this build supports up to version {CURRENT_SCHEMA_VERSION}."
            )

        nodes_data = _required_iterable(data, "nodes")
        edges_data = _required_iterable(data, "edges")

        graph = cls()

        # Restore graph-level metadata when present.
        raw_meta = data.get("metadata")
        if isinstance(raw_meta, dict):
            for key, value in raw_meta.items():
                graph.set_metadata(key, value)

        for node_data in nodes_data:
            if not isinstance(node_data, dict):
                raise NetworkError("serialized nodes must be dictionaries")
            graph.add_node(Node.from_dict(node_data))

        for edge_data in edges_data:
            if not isinstance(edge_data, dict):
                raise NetworkError("serialized edges must be dictionaries")
            graph.add_edge(Edge.from_dict(edge_data))

        return graph

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Return the number of nodes in the graph."""

        return len(self._nodes)

    def __repr__(self) -> str:
        return (
            f"DirectedGraph("
            f"nodes={len(self._nodes)}, "
            f"edges={len(self._edges)})"
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _required_iterable(data: dict[str, object], field_name: str) -> Iterable[object]:
    """Return a required iterable field or raise ``NetworkError``."""

    try:
        value = data[field_name]
    except KeyError as error:
        raise NetworkError(
            f"serialized graph is missing required field '{field_name}'"
        ) from error
    if isinstance(value, str) or not isinstance(value, Iterable):
        raise NetworkError(
            f"serialized graph field '{field_name}' must be iterable"
        )
    return value
