"""Core types for the Decision Engine."""

from __future__ import annotations

from enum import StrEnum
from typing import NewType

DecisionId = NewType("DecisionId", str)
RouteId = NewType("RouteId", str)


class DecisionType(StrEnum):
    """Every action a vehicle may be instructed to take.

    The Decision Engine produces one of these per evaluation cycle.
    The simulation core (future) executes the corresponding action.

    Phase 6 types
    -------------
    KEEP_CURRENT_ROUTE  – No change needed; continue as planned.
    REQUEST_REROUTE     – Current route is suboptimal or blocked; ask for
                          a new route from the RouteCandidateSource.
    YIELD               – An EmergencyVehicleEvent requires the vehicle to
                          hold position for a configurable duration.
    WAIT                – Battery or safety constraint requires a stop.
    REDUCE_SPEED        – Non-blocking suggestion to lower speed.
    BROADCAST_MESSAGE   – Vehicle has new information to share via V2V.
    REQUEST_EXPLORATION – Route quality is uncertain; request additional
                          coverage from scout agents (Phase 8+).
    IGNORE_EVENT        – Received event is irrelevant to this vehicle.
    EMERGENCY_STOP      – Hard safety constraint; immediate halt.

    Reserved for future phases
    --------------------------
    CHARGE              – Phase 9 (charging station logic).
    COORDINATE          – Phase 9+ (swarm coordination signal).
    """

    KEEP_CURRENT_ROUTE  = "keep_current_route"
    REQUEST_REROUTE     = "request_reroute"
    YIELD               = "yield"
    WAIT                = "wait"
    REDUCE_SPEED        = "reduce_speed"
    BROADCAST_MESSAGE   = "broadcast_message"
    REQUEST_EXPLORATION = "request_exploration"
    IGNORE_EVENT        = "ignore_event"
    EMERGENCY_STOP      = "emergency_stop"
    CHARGE              = "charge"
    COORDINATE          = "coordinate"
