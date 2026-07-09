"""Core types for the emergency framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, NewType

from e3hybrid.network.types import EdgeId, NodeId

EventId = NewType("EventId", str)


class EventStatus(StrEnum):
    """Lifecycle status of an emergency event.

    Transitions are forward-only:
    CREATED → SCHEDULED → ACTIVATED → BROADCAST → OBSERVED → HANDLED
                                                          ↘ RESOLVED
                                                          ↘ EXPIRED
    RESOLVED and EXPIRED are terminal states.
    """

    CREATED = "created"
    SCHEDULED = "scheduled"
    ACTIVATED = "activated"
    BROADCAST = "broadcast"
    OBSERVED = "observed"
    HANDLED = "handled"
    RESOLVED = "resolved"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class EventLocation:
    """Geographic location descriptor for an emergency event.

    At least one of ``edge_ids`` or ``center_node`` must be provided.

    Attributes
    ----------
    edge_ids:
        Directly affected road-segment edge IDs.  Used for events that
        apply to specific road segments (closures, blocks, accidents).
    center_node:
        Centre of a radius-based effect zone.  Used for area events
        (hazard zones, communication blackouts, emergency vehicle corridors).
    radius_m:
        Effect radius in metres from ``center_node``.  Only meaningful when
        ``center_node`` is set.
    metadata:
        Arbitrary annotations (altitude, zone name, …).
    """

    edge_ids: frozenset[EdgeId] = field(default_factory=frozenset)
    center_node: NodeId | None = None
    radius_m: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        from e3hybrid.core.exceptions import EmergencyError

        if not self.edge_ids and self.center_node is None:
            raise EmergencyError(
                "EventLocation must specify at least edge_ids or center_node"
            )
        if self.radius_m is not None and self.radius_m <= 0:
            raise EmergencyError("EventLocation.radius_m must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_ids": [str(e) for e in sorted(self.edge_ids)],
            "center_node": str(self.center_node) if self.center_node else None,
            "radius_m": self.radius_m,
            "metadata": dict(self.metadata),
        }
