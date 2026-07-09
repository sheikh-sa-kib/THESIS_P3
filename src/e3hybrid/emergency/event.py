"""EmergencyEvent Protocol and shared base dataclass.

Design
------
``EmergencyEvent`` is a ``typing.Protocol`` — no inheritance required.
All seven concrete event classes are frozen dataclasses that satisfy the
Protocol structurally.

``BaseEmergencyEvent`` is a mixin dataclass providing the common fields
and default implementations of the Protocol methods.  Concrete classes
include it via dataclass inheritance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Protocol

from e3hybrid.communication.enums import Priority
from e3hybrid.emergency.enums import EmergencyEventType
from e3hybrid.emergency.types import EventId, EventLocation, EventStatus
from e3hybrid.network.types import EdgeId


class EmergencyEvent(Protocol):
    """Interface satisfied by every emergency event class."""

    @property
    def event_id(self) -> EventId: ...

    @property
    def event_type(self) -> EmergencyEventType: ...

    @property
    def activation_time_s(self) -> float: ...

    @property
    def duration_s(self) -> float | None: ...

    @property
    def severity(self) -> float: ...

    @property
    def priority(self) -> Priority: ...

    @property
    def status(self) -> EventStatus: ...

    @property
    def affected_edge_ids(self) -> frozenset[EdgeId]: ...

    @property
    def location(self) -> EventLocation: ...

    @property
    def broadcast_radius_m(self) -> float: ...

    @property
    def metadata(self) -> Mapping[str, Any]: ...

    def is_active(self, sim_time_s: float) -> bool: ...

    def is_expired(self, sim_time_s: float) -> bool: ...

    def with_status(self, status: EventStatus) -> "EmergencyEvent": ...

    def to_dict(self) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Shared base (used via dataclass inheritance — not mandatory for Protocol)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BaseEmergencyEvent:
    """Common fields and default logic shared by all concrete event classes."""

    event_id: EventId
    event_type: EmergencyEventType
    activation_time_s: float
    severity: float
    priority: Priority
    location: EventLocation
    broadcast_radius_m: float
    status: EventStatus = EventStatus.CREATED
    duration_s: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        from e3hybrid.core.exceptions import EmergencyError

        if not str(self.event_id).strip():
            raise EmergencyError("event_id must be non-empty")
        if self.activation_time_s < 0:
            raise EmergencyError("activation_time_s must be non-negative")
        if self.duration_s is not None and self.duration_s <= 0:
            raise EmergencyError("duration_s must be positive when provided")
        if not (0.0 <= self.severity <= 1.0):
            raise EmergencyError("severity must be in [0.0, 1.0]")
        if self.broadcast_radius_m <= 0:
            raise EmergencyError("broadcast_radius_m must be positive")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def affected_edge_ids(self) -> frozenset[EdgeId]:
        return self.location.edge_ids

    @property
    def expiration_time_s(self) -> float | None:
        if self.duration_s is None:
            return None
        return self.activation_time_s + self.duration_s

    def is_active(self, sim_time_s: float) -> bool:
        """True when the event has been activated and not yet resolved."""
        if self.status in (EventStatus.RESOLVED, EventStatus.EXPIRED):
            return False
        if sim_time_s < self.activation_time_s:
            return False
        if self.expiration_time_s is not None and sim_time_s >= self.expiration_time_s:
            return False
        return True

    def is_expired(self, sim_time_s: float) -> bool:
        """True when the event TTL has elapsed."""
        if self.expiration_time_s is None:
            return False
        return sim_time_s >= self.expiration_time_s

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": str(self.event_id),
            "event_type": str(self.event_type),
            "activation_time_s": self.activation_time_s,
            "duration_s": self.duration_s,
            "severity": self.severity,
            "priority": str(self.priority),
            "status": str(self.status),
            "broadcast_radius_m": self.broadcast_radius_m,
            "location": self.location.to_dict(),
            "metadata": dict(self.metadata),
        }
