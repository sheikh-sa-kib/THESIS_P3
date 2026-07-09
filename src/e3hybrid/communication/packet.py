"""Packet model — a transmission envelope wrapping a Message.

A Packet represents one delivery attempt of a Message over the simulated
medium. While a Message captures the intent and content of communication,
a Packet captures the physical-layer transmission event: when it was sent,
what latency was applied, whether it was lost, and which nodes it passed
through.

One Message may produce multiple Packets:
- A broadcast message produces one Packet per eligible receiver.
- A relayed message produces a new Packet for each relay hop.
- A retransmitted message (future reliability protocol) produces a new Packet.

The communication layer never modifies the wrapped Message. Status updates
are recorded on the Packet, not on the Message.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from e3hybrid.communication.message import Message
from e3hybrid.communication.types import DeliveryStatus, MessageId
from e3hybrid.core.exceptions import CommunicationError
from e3hybrid.vehicle.types import VehicleId


@dataclass(frozen=True, slots=True)
class Packet:
    """A single transmission attempt carrying a Message.

    Attributes
    ----------
    packet_id:
        Unique identifier for this transmission attempt.
    message:
        The wrapped message. Never modified by the packet layer.
    sender_id:
        The agent transmitting this packet (may differ from message.sender_id
        when the packet is a relay).
    intended_receiver_id:
        The direct target of this packet. For broadcasts, set to None;
        the bus expands the delivery list from the radius model.
    transmitted_at_s:
        Simulation time at which this packet was placed onto the medium.
    latency_s:
        Propagation + processing delay in simulation seconds, as computed by
        the LatencyModel. 0.0 for deterministic baseline.
    delivery_status:
        Outcome of this specific transmission attempt.
    is_relay:
        True when this packet was created by a relay node, not the original
        sender.
    distance_m:
        Distance between sender and receiver at transmission time, in metres.
        None when positions are unavailable (pre-SUMO phases).
    """

    packet_id: MessageId
    message: Message
    sender_id: VehicleId
    transmitted_at_s: float
    latency_s: float = 0.0
    delivery_status: DeliveryStatus = DeliveryStatus.PENDING
    intended_receiver_id: VehicleId | None = None
    is_relay: bool = False
    distance_m: float | None = None

    def __post_init__(self) -> None:
        """Validate packet fields."""

        if not str(self.packet_id).strip():
            raise CommunicationError("packet_id must be non-empty")
        if self.transmitted_at_s < 0:
            raise CommunicationError("transmitted_at_s must be non-negative")
        if self.latency_s < 0:
            raise CommunicationError("latency_s must be non-negative")
        if self.distance_m is not None and self.distance_m < 0:
            raise CommunicationError("distance_m must be non-negative when provided")

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        message: Message,
        transmitted_at_s: float,
        latency_s: float = 0.0,
        intended_receiver_id: VehicleId | None = None,
        is_relay: bool = False,
        distance_m: float | None = None,
        packet_id: MessageId | None = None,
    ) -> "Packet":
        """Create a packet for a single transmission attempt."""

        pid = packet_id or MessageId(str(uuid.uuid4()))
        return cls(
            packet_id=pid,
            message=message,
            sender_id=message.sender_id if not is_relay else message.sender_id,
            transmitted_at_s=transmitted_at_s,
            latency_s=latency_s,
            intended_receiver_id=intended_receiver_id,
            is_relay=is_relay,
            distance_m=distance_m,
        )

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def arrival_time_s(self) -> float:
        """Simulation time at which this packet arrives at the receiver."""

        return self.transmitted_at_s + self.latency_s

    def is_expired(self, current_time_s: float) -> bool:
        """Return True when the wrapped message has expired by current_time_s."""

        return self.message.is_expired(current_time_s)

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def with_status(self, status: DeliveryStatus) -> "Packet":
        """Return a copy with updated delivery status."""

        return Packet(
            packet_id=self.packet_id,
            message=self.message,
            sender_id=self.sender_id,
            transmitted_at_s=self.transmitted_at_s,
            latency_s=self.latency_s,
            delivery_status=status,
            intended_receiver_id=self.intended_receiver_id,
            is_relay=self.is_relay,
            distance_m=self.distance_m,
        )

    def with_latency(self, latency_s: float) -> "Packet":
        """Return a copy with assigned latency."""

        return Packet(
            packet_id=self.packet_id,
            message=self.message,
            sender_id=self.sender_id,
            transmitted_at_s=self.transmitted_at_s,
            latency_s=latency_s,
            delivery_status=self.delivery_status,
            intended_receiver_id=self.intended_receiver_id,
            is_relay=self.is_relay,
            distance_m=self.distance_m,
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize the packet to a JSON-compatible dictionary."""

        return {
            "packet_id": str(self.packet_id),
            "message_id": str(self.message.message_id),
            "sender_id": str(self.sender_id),
            "intended_receiver_id": (
                str(self.intended_receiver_id)
                if self.intended_receiver_id
                else None
            ),
            "transmitted_at_s": self.transmitted_at_s,
            "latency_s": self.latency_s,
            "arrival_time_s": self.arrival_time_s,
            "delivery_status": str(self.delivery_status),
            "is_relay": self.is_relay,
            "distance_m": self.distance_m,
        }

    def __repr__(self) -> str:
        return (
            f"Packet("
            f"id={str(self.packet_id)[:8]}…, "
            f"msg={str(self.message.message_id)[:8]}…, "
            f"at={self.transmitted_at_s:.1f}s, "
            f"latency={self.latency_s:.3f}s, "
            f"status={self.delivery_status})"
        )
