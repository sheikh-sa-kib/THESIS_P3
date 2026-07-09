"""Message model for the communication framework.

A Message is the atomic unit of information exchanged between simulation
agents (vehicles, infrastructure nodes, or the emergency coordinator).

Design contract
---------------
- Messages are immutable once created.
- The communication layer transports messages without interpreting the payload.
- Routing algorithms, swarm agents, and emergency handlers consume payloads.
- Message identity is established by ``message_id``; duplicates are rejected
  by the MessageBus.

Broadcast vs unicast
--------------------
When ``is_broadcast=True`` the message is delivered to every vehicle within
the communication radius. ``receiver_id`` is ignored.
When ``is_broadcast=False`` the message is addressed to ``receiver_id``.
A unicast message with no ``receiver_id`` is invalid and rejected at
construction.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from e3hybrid.communication.enums import MessageType, Priority
from e3hybrid.communication.types import DeliveryStatus, MessageId
from e3hybrid.core.exceptions import CommunicationError
from e3hybrid.vehicle.types import VehicleId


@dataclass(frozen=True, slots=True)
class Message:
    """An immutable unit of information sent between simulation agents.

    Attributes
    ----------
    message_id:
        Globally unique identifier. Auto-generated via ``create()`` if
        not supplied.
    sender_id:
        VehicleId (or infrastructure node ID) of the originator.
    message_type:
        Category of information being carried (see ``MessageType``).
    priority:
        Delivery priority. Higher priority messages are processed first.
    payload:
        Arbitrary content. The communication layer never inspects this.
        Callers are responsible for encoding/decoding.
    is_broadcast:
        True = deliver to all agents within communication radius.
        False = unicast to ``receiver_id``.
    receiver_id:
        Target agent for unicast messages. Must be set when
        ``is_broadcast=False``.
    created_at_s:
        Simulation time (seconds) at which the message was created.
    ttl_s:
        Time-to-live in simulation seconds. Message expires when
        ``created_at_s + ttl_s`` is reached.
    hop_count:
        Number of relay hops this message has traversed. Incremented by
        the relay logic in the MessageBus. Starts at 0.
    max_hops:
        Maximum number of relay hops allowed. 0 = no relay (direct only).
        None = unlimited relaying.
    delivery_status:
        Current delivery status. Set to DELIVERED / DROPPED / EXPIRED by the
        MessageBus after a delivery attempt.
    """

    message_id: MessageId
    sender_id: VehicleId
    message_type: MessageType
    priority: Priority
    payload: Any
    is_broadcast: bool
    created_at_s: float
    ttl_s: float
    receiver_id: VehicleId | None = None
    hop_count: int = 0
    max_hops: int | None = None
    delivery_status: DeliveryStatus = DeliveryStatus.PENDING

    def __post_init__(self) -> None:
        """Validate message fields."""

        if not str(self.message_id).strip():
            raise CommunicationError("message_id must be non-empty")
        if not str(self.sender_id).strip():
            raise CommunicationError("sender_id must be non-empty")
        if not self.is_broadcast and self.receiver_id is None:
            raise CommunicationError(
                "receiver_id must be set for unicast messages (is_broadcast=False)"
            )
        if self.ttl_s <= 0:
            raise CommunicationError("ttl_s must be positive")
        if self.created_at_s < 0:
            raise CommunicationError("created_at_s must be non-negative")
        if self.hop_count < 0:
            raise CommunicationError("hop_count must be non-negative")
        if self.max_hops is not None and self.max_hops < 0:
            raise CommunicationError("max_hops must be non-negative when provided")

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        sender_id: VehicleId,
        message_type: MessageType,
        payload: Any,
        created_at_s: float,
        ttl_s: float,
        priority: Priority = Priority.NORMAL,
        is_broadcast: bool = True,
        receiver_id: VehicleId | None = None,
        max_hops: int | None = None,
        message_id: MessageId | None = None,
    ) -> "Message":
        """Create a new message, auto-generating a UUID if no id is given."""

        mid = message_id or MessageId(str(uuid.uuid4()))
        return cls(
            message_id=mid,
            sender_id=sender_id,
            message_type=message_type,
            priority=priority,
            payload=payload,
            is_broadcast=is_broadcast,
            receiver_id=receiver_id,
            created_at_s=created_at_s,
            ttl_s=ttl_s,
            max_hops=max_hops,
        )

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def expiration_time_s(self) -> float:
        """Simulation time at which this message expires."""

        return self.created_at_s + self.ttl_s

    def is_expired(self, current_time_s: float) -> bool:
        """Return True when the message has passed its TTL."""

        return current_time_s >= self.expiration_time_s

    def can_relay(self) -> bool:
        """Return True when the message may be relayed further."""

        if self.max_hops is None:
            return True
        return self.hop_count < self.max_hops

    # ------------------------------------------------------------------
    # State transitions (immutable copy pattern)
    # ------------------------------------------------------------------

    def with_status(self, status: DeliveryStatus) -> "Message":
        """Return a copy with updated delivery_status."""

        return Message(
            message_id=self.message_id,
            sender_id=self.sender_id,
            message_type=self.message_type,
            priority=self.priority,
            payload=self.payload,
            is_broadcast=self.is_broadcast,
            receiver_id=self.receiver_id,
            created_at_s=self.created_at_s,
            ttl_s=self.ttl_s,
            hop_count=self.hop_count,
            max_hops=self.max_hops,
            delivery_status=status,
        )

    def with_incremented_hop(self) -> "Message":
        """Return a copy with hop_count incremented by one."""

        return Message(
            message_id=self.message_id,
            sender_id=self.sender_id,
            message_type=self.message_type,
            priority=self.priority,
            payload=self.payload,
            is_broadcast=self.is_broadcast,
            receiver_id=self.receiver_id,
            created_at_s=self.created_at_s,
            ttl_s=self.ttl_s,
            hop_count=self.hop_count + 1,
            max_hops=self.max_hops,
            delivery_status=self.delivery_status,
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize the message to a JSON-compatible dictionary."""

        return {
            "message_id": str(self.message_id),
            "sender_id": str(self.sender_id),
            "receiver_id": str(self.receiver_id) if self.receiver_id else None,
            "message_type": str(self.message_type),
            "priority": int(self.priority),
            "is_broadcast": self.is_broadcast,
            "created_at_s": self.created_at_s,
            "ttl_s": self.ttl_s,
            "expiration_time_s": self.expiration_time_s,
            "hop_count": self.hop_count,
            "max_hops": self.max_hops,
            "delivery_status": str(self.delivery_status),
            "payload": self.payload,
        }

    def __repr__(self) -> str:
        target = "broadcast" if self.is_broadcast else str(self.receiver_id)
        return (
            f"Message("
            f"id={str(self.message_id)[:8]}…, "
            f"type={self.message_type}, "
            f"from={self.sender_id}, "
            f"to={target}, "
            f"priority={self.priority.name}, "
            f"status={self.delivery_status})"
        )
