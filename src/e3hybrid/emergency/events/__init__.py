"""Concrete emergency event implementations."""

from e3hybrid.emergency.events.accident import TrafficAccidentEvent
from e3hybrid.emergency.events.emergency_vehicle import EmergencyVehicleEvent
from e3hybrid.emergency.events.hazard import HazardZoneEvent
from e3hybrid.emergency.events.infrastructure import (
    CommunicationBlackoutEvent,
    InfrastructureFailureEvent,
)
from e3hybrid.emergency.events.road_block import RoadBlockEvent
from e3hybrid.emergency.events.road_closure import RoadClosureEvent

__all__ = [
    "CommunicationBlackoutEvent",
    "EmergencyVehicleEvent",
    "HazardZoneEvent",
    "InfrastructureFailureEvent",
    "RoadBlockEvent",
    "RoadClosureEvent",
    "TrafficAccidentEvent",
]
