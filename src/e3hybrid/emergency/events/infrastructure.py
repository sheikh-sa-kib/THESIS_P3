"""InfrastructureFailureEvent and CommunicationBlackoutEvent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from e3hybrid.core.exceptions import EmergencyError
from e3hybrid.emergency.enums import EmergencyEventType
from e3hybrid.emergency.event import BaseEmergencyEvent
from e3hybrid.emergency.types import EventStatus


@dataclass(frozen=True, slots=True)
class InfrastructureFailureEvent(BaseEmergencyEvent):
    """Traffic signal, bridge sensor, or road IoT device failure.

    Network effect: affected edges lose authoritative dynamic data.
    Vehicles fall back to static ``speed_limit_mps``.
    No penalty is applied in Phase 5; a future ``UncertaintyPenaltyEffect``
    can be added through the ``NetworkEffect`` interface.

    Extra attributes
    ----------------
    failed_sensor_ids:
        Identifiers of the failed infrastructure components.
    fallback_to_static:
        When True (default), affected edges revert to their static speed limit.
    """

    failed_sensor_ids: frozenset[str] = field(default_factory=frozenset)
    fallback_to_static: bool = True

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(
            self, "event_type", EmergencyEventType.INFRASTRUCTURE_FAILURE
        )

    def with_status(self, status: EventStatus) -> "InfrastructureFailureEvent":
        return InfrastructureFailureEvent(
            event_id=self.event_id,
            event_type=self.event_type,
            activation_time_s=self.activation_time_s,
            duration_s=self.duration_s,
            severity=self.severity,
            priority=self.priority,
            location=self.location,
            broadcast_radius_m=self.broadcast_radius_m,
            status=status,
            metadata=self.metadata,
            failed_sensor_ids=self.failed_sensor_ids,
            fallback_to_static=self.fallback_to_static,
        )

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base["failed_sensor_ids"] = sorted(self.failed_sensor_ids)
        base["fallback_to_static"] = self.fallback_to_static
        return base


@dataclass(frozen=True, slots=True)
class CommunicationBlackoutEvent(BaseEmergencyEvent):
    """V2V/V2X communication disrupted in a geographic zone.

    Decision 3 (approved): This event NEVER manipulates the MessageBus
    directly.  It sets ``communication_penalty_s`` on affected edges via
    the ``NetworkEffectSubscriber``.  A future ``CommunicationPolicy``
    subscriber can then adjust the MessageBus channel model based on the
    active penalty level.

    Network effect: ``communication_penalty_s`` raised on affected edges.

    Extra attributes
    ----------------
    communication_penalty_s:
        Additive time penalty reflecting disrupted coordination cost.
    blackout_cause:
        Descriptive label ("jamming", "obstruction", "spectrum_congestion").
    """

    communication_penalty_s: float = 60.0
    blackout_cause: str = "unspecified"

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(
            self, "event_type", EmergencyEventType.COMMUNICATION_BLACKOUT
        )
        if self.communication_penalty_s <= 0:
            raise EmergencyError("communication_penalty_s must be positive")

    def with_status(self, status: EventStatus) -> "CommunicationBlackoutEvent":
        return CommunicationBlackoutEvent(
            event_id=self.event_id,
            event_type=self.event_type,
            activation_time_s=self.activation_time_s,
            duration_s=self.duration_s,
            severity=self.severity,
            priority=self.priority,
            location=self.location,
            broadcast_radius_m=self.broadcast_radius_m,
            status=status,
            metadata=self.metadata,
            communication_penalty_s=self.communication_penalty_s,
            blackout_cause=self.blackout_cause,
        )

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base["communication_penalty_s"] = self.communication_penalty_s
        base["blackout_cause"] = self.blackout_cause
        return base
