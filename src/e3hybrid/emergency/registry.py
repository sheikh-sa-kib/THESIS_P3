"""EmergencyRegistry — tracks all events across their entire lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from e3hybrid.core.exceptions import EmergencyError
from e3hybrid.emergency.enums import EmergencyEventType
from e3hybrid.emergency.event import EmergencyEvent
from e3hybrid.emergency.types import EventId, EventStatus


@dataclass
class EmergencyRegistry:
    """Single source of truth for all emergency events in a simulation run.

    The scheduler inserts events; the event bus updates their status;
    the state manager tracks their effects.  The registry only stores and
    indexes event objects — it never applies effects or publishes messages.

    Guarantees
    ----------
    - No duplicate ``event_id`` values.
    - Status transitions are forward-only (validated on update).
    - Terminal events (RESOLVED, EXPIRED) are never updated again.
    """

    _events: dict[EventId, EmergencyEvent] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Insertion
    # ------------------------------------------------------------------

    def register(self, event: EmergencyEvent) -> None:
        """Add an event to the registry.

        Raises
        ------
        EmergencyError:
            If the event_id is already registered.
        """
        if event.event_id in self._events:
            raise EmergencyError(
                f"duplicate event_id in registry: '{event.event_id}'"
            )
        self._events[event.event_id] = event

    # ------------------------------------------------------------------
    # Status updates
    # ------------------------------------------------------------------

    _FORWARD_TRANSITIONS: frozenset[tuple[EventStatus, EventStatus]] = frozenset({
        (EventStatus.CREATED, EventStatus.SCHEDULED),
        (EventStatus.SCHEDULED, EventStatus.ACTIVATED),
        (EventStatus.ACTIVATED, EventStatus.BROADCAST),
        (EventStatus.BROADCAST, EventStatus.OBSERVED),
        (EventStatus.OBSERVED, EventStatus.HANDLED),
        (EventStatus.HANDLED, EventStatus.RESOLVED),
        # Any non-terminal → EXPIRED or RESOLVED allowed
        (EventStatus.ACTIVATED, EventStatus.RESOLVED),
        (EventStatus.BROADCAST, EventStatus.RESOLVED),
        (EventStatus.OBSERVED, EventStatus.RESOLVED),
        (EventStatus.ACTIVATED, EventStatus.EXPIRED),
        (EventStatus.BROADCAST, EventStatus.EXPIRED),
        (EventStatus.OBSERVED, EventStatus.EXPIRED),
        (EventStatus.HANDLED, EventStatus.EXPIRED),
        (EventStatus.SCHEDULED, EventStatus.EXPIRED),
    })

    def update_status(self, event_id: EventId, status: EventStatus) -> None:
        """Update an event's lifecycle status.

        Raises
        ------
        EmergencyError:
            If the event is not registered, is already terminal, or the
            transition is not a valid forward move.
        """
        event = self.get(event_id)
        if event.status in (EventStatus.RESOLVED, EventStatus.EXPIRED):
            raise EmergencyError(
                f"event '{event_id}' is already in terminal state"
                f" {event.status} — cannot update to {status}"
            )
        if (event.status, status) not in self._FORWARD_TRANSITIONS:
            raise EmergencyError(
                f"invalid status transition for '{event_id}': "
                f"{event.status} → {status}"
            )
        self._events[event_id] = event.with_status(status)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, event_id: EventId) -> EmergencyEvent:
        """Return the event or raise EmergencyError if not found."""

        try:
            return self._events[event_id]
        except KeyError as exc:
            raise EmergencyError(
                f"unknown event_id: '{event_id}'"
            ) from exc

    def all_events(self) -> tuple[EmergencyEvent, ...]:
        """Return all registered events in insertion order."""

        return tuple(self._events.values())

    def active_events(self, sim_time_s: float) -> tuple[EmergencyEvent, ...]:
        """Return all events that are currently active at ``sim_time_s``."""

        return tuple(e for e in self._events.values() if e.is_active(sim_time_s))

    def by_type(
        self, event_type: EmergencyEventType
    ) -> tuple[EmergencyEvent, ...]:
        """Return all events of a specific type."""

        return tuple(
            e for e in self._events.values() if e.event_type == event_type
        )

    def by_status(self, status: EventStatus) -> tuple[EmergencyEvent, ...]:
        """Return all events in a specific lifecycle status."""

        return tuple(e for e in self._events.values() if e.status == status)

    def total_count(self) -> int:
        return len(self._events)

    def active_count(self, sim_time_s: float) -> int:
        return len(self.active_events(sim_time_s))

    def clear(self) -> None:
        """Remove all events (between experiment runs)."""
        self._events.clear()
