"""Communication statistics tracker.

``CommunicationStatistics`` accumulates per-run metrics about message and
packet flow. It is updated by the ``MessageBus`` after every delivery
attempt and is written to ``communication_log.csv`` at run end.

All statistics are in-memory only. Persistence is the responsibility of
the future experiment runner (Phase 9).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CommunicationStatistics:
    """Mutable accumulator for communication-layer metrics.

    Updated by ``MessageBus`` after every packet delivery attempt.

    Attributes
    ----------
    messages_sent:
        Total messages placed onto the bus (before delivery attempts).
    messages_delivered:
        Packets that reached at least one receiver with status DELIVERED.
    messages_dropped:
        Packets discarded by the PacketLossModel.
    messages_expired:
        Messages that were discarded because their TTL elapsed.
    messages_out_of_range:
        Unicast packets where sender and receiver were not in range.
    broadcast_count:
        Number of broadcast messages sent.
    unicast_count:
        Number of unicast messages sent.
    total_latency_s:
        Sum of all delivered packet latencies. Used to compute average.
    delivered_packet_count:
        Number of individual delivered packet transmissions. (One broadcast
        message may produce many delivered packets.)
    relay_count:
        Number of relay-forwarded packets.
    """

    messages_sent: int = 0
    messages_delivered: int = 0
    messages_dropped: int = 0
    messages_expired: int = 0
    messages_out_of_range: int = 0
    broadcast_count: int = 0
    unicast_count: int = 0
    total_latency_s: float = 0.0
    delivered_packet_count: int = 0
    relay_count: int = 0

    # ------------------------------------------------------------------
    # Derived metrics
    # ------------------------------------------------------------------

    @property
    def delivery_ratio(self) -> float:
        """Fraction of sent messages successfully delivered (0.0–1.0).

        Returns 0.0 when no messages have been sent.
        """

        if self.messages_sent == 0:
            return 0.0
        return self.messages_delivered / self.messages_sent

    @property
    def drop_ratio(self) -> float:
        """Fraction of sent messages that were dropped (0.0–1.0)."""

        if self.messages_sent == 0:
            return 0.0
        return self.messages_dropped / self.messages_sent

    @property
    def average_latency_s(self) -> float:
        """Mean delivered packet latency in seconds.

        Returns 0.0 when no packets have been delivered.
        """

        if self.delivered_packet_count == 0:
            return 0.0
        return self.total_latency_s / self.delivered_packet_count

    # ------------------------------------------------------------------
    # Update helpers (called by MessageBus)
    # ------------------------------------------------------------------

    def record_sent(self, *, is_broadcast: bool) -> None:
        """Record that a message was placed onto the bus."""

        self.messages_sent += 1
        if is_broadcast:
            self.broadcast_count += 1
        else:
            self.unicast_count += 1

    def record_delivered(self, latency_s: float) -> None:
        """Record a successful packet delivery."""

        self.messages_delivered += 1
        self.delivered_packet_count += 1
        self.total_latency_s += latency_s

    def record_dropped(self) -> None:
        """Record a packet discarded by the loss model."""

        self.messages_dropped += 1

    def record_expired(self) -> None:
        """Record a message discarded due to TTL expiry."""

        self.messages_expired += 1

    def record_out_of_range(self) -> None:
        """Record a unicast packet that could not reach its target."""

        self.messages_out_of_range += 1

    def record_relay(self) -> None:
        """Record a relay-forwarded packet."""

        self.relay_count += 1

    def reset(self) -> None:
        """Reset all counters to zero."""

        self.messages_sent = 0
        self.messages_delivered = 0
        self.messages_dropped = 0
        self.messages_expired = 0
        self.messages_out_of_range = 0
        self.broadcast_count = 0
        self.unicast_count = 0
        self.total_latency_s = 0.0
        self.delivered_packet_count = 0
        self.relay_count = 0

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize current statistics to a JSON-compatible dictionary."""

        return {
            "messages_sent": self.messages_sent,
            "messages_delivered": self.messages_delivered,
            "messages_dropped": self.messages_dropped,
            "messages_expired": self.messages_expired,
            "messages_out_of_range": self.messages_out_of_range,
            "broadcast_count": self.broadcast_count,
            "unicast_count": self.unicast_count,
            "delivery_ratio": self.delivery_ratio,
            "drop_ratio": self.drop_ratio,
            "average_latency_s": self.average_latency_s,
            "relay_count": self.relay_count,
        }

    def __repr__(self) -> str:
        return (
            f"CommunicationStatistics("
            f"sent={self.messages_sent}, "
            f"delivered={self.messages_delivered}, "
            f"dropped={self.messages_dropped}, "
            f"expired={self.messages_expired}, "
            f"ratio={self.delivery_ratio:.2%})"
        )
