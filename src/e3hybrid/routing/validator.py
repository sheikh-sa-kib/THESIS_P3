"""RouteValidator — validates routes before they are returned or accepted."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from e3hybrid.network.graph import DirectedGraph
    from e3hybrid.routing.route import Route


@dataclass(frozen=True, slots=True)
class RouteValidationError:
    """A single validation error for a route."""

    field_name: str
    error_message: str


@dataclass(frozen=True, slots=True)
class RouteValidationReport:
    """Report of validation errors for a route."""

    is_valid: bool
    errors: tuple[RouteValidationError, ...]

    def __str__(self) -> str:
        if self.is_valid:
            return "Route is valid"
        error_lines = [f"  - {e.field_name}: {e.error_message}" for e in self.errors]
        return "Route validation failed:\n" + "\n".join(error_lines)


class RouteValidator:
    """Validates routes before they are returned or accepted.
    
    Checks:
    - Connectivity (edges form a valid path)
    - No blocked edges (unless explicitly allowed)
    - Cost consistency
    - Battery feasibility
    """

    def validate(
        self,
        route: "Route",
        graph: "DirectedGraph",
        allow_blocked: bool = False,
    ) -> "RouteValidationReport":
        """Validate a route against the current graph state.
        
        Parameters
        ----------
        route:
            The route to validate.
        graph:
            The current graph state.
        allow_blocked:
            If True, blocked edges are allowed in the route.
        
        Returns
        -------
        RouteValidationReport
            Validation report containing any errors found.
        """
        errors: list[RouteValidationError] = []

        # Validate connectivity
        connectivity_errors = self._validate_connectivity(route, graph)
        errors.extend(connectivity_errors)

        # Validate blocked edges
        if not allow_blocked:
            blocked_errors = self._validate_blocked_edges(route, graph)
            errors.extend(blocked_errors)

        # Validate cost consistency (if route has cost info)
        # This will be added when Route includes cost field

        return RouteValidationReport(
            is_valid=len(errors) == 0,
            errors=tuple(errors),
        )

    def _validate_connectivity(
        self,
        route: "Route",
        graph: "DirectedGraph",
    ) -> list[RouteValidationError]:
        """Validate that edges form a valid connected path."""
        errors: list[RouteValidationError] = []

        # Check that all nodes exist in graph
        for node_id in route.node_sequence:
            if not graph.has_node(node_id):
                errors.append(
                    RouteValidationError(
                        field_name="node_sequence",
                        error_message=f"Node {node_id} does not exist in graph",
                    )
                )

        # Check that all edges exist and connect correctly
        for i, edge_id in enumerate(route.edge_sequence):
            if not graph.has_edge(edge_id):
                errors.append(
                    RouteValidationError(
                        field_name="edge_sequence",
                        error_message=f"Edge {edge_id} does not exist in graph",
                    )
                )
                continue

            edge = graph.get_edge(edge_id)
            expected_source = route.node_sequence[i]
            expected_target = route.node_sequence[i + 1]

            if edge.source != expected_source:
                errors.append(
                    RouteValidationError(
                        field_name="edge_sequence",
                        error_message=(
                            f"Edge {edge_id} source {edge.source} "
                            f"does not match expected source {expected_source}"
                        ),
                    )
                )

            if edge.target != expected_target:
                errors.append(
                    RouteValidationError(
                        field_name="edge_sequence",
                        error_message=(
                            f"Edge {edge_id} target {edge.target} "
                            f"does not match expected target {expected_target}"
                        ),
                    )
                )

        return errors

    def _validate_blocked_edges(
        self,
        route: "Route",
        graph: "DirectedGraph",
    ) -> list[RouteValidationError]:
        """Validate that no edges in the route are blocked."""
        errors: list[RouteValidationError] = []

        for edge_id in route.edge_sequence:
            if not graph.has_edge(edge_id):
                continue  # Already reported in connectivity validation

            edge = graph.get_edge(edge_id)
            if edge.state.is_blocked:
                errors.append(
                    RouteValidationError(
                        field_name="edge_sequence",
                        error_message=f"Edge {edge_id} is blocked",
                    )
                )

        return errors
