"""Emergency framework — simulator-independent, deterministic, reproducible.

Phase 5 public API.

Design principles
-----------------
1. Events are PUBLISHED, not PUSHED.  The emergency framework fires events
   onto the ``EmergencyEventBus``; subscribers react independently.
2. Events NEVER directly modify the graph.  Only ``NetworkEffectSubscriber``
   touches graph state, and only through the ``EmergencyState`` manager.
3. Effects compose ADDITIVELY.  Multiple simultaneous events stack penalties.
   Blocked edges take unconditional precedence.
4. Resolution is CLEAN.  When an event resolves, the graph returns exactly to
   its original state.  No residual values accumulate.
5. Everything is REPRODUCIBLE.  Random events use seeded streams.
"""

from e3hybrid.emergency.bus import EmergencyBusStatistics, EmergencyEventBus
from e3hybrid.emergency.effects import (
    CommunicationEffect,
    CongestionEffect,
    EmergencyPriorityEffect,
    HazardEffect,
    NetworkEffect,
    RoadClosureEffect,
)
from e3hybrid.emergency.enums import EmergencyEventType
from e3hybrid.emergency.event import BaseEmergencyEvent, EmergencyEvent
from e3hybrid.emergency.events import (
    CommunicationBlackoutEvent,
    EmergencyVehicleEvent,
    HazardZoneEvent,
    InfrastructureFailureEvent,
    RoadBlockEvent,
    RoadClosureEvent,
    TrafficAccidentEvent,
)
from e3hybrid.emergency.registry import EmergencyRegistry
from e3hybrid.emergency.scenario import LoadedScenario, ScenarioLoader, ScenarioMetadata
from e3hybrid.emergency.scheduler import EventScheduler
from e3hybrid.emergency.state import EmergencyState
from e3hybrid.emergency.subscribers import NetworkEffectSubscriber
from e3hybrid.emergency.types import EventId, EventLocation, EventStatus
from e3hybrid.emergency.validation import validate_scenario_dict

__all__ = [
    "BaseEmergencyEvent",
    "CommunicationBlackoutEvent",
    "CommunicationEffect",
    "CongestionEffect",
    "EmergencyBusStatistics",
    "EmergencyEvent",
    "EmergencyEventBus",
    "EmergencyEventType",
    "EmergencyPriorityEffect",
    "EmergencyRegistry",
    "EmergencyState",
    "EmergencyVehicleEvent",
    "EventId",
    "EventLocation",
    "EventScheduler",
    "EventStatus",
    "HazardEffect",
    "HazardZoneEvent",
    "InfrastructureFailureEvent",
    "LoadedScenario",
    "NetworkEffect",
    "NetworkEffectSubscriber",
    "RoadBlockEvent",
    "RoadClosureEffect",
    "RoadClosureEvent",
    "ScenarioLoader",
    "ScenarioMetadata",
    "TrafficAccidentEvent",
    "validate_scenario_dict",
]
