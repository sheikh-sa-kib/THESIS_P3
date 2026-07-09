"""NetworkEffect Protocol and concrete effect implementations.

Design
------
Emergency events must NEVER directly modify the graph. Instead, each event
produces one or more ``NetworkEffect`` objects. The ``EmergencyState`` manager
applies and tracks these effects via a controlled interface.

Effect composition rules (Decision 1 — approved)
-------------------------------------------------
1. ``is_blocked = True`` takes unconditional precedence. A blocked edge is
   non-traversable regardless of any other effect.
2. ``congestion_factor`` effects are **multiplicative** and combine with the
   base congestion factor from simulation state.
3. ``hazard_penalty_s``, ``emergency_penalty_s``, ``communication_penalty_s``
   are **additive** across simultaneous active events on the same edge.
4. When all events contributing an effect to an edge are resolved or expired,
   the edge returns exactly to its original state. No residual values remain.

Event resolution cleanup (Decision 2 — approved)
-------------------------------------------------
Each ``NetworkEffect`` is tagged with the ``EventId`` that owns it.
The ``EmergencyState`` manager holds a reference count per (EdgeId, effect_type)
pair. When an event resolves, all its owned effects are removed and the
manager recomputes the composite state for each affected edge from scratch
(from remaining active effects). This prevents floating-point drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from e3hybrid.emergency.types import EventId
from e3hybrid.network.edge import MutableEdgeState
from e3hybrid.network.types import EdgeId


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class NetworkEffect(Protocol):
    """Interface satisfied by every concrete network effect.

    The ``EmergencyState`` applies effects through this interface.
    The ``DirectedGraph`` is never imported by the emergency module —
    only by the ``NetworkEffectSubscriber``.
    """

    @property
    def event_id(self) -> EventId: ...

    @property
    def edge_id(self) -> EdgeId: ...

    @property
    def effect_type(self) -> str: ...

    def apply(self, current_state: MutableEdgeState) -> MutableEdgeState:
        """Return a new MutableEdgeState with this effect applied.

        Never mutates ``current_state``.
        """
        ...

    def to_dict(self) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Concrete effects
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RoadClosureEffect:
    """Sets ``is_blocked = True`` unconditionally.

    Blocked edges always take precedence over all other effects.
    A blocked edge returns ``math.inf`` cost regardless of any additive
    penalties (``TravelTimeCostProvider`` enforces this via the
    ``edge.state.is_blocked`` flag).
    """

    event_id: EventId
    edge_id: EdgeId
    effect_type: str = "road_closure"

    def apply(self, current_state: MutableEdgeState) -> MutableEdgeState:
        return MutableEdgeState(
            is_blocked=True,
            current_speed_mps=current_state.current_speed_mps,
            travel_time_override_s=current_state.travel_time_override_s,
            congestion_factor=current_state.congestion_factor,
            hazard_penalty_s=current_state.hazard_penalty_s,
            emergency_penalty_s=current_state.emergency_penalty_s,
            communication_penalty_s=current_state.communication_penalty_s,
            metadata=current_state.metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return {"effect_type": self.effect_type, "event_id": str(self.event_id),
                "edge_id": str(self.edge_id)}


@dataclass(frozen=True, slots=True)
class CongestionEffect:
    """Adds a delta to ``congestion_factor`` (multiplicative on travel time).

    Multiple active ``CongestionEffect`` objects on the same edge are summed
    before being multiplied against base travel time:

        effective_congestion = base_congestion + Σ(delta_i)
    """

    event_id: EventId
    edge_id: EdgeId
    congestion_factor_delta: float
    effect_type: str = "congestion"

    def apply(self, current_state: MutableEdgeState) -> MutableEdgeState:
        new_factor = max(
            1.0, current_state.congestion_factor + self.congestion_factor_delta
        )
        return MutableEdgeState(
            is_blocked=current_state.is_blocked,
            current_speed_mps=current_state.current_speed_mps,
            travel_time_override_s=current_state.travel_time_override_s,
            congestion_factor=new_factor,
            hazard_penalty_s=current_state.hazard_penalty_s,
            emergency_penalty_s=current_state.emergency_penalty_s,
            communication_penalty_s=current_state.communication_penalty_s,
            metadata=current_state.metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return {"effect_type": self.effect_type, "event_id": str(self.event_id),
                "edge_id": str(self.edge_id),
                "congestion_factor_delta": self.congestion_factor_delta}


@dataclass(frozen=True, slots=True)
class HazardEffect:
    """Adds ``hazard_penalty_s`` to an edge (additive, non-blocking)."""

    event_id: EventId
    edge_id: EdgeId
    hazard_penalty_s: float
    effect_type: str = "hazard"

    def apply(self, current_state: MutableEdgeState) -> MutableEdgeState:
        return MutableEdgeState(
            is_blocked=current_state.is_blocked,
            current_speed_mps=current_state.current_speed_mps,
            travel_time_override_s=current_state.travel_time_override_s,
            congestion_factor=current_state.congestion_factor,
            hazard_penalty_s=current_state.hazard_penalty_s + self.hazard_penalty_s,
            emergency_penalty_s=current_state.emergency_penalty_s,
            communication_penalty_s=current_state.communication_penalty_s,
            metadata=current_state.metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return {"effect_type": self.effect_type, "event_id": str(self.event_id),
                "edge_id": str(self.edge_id), "hazard_penalty_s": self.hazard_penalty_s}


@dataclass(frozen=True, slots=True)
class EmergencyPriorityEffect:
    """Adds ``emergency_penalty_s`` to discourage corridor use (additive)."""

    event_id: EventId
    edge_id: EdgeId
    emergency_penalty_s: float
    effect_type: str = "emergency_priority"

    def apply(self, current_state: MutableEdgeState) -> MutableEdgeState:
        return MutableEdgeState(
            is_blocked=current_state.is_blocked,
            current_speed_mps=current_state.current_speed_mps,
            travel_time_override_s=current_state.travel_time_override_s,
            congestion_factor=current_state.congestion_factor,
            hazard_penalty_s=current_state.hazard_penalty_s,
            emergency_penalty_s=(
                current_state.emergency_penalty_s + self.emergency_penalty_s
            ),
            communication_penalty_s=current_state.communication_penalty_s,
            metadata=current_state.metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return {"effect_type": self.effect_type, "event_id": str(self.event_id),
                "edge_id": str(self.edge_id),
                "emergency_penalty_s": self.emergency_penalty_s}


@dataclass(frozen=True, slots=True)
class CommunicationEffect:
    """Adds ``communication_penalty_s`` to edges in a blackout zone.

    Decision 3 (approved): this effect only touches ``communication_penalty_s``
    on ``MutableEdgeState``.  The ``MessageBus`` is never directly modified by
    the emergency framework.  A future ``CommunicationPolicySubscriber`` can
    observe the raised ``communication_penalty_s`` and adjust the channel model.
    """

    event_id: EventId
    edge_id: EdgeId
    communication_penalty_s: float
    effect_type: str = "communication"

    def apply(self, current_state: MutableEdgeState) -> MutableEdgeState:
        return MutableEdgeState(
            is_blocked=current_state.is_blocked,
            current_speed_mps=current_state.current_speed_mps,
            travel_time_override_s=current_state.travel_time_override_s,
            congestion_factor=current_state.congestion_factor,
            hazard_penalty_s=current_state.hazard_penalty_s,
            emergency_penalty_s=current_state.emergency_penalty_s,
            communication_penalty_s=(
                current_state.communication_penalty_s
                + self.communication_penalty_s
            ),
            metadata=current_state.metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return {"effect_type": self.effect_type, "event_id": str(self.event_id),
                "edge_id": str(self.edge_id),
                "communication_penalty_s": self.communication_penalty_s}
