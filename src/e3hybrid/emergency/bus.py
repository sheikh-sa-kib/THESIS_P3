"""EmergencyEventBus — publish/subscribe event dispatcher.

Design requirements met
-----------------------
- subscribe() / unsubscribe() / publish() / clear()
- Subscriber priorities (higher int = called first)
- Deterministic delivery order (stable sort by priority descending, then
  registration order for equal priority — insertion index tiebreaker)
- Exception isolation (subscriber exception logged; other subscribers still notified)
- Delivery statistics (events published, delivered, failed per type)
- Typed subscriptions (subscribe to one type or all types)
- Future async compatibility: the synchronous ``publish`` signature is
  designed so that a future ``AsyncEmergencyEventBus`` can satisfy the same
  ``EmergencyEventBus`` Protocol by implementing ``async def publish()``.
  Callers that use type annotations against the Protocol will require no changes.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

from e3hybrid.core.exceptions import EmergencyError
from e3hybrid.emergency.enums import EmergencyEventType
from e3hybrid.emergency.event import EmergencyEvent
from e3hybrid.emergency.types import EventId

_logger = logging.getLogger(__name__)

# Subscriber callable type: receives the published event.
EventHandler = Callable[[EmergencyEvent], None]

_ALL_TYPES = "__all__"  # sentinel key for subscribe_all()


@dataclass
class _SubscriberEntry:
    handler: EventHandler
    priority: int
    insertion_index: int


@dataclass
class EmergencyBusStatistics:
    """Delivery statistics for the EmergencyEventBus."""

    events_published: int = 0
    total_deliveries: int = 0
    total_failures: int = 0
    per_type_published: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "events_published": self.events_published,
            "total_deliveries": self.total_deliveries,
            "total_failures": self.total_failures,
            "per_type_published": dict(self.per_type_published),
        }


class EmergencyEventBus:
    """Publish/subscribe dispatcher for emergency events.

    Usage
    -----
    ::

        bus = EmergencyEventBus()
        bus.subscribe(EmergencyEventType.ROAD_CLOSURE, my_handler, priority=10)
        bus.publish(road_closure_event)

    Delivery order
    --------------
    Subscribers with higher ``priority`` values are called first.
    For equal priorities, registration order is preserved (FIFO).

    Exception isolation
    -------------------
    If a subscriber raises an exception, the exception is logged at ERROR
    level and the remaining subscribers still receive the event.
    This prevents one faulty subscriber from silently blocking all others.
    """

    def __init__(self) -> None:
        # Maps event_type_str → list of _SubscriberEntry (or _ALL_TYPES key)
        self._subscribers: dict[str, list[_SubscriberEntry]] = defaultdict(list)
        self._insertion_counter: int = 0
        self._stats = EmergencyBusStatistics()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def subscribe(
        self,
        event_type: EmergencyEventType,
        handler: EventHandler,
        *,
        priority: int = 0,
    ) -> None:
        """Register a handler for a specific event type."""

        entry = _SubscriberEntry(
            handler=handler,
            priority=priority,
            insertion_index=self._insertion_counter,
        )
        self._insertion_counter += 1
        self._subscribers[str(event_type)].append(entry)

    def subscribe_all(
        self, handler: EventHandler, *, priority: int = 0
    ) -> None:
        """Register a handler that receives every published event type."""

        entry = _SubscriberEntry(
            handler=handler,
            priority=priority,
            insertion_index=self._insertion_counter,
        )
        self._insertion_counter += 1
        self._subscribers[_ALL_TYPES].append(entry)

    def unsubscribe(
        self, event_type: EmergencyEventType, handler: EventHandler
    ) -> None:
        """Remove a handler for a specific event type.

        Silently does nothing if the handler was not registered.
        """
        key = str(event_type)
        self._subscribers[key] = [
            e for e in self._subscribers[key] if e.handler is not handler
        ]

    def unsubscribe_all(self, handler: EventHandler) -> None:
        """Remove a handler from all subscriptions."""

        for key in list(self._subscribers.keys()):
            self._subscribers[key] = [
                e for e in self._subscribers[key] if e.handler is not handler
            ]

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def publish(self, event: EmergencyEvent) -> None:
        """Dispatch an event to all matching subscribers.

        Delivery order: higher priority first; equal priority in FIFO order.
        Exception isolation: subscriber exceptions are logged and skipped.
        """
        # Collect typed subscribers + wildcard subscribers
        typed_entries = self._subscribers.get(str(event.event_type), [])
        all_entries = self._subscribers.get(_ALL_TYPES, [])
        combined = list(typed_entries) + list(all_entries)

        # Stable sort: descending priority, then ascending insertion index
        combined.sort(key=lambda e: (-e.priority, e.insertion_index))

        type_key = str(event.event_type)
        self._stats.events_published += 1
        self._stats.per_type_published[type_key] = (
            self._stats.per_type_published.get(type_key, 0) + 1
        )

        for entry in combined:
            try:
                entry.handler(event)
                self._stats.total_deliveries += 1
            except Exception as exc:  # noqa: BLE001
                self._stats.total_failures += 1
                _logger.error(
                    "EmergencyEventBus: subscriber %r raised %s: %s",
                    entry.handler,
                    type(exc).__name__,
                    exc,
                )

    # ------------------------------------------------------------------
    # Management
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Remove all subscribers and reset statistics."""

        self._subscribers.clear()
        self._insertion_counter = 0
        self._stats = EmergencyBusStatistics()

    def subscriber_count(
        self, event_type: EmergencyEventType | None = None
    ) -> int:
        """Return number of subscribers for a type, or total across all types."""

        if event_type is not None:
            return len(self._subscribers.get(str(event_type), []))
        return sum(len(v) for v in self._subscribers.values())

    @property
    def statistics(self) -> EmergencyBusStatistics:
        """Return current delivery statistics."""

        return self._stats
