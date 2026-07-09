"""Node model for the internal road-network graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from e3hybrid.core.exceptions import NetworkError
from e3hybrid.network.types import NodeId


@dataclass(frozen=True, slots=True)
class Node:
    """A directed-graph node representing a road-network junction or point."""

    node_id: NodeId
    x: float | None = None
    y: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate node identity and freeze metadata."""

        if not str(self.node_id).strip():
            raise NetworkError("node_id must be non-empty")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        """Serialize the node to a JSON-compatible dictionary."""

        return {
            "node_id": str(self.node_id),
            "x": self.x,
            "y": self.y,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Node":
        """Create a node from a serialized dictionary."""

        try:
            node_id = data["node_id"]
        except KeyError as error:
            raise NetworkError("serialized node is missing node_id") from error
        return cls(
            node_id=NodeId(str(node_id)),
            x=_optional_float(data.get("x"), "node.x"),
            y=_optional_float(data.get("y"), "node.y"),
            metadata=_metadata_mapping(data.get("metadata")),
        )


def _optional_float(value: Any, field_name: str) -> float | None:
    """Return an optional numeric value as a float."""

    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise NetworkError(f"{field_name} must be numeric when provided")
    return float(value)


def _metadata_mapping(value: Any) -> Mapping[str, Any]:
    """Return metadata as a mapping or raise a network error."""

    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise NetworkError("metadata must be a mapping")
    return value
