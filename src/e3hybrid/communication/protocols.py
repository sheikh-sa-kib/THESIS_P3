"""Communication protocol interfaces.

Design philosophy
-----------------
Following the same Protocol-based design as ``CostProvider`` and ``EnergyModel``,
every communication abstraction is expressed as a ``typing.Protocol``. Concrete
implementations (deterministic baselines, realistic IEEE 802.11p models, future
5G-V2X models) plug in without changing the MessageBus or any other module.

Interfaces defined here
-----------------------
``CommunicationProtocol``   – top-level medium controller used by the MessageBus.
``PacketLossModel``         – decides whether a packet is lost in transit.
``LatencyModel``            – computes propagation + processing delay.
``CommunicationRadiusModel``– decides whether two agents are within range.

Nothing in this module knows about:
- routing algorithms (ACO, BCO, PSO)
- vehicle physics or energy consumption
- SUMO or TraCI
- emergency corridor logic

The communication layer only transports Packets.
"""

from __future__ import annotations

from typing import Protocol

from e3hybrid.communication.packet import Packet
from e3hybrid.vehicle.types import VehicleId


# ---------------------------------------------------------------------------
# Packet loss model
# ---------------------------------------------------------------------------


class PacketLossModel(Protocol):
    """Decide whether a packet is lost during transmission.

    Implementations can model:
    - No loss (deterministic baseline — always returns False).
    - Distance-dependent loss (probability increases with distance).
    - Congestion-dependent loss (probability increases with channel load).
    - IEEE 802.11p BER curves (future — requires channel simulation).
    - Empirical traces from V2V measurement campaigns (future).

    The MessageBus calls ``is_lost(packet)`` before attempting delivery.
    If the model returns True, the packet is marked DROPPED.
    """

    def is_lost(self, packet: Packet) -> bool:
        """Return True when the packet should be dropped.

        Parameters
        ----------
        packet:
            The packet about to be delivered. ``packet.distance_m`` and
            ``packet.message.priority`` may influence the decision.

        Returns
        -------
        bool:
            True = packet is lost (mark DROPPED).
            False = packet survives (continue to latency and delivery).
        """
        ...


# ---------------------------------------------------------------------------
# Latency model
# ---------------------------------------------------------------------------


class LatencyModel(Protocol):
    """Compute propagation and processing delay for a packet.

    Implementations can model:
    - Zero latency (deterministic baseline).
    - Constant latency (fixed delay for all packets).
    - Distance-proportional latency (speed-of-light + processing).
    - Congestion-dependent latency (queuing delay under channel load).
    - DSRC / IEEE 802.11p delay distributions (future).

    The MessageBus calls ``compute_latency_s(packet)`` before marking delivery.
    """

    def compute_latency_s(self, packet: Packet) -> float:
        """Return the transmission latency in simulation seconds.

        Parameters
        ----------
        packet:
            The packet being transmitted.

        Returns
        -------
        float:
            Latency in seconds. Must be non-negative.
        """
        ...


# ---------------------------------------------------------------------------
# Communication radius model
# ---------------------------------------------------------------------------


class CommunicationRadiusModel(Protocol):
    """Decide whether two agents are within communication range.

    Implementations can model:
    - Infinite radius (all agents always reachable — deterministic baseline).
    - Fixed-radius disk model (typical V2V simplification).
    - Obstacle-aware model (buildings reduce effective range).
    - Signal-strength model (RSSI-based, requires position data).
    - SUMO-integrated model (uses TraCI position queries — future Phase 8).

    The MessageBus calls ``in_range(sender_id, receiver_id)`` for unicast
    messages and ``receivers_in_range(sender_id, all_ids)`` for broadcasts.
    """

    def in_range(self, sender_id: VehicleId, receiver_id: VehicleId) -> bool:
        """Return True when receiver is within transmission range of sender.

        Parameters
        ----------
        sender_id:
            The transmitting agent.
        receiver_id:
            The intended recipient.

        Returns
        -------
        bool:
            True = within range (delivery eligible).
            False = out of range (packet marked OUT_OF_RANGE).
        """
        ...

    def receivers_in_range(
        self,
        sender_id: VehicleId,
        all_receiver_ids: frozenset[VehicleId],
    ) -> frozenset[VehicleId]:
        """Return the subset of receivers within range of sender.

        Used by the MessageBus to expand broadcast recipients.

        Parameters
        ----------
        sender_id:
            The broadcasting agent.
        all_receiver_ids:
            All currently registered receivers in the simulation.

        Returns
        -------
        frozenset[VehicleId]:
            Receivers within transmission range (excluding sender_id).
        """
        ...


# ---------------------------------------------------------------------------
# Top-level communication protocol
# ---------------------------------------------------------------------------


class CommunicationProtocol(Protocol):
    """Top-level medium controller used by the MessageBus.

    A ``CommunicationProtocol`` bundles the three sub-models into a single
    injectable object. The MessageBus depends only on this interface.

    Concrete implementations:
    - ``DeterministicProtocol`` – no loss, zero latency, infinite radius
      (Phase 4 baseline, used in all unit tests).
    - Future: ``DSRCProtocol``, ``C_V2XProtocol`` for SUMO integration.
    """

    @property
    def loss_model(self) -> PacketLossModel:
        """Return the packet loss model."""
        ...

    @property
    def latency_model(self) -> LatencyModel:
        """Return the latency model."""
        ...

    @property
    def radius_model(self) -> CommunicationRadiusModel:
        """Return the communication radius model."""
        ...
