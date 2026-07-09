"""EmergencyVehicleEvent — corridor priority request (no routing)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from e3hybrid.core.exceptions import EmergencyError
from e3hybrid.emergency.enums import EmergencyEventType
from e3hybrid.emergency.event import BaseEmergencyEvent
from e3hybrid.emergency.types import EventStatus
from e3hybrid.network.types import NodeId


@dataclass(frozen=True, slots=True)
class EmergencyVehicleEvent(BaseEmergencyEvent):
    """An emergency vehicle requires a priority corridor.

    Decision 4 (approved): This event ONLY publishes a corridor request.
    It does NOT perform routing, compute paths, or modify routing algorithms.
    Future routing algorithms react to this event through the Decision Engine.

    Network effect: ``emergency_penalty_s`` raised on ``affected_edge_ids``
    (the requested corridor region). Other vehicles are discouraged but not
    blocked. The emergency vehicle itself is unaffected by cost models.

    Extra attributes
    ----------------
    origin_node:
        Node from which the emergency vehicle departs.
    destination_node:
        Node the emergency vehicle must reach.
    vehicle_type:
        Descriptive label ("ambulance", "fire_truck", "police").
    emergency_penalty_s:
        Additive time penalty applied to corridor edges to discourage
        civilian traffic.  Must be positive.
    """

    origin_node: NodeId | None = None
    destination_node: NodeId | None = None
    vehicle_type: str = "ambulance"
    emergency_penalty_s: float = 120.0

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "event_type", EmergencyEventType.EMERGENCY_VEHICLE)
        if self.emergency_penalty_s <= 0:
            raise EmergencyError("emergency_penalty_s must be positive")
        # Both origin and destination required when routing is attempted later.
        # In Phase 5 they may be None (corridor not yet computed).

    def with_status(self, status: EventStatus) -> "EmergencyVehicleEvent":
        return EmergencyVehicleEvent(
            event_id=self.event_id,
            event_type=self.event_type,
            activation_time_s=self.activation_time_s,
            duration_s=self.duration_s,
            severity=self.severity,
            priority=self.priority,
            location=self.location,
            broadcast_radius_m=self.broadcast_radius_m,
            status=status,
            metadata=self.metadata,
            origin_node=self.origin_node,
            destination_node=self.destination_node,
            vehicle_type=self.vehicle_type,
            emergency_penalty_s=self.emergency_penalty_s,
        )

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base["origin_node"] = str(self.origin_node) if self.origin_node else None
        base["destination_node"] = (
            str(self.destination_node) if self.destination_node else None
        )
        base["vehicle_type"] = self.vehicle_type
        base["emergency_penalty_s"] = self.emergency_penalty_s
        return base
