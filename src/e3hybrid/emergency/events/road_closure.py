"""RoadClosureEvent — edge fully blocked."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from e3hybrid.communication.enums import Priority
from e3hybrid.emergency.enums import EmergencyEventType
from e3hybrid.emergency.event import BaseEmergencyEvent
from e3hybrid.emergency.types import EventId, EventLocation, EventStatus


@dataclass(frozen=True, slots=True)
class RoadClosureEvent(BaseEmergencyEvent):
    """A road segment is physically impassable.

    Network effect: ``is_blocked = True`` on all ``affected_edge_ids``.
    Blocked edges always take precedence over all other penalties.
    A blocked edge returns ``inf`` cost regardless of any additive penalties.

    Extra attributes
    ----------------
    blocking_cause:
        Human-readable cause description (e.g., "flooding", "police cordon").
    """

    blocking_cause: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        # event_type is fixed — override the base default
        object.__setattr__(self, "event_type", EmergencyEventType.ROAD_CLOSURE)

    def with_status(self, status: EventStatus) -> "RoadClosureEvent":
        return RoadClosureEvent(
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
            blocking_cause=self.blocking_cause,
        )

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base["blocking_cause"] = self.blocking_cause
        return base
