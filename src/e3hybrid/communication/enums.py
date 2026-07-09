"""Message-type and priority enumerations.

MessageType defines what kind of information a message carries.
The communication layer transports messages without interpreting their content —
routing algorithms, emergency handlers, and swarm agents read the payload.

Priority controls ordering in the message bus queue. Higher-priority messages
are delivered before lower-priority ones when the bus is under load.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum


class MessageType(StrEnum):
    """Supported message content types.

    The communication layer never inspects the payload beyond reading the type
    field for statistics. New types can be added here without changing any
    other module.

    Traffic and road conditions
    ---------------------------
    TRAFFIC_UPDATE      Current congestion level on a road segment.
    ROAD_CLOSURE        A road segment has been closed (emergency or accident).
    HAZARD              A hazard (obstacle, debris, flood) is present on a segment.

    Emergency coordination
    ----------------------
    EMERGENCY_VEHICLE   An emergency vehicle is en route; priority corridor request.

    Swarm intelligence (future Phase 7)
    ------------------------------------
    PHEROMONE_UPDATE    ACO pheromone deposit or evaporation notification.
    SCOUT_REPORT        BCO scout vehicle sharing a discovered route.
    VEHICLE_STATE       PSO particle sharing its current position (routing state).

    Operational
    -----------
    HEARTBEAT           Periodic presence announcement (vehicle is alive).
    ACKNOWLEDGEMENT     Explicit delivery confirmation for reliability protocols.

    Reserved for future use
    -----------------------
    ROUTE_REQUEST       A vehicle requests routing assistance from neighbours.
    ROUTE_OFFER         A vehicle offers a candidate route to another vehicle.
    COORDINATION        Generic swarm coordination payload.
    CUSTOM              Escape hatch for experiment-specific payload types.
    """

    # Traffic / road conditions
    TRAFFIC_UPDATE = "traffic_update"
    ROAD_CLOSURE = "road_closure"
    HAZARD = "hazard"

    # Emergency
    EMERGENCY_VEHICLE = "emergency_vehicle"

    # Swarm (Phase 7)
    PHEROMONE_UPDATE = "pheromone_update"
    SCOUT_REPORT = "scout_report"
    VEHICLE_STATE = "vehicle_state"

    # Operational
    HEARTBEAT = "heartbeat"
    ACKNOWLEDGEMENT = "acknowledgement"

    # Future / extensible
    ROUTE_REQUEST = "route_request"
    ROUTE_OFFER = "route_offer"
    COORDINATION = "coordination"
    CUSTOM = "custom"


class Priority(IntEnum):
    """Message delivery priority.

    Higher integer values are processed first by the message bus.
    Algorithms may request higher priority for time-sensitive messages
    (e.g., emergency corridor notifications).

    CRITICAL  –  Emergency broadcasts that must reach all vehicles immediately.
    HIGH      –  Time-sensitive coordination (pheromone updates, scout reports).
    NORMAL    –  Standard operational messages (traffic updates, heartbeats).
    LOW       –  Background or non-urgent messages (bulk statistics, logging).
    """

    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
