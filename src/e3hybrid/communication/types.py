"""Strongly typed identifiers and delivery status for the communication module."""

from __future__ import annotations

from enum import StrEnum
from typing import NewType

from e3hybrid.vehicle.types import VehicleId  # noqa: F401  – re-exported for convenience

MessageId = NewType("MessageId", str)


class DeliveryStatus(StrEnum):
    """Lifecycle status of a message or packet.

    Transitions:
        PENDING  →  DELIVERED  (successful unicast or broadcast delivery)
        PENDING  →  DROPPED    (packet-loss model decided to discard)
        PENDING  →  EXPIRED    (TTL elapsed before delivery was attempted)
        PENDING  →  OUT_OF_RANGE (sender and receiver too far apart)
    """

    PENDING = "pending"
    DELIVERED = "delivered"
    DROPPED = "dropped"
    EXPIRED = "expired"
    OUT_OF_RANGE = "out_of_range"
