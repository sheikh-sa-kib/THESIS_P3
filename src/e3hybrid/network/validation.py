"""Validation utilities for internal road-network graphs.

Validation is a read-only pass over a ``DirectedGraph``.  It never mutates the
graph; it only produces a ``GraphValidationReport`` describing what it found.

Hard errors (``GraphValidationReport.errors``)
----------------------------------------------
The following conditions are always rejected:

- Empty graph (no nodes).
- Duplicate node IDs detected by ``add_node`` (enforced at insertion time).
- Duplicate edge IDs detected by ``add_edge`` (enforced at insertion time).
- Self-loops — edges whose source equals their target, unless
  ``allow_self_loops=True`` is passed to ``GraphValidator``.
- Disconnected edges — edges referencing node IDs that do not exist.
- Negative or zero edge lengths.
- Negative or zero speed limits.
- Duplicate entries in adjacency lists (same edge ID appearing more than once
  in the outgoing list of a node).

Soft warnings (``GraphValidationReport.warnings``)
---------------------------------------------------
- Isolated nodes — nodes with no incoming and no outgoing edges.  This is
  valid in some scenarios (disconnected waypoints) but is usually a data
  error, so it is reported as a warning for human review.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from e3hybrid.core.exceptions import NetworkError
from e3hybrid.network.graph import DirectedGraph
from e3hybrid.network.types import NodeId

_logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GraphValidationReport:
    """Result of validating a directed road-network graph."""

    node_count: int
    edge_count: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        """Return True when the graph has no hard validation errors."""

        return not self.errors

    def log_warnings(self) -> None:
        """Emit any warnings to the framework logger."""

        for warning in self.warnings:
            _logger.warning("GraphValidation: %s", warning)


class GraphValidator:
    """Validate structural consistency of an internal road-network graph.

    Parameters
    ----------
    allow_self_loops:
        When ``False`` (default), edges whose source equals their target are
        reported as hard errors.  Set to ``True`` only for special graph types
        (e.g., roundabout pseudo-loops) that are verified by the caller.
    """

    def __init__(self, *, allow_self_loops: bool = False) -> None:
        self._allow_self_loops = allow_self_loops

    def validate(self, graph: DirectedGraph) -> GraphValidationReport:
        """Return a validation report for the graph without raising."""

        errors: list[str] = []
        warnings: list[str] = []

        nodes = graph.nodes()
        edges = graph.edges()

        # --- Must have at least one node --------------------------------
        if not nodes:
            errors.append("graph must contain at least one node")

        # --- Per-edge checks --------------------------------------------
        for edge in edges:
            # Disconnected edge — source or target missing.
            if not graph.has_node(edge.source):
                errors.append(
                    f"edge '{edge.edge_id}' references missing source node"
                    f" '{edge.source}'"
                )
            if not graph.has_node(edge.target):
                errors.append(
                    f"edge '{edge.edge_id}' references missing target node"
                    f" '{edge.target}'"
                )

            # Self-loop check.
            if edge.source == edge.target and not self._allow_self_loops:
                errors.append(
                    f"edge '{edge.edge_id}' is a self-loop"
                    f" (source == target == '{edge.source}')"
                )

            # Negative / zero length.
            if edge.length_m <= 0:
                errors.append(
                    f"edge '{edge.edge_id}' has non-positive length_m"
                    f" ({edge.length_m})"
                )

            # Negative / zero speed limit.
            if edge.speed_limit_mps <= 0:
                errors.append(
                    f"edge '{edge.edge_id}' has non-positive speed_limit_mps"
                    f" ({edge.speed_limit_mps})"
                )

            # Lane count already enforced by Edge.__post_init__, but
            # double-check here for graphs that bypass the constructor.
            if edge.lane_count <= 0:
                errors.append(
                    f"edge '{edge.edge_id}' has non-positive lane_count"
                    f" ({edge.lane_count})"
                )

        # --- Duplicate adjacency entries --------------------------------
        for node in nodes:
            outgoing = graph.outgoing_edges(node.node_id)
            seen_edge_ids = set()
            for edge in outgoing:
                if edge.edge_id in seen_edge_ids:
                    errors.append(
                        f"node '{node.node_id}' adjacency list contains"
                        f" duplicate entry for edge '{edge.edge_id}'"
                    )
                seen_edge_ids.add(edge.edge_id)

        # --- Isolated nodes (warning only) ------------------------------
        if nodes:
            for node in nodes:
                has_outgoing = bool(graph.outgoing_edges(node.node_id))
                has_incoming = bool(graph.incoming_edges(node.node_id))
                if not has_outgoing and not has_incoming:
                    warnings.append(
                        f"node '{node.node_id}' is isolated"
                        " (no incoming or outgoing edges)"
                    )

        return GraphValidationReport(
            node_count=len(nodes),
            edge_count=len(edges),
            errors=tuple(errors),
            warnings=tuple(warnings),
        )

    def validate_or_raise(self, graph: DirectedGraph) -> GraphValidationReport:
        """Validate and raise ``NetworkError`` if any hard errors are found.

        Returns the report (including any warnings) when the graph is valid.
        Warnings are emitted to the logger but do not raise.
        """

        report = self.validate(graph)
        report.log_warnings()
        if not report.is_valid:
            raise NetworkError(
                f"Graph validation failed with {len(report.errors)} error(s): "
                + "; ".join(report.errors)
            )
        return report
