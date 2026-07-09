"""TrafficAccidentEvent — combined closure/block; may spawn EmergencyVehicle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from e3hybrid.core.exceptions import EmergencyError
from e3hybrid.emergency.enums import EmergencyEventType
from e3hybrid.emergency.event import BaseEmergencyEvent
from e3hybrid.emergency.types import EventStatus


@dataclass(frozen=True, slots=True)
class TrafficAccidentEvent(BaseEmergencyEvent):
    """A traffic accident combining road closure and congestion effects.

    Network effects:
    - ``is_blocked = True`` on directly affected edges (primary lanes).
    - ``congestion_factor`` raised on adjacent edges (secondary congestion).
    - May trigger an ``EmergencyVehicleEvent`` automatically (scheduler logic).

    Extra attributes
    ----------------
    vehicle_count:
        Estimated number of vehicles involved.  Informs severity heuristics.
    blocks_all_lanes:
        If True, the accident closes the edge entirely (is_blocked).
        If False, it reduces capacity (congestion_factor only).
    spawns_emergency_vehicle:
        When True, the ``EventScheduler`` should automatically enqueue an
        ``EmergencyVehicleEvent`` shortly after activation.  The scheduler
        reads this flag; the event itself does not create child events.
    secondary_congestion_delta:
        Congestion factor added to adjacent edges not directly blocked.
    """

    vehicle_count: int = 1
    blocks_all_lanes: bool = True
    spawns_emergency_vehicle: bool = True
    secondary_congestion_delta: float = 0.5

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "event_type", EmergencyEventType.TRAFFIC_ACCIDENT)
        if self.vehicle_count < 1:
            raise EmergencyError("vehicle_count must be at least 1")
        if self.secondary_congestion_delta < 0:
            raise EmergencyError("secondary_congestion_delta must be non-negative")

    def with_status(self, status: EventStatus) -> "TrafficAccidentEvent":
        return TrafficAccidentEvent(
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
            vehicle_count=self.vehicle_count,
            blocks_all_lanes=self.blocks_all_lanes,
            spawns_emergency_vehicle=self.spawns_emergency_vehicle,
            secondary_congestion_delta=self.secondary_congestion_delta,
        )

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base["vehicle_count"] = self.vehicle_count
        base["blocks_all_lanes"] = self.blocks_all_lanes
        base["spawns_emergency_vehicle"] = self.spawns_emergency_vehicle
        base["secondary_congestion_delta"] = self.secondary_congestion_delta
        return base
