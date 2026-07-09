"""Emergency event type enumeration."""

from __future__ import annotations

from enum import StrEnum


class EmergencyEventType(StrEnum):
    """All supported emergency event categories.

    New types are added here and implemented as a new frozen dataclass
    satisfying the ``EmergencyEvent`` Protocol.  No existing code changes
    are required.

    Phase 5 types
    -------------
    ROAD_CLOSURE           – edge fully blocked; is_blocked = True
    ROAD_BLOCK             – partial obstruction; congestion_factor raised
    TRAFFIC_ACCIDENT       – combined closure + congestion; may spawn EV event
    EMERGENCY_VEHICLE      – priority corridor request; emergency_penalty_s raised
    INFRASTRUCTURE_FAILURE – sensor/signal failure; static speed fallback
    COMMUNICATION_BLACKOUT – V2V disruption zone; communication_penalty_s raised
    HAZARD_ZONE            – diffuse area hazard; hazard_penalty_s raised

    Reserved for future phases
    --------------------------
    FLOODING, CONSTRUCTION, WEATHER_EVENT, FIRE_INCIDENT, POLICE_OPERATION
    """

    ROAD_CLOSURE = "road_closure"
    ROAD_BLOCK = "road_block"
    TRAFFIC_ACCIDENT = "traffic_accident"
    EMERGENCY_VEHICLE = "emergency_vehicle"
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"
    COMMUNICATION_BLACKOUT = "communication_blackout"
    HAZARD_ZONE = "hazard_zone"

    # Reserved — not implemented in Phase 5
    FLOODING = "flooding"
    CONSTRUCTION = "construction"
    WEATHER_EVENT = "weather_event"
    FIRE_INCIDENT = "fire_incident"
    POLICE_OPERATION = "police_operation"
