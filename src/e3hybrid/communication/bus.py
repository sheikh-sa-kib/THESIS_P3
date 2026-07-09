"""Message bus, broadcaster, and receiver for the communication framework.

The ``MessageBus`` is the central coordinator of the communication layer. It:

1. Maintains the registry of active ``Receiver`` agents.
2. Accepts ``Message`` objects from ``Broadcaster`` agents.
3. For each message, creates ``Packet`` objects per eligible receiver.
4. Applies the ``CommunicationProtocol`` (loss, latency, radius) to each packet.
5. Delivers surviving packets to the target ``Receiver`` inboxes.
6. Updates ``CommunicationStatistics`` after every delivery attempt.
7. Maintains a log of all packets for experiment output.

Design invariants
-----------------
- No threads, sockets, or async I/O. Everything is deterministic and
  advances only when ``MessageBus.tick(current_time_s)`` is called.
- The bus never modifies ``Message`` objects. Status is tracked on ``Packet``.
- Duplicate message IDs are rejected (idempotency guard).
- Expired messages are purged lazily during ``tick()``.
- The bus does not know anything about routing, SUMO, or vehicle physics.

``Broadcaster``
    A lightweight agent view: holds a ``VehicleId`` and a reference to the
    bus. Calling ``send(message)`` places the message on the bus.

``Receiver``
    A lightweight agent view: holds a ``VehicleId`` and an inbox queue.
    The bus deposits delivered packets into ``inbox``. Agents drain the
    inbox during their per-tick update.
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Sequence

from e3hybrid.communication.message import Message
from e3hybrid.communication.models import DeterministicProtocol
from e3hybrid.communication.packet import Packet
from e3hybrid.communication.protocols import CommunicationProtocol
from e3hybrid.communication.statistics import CommunicationStatistics
from e3hybrid.communication.types import DeliveryStatus, MessageId
from e3hybrid.core.exceptions import CommunicationError
from e3hybrid.vehicle.types import VehicleId

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Receiver
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Receiver:
    """An agent endpoint that receives delivered packets.

    Attributes
    ----------
    vehicle_id:
        The identifier of the agent this receiver belongs to.
    inbox:
        Delivered packets waiting to be processed. Agents drain this
        queue during their per-tick update. FIFO order.
    """

    vehicle_id: VehicleId
    inbox: deque[Packet] = field(default_factory=deque)

    def drain(self) -> list[Packet]:
        """Remove and return all packets currently in the inbox."""

        packets = list(self.inbox)
        self.inbox.clear()
        return packets

    def peek(self) -> list[Packet]:
        """Return all packets without removing them."""

        return list(self.inbox)

    def __repr__(self) -> str:
        return f"Receiver(id={self.vehicle_id}, inbox={len(self.inbox)})"


# ---------------------------------------------------------------------------
# Broadcaster
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Broadcaster:
    """An agent endpoint for sending messages onto the bus.

    Attributes
    ----------
    vehicle_id:
        The sender identity stamped on outgoing messages.
    _bus:
        The MessageBus this broadcaster is connected to.
    """

    vehicle_id: VehicleId
    _bus: "MessageBus"

    def send(self, message: Message) -> None:
        """Place a message onto the bus for delivery.

        Raises
        ------
        CommunicationError:
            If the message sender_id does not match this broadcaster's
            vehicle_id.
        """

        if message.sender_id != self.vehicle_id:
            raise CommunicationError(
                f"Broadcaster '{self.vehicle_id}' cannot send message "
                f"with sender_id '{message.sender_id}'"
            )
        self._bus.submit(message)

    def __repr__(self) -> str:
        return f"Broadcaster(id={self.vehicle_id})"


# ---------------------------------------------------------------------------
# MessageBus
# ---------------------------------------------------------------------------


class MessageBus:
    """Central communication coordinator.

    Parameters
    ----------
    protocol:
        The ``CommunicationProtocol`` to use for loss, latency, and radius
        decisions. Defaults to ``DeterministicProtocol`` (no-loss, zero-
        latency, infinite-radius) for Phase 4 testing.

    Usage
    -----
    1. Register receivers: ``bus.register(receiver)``
    2. Agents call ``broadcaster.send(message)`` each tick.
    3. Simulation core calls ``bus.tick(current_time_s)`` once per step.
    4. Agents call ``receiver.drain()`` to process delivered packets.
    5. At run end: ``bus.statistics`` holds the full delivery record.
    """

    def __init__(
        self,
        protocol: CommunicationProtocol | None = None,
    ) -> None:
        self._protocol: CommunicationProtocol = (
            protocol if protocol is not None else DeterministicProtocol()
        )
        self._receivers: dict[VehicleId, Receiver] = {}
        self._pending: deque[Message] = deque()
        self._seen_ids: set[MessageId] = set()
        self._packet_log: list[Packet] = []
        self._statistics: CommunicationStatistics = CommunicationStatistics()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, receiver: Receiver) -> None:
        """Register a receiver endpoint.

        Raises
        ------
        CommunicationError:
            If a receiver with the same vehicle_id is already registered.
        """

        if receiver.vehicle_id in self._receivers:
            raise CommunicationError(
                f"Receiver '{receiver.vehicle_id}' is already registered"
            )
        self._receivers[receiver.vehicle_id] = receiver

    def unregister(self, vehicle_id: VehicleId) -> None:
        """Remove a receiver from the bus (vehicle has left the simulation)."""

        self._receivers.pop(vehicle_id, None)

    def create_broadcaster(self, vehicle_id: VehicleId) -> Broadcaster:
        """Create a Broadcaster bound to this bus for the given vehicle."""

        return Broadcaster(vehicle_id=vehicle_id, _bus=self)

    def create_receiver(self, vehicle_id: VehicleId) -> Receiver:
        """Create and register a Receiver for the given vehicle."""

        receiver = Receiver(vehicle_id=vehicle_id)
        self.register(receiver)
        return receiver

    def registered_ids(self) -> frozenset[VehicleId]:
        """Return the set of currently registered receiver IDs."""

        return frozenset(self._receivers.keys())

    # ------------------------------------------------------------------
    # Submission
    # ------------------------------------------------------------------

    def submit(self, message: Message) -> None:
        """Place a message on the pending queue for delivery on the next tick.

        Duplicate message IDs are silently ignored (idempotency).

        Raises
        ------
        CommunicationError:
            If the message is already expired at submission time (caller error).
        """

        if message.message_id in self._seen_ids:
            _logger.debug("MessageBus: duplicate message_id %s ignored", message.message_id)
            return
        self._pending.append(message)
        self._statistics.record_sent(is_broadcast=message.is_broadcast)

    # ------------------------------------------------------------------
    # Tick — advance one simulation step
    # ------------------------------------------------------------------

    def tick(self, current_time_s: float) -> None:
        """Process all pending messages and deliver surviving packets.

        Called once per simulation step by the simulation core.

        Parameters
        ----------
        current_time_s:
            Current simulation clock in seconds. Used for TTL checks and
            packet arrival-time computation.
        """

        all_receiver_ids = frozenset(self._receivers.keys())

        while self._pending:
            message = self._pending.popleft()

            # Mark message as seen to prevent duplicate processing.
            self._seen_ids.add(message.message_id)

            # Expired messages are purged without delivery.
            if message.is_expired(current_time_s):
                self._statistics.record_expired()
                _logger.debug(
                    "MessageBus: message %s expired at t=%.2f",
                    message.message_id,
                    current_time_s,
                )
                continue

            # Determine target receivers.
            if message.is_broadcast:
                targets = self._protocol.radius_model.receivers_in_range(
                    message.sender_id, all_receiver_ids
                )
            else:
                # Unicast — check range first.
                assert message.receiver_id is not None
                if message.receiver_id not in self._receivers:
                    self._statistics.record_out_of_range()
                    continue
                if not self._protocol.radius_model.in_range(
                    message.sender_id, message.receiver_id
                ):
                    self._statistics.record_out_of_range()
                    continue
                targets = frozenset({message.receiver_id})

            # Create and process one packet per target.
            for target_id in targets:
                packet = Packet.create(
                    message=message,
                    transmitted_at_s=current_time_s,
                    intended_receiver_id=target_id,
                )

                # Loss check.
                if self._protocol.loss_model.is_lost(packet):
                    final_packet = packet.with_status(DeliveryStatus.DROPPED)
                    self._packet_log.append(final_packet)
                    self._statistics.record_dropped()
                    continue

                # Latency.
                latency = self._protocol.latency_model.compute_latency_s(packet)
                packet = packet.with_latency(latency)

                # Deliver to inbox.
                final_packet = packet.with_status(DeliveryStatus.DELIVERED)
                self._receivers[target_id].inbox.append(final_packet)
                self._packet_log.append(final_packet)
                self._statistics.record_delivered(latency)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def statistics(self) -> CommunicationStatistics:
        """Return the live statistics accumulator."""

        return self._statistics

    def packet_log(self) -> list[Packet]:
        """Return a snapshot of all processed packets (for experiment output)."""

        return list(self._packet_log)

    def pending_count(self) -> int:
        """Return the number of messages waiting for the next tick."""

        return len(self._pending)

    def reset_log(self) -> None:
        """Clear the packet log and statistics (between experiment runs)."""

        self._packet_log.clear()
        self._statistics.reset()
        self._seen_ids.clear()

    def __repr__(self) -> str:
        return (
            f"MessageBus("
            f"receivers={len(self._receivers)}, "
            f"pending={len(self._pending)}, "
            f"stats={self._statistics})"
        )
