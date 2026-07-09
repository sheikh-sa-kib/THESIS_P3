"""HazardZoneEvent — diffuse area hazard adding a time penalty."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from e3hybrid.core.exceptions import EmergencyError
from e3hybrid.emergency.enums import EmergencyEventType
from e3hybrid.emergency.event import BaseEmergencyEvent
from e3hybrid.emergency.types import EventStatus


@dataclass(frozen=True, slots=True)
class HazardZoneEvent(BaseEmergencyEvent):
    """A diffuse area hazard that discourages but does not block traversal.

    Network effect: ``hazard_penalty_s`` raised on affected edges (additive).

    Extra attributes
    ----------------
    hazard_type:
        Descriptive label (e.g., "ice_patch", "chemical_spill", "flood_water").
    hazard_penalty_s:
        Additive time penalty in seconds applied to each affected edge.
        Stacks additively with other active hazard events on the same edge.
    """

    hazard_type: str = "unspecified"
    hazard_penalty_s: float = 30.0

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "event_type", EmergencyEventType.HAZARD_ZONE)
        if self.hazard_penalty_s < 0:
            raise EmergencyError("hazard_penalty_s must be non-negative")

    def with_status(self, status: EventStatus) -> "HazardZoneEvent":
        return HazardZoneEvent(
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
            hazard_type=self.hazard_type,
            hazard_penalty_s=self.hazard_penalty_s,
        )

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base["hazard_type"] = self.hazard_type
        base["hazard_penalty_s"] = self.hazard_penalty_s
        return base
