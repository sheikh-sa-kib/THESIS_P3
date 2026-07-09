"""NetworkEffectSubscriber — applies emergency effects to the graph.

This subscriber is the ONLY module that touches the ``DirectedGraph`` on behalf
of the emergency framework.  The emergency event classes themselves never import
the graph.

It subscribes to ``EmergencyEventBus.subscribe_all()`` and:
1. On ACTIVATED events: registers baselines and applies effects via EmergencyState.
2. On RESOLVED/EXPIRED events: removes effects and restores original edge states.
"""

from __future__ import annotations

import logging
from typing import Sequence

from e3hybrid.emergency.effects import (
    CommunicationEffect,
    CongestionEffect,
    EmergencyPriorityEffect,
    HazardEffect,
    NetworkEffect,
    RoadClosureEffect,
)
from e3hybrid.emergency.enums import EmergencyEventType
from e3hybrid.emergency.event import EmergencyEvent
from e3hybrid.emergency.events import (
    CommunicationBlackoutEvent,
    EmergencyVehicleEvent,
    HazardZoneEvent,
    InfrastructureFailureEvent,
    RoadBlockEvent,
    RoadClosureEvent,
    TrafficAccidentEvent,
)
from e3hybrid.emergency.state import EmergencyState
from e3hybrid.emergency.types import EventStatus
from e3hybrid.network.graph import DirectedGraph

_logger = logging.getLogger(__name__)


class NetworkEffectSubscriber:
    """Subscribes to the EmergencyEventBus and applies/removes graph effects.

    Registered via:
    ::

        bus.subscribe_all(subscriber.handle, priority=100)

    The high priority (100) ensures network effects are applied before
    communication or decision engine subscribers read the updated state.
    """

    def __init__(self, graph: DirectedGraph, state: EmergencyState) -> None:
        self._graph = graph
        self._state = state

    def handle(self, event: EmergencyEvent) -> None:
        """Route the event to the appropriate handler based on status."""

        if event.status == EventStatus.ACTIVATED:
            self._activate(event)
        elif event.status in (EventStatus.RESOLVED, EventStatus.EXPIRED):
            self._resolve(event)

    def _activate(self, event: EmergencyEvent) -> None:
        effects = self._effects_for(event)
        if not effects:
            return
        for effect in effects:
            edge = self._graph.get_edge(effect.edge_id)
            self._state.register_baseline(effect.edge_id, edge.state)
        self._state.apply_effects(event.event_id, effects)
        self._apply_composite_states(event.affected_edge_ids)

    def _resolve(self, event: EmergencyEvent) -> None:
        affected = self._state.remove_effects(event.event_id)
        self._apply_composite_states(affected)

    def _apply_composite_states(self, edge_ids) -> None:
        for edge_id in edge_ids:
            new_state = self._state.composite_state(edge_id)
            if new_state is not None:
                try:
                    self._graph.update_edge_state(edge_id, new_state)
                except Exception as exc:  # noqa: BLE001
                    _logger.error(
                        "NetworkEffectSubscriber: failed to update edge %s: %s",
                        edge_id, exc,
                    )

    def _effects_for(self, event: EmergencyEvent) -> list[NetworkEffect]:
        eid = event.event_id
        edges = event.affected_edge_ids
        effects: list[NetworkEffect] = []

        if isinstance(event, RoadClosureEvent):
            effects += [RoadClosureEffect(event_id=eid, edge_id=e) for e in edges]

        elif isinstance(event, RoadBlockEvent):
            effects += [
                CongestionEffect(
                    event_id=eid, edge_id=e,
                    congestion_factor_delta=event.congestion_factor_delta,
                )
                for e in edges
            ]

        elif isinstance(event, TrafficAccidentEvent):
            if event.blocks_all_lanes:
                effects += [RoadClosureEffect(event_id=eid, edge_id=e) for e in edges]
            else:
                effects += [
                    CongestionEffect(
                        event_id=eid, edge_id=e,
                        congestion_factor_delta=event.secondary_congestion_delta,
                    )
                    for e in edges
                ]

        elif isinstance(event, EmergencyVehicleEvent):
            effects += [
                EmergencyPriorityEffect(
                    event_id=eid, edge_id=e,
                    emergency_penalty_s=event.emergency_penalty_s,
                )
                for e in edges
            ]

        elif isinstance(event, HazardZoneEvent):
            effects += [
                HazardEffect(
                    event_id=eid, edge_id=e,
                    hazard_penalty_s=event.hazard_penalty_s,
                )
                for e in edges
            ]

        elif isinstance(event, CommunicationBlackoutEvent):
            effects += [
                CommunicationEffect(
                    event_id=eid, edge_id=e,
                    communication_penalty_s=event.communication_penalty_s,
                )
                for e in edges
            ]

        elif isinstance(event, InfrastructureFailureEvent):
            pass  # Phase 5: no penalty applied yet

        return effects
