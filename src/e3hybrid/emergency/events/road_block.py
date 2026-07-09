"""RoadBlockEvent — partial obstruction reducing speed/capacity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from e3hybrid.core.exceptions import EmergencyError
from e3hybrid.emergency.enums import EmergencyEventType
from e3hybrid.emergency.event import BaseEmergencyEvent
from e3hybrid.emergency.types import EventId, EventLocation, EventStatus


@dataclass(frozen=True, slots=True)
class RoadBlockEvent(BaseEmergencyEvent):
    """A partial obstruction that raises congestion without full closure.

    Network effect: ``congestion_factor`` raised on affected edges.
    Edge remains traversable but travel time increases.

    Extra attributes
    ----------------
    speed_reduction_factor:
        Multiplier applied to effective speed (0 < f <= 1.0).
        0.5 means half the normal speed.
    congestion_factor_delta:
        Amount added to the edge's existing ``congestion_factor``.
        Additive with other active block events on the same edge.
    """

    speed_reduction_factor: float = 0.5
    congestion_factor_delta: float = 1.0

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "event_type", EmergencyEventType.ROAD_BLOCK)
        if not (0.0 < self.speed_reduction_factor <= 1.0):
            raise EmergencyError("speed_reduction_factor must be in (0, 1]")
        if self.congestion_factor_delta <= 0:
            raise EmergencyError("congestion_factor_delta must be positive")

    def with_status(self, status: EventStatus) -> "RoadBlockEvent":
        return RoadBlockEvent(
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
            speed_reduction_factor=self.speed_reduction_factor,
            congestion_factor_delta=self.congestion_factor_delta,
        )

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base["speed_reduction_factor"] = self.speed_reduction_factor
        base["congestion_factor_delta"] = self.congestion_factor_delta
        return base
